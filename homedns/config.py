import collections.abc
import copy
import pathlib
import shutil
from abc import ABC, abstractmethod
from os.path import join, dirname, getmtime, isfile
import os
from typing import Any

from twisted.logger import Logger
from twisted.names import dns
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from homedns.constants import DEFAULT_SERVER_CONFIG_PATH, DEFAULT_NAME_SERVERS


class ServerRuntime:
    runtime = None

    @classmethod
    def get_runtime_config(cls):
        return cls.runtime

    @classmethod
    def set_runtime_config(cls):
        return cls.runtime


def set_file_permissions(path, mode=None, owner=None, group=None):
    """
    Configure a files permissions and ownership

    :param path: File to configure permissions for
    :param mode: File permissions mode, 0o640
    :param owner: Set explicit owner of the file, default is the parent directory owner
    :param group: Set explicit group of the file, default is the parent directory group

    some configurations can create themselves and initialize themselves.
    The authentication configurations (JWT, Basic Auth) are examples of this.
    They just need to be empty files so when you interact with them the program either knows
    "hey these are empty files with no config" .... or,... they aren't empty, and the server needs to
    read the file during execution.

    So how do we know what the file permissions should be. Here's a fairly big, but hopefully pretty safe
    assumption. You can customize the config concrete configuration class so it passes an
    explicit user / group.
    But the default behavior will be thus.
    IF the parent directory user/group is set, and is different than this files user/group
    (possibly because root / sudo was used to create the file) we will CHANGE the files
    permissions to match that of the PARENT DIRECTORY.

    This means that no matter where the installation resides, as long as the owner/group on the installation
    directory is set for the user you intend to run homedns as, this file will get consistent permissions and be
    able to be reliably read by the server process.
    """
    log = Logger('permissions')

    set_owner = None
    set_group = None

    try:
        conf = pathlib.Path(path)
        directory = conf.resolve().parents[0]
        current_owner = conf.owner()
        current_group = conf.group()
    except PermissionError as e:
        log.error(f'{e.__class__.__name__} - Unable to read owner/group permissions "{path}", '
                        f'Error: {e}')
        # nothing more to do
        return
    except FileNotFoundError as e:
        log.error(f'{e.__class__.__name__} - Unable to read owner/group permissions "{path}", '
                        f'Error: {e} - It is expected that the file exists before attempting to set permissions')
        return

    if owner and current_owner != owner:
        # an explicit owner was given
        set_owner = owner
    elif not owner and directory.owner() != current_owner:
        # make the file ownership match that of the parent directory
        set_owner = directory.owner()

    if group and current_group != group:
        # an explicit group was given
        set_group = group
    elif not group and directory.group() != current_group:
        # make the file group match that of the parent directory
        set_group = directory.group()

    if set_owner or set_group:
        try:
            shutil.chown(path, user=set_owner, group=set_group)
            log.info(f'Changed file ownership: "{path}", owner: {set_owner or "no change"}, '
                           f'group: {set_group or "no change"}')
        except PermissionError as e:
            log.error(f'{e.__class__.__name__} - Unable to set owner/group permissions "{path}", '
                            f'current owner: {current_owner}, current group: {current_group}\n'
                            f'Error: {e}')
            return

    current_mode = conf.stat().st_mode
    current_octal = oct(current_mode & 0o777)

    short_mode = int(oct(mode)[2:])
    if short_mode > 777 or short_mode < 400:
        raise ValueError(f'Illogical file permission: [{short_mode}], valid range is 777 to 400')

    if mode and mode != current_octal:
        try:
            conf.chmod(mode)  # chmod(0o444)
            log.info(f'Changed file permissions: "{path}" previous: {current_octal[2:]}, '
                           f'new: {short_mode}')
        except PermissionError as e:
            log.error(f'Unable to change file permissions: "{path}" previous: {current_octal[2:]}, '
                            f'new: {short_mode}, Error: {str(e)}')
            return


class AbstractConfig(ABC):
    """
    Generic yaml configuration with convenience methods
    """
    _log = Logger()

    def __init__(self, path: str):
        self._modify_time = 0
        self._path = None
        self._config = {}
        self.load_file(path)

    @property
    def path(self) -> str:
        """
        The path of the currently loaded config file
        """
        return self._path

    @property
    def modified(self) -> float:
        """
        Config file modify time (epoch)
        """
        return self._modify_time

    @property
    def config(self):
        """
        Retrieve current configuration
        """
        if getmtime(self.path) > self.modified:
            self.reload()

        return self._config

    def reload(self):
        """
        Reload configuration from file
        """
        self.load_file(self._path)

    def set_permissions(self, path, mode=None, owner=None, group=None):
        """
        :param path: File to configure permissions for
        :param mode: File permissions mode, 0o640
        :param owner: Set explicit owner of the file, default is the parent directory owner
        :param group: Set explicit group of the file, default is the parent directory group
        """
        set_file_permissions(path, mode, owner, group)

    def initialize_file(self, path, contents=''):
        """
        Initialize the configuration if the path doesn't exist
        Some configurations need to be empty files to be used correctly.
        """
        try:
            if not isfile(path):
                with open(path, 'w') as fp:
                    fp.write(contents)
        except PermissionError as e:
            self._log.error(f'{e.__class__.__name__} - Unable to read or initialize configuration at "{path}", '
                            f'Error: {e}')
            return

    def load_file(self, path):
        """
        Load yaml configuration from file
        """
        self._path = path
        try:
            self._modify_time = getmtime(path)
            self._config = load(open(path, 'r'), Loader) or {}  # an empty file will load to None
        except FileNotFoundError:
            self._modify_time = 0
            self._config = {}
        self.apply_defaults(self.get_default(dirname(path)))

    @abstractmethod
    def get_default(self, directory: str):
        pass

    def apply_defaults(self, default_config=None):
        return self._recursive_update(self._config, default_config or self.get_default())

    def _recursive_update(self, config, defaults):
        # d is the thing we are updating
        def update(d, u):
            for k, v in u.items():
                if isinstance(v, collections.abc.Mapping):
                    d[k] = update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d

        return update(config, defaults)

    def update(self):
        """
        Write configuration back to disk
        """
        with open(self.path, 'w') as fp:
            dump(self._config, fp, Dumper, indent=2)

    def __str__(self):
        return dump(self._config, indent=2, Dumper=Dumper)

class ServerConfig(AbstractConfig):
    def __init__(self, path=DEFAULT_SERVER_CONFIG_PATH):
        super().__init__(path)

    def get_default(self, directory: str = None) -> dict[str, Any]:
        if not directory:
            directory = os.getcwd()

        conf = {
            "http": None,
            "https": {
                "listen": 443,
                "generate_keys": True,
                "private_key": join(directory, "server.pem"),
                "public_key": join(directory, "server.crt"),
            },
            "no_auth": {
                "enabled": False
            },
            "jwt_auth": {
                "enabled": True,
                "algorithms": [
                    "RS256"
                ],
                "subjects": join(directory, "jwt_secrets/jwt_subjects.yaml"),
                "issuer": "homedns-clients",
                "audience": [
                    "homedns-api"
                ],
                "leeway": 30,
                "options": {
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_aud": True,
                    "verify_iss": True
                }
            },
            "basic_auth": {
                "enabled": False,
                "secrets": None
            },
            "dns": {
                "listen_tcp": dns.PORT,
                "listen_udp": dns.PORT,
                "cache": {
                    "enabled": True
                },
                "forwarding": {
                    "enabled": True,
                    "servers": DEFAULT_NAME_SERVERS,
                    "timeouts": [
                        1,
                        3,
                        11,
                        30
                    ]
                },
                "database": {
                    "sqlite": {
                        "path": join(directory, "records.sqlite")
                    }
                },
                "ttl": 300,
                "verbosity": 1
            }
        }

        return conf

