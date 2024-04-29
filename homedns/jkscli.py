"""
A CLI to create JKS credentials
"""
import sys

from twisted.python import log


def main(argv = None):
    log.startLogging(sys.stdout)
    argv = argv or ['']

    # generate credentials
    # generate client code example
    # test a jwt token


if __name__ == '__main__':
    sys.exit(main(sys.argv))