import abc
import argparse
import io
from os import getenv
from os.path import isfile, isdir
from typing import Any

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


def format_default(default: Any):
    """
    Format the default value that will be shown in the --help of argparse
    based on type.
    """
    if isinstance(default, io.IOBase):
        return default.name
    if isinstance(default, str):
        return f'"{default}"'
    if isinstance(default, int):
        return f'{default:,}'
    if isinstance(default, float):
        return f'{default:,.2f}'
    if isinstance(default, abc.mapping.type):
        return '{mapping}'
    if isinstance(default, list):
        return '[list]'
    if isinstance(default, tuple):
        return '[tuple]'
    if isinstance(default, type):
        return default.__class__.__name__
    else:
        return str(default)


def env_or_default(env: str, default=None):
    """
    Used by argparse, when configuring the default get the environment variable, or return the original default
    set inline
    """
    value = getenv(env)
    if not value:
        return default

    return value


def is_env_true(env: str, default=None):
    """
    Used by argparse, when configuring the default, get a True/False value from the environment variable or
    return the default, for 'store_true' switches the default is automatically set to False.
    """
    value = getenv(env)
    if not value:
        return default

    return value.lower() in {'true', '1', 'yes'}


def is_env_true_reversed(env: str, default=None):
    """
    Same as `is_env_true` except True becomes False, and False becomes True
    If no env is set, the default is preserved without reversing or negating it.
    Only the env variable itself is negated "True" becomes False, "False" becomes True
    """
    value = getenv(env)
    if not value:
        return default

    return not value.lower() in {'true', '1', 'yes'}