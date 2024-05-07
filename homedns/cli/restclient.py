import io
import sys
import os
import argparse
from urllib.error import HTTPError, URLError

from twisted.names import dns

from homedns.constants import DEFAULT_TTL
from homedns.cli.common import is_env_true, is_env_true_reversed, env_or_default, format_default
from homedns.restclient import JwtAuthenticationRS256, Client

HOMEDNS_SERVER_ENV = 'HOMEDNS_SERVER'
HOMEDNS_VERIFY_ENV = 'HOMEDNS_VERIFY'
HOMEDNS_HTTP_ENV = 'HOMEDNS_HTTP'
JWT_SUBJECT_ENV = 'JWT_SUBJECT'
JWT_AUDIENCE_ENV = 'JWT_AUDIENCE'
JWT_ISSUER_ENV = 'JWT_ISSUER'
JWT_KEY_ENV = 'JWT_KEY'

IP4_COMMAND = 'IP4'
ENV_COMMAND = 'ENV'
A_COMMAND = 'A'
CNAME_COMMAND = 'CNAME'
SUB_COMMAND = 'sub_command'
GET_COMMAND = 'GET'
UPDATE_COMMAND = 'UPDATE'
UPSERT_COMMAND = 'UPSERT'
CREATE_COMMAND = 'CREATE'
DELETE_COMMAND = 'DELETE'

OPTION_ENV_MAP = {
    '--server': {'env': HOMEDNS_SERVER_ENV, 'default': env_or_default},
    '--no-verify': {'env': HOMEDNS_VERIFY_ENV, 'default': is_env_true_reversed},
    '--http': {'env': HOMEDNS_HTTP_ENV, 'default': is_env_true},
    '--jwt-key': {'env': JWT_KEY_ENV, 'default': env_or_default},
    '--jwt-subject': {'env': JWT_SUBJECT_ENV, 'default': env_or_default},
    '--jwt-audience': {'env': JWT_AUDIENCE_ENV, 'default': env_or_default},
    '--jwt-issuer': {'env': JWT_ISSUER_ENV, 'default': env_or_default},
}


def add_env_defaults(parser: argparse.ArgumentParser):
    for action in parser._get_optional_actions():
        if not isinstance(action, argparse._HelpAction) and not isinstance(action, argparse._SubParsersAction):
            options = [opt for opt in action.option_strings if opt.startswith('--')]
            if not options or options[0] not in OPTION_ENV_MAP:
                continue

            settings = OPTION_ENV_MAP[options[0]]
            env_var = settings['env']
            default_fn = settings['default']
            # assign a new default based on the combination
            if os.getenv(env_var) is None:
                if action.default is None:
                    msg = ''
                else:
                    # if no environment override is present, just add the default to the help
                    msg = f'- default={format_default(action.default)}'
            else:
                # if an environment override is present show the env variable and tis value
                action.default = default_fn(env_var, default=action.default)
                msg = f'- ${env_var}="{action.default}"'

            action.help = f'{action.help} {msg}'


def cli_ip4(args, client):
    result = client.echo_ip4()
    print(result)


def cli_genenv(args, client: Client):
    """
    Using cli arguments, format environment variables for the user
    """
    try:
        client.echo_ip4()
    except HTTPError as e:
        if e.code not in (403, 401):
            raise
        print("\nAuthentication failed, check your inputs")
        print('The settings below will probably not work!')
    except ConnectionError as e:
        print(f'\nServer connection failed: "{args.server}", unable to validate settings')

    print('\nCopy and Paste these into your shell:')
    print('=======================================')
    if args.server:
        print(f'export {HOMEDNS_SERVER_ENV}="{args.server}"')
    if args.no_verify:
        print(f'export {HOMEDNS_VERIFY_ENV}=false')
    if args.http:
        print(f'export {HOMEDNS_HTTP_ENV}=true')
    if args.jwt_subject:
        print(f'export {JWT_SUBJECT_ENV}="{args.jwt_subject}"')
    if args.jwt_key:
        if isinstance(args.jwt_key, io.IOBase):
            print(f'export {JWT_KEY_ENV}="{args.jwt_key.name}"')
        else:
            print(f'export {JWT_KEY_ENV}="{args.jwt_key}"')
    if args.jwt_audience:
        print(f'export {JWT_AUDIENCE_ENV}="{args.jwt_audience}"')
    if args.jwt_issuer:
        print(f'export {JWT_ISSUER_ENV}="{args.jwt_issuer}"')


def cli_A(args, client):
    action = args.sub_command
    if action == GET_COMMAND:
        result = client.get_a_by_hostname(args.name)

    elif action == CREATE_COMMAND:
        result = client.create_a_record(hostname=args.name, address=args.address, ttl=args.ttl)

    elif action == UPDATE_COMMAND:
        result = client.update_a_record(hostname=args.name, address=args.address, ttl=args.ttl)

    elif action == UPSERT_COMMAND:
        result = client.upsert_a_record(hostname=args.name, address=args.address, ttl=args.ttl)

    elif action == DELETE_COMMAND:
        result = client.delete_a_by_hostname(hostname=args.name)

    else:
        raise UserWarning(f'Invalid [{A_COMMAND}] command: "{action}"')

    print(result)


def cli_CNAME(args, client):
    action = args.sub_command
    if action == GET_COMMAND:
        result = client.get_cname_by_hostname(args.name)

    elif action == CREATE_COMMAND:
        result = client.create_cname_record(hostname=args.name, alias=args.alias, ttl=args.ttl)

    else:
        raise UserWarning(f'Invalid [{CNAME_COMMAND}] command: "{action}"')

    print(result)


def main(argv=None):
    argv = argv or sys.argv

    parser = argparse.ArgumentParser('rest-client', description='HomeDNS REST CLI - create, '
                                                                'update, delete DNS records')
    parser.add_argument('--server', help='Rest Server')
    parser.add_argument('--http', action='store_true', help="Use http instead of https")
    parser.add_argument('--no-verify', action='store_true', help="Don't verify server ssl certificate")
    parser.add_argument('--jwt-subject', help='JWT subject (account identity)')
    parser.add_argument('--jwt-key', type=argparse.FileType('r'),
                        help='Authenticate with JWT, Private key for RS256 Encoding')
    parser.add_argument('--jwt-audience', help='Audience, who the token is intended for '
                        '(Must match the server)', default='homedns-api')
    parser.add_argument('--jwt-issuer', help='Issuer, who created the token '
                        '(Must match the server)', default='homedns-clients')
    parser.add_argument('--debug', action='store_true', help='Debug logging')

    subparsers = parser.add_subparsers(dest='command')

    # IPV4
    subparsers.add_parser(IP4_COMMAND, aliases=[IP4_COMMAND.lower()], help=f'Have server echo back IPV4')
    # ENV
    subparsers.add_parser(ENV_COMMAND, aliases=[ENV_COMMAND.lower()], help=f'Generate environment variable statements')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////   A GROUP   ///////////////////////////////////
    parser_a = subparsers.add_parser(A_COMMAND, aliases=[A_COMMAND.lower()], help=f'A Record Operations')

    subparsers_A = parser_a.add_subparsers(dest=SUB_COMMAND)

    # ////////////////////////////   GET   ////////////////////////////////////

    get = subparsers_A.add_parser(GET_COMMAND, help='Retrieve an A record')
    get.add_argument('name', metavar='HOST', help=f'Hostname')

    # //////////////////////////   CREATE   ///////////////////////////////////

    create = subparsers_A.add_parser(CREATE_COMMAND, help='Create an A record')
    create.add_argument('name', metavar='HOST', help=f'Hostname')
    create.add_argument('--address', help='IP Address')
    create.add_argument('--ttl', type=int, help='Time to live', default=DEFAULT_TTL)

    # //////////////////////////   UPDATE   ///////////////////////////////////

    update = subparsers_A.add_parser(UPDATE_COMMAND, help='Create or update an A record')
    update.add_argument('name', metavar='HOST', help=f'Hostname')
    update.add_argument('--address', help='IP Address')
    update.add_argument('--ttl', type=int, help='Time to live', default=DEFAULT_TTL)

    # //////////////////////////   UPSERT   ///////////////////////////////////

    upsert = subparsers_A.add_parser(UPSERT_COMMAND, help='Create or update an A record')
    upsert.add_argument('name', metavar='HOST', help=f'Hostname')
    upsert.add_argument('--address', help='IP Address')
    upsert.add_argument('--ttl', type=int, help='Time to live', default=DEFAULT_TTL)

    # //////////////////////////   DELETE   ///////////////////////////////////

    delete = subparsers_A.add_parser(DELETE_COMMAND, help='Delete an A record')
    delete.add_argument('name', metavar='HOST', help=f'Delete all records associated with this host name')

    # /////////////////////////////////////////////////////////////////////////
    # ///////////////////////   CNAME GROUP   /////////////////////////////////
    parser_a = subparsers.add_parser(CNAME_COMMAND, aliases=[CNAME_COMMAND.lower()], help=f'A Record Operations')

    subparsers_CNAME = parser_a.add_subparsers(dest=SUB_COMMAND)

    # ////////////////////////////   GET   ////////////////////////////////////

    get = subparsers_CNAME.add_parser(GET_COMMAND, help='Retrieve CNAME record')
    get.add_argument('name', metavar='HOST', help=f'Hostname')

    # //////////////////////////   CREATE   ///////////////////////////////////

    create = subparsers_CNAME.add_parser(CREATE_COMMAND, help='Create CNAME record')
    create.add_argument('name', metavar='HOST', help=f'Hostname')
    create.add_argument('--alias', help='Alias is the host the cname resolves to.')
    create.add_argument('--ttl', type=int, help='Time to live', default=DEFAULT_TTL)

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    add_env_defaults(parser)
    args = parser.parse_args(argv[1:])

    if args.command:
        # you can use lowercase commands if you like
        args.command = args.command.upper()
    if hasattr(args, SUB_COMMAND) and args.sub_command:
        args.sub_command = args.sub_command.upper()

    auth = None
    if args.jwt_key:
        auth = JwtAuthenticationRS256(args.jwt_key.read(),
                                      subject=args.jwt_subject,
                                      audience=args.jwt_audience,
                                      issuer=args.jwt_issuer)
    client = Client(args.server, auth, https=not args.http, verify=not args.no_verify)

    try:
        if args.command == A_COMMAND:
            cli_A(args, client)
        elif args.command == CNAME_COMMAND:
            cli_CNAME(args, client)
        elif args.command == IP4_COMMAND:
            cli_ip4(args, client)
        elif args.command == ENV_COMMAND:
            cli_genenv(args, client)
        else:
            parser.print_help()
    except HTTPError as e:
        print(Client.pretty_error(e))
    except URLError as e:
        print(f'Connection Error: {str(e)}')
    except ConnectionError as e:
        print(f'Connection Error: {str(e)}')
    except UserWarning as e:
        print(e)


if __name__ == '__main__':
    sys.exit(main(sys.argv))

