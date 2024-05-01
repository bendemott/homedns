import sys
import argparse
import json

from homedns.certificates import KeyPair
from homedns.config import ServerConfig
from homedns.jwt import JwtFileCredentials, JwtSubject
from homedns.cli.server import DEFAULT_SERVER_CONFIG_PATH
from homedns.cli.common import file_exists

ADD_COMMAND = 'add'
LIST_COMMAND = 'list'


def load_jwt_creds(config_path):
    server = ServerConfig(config_path)
    jwt_path = server.config['jwt']['subjects']
    return JwtFileCredentials(jwt_path)


def cli_add(args):
    creds = load_jwt_creds(args.config)
    kp = KeyPair()
    kp.options(country='US', organization='homedns')
    pair = kp.generate()
    subject = JwtSubject(certificate=pair.cert.decode())
    creds.add_subject(subject)

    if args.json:
        print(json.dumps({
            'subject': subject.subject,
            'key': pair.key.decode()
        }))
    else:
        print('JWT CREDENTIALS GENERATED')
        print('=' * 20)
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print(f'SUBJECT: {subject.subject}')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print('\n')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print('>>>>>>> PRIVATE KEY, COPY AND SAVE SECURELY FOR CLIENT SIDE AUTH >>>>>>>>')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print(pair.key.decode())
        print(f'\nPublic key saved in "{creds.path}"')


def cli_list(args):
    creds = load_jwt_creds(args.config)
    subjects = creds.config
    print(f'A total of [{len(subjects):,}] JWT subjects exist')
    for key, data in subjects.items():
        print(f'{key} | {data["created"]}')


def main(argv=None):
    argv = argv or ['']

    parser = argparse.ArgumentParser('jwt', description='Configure JWT Auth')
    parser.add_argument(
        '--config',
        metavar='PATH',
        help=f'Server config path, default="{DEFAULT_SERVER_CONFIG_PATH}"',
        default=DEFAULT_SERVER_CONFIG_PATH,
        type=file_exists
    )
    parser.add_argument('--debug', action='store_true', help='Debug logging')

    # /////////////////////////////////////////////////////////////////////////
    # ////////////////////////////   GET   ////////////////////////////////////

    subparsers = parser.add_subparsers(dest='command')
    add = subparsers.add_parser(ADD_COMMAND, help='Create a new JWT key pair and identity (subject)')
    add.add_argument('--json', action='store_true', help='Return json output (useful for automation)')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    args = parser.parse_args(argv[1:])

    if args.command == ADD_COMMAND:
        cli_add(args)
    elif args.command == LIST_COMMAND:
        cli_list(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
