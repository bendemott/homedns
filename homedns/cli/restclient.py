import sys
import argparse

from twisted.names import dns

from homedns.restclient import JwtAuthenticationRS256, Client

GET_COMMAND = 'GET'


def cli_get(args):
    auth = None
    if args.jwt_key:
        auth = JwtAuthenticationRS256(args.jwt_key, args.audience, args.issuer)
    client = Client(args.server, auth, https=not args.http, verify=not args.no_verify)
    result = {}
    if args.type == dns.A:
        result = client.get_a_by_hostname(args.name)
    elif args.type == dns.CNAME:
        result = client.get_cname_by_hostname(args.name)

    print(result)


def main(argv=None):
    argv = argv or ['']

    parser = argparse.ArgumentParser('rest-client', description='HomeDNS DNS Rest Client, create, '
                                                                'update, delete records')
    parser.add_argument('--server', help='Rest Server')
    parser.add_argument('--http', action='store_true', help="Use http instead of https")
    parser.add_argument('--no-verify', action='store_true', help="Don't verify server ssl certificate")
    #parser.add_argument('--jwt-key', type=argparse.FileType('r'),
    #                    help='Authenticate with JWT, Private key for RS256 Encoding')
    parser.add_argument('--jwt-audience', help='Audience, who the token is intended for '
                        '(Must match the server)')
    parser.add_argument('--jwt-issuer', help='Issuer, who created the token '
                        '(Must match the server)')
    parser.add_argument('--debug', action='store_true', help='Debug logging')

    # /////////////////////////////////////////////////////////////////////////
    # ////////////////////////////   GET   ////////////////////////////////////

    subparsers = parser.add_subparsers(dest='command')
    get = subparsers.add_parser(GET_COMMAND, help='Retrieve a DNS record')
    get.add_argument('name', metavar='PATH', help=f'Hostname')
    get.add_argument('type', help='record type, A, AAAA, MX, CNAME')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    args = parser.parse_args(argv[1:])

    if args.command == GET_COMMAND:
        cli_get(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
