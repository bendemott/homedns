import traceback
from typing import Iterator

from twisted.internet import threads, defer
from twisted.internet.defer import inlineCallbacks
from twisted.names import dns, error, common
from twisted.logger import Logger
from twisted.names.dns import Query

from homedns.store import IRecordStorage, HostnameAndRecord


class HomeDnsResolver(common.ResolverBase):
    """
    A Dns Name Resolver that resolves dns names for specific addresses stored by the application
    """

    def __init__(self, record_store: IRecordStorage, soa_domains, ttl: int = 3600):
        super().__init__()
        self._store = record_store
        self.log = Logger(self.__class__.__name__)
        self._ttl = ttl
        self._soa = set()
        self._soa_sizes = set()
        self._soa_min = 2
        common.ResolverBase.__init__(self)
        self.setup_soa(soa_domains)

    def get_suffix_tuple(self, name: str, suffix=None):
        parts = name.split('.')
        if suffix:
            suffix = min(suffix, len(parts) - 1)
            return tuple(parts[-suffix:])
        else:
            return tuple(parts)

    def setup_soa(self, domains):
        for soa_domain in domains:
            domain = soa_domain.lstrip('*.')
            soa_tuple = self.get_suffix_tuple(domain)
            self._soa_sizes.add(len(soa_tuple))
            self._soa.add(soa_tuple)

        self._soa_min = min(self._soa_sizes or [0])

    def is_soa_domain(self, name: str) -> bool:
        """
        Return True if the domain name given is within a START OF AUTHORITY DOMAIN.
        """
        for size in self._soa_sizes:
            soa_tuple = self.get_suffix_tuple(name, size)
            if soa_tuple in self._soa:
                return True

            if len(soa_tuple) <= self._soa_min:
                return False

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
        authoritative = self.is_soa_domain(name)

        if not authoritative:
            raise error.DomainError(f'Not-Authoritative: no matching record: "{name}"')

        # Return an error if we don't support the request coming in
        if query.type not in dns.QUERY_TYPES:
            # modern browsers ask for type 65, HTTPS RESOURCE REQUEST as an example of an unavoidable unsupported
            # request type...
            raise error.AuthoritativeDomainError(f'Unsupported query type: {query.type}')  # error.DNSNotImplementedError()

        # we have to defer to thread because our storage api is NOT async (its blocking)
        try:
            results: Iterator[HostnameAndRecord] = yield threads.deferToThread(self.store.name_search,
                                                                               query.name.name.decode(),
                                                                               query.type)
        except Exception as e:
            self.log.error(f'Storage engine error while looking up "{name}", {e}')
            self.log.debug(traceback.format_exc())
            raise error.AuthoritativeDomainError(f'Storage engine error while looking up "{name}", {e}') from e

        # answers, is all you need to populate. By adding `auth=True` to the RRHeader the returned record will
        # indicate it is authoritative. We respond as the authority for all records we house
        answers: list[dns.RRHeader] = [
            dns.RRHeader(name=d.hostname, payload=d.record, ttl=d.record.ttl or self._ttl, auth=True) for d in results]
        authority: list[dns.RRHeader] = []
        additional: list[dns.RRHeader] = []

        """
        If the server is configured with the option to forward queries, the next resolver class
        will handle the query. By returning `DomainError` we are indicating to twisted that this resolver
        cannot answer the dns query, and others should be tried
        """
        if not results:
            raise error.AuthoritativeDomainError(f'Authoritative: no matching record: "{name}"')

        defer.returnValue((answers, authority, additional))