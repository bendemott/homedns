"""
An example demonstrating how to create a custom DNS server.

The server will calculate the responses to A queries where the name begins with
the word "workstation".

Other queries will be handled by a fallback resolver.


    $ dig -p 10053 @localhost workstation1.example.com A +short
    172.0.2.1
"""
import sys
import argparse

from twisted.internet import reactor, defer, threads
from twisted.names import client, dns, error, server, common
from twisted.python import log
from twisted.web.server import Site

from klein import Klein

from homedns.dnsserver import HomeDnsResolver
from homedns.restserver import DNSRestApi
from homedns.store import SqliteStorage


def setup_dns(args, store):
    log.startLogging(sys.stdout)

    factory = server.DNSServerFactory(
        clients=[HomeDnsResolver(store)],
        verbose=2
    )
    protocol = dns.DNSDatagramProtocol(controller=factory)
    reactor.listenUDP(args.dns_udp, protocol)
    reactor.listenTCP(args.dns_tcp, factory)


def setup_rest(args, store):
    log.startLogging(sys.stdout)

    klein_app = DNSRestApi(store).app
    site = Site(klein_app.resource())  # klein self.resource?
    reactor.listenTCP(args.http, site)


def main(argv=None):
    argv = argv or [None]
    # Top level parser
    parser = argparse.ArgumentParser(prog='homedns')
    subparsers = parser.add_subparsers(help='--- available sub-commands ---', dest='command')

    # -- SETUP THE `start` COMMAND --------------------------------------------
    p_start = subparsers.add_parser('start', help='start services')
    p_start.add_argument('--dns-udp', metavar='', type=int, default=10053, help='DNS port to listen on for TCP')
    p_start.add_argument('--dns-tcp', metavar='', type=int, default=10053, help='DNS port to listen on for TCP')
    p_start.add_argument('--database', metavar='PATH', default='./dns-records.sqlite',
                         help='File path for where to store DNS record database')
    p_start.add_argument('--http', metavar='', default=8080, type=int, help='HTTP port to listen on for Rest API')
    # TWISTED arguments
    p_start.add_argument('--https', metavar='', type=int, required=False,
                         help="HTTPS Secure port for Rest API")
    p_start.add_argument('-n', '--daemon', action='store_true',
                         help="Daemonize (run in background) - use default umask of 0077")
    p_start.add_argument('-c', '--certificate', required=False,
                         help='SSL certificate to use for HTTPS.')
    p_start.add_argument('-k', '--privkey', required=False,
                         help="SSL certificate to use for HTTPS.")
    p_start.add_argument('-r', '--reactor', required=False,
                         help="Which reactor to use (see --help-reactors for a list)")
    p_start.add_argument('-u', '--uid', required=False, help="Linux userid to run as")
    p_start.add_argument('-g', '--gid', required=False, help="Linux groupid to run as")
    p_start.add_argument('--euid', help='\n'.join([
        "Set only effective user-id rather than real user-id.",
        "(This option has no effect unless the server is running",
        "as root, in which case it means not to shed all",
        "privileges after binding ports, retaining the option to",
        "regain privileges in cases such as spawning processes.",
        "Use with caution."]), type=int)
    p_start.add_argument('--version', required=False, action='store_true',
                         help='Print version information and exit.')
    p_start.add_argument('--level', required=False, help="Set log level (DEBUG, INFO, WARNING)")

    args = parser.parse_args(argv[1:])

    store = SqliteStorage(args.database)
    setup_dns(args, store)
    setup_rest(args, store)
    reactor.run()


if __name__ == '__main__':
    raise sys.exit(main(sys.argv))
