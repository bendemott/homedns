import collections.abc
import copy
from abc import ABC, abstractmethod
from os.path import join, dirname, getmtime
import os
from typing import Any

from twisted.names import dns
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from homedns.constants import DEFAULT_SERVER_CONFIG_PATH, DEFAULT_NAME_SERVERS


class AbstractConfig(ABC):
    """
    Generic yaml configuration with convenience methods
    """
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

    def load_file(self, path):
        """
        Load yaml configuration from file
        """
        self._path = path
        self._modify_time = getmtime(path)
        # an empty file will load to None
        self._config = load(open(path, 'r'), Loader) or {}
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

