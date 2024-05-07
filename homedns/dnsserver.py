import traceback
from typing import Iterator

from twisted.internet import threads, defer
from twisted.internet.defer import inlineCallbacks
from twisted.names import dns, error, common
from twisted.logger import Logger
from twisted.names.dns import Query, Record_SOA, Record_NS

from homedns.store import IRecordStorage, HostnameAndRecord


class HomeDnsResolver(common.ResolverBase):
    """
    A Dns Name Resolver that resolves dns names for specific addresses stored by the application
    """

    def __init__(self, record_store: IRecordStorage, soa_domains: list[str], name_servers: list[str], ttl: int = 3600):
        super().__init__()
        self._store = record_store
        self.log = Logger(self.__class__.__name__)
        self._ttl = ttl
        self._soa = set()
        self._soa_sizes = set()
        self._soa_min = 2
        self._name_servers = name_servers
        common.ResolverBase.__init__(self)
        self._soa_domains = soa_domains or []
        self._soa = {tuple(d.split('.')) for d in soa_domains}

    def get_soa_domain(self, name: str) -> bool:
        domain = name.split('.')
        if len(domain) < 2:
            return False

        soa_tuple = tuple(domain[-2:])
        if soa_tuple in self._soa:
            return '.'.join(soa_tuple)

        return False

    @property
    def store(self):
        return self._store

    @inlineCallbacks
    def query(self, query: Query, timeout=None):
        """
        Notice that this method returns a Deferred.
        On success, it returns three lists of DNS records (answers, authority, additional),
        each one of the elements in these tuples is a list of `dns.RRHeader` objects,
        which will be encoded by `dns.Message` and returned to the client.

        On failure, it raises DomainError, which is a signal that the query should be dispatched to the next
        client resolver in the list.
        """

        # if we are authority for a domain we need to raise `AuthoritativeDomainError` to prevent an
        # infinite loop where the request gets forwarded to another domain server for which we are the authority
        # see: https://docs.twisted.org/en/twisted-22.2.0/api/twisted.names.error.html

        name = query.name.name.decode()
        soa_domain = self.get_soa_domain(name)
        query_types = [query.type]

        self.log.info(f'looking up "{name}" <{dns.QUERY_TYPES.get(query.type)}>')
        if not soa_domain:
            # If we are not an authority for this domain, we will allow forwarding by returning DomainError
            msg = f'Not-Authoritative: no matching record: "{name}"'
            self.log.info(msg)
            raise error.DomainError(msg)

        answers: list[dns.RRHeader] = []  # Answers contains all dns lookup responses
        authority: list[dns.RRHeader] = []  # Authority we will not use, this is for add NS records to a response
                                            # to indicate the authoritative name server
        additional: list[dns.RRHeader] = []  # Additional information can be added to the response, this is meta info

        # a search for A, should include CNAME
        if query.type == dns.A:
            query_types.append(dns.CNAME)

        #  SOA response
        if query.type == dns.SOA:
            first_ns = self._name_servers[0] if self._name_servers else None
            soa = HomeDnsResolver.get_soa_record(soa_domain, first_ns, ttl=self._ttl)
            answers.append(soa)

        # Respond with ns record
        if query.type == dns.NS:
            for ns in self._name_servers:
                ns_record = HomeDnsResolver.get_ns_record(ns, soa_domain, ttl=self._ttl)
                answers.append(ns_record)

        # Return an error if we don't support the request coming in
        if query.type not in dns.QUERY_TYPES:
            # modern browsers ask for type 65, HTTPS RESOURCE REQUEST as an example of an unavoidable unsupported
            # request type...
            self.log.error(f'unsupported query type: {query.type}')
            raise error.DNSNotImplementedError(f'Unsupported query type: {query.type}')

        # we have to defer to thread because our storage api is NOT async (its blocking)
        try:
            results: Iterator[HostnameAndRecord] = yield threads.deferToThread(self.store.name_search,
                                                                               name,
                                                                               query_types)
        except Exception as e:
            self.log.error(f'Storage engine error while looking up "{name}", {str(e)}')
            self.log.debug(traceback.format_exc())
            raise error.AuthoritativeDomainError(f'Storage engine error while looking up "{name}", {str(e)}') from e
        else:
            self.log.info(f'matched [{len(results)}] records for "{name}"')

        for r in results:
            record = r.record
            ttl = r.record.ttl or self._ttl
            if isinstance(record, dns.Record_A):
                response = dns.RRHeader(name=r.hostname, type=dns.A, ttl=ttl, payload=record, auth=True)
            elif isinstance(record, dns.Record_AAAA):
                response = dns.RRHeader(name=r.hostname, type=dns.AAAA, ttl=ttl, payload=record, auth=True)
            elif isinstance(record, dns.Record_CNAME):
                response = dns.RRHeader(name=r.hostname, type=dns.CNAME, ttl=ttl, payload=record, auth=True)
            elif isinstance(record, dns.Record_MX):
                response = dns.RRHeader(name=r.hostname, type=dns.MX, ttl=ttl, payload=record, auth=True)
            else:
                self.log.error(f'Unhandled type from store {type(r)}')
                continue

            answers.append(response)

        """
        If the server is configured with the option to forward queries, the next resolver class
        will handle the query. By returning `DomainError` we are indicating to twisted that this resolver
        cannot answer the dns query, and others should be tried
        """
        if not answers:
            self.log.info(f'No matching records were returned from store for {name}')
            raise error.AuthoritativeDomainError(f'Authoritative: no matching record: "{name}"')

        defer.returnValue((answers, authority, additional))

    @staticmethod
    def get_soa_record(domain, name_server, ttl=600, refresh=46800, retry=6200, expire=3000000, minimum=300):
        """
        Generate the Start of Authority response header.
        Clients expect a SOA to be available when performing DNS request to an authoritative server

        Name: This is the name of your domain. For example: mydomain.com
        mname: The MNAME in the above format represents the domain’s primary name server
        rname: This holds the administrator’s email address without the @ sign. So admin.mywebsite corresponds to admin@mywebsite.com.
        serial: This is the number for the DNS zone Increase the serial value each time you make changes to your zone file to ensure that they’re propagated across all secondary DNS servers.
        refresh: This is the timeframe in seconds a secondary server waits before sending a query to the primary server SOA record for any new changes.
        retry: This is the time a server should wait after a failed refresh before sending a new query.
        expire: The period in seconds that a secondary server will continue to query the primary server for an update.
                When this time expires, the secondary server’s zone files expire, and it stops responding to queries.
        minimum: The minimum ttl for the domain
        ttl: The default TTL for records in the domain
        """
        soa = Record_SOA(
            mname=name_server,  # primary server
            rname="",      # email address
            serial=0,      # increment with soa changes # TODO
            refresh=refresh,     #
            retry=retry,
            expire=expire,
            minimum=minimum,
            ttl=ttl
        )
        return dns.RRHeader(name=domain, type=dns.SOA, cls=dns.IN, ttl=ttl, payload=soa, auth=True)

    @staticmethod
    def get_ns_record(name_server, domain, ttl=600):
        ns = Record_NS(name=name_server)

        # example.com.      IN        NS        ns1.example.com.
        # Tells clients to use the address ns1.example.com to perform lookups for example.com
        return dns.RRHeader(domain, dns.NS, dns.IN, ttl, ns, auth=False)