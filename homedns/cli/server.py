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
        help=f'Config path',
        type=file_exists
    )
    server.add_argument(
        '--json',
        action='store_true',
        help=f'format as json'
    )

    args = parser.parse_args(argv[1:])

    if args.command == START_COMMAND:
        server = ServerConfig(args.config)
        server_main(server, DEFAULT_LOG_LEVEL if not args.debug else 'debug')
    elif args.command == CONFIG_DUMP_COMMAND:
        config = ServerConfig()
        if args.json:
            print(json.dumps(config.config, indent=4))
        else:
            print(str(config))


if __name__ == '__main__':
    sys.exit(main(sys.argv))