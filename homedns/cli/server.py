"""
If someone calls `python3 -m homedns` this is called!
"""

import sys
import argparse
from os.path import isfile
import json

from homedns.server import server_main
from homedns.constants import DEFAULT_SERVER_CONFIG_PATH, DEFAULT_LOG_LEVEL
from homedns.config import ServerConfig
from homedns.cli.common import file_exists

from yaml import load, dump, YAMLError
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

START_COMMAND = 'start'
CONFIG_DUMP_COMMAND = 'config-dump'
CONFIG_TEMPLATE_COMMAND = 'config-template'


def config_dump(args):
    config = ServerConfig()
    if args.json:
        contents = json.dumps(config.config, indent=4)
    else:
        contents = str(config)

    if args.save:
        if not isfile(args.save) or args.overwrite:
            with open(args.save, 'w') as fp:
                fp.write(contents)
                print(f'Configuration written to: "{args.save}"')
        else:
            print(f'Configuration already exists at "{args.save}", use --overwrite to replace')

    if args.save_to_default:
        if not isfile(DEFAULT_SERVER_CONFIG_PATH) or args.overwrite:
            with open(DEFAULT_SERVER_CONFIG_PATH, 'w') as fp:
                fp.write(contents)
                print(f'Configuration written to: "{DEFAULT_SERVER_CONFIG_PATH}"')
        else:
            print(f'Configuration already exists at "{DEFAULT_SERVER_CONFIG_PATH}", use --overwrite to replace')

def main(argv=None):
    argv = argv or sys.argv

    parser = argparse.ArgumentParser('homedns')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Debug logging'
    )

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    subparsers = parser.add_subparsers(dest='command')
    server = subparsers.add_parser(START_COMMAND, help='Start Server')
    server.add_argument(
        '--config',
        metavar='PATH',
        help=f'Config path, default="{DEFAULT_SERVER_CONFIG_PATH}"',
        default=DEFAULT_SERVER_CONFIG_PATH,
        type=file_exists
    )

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    server = subparsers.add_parser(CONFIG_DUMP_COMMAND, help='Show working config')
    server.add_argument(
        '--config',
        metavar='PATH',
        help=f'Config path, if not specified the default configuration is returned',
        type=file_exists
    )
    server.add_argument(
        '--json',
        action='store_true',
        help=f'format as JSON instead of Yaml (default)'
    )

    server.add_argument(
        '--save',
        metavar='PATH',
        help=f'Save the configuration to this path'
    )

    server.add_argument(
        '--save-to-default',
        action='store_true',
        help=f'Save the configuration to the default application path: "{DEFAULT_SERVER_CONFIG_PATH}"'
    )

    server.add_argument(
        '--overwrite',
        action='store_true',
        help=f'Overwrite a file that already exists when using --save or --save-to-default'
    )

    args = parser.parse_args(argv[1:])

    if args.command == START_COMMAND:
        server = ServerConfig(args.config)
        server_main(server, DEFAULT_LOG_LEVEL if not args.debug else 'debug')
    elif args.command == CONFIG_DUMP_COMMAND:
        config_dump(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))