"""
If someone calls `python3 -m homedns` this is called!
"""
import sys
from homedns.cli.server import main as cli_main


def main(argv=None):
    return cli_main(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv))