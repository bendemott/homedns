from typing import Iterator

from twisted.internet import threads
from twisted.names import dns, error, common
from twisted.logger import Logger

from homedns.store import IRecordStorage, HostnameAndRecord


class HomeDnsResolver(common.ResolverBase):
    """
    A Dns Name Resolver that resolves dns names for specific addresses stored by the application
    """

    def __init__(self, record_store: IRecordStorage):
        self._store = record_store
        self.log = Logger(self.__class__.__name__)

    @property
    def store(self):
        return self._store

    async def query(self, query, timeout=None):
        """
        Notice that this method returns a Deferred.
        On success, it returns three lists of DNS records (answers, authority, additional),
        each one of the elements in these tuples is a list of `dns.RRHeader` objects,
        which will be encoded by `dns.Message` and returned to the client.

        On failure, it raises DomainError, which is a signal that the query should be dispatched to the next
        client resolver in the list.
        """
        # Return an error if we don't support the request coming in
        if query.type not in dns.QUERY_TYPES:
            # modern browsers ask for type 65, HTTPS RESOURCE REQUEST as an example of an unavoidable unsupported
            # request type...
            raise error.DNSNotImplementedError()

        # we have to defer to thread because our storage api is NOT async (its blocking)
        results: Iterator[HostnameAndRecord] = await threads.deferToThread(self.store.name_search,
                                                                           query.name.name.decode(),
                                                                           query.type)
        await threads.deferToThread(self.store.log_table)

        answers = [dns.RRHeader(name=d.hostname, payload=d.record, ttl=d.record.ttl) for d in results]
        authority = [dns.RRHeader(name=d.hostname, payload=d.record, ttl=d.record.ttl, auth=True) for d in results]  # dns.RRHeader
        additional = []  # dns.RRHeader

        # we have no answers for this hostname
        if not answers:
            raise error.DomainError()

        return answers, authority, additional

    """
    Instead of implementing the `query` method you can implement all these other specific methods.
    ... fyi
    """

    def lookupAddress(self, name, timeout=None):
        pass

    def lookupIPV6Address(self, name, timeout=None):
        pass

    def lookupMailExchange(self, name, timeout=None):
        pass

    def lookupCanonicalName(self, name, timeout=None):
        pass

    def lookupNameservers(self, name, timeout=None):
        pass