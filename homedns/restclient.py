import json
import ssl
import textwrap
from abc import ABC, abstractmethod
from base64 import b64encode
from datetime import datetime, timezone, timedelta
import urllib.request
from urllib.parse import urlunparse, urlencode
from typing import Any
from urllib.error import HTTPError, URLError

from homedns import __version__

import jwt

from twisted.names import dns
from twisted.names.dns import QUERY_TYPES

"""
All query types
    A: "A",
    NS: "NS",
    MD: "MD",
    MF: "MF",
    CNAME: "CNAME",
    SOA: "SOA",
    MB: "MB",
    MG: "MG",
    MR: "MR",
    NULL: "NULL",
    WKS: "WKS",
    PTR: "PTR",
    HINFO: "HINFO",
    MINFO: "MINFO",
    MX: "MX",
    TXT: "TXT",
    RP: "RP",
    AFSDB: "AFSDB",
    # 19 through 27?  Eh, I'll get to 'em.
    AAAA: "AAAA",
    SRV: "SRV",
    NAPTR: "NAPTR",
    A6: "A6",
    DNAME: "DNAME",
    OPT: "OPT",
    SSHFP: "SSHFP",
    SPF: "SPF",
    TKEY: "TKEY",
    TSIG: "TSIG",
    
"""


class ClientAuthentication(ABC):

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        raise NotImplemented()


class JwtAuthenticationRS256(ClientAuthentication):

    def __init__(self, private_key: str, subject: str, audience: str = None, issuer: str = None, expire_in: int = 0):
        """
        :param private_key: The jwt signing key, this is your "password"
        :param subject: The jwt identity / account
        :param audience: Audience, who the token is intended for
        :param issuer: Issuer, who created the token
        :param expire_in: How many seconds in the future to set the token to expire
        """
        self.issuer = issuer
        self.audience = audience
        self.subject = subject
        self.expire_in = expire_in
        self.private_key = private_key

    def get_token(self):
        payload = {
            'iat': datetime.now(tz=timezone.utc),
            'nbf': datetime.now(tz=timezone.utc),
            'exp': datetime.now(tz=timezone.utc) + timedelta(seconds=self.expire_in),
            'sub': self.subject
        }
        if self.audience:
            payload['aud'] = self.audience
        if self.issuer:
            payload['iss'] = self.issuer

        # encodes a base64 token, encrypted with private_key
        # asymmetric encryption is much safer than symmetric (HS256)
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def get_headers(self) -> dict[str, str]:
        return {'authorization': f'Bearer {self.get_token()}'}


class BasicAuthentication(ClientAuthentication):
    def __init__(self, username, password):
        self._username = username
        self._password = password

    def get_headers(self) -> dict[str, str]:
        """
        Get authorization headers for basic authentication
        - Returns a 'Authorization' header
        """
        token = b64encode(f"{self._username}:{self._password}".encode('utf-8')).decode("ascii")
        return {'authorization': f'Basic {token}'}


class Client:
    """
    Client for manage dns records via REST API in HomeDNS Server.
    The client intentionally avoids the use of `requests` as well as the twisted client.
    This means it can be used standalone separate from the rest of the applicatio if needed.

    Anytime you see a reference to `record_type` use the constants:
    - dns.A
    - dns.AAAA
    - dns.CNAME
    - dns.MX
    """

    def __init__(self, server: str, credentials: ClientAuthentication = None, https=True, verify=True):
        self._server = server
        self._credentials = credentials
        self._https = https
        self._proto = 'https' if self._https else 'http'
        if https:
            self._context = ssl.create_default_context()
            self._context.check_hostname = verify
            self._context.verify_mode = ssl.CERT_REQUIRED if verify else ssl.CERT_NONE
        else:
            self._context = None

        if not isinstance(credentials, ClientAuthentication):
            raise ValueError(f'invalid credentials argument: {type(credentials)}')

    def auth_headers(self):
        return self._credentials.get_headers()

    def url(self, uri: str, params: dict[str, str] = None):
        if not uri.startswith('/'):
            raise ValueError(f'URI must begin with /, uri: {uri}')
        if params is None:
            params = {}
        # parts = ('https', 'www.example.com', '/path/to/resource', '', 'param=value', 'fragment')
        return urlunparse([self._proto, self._server, uri, '', urlencode(params), ''])

    def get_headers(self):
        headers = self.auth_headers()
        headers.update({'Content-Type': 'application/json'})
        headers.update({'Accept-Encoding': 'gzip, deflate'})
        headers.update({'Accept': 'application/json'})
        headers.update({'User-Agent': f'HomeDNS Client ({__version__})'})
        assert 'authorization' in headers
        return headers

    def add_headers(self, request):
        headers = self.get_headers()
        for header, value in headers.items():
            request.add_header(header, value)

    def get(self, uri, params: dict[str, str] = None):
        """
        HTTP GET, for fetching
        """
        url = self.url(uri, params)
        request = urllib.request.Request(url, headers=self.get_headers(), method='GET')
        response = urllib.request.urlopen(request, context=self._context)
        raw = response.read()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid response from "{url}"\n{raw}\n{e}') from e

    def put(self, uri: str, data: dict[Any, Any]):
        """
        HTTP PUT, for update/replace
        """
        url = self.url(uri)
        data = json.dumps(data).encode()  # bytes
        request = urllib.request.Request(url, data, headers=self.get_headers(), method='PUT')
        response = urllib.request.urlopen(request, context=self._context)
        raw = response.read()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid response from "{url}"\n{raw}\n{e}') from e

    def post(self, uri: str, data: dict[Any, Any]):
        """
        HTTP POST, for create
        """
        url = self.url(uri)
        data = json.dumps(data).encode()  # bytes
        request = urllib.request.Request(url, data, headers=self.get_headers(), method='POST')
        response = urllib.request.urlopen(request, context=self._context)
        raw = response.read()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid response from "{url}"\n{raw}\n{e}') from e

    def delete(self, uri: str, params: dict[str, str] = None):
        """
        HTTP DELETE, for deleting
        """
        url = self.url(uri, params)
        request = urllib.request.Request(url, headers=self.get_headers(), method='DELETE')
        response = urllib.request.urlopen(request, context=self._context)
        raw = response.read()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid response from "{url}"\n{raw}\n{e}') from e

    def update_a_record(self, hostname: str, address: str, ttl: int):
        """
        Update address of record with `hostname`
        Note that multiple A records can be associated with a single hostname.
        If this is the case, all records will be updated with `address`

        Raises NotFoundError if the dns record doesn't exist

        :param hostname: A Record Hostname to be updated
        :param address: The address that will be set on record with hostname
        :param ttl: update interval of the dns record
        """
        return self.put(f'/update/a/{hostname}', {'address': address, 'ttl': ttl})

    def create_a_record(self, hostname: str, address: str, ttl: int):
        """
        Create a hostname record
        """
        return self.post(f'/create/a/{hostname}', {'address': address, 'ttl': ttl})

    def upsert_a_record(self, hostname: str, address: str, ttl: int):
        assert isinstance(hostname, str)
        assert isinstance(address, str)
        assert isinstance(ttl, int)
        return self.put(f'/upsert/a/{hostname}', {'address': address, 'ttl': ttl})

    def delete_a_by_hostname(self, hostname: str):
        return self.delete(f'/hostname/a/{hostname}')

    def get_a_by_hostname(self, hostname: str):
        """
        Return A records by hostname
        """
        return self.get(f'/hostname/a/{hostname}')

    def get_cname_by_hostname(self, hostname):
        """
        Return A records by hostname
        """
        return self.get(f'/hostname/cname/{hostname}')

    def delete_records_by_hostname(self, hostname, record_type=None):
        return self.delete(f'/hostname/{hostname}', {'type': record_type})

    def delete_records_by_address(self, address, record_type=None):
        return self.delete(f'/address/{address}', {'type': record_type})

    def search_address(self, address, record_type=None):
        return self.get(f'/search/address/{address}', {'address': address, 'type': record_type})

    def echo_ip4(self):
        """
        Echo back my ip address to me
        """
        return self.get('/ip4')

    @staticmethod
    def pretty_headers(headers: dict):
        pretty = []
        width = max([len(str(h)) for h in headers] or [0])
        for name, value in headers.items():
            pretty.append(f'{name.ljust(width)}: {value}')
        return '\n'.join(pretty)

    @classmethod
    def pretty_error(cls, error: HTTPError):
        headers = cls.pretty_headers(error.headers) or '(No response headers)'
        headers = textwrap.indent(headers, ' ' * 4)
        text = textwrap.dedent(f"""
            API Error [{error.code} {error.msg}]
            URL: {error.url}
            Response Headers:
            %s
        """) % headers
        return text
