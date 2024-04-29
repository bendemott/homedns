"""
Custom DNS Server

    $ dig -p 10053 @localhost workstation1.example.com A +short
    172.0.2.1
"""
import sys

from twisted.cred.portal import Portal
from twisted.internet import reactor, ssl
from twisted.names import dns, server, cache, resolve, client
from twisted.python import log
from twisted.web import guard
from twisted.web._auth.basic import BasicCredentialFactory
from twisted.web.server import Site

from homedns.certificates import KeyPair
from homedns.dnsserver import HomeDnsResolver
from homedns.restapi import DNSRestApi
from homedns.store import SqliteStorage, IRecordStorage
from homedns.cred import JsonPasswordDB, PassthroughRealm
from homedns.log import LevelObserver
from homedns.jwt import JwtTokenChecker, JwtCredentialFactory


def setup_dns(config: dict, store: IRecordStorage):
    clients = []
    if config['dns']['forwarding']['enabled']:
        resolvers = []  # dns servers twisted expects pairs of (host, port)
        for s in config['dns']['forwarding']['servers']:
            if isinstance(s, str) and  ':' in s:
                resolvers.append(s.split(':'))
            elif isinstance(s, str):
                resolvers.append((s, dns.PORT))
            elif isinstance(s, (list, tuple)):
                if len(s) == 2:
                    resolvers.append(s)
                elif len(s) == 1:
                    resolvers.append((s[0], dns.PORT))
                else:
                    raise ValueError(f'Invalid configuration at `dns.forwarding.servers`: {s}')
            else:
                raise ValueError(f'Invalid configuration at `dns.forwarding.servers`: {s}')

        if not resolvers:
            raise ValueError(f'Invalid configuration, value required: `dns.forwarding.servers`')

        clients.append(client.Resolver(servers=resolvers))

    caches = []
    if config['dns']['cache']['enabled']:
        caches.append(cache.CacheResolver())

    factory = server.DNSServerFactory(
        authorities=[HomeDnsResolver(store)],
        caches=caches,
        clients=clients,
        verbose=int(config.get('verbosity', 0))
    )
    protocol = dns.DNSDatagramProtocol(controller=factory)
    reactor.listenUDP(int(config['dns']['listen_udp']), protocol)
    reactor.listenTCP(int(config['dns']['listen_tcp']), factory)


def secure_resource(config, resource):
    """
    Pass a root resource to this function to secure it via twisted.cred
    You can pass the klein() resource to this function and wrap it as well

    See this documentation for help understanding how this works:
    https://docs.twisted.org/en/twisted-18.9.0/web/howto/web-in-60/http-auth.html
    """
    if config.get('no_auth', {}).get('enabled'):
        return resource

    if config['basic_auth']['enabled']:
        checkers = [JsonPasswordDB(filename=config['basic_auth']['secrets_path'])]
        wrapper = guard.HTTPAuthSessionWrapper(
            Portal(PassthroughRealm(resource), checkers),
            [BasicCredentialFactory(b"homedns")])
        return wrapper
    elif config['jwt_auth']['enabled']:
        checkers = [JwtTokenChecker]
        wrapper = guard.HTTPAuthSessionWrapper(
            Portal(PassthroughRealm(resource), checkers),
            [JwtCredentialFactory(b"homedns")])
        return wrapper
    else:
        raise RuntimeError('authentication is not enabled')


def setup_rest(config, store):
    log.startLogging(sys.stdout)

    """
    The klein app is just a fancy resource under the hood.
    You can use Klein() as any other resource in twisted.
    """
    klein_app = DNSRestApi(store).app
    resource = secure_resource(config, klein_app.resource())
    site = Site(resource)

    if config['http']:
        reactor.listenTCP(config['http']['listen'], site)
    if config['https']:
        private_key = config['https']['private_key']
        public_key = config['https']['public_key']
        pair = KeyPair()
        if not pair.exists(private_key, public_key) and config['https']['generate_keys']:
            pair.options(organization='homedns')
            # generate pair
            pair.write(private_key, public_key)
        ssl_context = ssl.DefaultOpenSSLContextFactory(
            private_key,  # Private Key
            public_key,   # Certificate
        )
        reactor.listenSSL(config['https']['listen'], site, ssl_context)


def config_main(config: dict, log_level: str = 'info'):
    log.startLogging(sys.stdout)
    #log.addObserver(LevelObserver(log_level))  # TODO is hiding exceptions

    sqlite_path = config.get('dns', {}).get('database', {}).get('sqlite', {}).get('path')
    if not sqlite_path:
        raise ValueError(f'Configuration missing: `dns.database.sqlite.path`')

    store = SqliteStorage(sqlite_path)
    setup_dns(config, store)
    setup_rest(config, store)

    try:
        reactor.run()
    except KeyboardInterrupt:
        pass


def main(argv=None):
    log.startLogging(sys.stdout)
    argv = argv or ['']





if __name__ == '__main__':
    raise sys.exit(main(sys.argv))
