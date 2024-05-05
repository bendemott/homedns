"""
Note, when we are done here we'll split this out into its own little project
We don't need twisted as a dependency on the client
"""
import urllib.request
from socket import socket
import fcntl
import struct
from typing import Sequence

from twisted.logger import Logger

from homedns.config import AbstractConfig
from homedns.restclient import Client
from homedns.constants import DEFAULT_UPDATER_PIVATE_JWT_KEY_PATH

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


class LocalInterfaceAddressResolver(AbstractAddressResolver):

    def __init__(self, interface=None):
        self._iface = interface

    def external_ipv4(ifname) -> str:
        """
        pass arguments?
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])


class UPNPAddressResolver(AbstractAddressResolver):
    """
    To install miniupnpc on linux you must also install:
    - make
    - gcc (cc)
    - python3-dev (python headers)
    """

    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        # Note only on linux
        import miniupnpc
        u = miniupnpc.UPnP()
        u.discoverdelay = 200
        u.discover()
        u.selectigd()
        return u.externalipaddress()


class IdentMeAddressResolver(AbstractAddressResolver):
    def external_ipv6(self):
        # Note documentation says this works, but it doesn't work
        return urllib.request.urlopen('https://6.ident.me').read().decode().strip()

    def external_ipv4(self):
        return urllib.request.urlopen('https://4.ident.me').read().decode().strip()


class IpifyAddressResolver(AbstractAddressResolver):

    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        return urllib.request.urlopen('https://api.ipify.org').read().decode().strip()


class AmazonAwsAddressResolver(AbstractAddressResolver):
    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        return urllib.request.urlopen('https://checkip.amazonaws.com').read().decode().strip()


class HomeDNSAddressResolver(AbstractAddressResolver):
    def __init__(self, client: Client):
        self._client = client

    def external_ipv6(self):
        raise NotImplementedError()

    def external_ipv4(self):
        return self._client.echo_ip4()['address']


class PublicIPResolvers:
    """
    Capable
    """

    RESOLVERS = {
        'homedns': HomeDNSAddressResolver,
        'amazon': AmazonAwsAddressResolver,
        'ipify': IpifyAddressResolver,
        'identme': IdentMeAddressResolver,
    }

    def __init__(self):
        self._resolvers = []
        self._log = Logger()

    def resolve(self, resolver: str, **kwargs):

        if resolver not in self.RESOLVERS:
            raise ValueError(f'Invalid resolver name: "{resolver}"')

        try:
            cls = self.RESOLVERS[resolver]
            instance = cls(**kwargs)
        except Exception as e:
            self._log.info(f'IP Address Resolver [{resolver}] encountered error: {str(e)}')


class UpdaterConfig(AbstractConfig):

    def get_default(self, directory: str):
        return {
            "interval": 30,
            "ttl": 5,
            "domains": {
                "A": [
                    "example.local"
                ]
            },
            "resolvers": [
                "amazon", "ipify", "identme"
            ],
            "resolve_using_server": True,
            "jwt_auth": {
                "enabled": True,
                "subject": "0aaa1111-1111-1a1a-a111-aa11aa11111a",
                "private_key": DEFAULT_UPDATER_PIVATE_JWT_KEY_PATH,
                "issuer": "homedns-clients",  # TODO default constants
                "audience": ["homedns-api"]
            },
            "basic_auth": {
                "username": None,
                "password": None,
            }
        }


def updater_main(updater: UpdaterConfig, log_level: str):
    pass