"""
Note, when we are done here we'll split this out into its own little project
We don't need twisted as a dependency on the client
"""
import urllib.request

# query the router
from twisted.names.dns import IRecord


# rely on external service

external_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
print(external_ip)

ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
print('My public IP address is: {}'.format(ip))

ip = urllib.request.urlopen('https://checkip.amazonaws.com').read().decode('utf8')


class AbstractAddressResolver:

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        raise NotImplementedError()

# import miniupnpc
# u = miniupnpc.UPnP()
# u.discoverdelay = 200
# u.discover()
# u.selectigd()
# print('external ip address: {}'.format(u.externalipaddress()))
class UPNPAddressResolver(AbstractAddressResolver):

    def external_ipv6(self):
        # Note documentation says this works, but it doesn't work
        return urllib.request.urlopen('https://6.ident.me').read().decode('utf8')

    def external_ipv4(self):
        return urllib.request.urlopen('https://4.ident.me').read().decode('utf8')


class IdentMeAddressResolver(AbstractAddressResolver):
    def external_ipv6(self):
        # Note documentation says this works, but it doesn't work
        return urllib.request.urlopen('https://6.ident.me').read().decode('utf8')

    def external_ipv4(self):
        return urllib.request.urlopen('https://4.ident.me').read().decode('utf8')


class IpifyAddressResolver(AbstractAddressResolver):

    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        raise NotImplementedError()


class AmazonAwsAddressResolver(AbstractAddressResolver):
    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        raise NotImplementedError()


class HomeDnsClient:
    """
    The client communicates and authenticates with the server via its REST api
    the client is capable of setting, and getting IP addresses configured for specific domains
    """

    def __init__(self, address: str, port=8080, credentials=None):
        pass

    def set(self, record: IRecord):
        """
        Set a DNS record

        :param record: A dns record that will be created or updated
        :return:
        """
        pass

    def get(self, fqdn) -> IRecord:
        pass