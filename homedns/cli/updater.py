
"""
If someone calls `python3 -m homedns` this is called!
"""

import sys
import argparse
from os.path import isfile
import json

from homedns.server import config_main
from homedns.constants import DEFAULT_SERVER_CONFIG_PATH, DEFAULT_UPDATER_CONFIG_PATH, DEFAULT_CONFIG_LEVEL
from homedns.config import ServerConfig

from yaml import load, dump, YAMLError
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

UPDATER_COMMAND = 'updater'
CONFIG_DUMP_COMMAND = 'config-dump'

def file_exists(arg):
    if not isfile(arg):
        raise argparse.ArgumentTypeError(f'"{arg}" invalid file')
    return arg


def yaml_file(arg):
    file_exists(arg)
    try:
        return load(open(arg), Loader)
    except YAMLError as e:
        raise argparse.ArgumentTypeError(f'not a yaml file: "{arg}", error: {e}')


def main(argv=None):
    argv = argv or ['']

    parser = argparse.ArgumentParser('updater', description='HomeDNS Dynamic DNS Updater Client')
    parser.add_argument('--debug', action='store_true', help='Debug logging')

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    subparsers = parser.add_subparsers(dest='command')
    server = subparsers.add_parser(UPDATER_COMMAND, help='Start Updater')
    server.add_argument(
        '--config',
        metavar='PATH',
        help=f'Config path, default="{DEFAULT_UPDATER_CONFIG_PATH}"',
        default=DEFAULT_UPDATER_CONFIG_PATH,
        type=yaml_file
    )

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    server = subparsers.add_parser(UPDATER_COMMAND, help='Start Updater')
    server.add_argument(
        '--config',
        metavar='PATH',
        help=f'Config path, default="{DEFAULT_UPDATER_CONFIG_PATH}"',
        default=DEFAULT_UPDATER_CONFIG_PATH,
        type=yaml_file
    )

    # /////////////////////////////////////////////////////////////////////////
    # /////////////////////////////////////////////////////////////////////////

    server = subparsers.add_parser(CONFIG_DUMP_COMMAND, help='Show working config')
    server.add_argument(
        '--config',
        metavar='PATH',
        help=f'Config path',
        type=yaml_file
    )
    server.add_argument(
        '--json',
        action='store_true',
        help=f'format as json'
    )

    args = parser.parse_args(argv[1:])

    if args.command == UPDATER_COMMAND:
        pass
        #server = UpdaterConfig(args.config)
        #config = server.apply_defaults()
        #config_main(config, DEFAULT_CONFIG_LEVEL if not args.debug else 'debug')
    elif args.command == CONFIG_DUMP_COMMAND:
        config = args.config or yaml_file(DEFAULT_SERVER_CONFIG_PATH)
        config = ServerConfig(config).apply_defaults()
        if args.json:
            print(json.dumps(config, indent=4))
        else:
            print(dump(config, indent=4))


if __name__ == '__main__':
    sys.exit(main(sys.argv))