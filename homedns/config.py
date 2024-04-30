import collections.abc
import copy
from os.path import join
import os
from typing import Any


class ServerConfig:
    def __init__(self, config: dict):
        self._config = config

    @classmethod
    def get_default(cls, directory=None) -> dict[str, Any]:
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
                "secrets_path": join(directory, "jwt_secrets"),
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
                "enabled": False
            },
            "dns": {
                "listen_tcp": 53,
                "listen_udp": 53,
                "cache": {
                    "enabled": True
                },
                "forwarding": {
                    "enabled": True,
                    "servers": [
                        "208.67.222.222",
                        "208.67.220.220"
                    ],
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
                "tld": 300,
                "verbosity": 2
            }
        }

        return conf

    def apply_defaults(self, default_config=None):
        return self._recursive_update(self._config, default_config or ServerConfig.get_default())

    def _recursive_update(self, config, defaults):
        def update(d, u):
            for k, v in u.items():
                if isinstance(v, collections.abc.Mapping):
                    d[k] = update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d

        updated = copy.deepcopy(defaults)
        return update(updated, config)