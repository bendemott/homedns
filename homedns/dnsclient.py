from twisted.internet import reactor
from twisted.names import client, dns

DNS_RECORD_MAP = {
    "A": dns.A,
    "NS": dns.NS,
    "MD": dns.MD,
    "MF": dns.MF,
    "CNAME": dns.CNAME,
    "SOA": dns.SOA,
    "MB": dns.MB,
    "MG": dns.MG,
    "MR": dns.MR,
    "NULL": dns.NULL,
    "WKS": dns.WKS,
    "PTR": dns.PTR,
    "HINFO": dns.HINFO,
    "MINFO": dns.MINFO,
    "MX": dns.MX,
    "TXT": dns.TXT,
    "RP": dns.RP,
    "AFSDB": dns.AFSDB,
    "AAAA": dns.AAAA,
    "SRV": dns.SRV,
    "NAPTR": dns.NAPTR,
    "A6": dns.A6,
    "DNAME": dns.DNAME,
    "OPT": dns.OPT,
    "SSHFP": dns.SSHFP,
    "SPF": dns.SPF,
    "TKEY": dns.TKEY,
    "TSIG": dns.TSIG,
}


class Container:
    def __init__(self, function, name: str, timeout: int):
        self.response = None
        self.function = function
        self.name = name
        self.timeout = timeout

    def run(self):

        async def query(c: Container):
            try:
                c.response = await c.function(c.name, timeout=c.timeout)
            finally:
                reactor.stop()

        # Run the async function in the Twisted event loop
        reactor.callWhenRunning(query, self)
        reactor.run()

        return self.response.answers


class DnsClient:
    """
    A DNS Client
    """

    def __init__(self, server: str, timeout: int = 15):
        if ':' in server:
            self._server = server.split()
            self._server[1] = int(self._server[1])
            self._server = tuple(self._server)
        else:
            self._server = (server, dns.PORT)

        self._timeout = int(timeout)

    def lookup_address(self, name: str):
        """
        Lookup A records by domain name
        """
        c = Container(client.lookupAddress, name, self._timeout)
        return c.run()

    def lookup_a(self, name: str):
        """
        Alias for `lookup_address
        """
        return self.lookup_address(name)

    def lookup_mx(self, name: str):
        """
        Lookup MX records by domain name
        """
        c = Container(client.lookupAddress, name, self._timeout)
        return c.run()

    def lookup_authority(self, name: str):
        """
        Lookup Authority
        """
        c = Container(client.lookupAuthority, name, self._timeout)
        return c.run()

    def lookup_cname(self, name: str):
        """
        Lookup Authority
        """
        c = Container(client.lookupCanonicalName, name, self._timeout)
        return c.run()

