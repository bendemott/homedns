import sys
import argparse
import json
from datetime import datetime

from homedns.certificates import CertPair, KeyPair
from homedns.config import ServerConfig
from homedns.jwt import JwtFileCredentials, JwtSubject
from homedns.cli.server import DEFAULT_SERVER_CONFIG_PATH
from homedns.cli.common import file_exists

ADD_COMMAND = 'add'
LIST_COMMAND = 'list'
REMOVE_COMMAND = 'remove'


def load_jwt_creds(config_path):
    server = ServerConfig(config_path)
    jwt_path = server.config['jwt_auth']['subjects']
    return JwtFileCredentials(jwt_path)


def cli_add(args):
    creds = load_jwt_creds(args.config)
    kp = KeyPair()
    pair = kp.generate()
    subject = JwtSubject(certificate=pair.public)
    creds.add_subject(subject)

    if args.json:
        print(json.dumps({
            'subject': subject.subject,
            'key': pair.key.decode()
        }, indent=4))
    else:
        print('\nJWT CREDENTIALS GENERATED')
        print('')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print(f'SUBJECT: {subject.subject}')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print('')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print('>>>>>>> PRIVATE KEY, COPY AND SAVE SECURELY FOR CLIENT SIDE AUTH >>>>>>>>')
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print(pair.private.decode())
        print(f'\nSubject added to "{creds.path}"')
        print(f'Public Key save to "{creds.create_certificate_path(subject.subject)}"')


def cli_list(args):
    creds = load_jwt_creds(args.config)
    subjects = creds.config
    if  args.json:
        print(json.dumps(subjects, indent=4, sort_keys=True))
    else:
        print(f'A total of [{len(subjects):,}] JWT subjects exist')
        for key, data in subjects.items():
            created = datetime.fromtimestamp(data[creds.CREATED_KEY]).strftime("%Y-%m-%d %H:%M")
            print(f'{key} | {data[creds.CERTIFICATE_PATH]} | {created}')


def cli_remove(args):
    remove_sub = args.subject
    creds = load_jwt_creds(args.config)
    subjects = creds.config
    if not creds.subject_exists(remove_sub):
        if args.json:
            print(json.dumps({'error': 'invalid subject',
                              'subject': remove_sub}))
        else:
            print(f'Invalid subject: "{remove_sub}"')

    else:
        creds.remove_subject(remove_sub)
        if args.json:
            return json.umps({'ok': True})
        else:
            print(f'Removed subject: "{args.subject}"')


def main(argv=None):
    argv = argv or sys.argv

    parser = argparse.ArgumentParser('jwt', description='Configure JWT Auth')
    parser.add_argument(
        '--config',
        metavar='PATH',
        help=f'Server config path, default="{DEFAULT_SERVER_CONFIG_PATH}"',
        default=DEFAULT_SERVER_CONFIG_PATH,
        type=file_exists
    )

    parser.add_argument('--json', action='store_true', help='Return json output (useful for automation)')
    parser.add_argument('--debug', action='store_true', help='Debug logging')
    subparsers = parser.add_subparsers(dest='command')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////  REMOVE JWT CREDENTIAL   //////////////////////////

    list = subparsers.add_parser(LIST_COMMAND, help='List JWT Subjects')

    # /////////////////////////////////////////////////////////////////////////
    # //////////////////////  ADD JWT CREDENTIAL   ////////////////////////////

    add = subparsers.add_parser(ADD_COMMAND, help='Create a new JWT key pair and identity (subject)')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////  REMOVE JWT CREDENTIAL   //////////////////////////

    remove = subparsers.add_parser(REMOVE_COMMAND, help='Delete a JWT key pair and identity (subject)')
    remove.add_argument('subject', help='Remove the given subject')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    args = parser.parse_args(argv[1:])
    if args.command == ADD_COMMAND:
        cli_add(args)
    elif args.command == LIST_COMMAND:
        cli_list(args)
    elif args.command == REMOVE_COMMAND:
        cli_remove(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
