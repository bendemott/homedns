import argparse
from os.path import isfile, isdir
from yaml import load, dump, YAMLError
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def file_exists(arg):
    if not isfile(arg):
        raise argparse.ArgumentTypeError(f'"{arg}" invalid file')
    return arg


def dir_exists(arg):
    if not isdir(arg):
        raise argparse.ArgumentTypeError(f'"{arg}" invalid directory')
    return arg


def yaml_file(arg):
    file_exists(arg)
    try:
        return load(open(arg), Loader)
    except YAMLError as e:
        raise argparse.ArgumentTypeError(f'not a yaml file: "{arg}", error: {e}')
