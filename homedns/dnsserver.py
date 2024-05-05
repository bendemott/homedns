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

    def __init__(self, record_store: IRecordStorage, forwarding: bool = True, tld: int = 3600):
        super().__init__()
        self._store = record_store
        self.log = Logger(self.__class__.__name__)
        self._tld = tld
        self._forwarding = forwarding
        common.ResolverBase.__init__(self)

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
        # Return an error if we don't support the request coming in
        if query.type not in dns.QUERY_TYPES:
            # modern browsers ask for type 65, HTTPS RESOURCE REQUEST as an example of an unavoidable unsupported
            # request type...
            raise error.DNSNotImplementedError()

        # we have to defer to thread because our storage api is NOT async (its blocking)
        results: Iterator[HostnameAndRecord] = yield threads.deferToThread(self.store.name_search,
                                                                           query.name.name.decode(),
                                                                           query.type)

        # answers, is all you need to populate. By adding `auth=True` to the RRHeader the returned record will
        # indicate it is authoritative. We respond as the authority for all records we house
        answers: list[dns.RRHeader] = [
            dns.RRHeader(name=d.hostname, payload=d.record, ttl=d.record.ttl, auth=True) for d in results]
        authority: list[dns.RRHeader] = []
        additional: list[dns.RRHeader] = []

        """
        If the server is configured with the option to forward queries, the next resolver class
        will handle the query. By returning `DomainError` we are indicating to twisted that this resolver
        cannot answer the dns query, and others should be tried
        """
        if not results:
            raise error.DomainError()

        defer.returnValue((answers, authority, additional))