"""
JWT Cred module for Twisted

To understand how json web tokens work see: https://github.com/bendemott/homedns
"""
import json
import os
import re
import sys
import traceback
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from os.path import dirname, join, isfile
from typing import Any
import textwrap

import jwt
from cryptography.hazmat.primitives import serialization
from jwt import PyJWTError
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import ICredentials
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer
from twisted.logger import Logger
from twisted.web.iweb import ICredentialFactory
from twisted.cred import error
from zope.interface import implementer
from OpenSSL import crypto

from homedns.config import AbstractConfig, set_file_permissions
from homedns.constants import DEFAULT_JWT_SUBJECTS_PATH

AUDIENCE_KEY = 'aud'  # audience
ISSUER_KEY = 'iss'    # who created the token
SUBJECT_KEY = 'sub'   # user id / username
ISSUED_AT_KEY = 'iat'
EXPIRES_AT_KEY = 'exp'
NOT_BEFORE_KEY = 'nbf'
JWT_ID_KEY = 'jti'  # onotonically incrementing number (replay prevention) (optional)


@dataclass
class JwtSubject:
    """
    Creates and stores subject objects
    """
    subject: str = None
    created: datetime = None
    certificate: str = None

    def __post_init__(self):
        if not self.subject:
            self.subject = JwtSubject.create_subject()
        if not self.created:
            self.created = datetime.now().timestamp()

    @classmethod
    def create_subject(cls):
        return str(uuid.uuid4())


class InvalidSubject(UnauthorizedLogin):
    pass


class JwtFileCredentials(AbstractConfig):
    """
    Store JWT file credentials

    Json Web Tokens are identified by an identity, or account, that account is the `subject`.
    The subject is held in the `sub` field of the payload of the jwt token.
    This is somewhat of a convention, there is nothing that truly enforces you use the `sub` field.
    But being good neighbors we'll follow this convention.

    This configuration stores data about each subject. In our case when we generate a subject we use a `uuid`.
    You can manually configure a subject with any name, but `uuid` is sufficiently random and complex to act
    as a unique id for each client by default.

    This configuration is a yaml file in which the top level keys of the yaml file are the subject names.
    There is a corresponding object / mapping for each subject name that contains the creation time and the path
    to the credential file on disk
    """
    SUBJECT_KEY = 'subject'
    CREATED_KEY = 'created'
    CERTIFICATE_CONTENTS = 'certificate'
    CERTIFICATE_PATH = 'certificate_path'
    DEFAULT_MODE = 0o640

    def __init__(self, path: str = DEFAULT_JWT_SUBJECTS_PATH):
        # create the file if it doesn't exist
        self._log = Logger(self.__class__.__name__)

        self.initialize_file(path, contents='')
        self.set_permissions(path, mode=self.DEFAULT_MODE)

        # super will do the work
        super().__init__(path)

    def subject_exists(self, subject_name: str):
        return subject_name in self.config

    def create_certificate_path(self, subject_name: str):
        if not isinstance(subject_name, str):
            raise ValueError(f'Invalid subject name type: {type(subject_name)}')
        return join(dirname(self.path), f'{subject_name}.crt')

    def read_certificate(self, subject_name) -> bytes:
        """
        Read the certificate contents from disk.
        Each JWT subject stores a unique public key on disk that is used to verify the identity
        of the client and decrypt the contents of the passed jwt token.
        """
        subject_config = self.config.get(subject_name)
        if not subject_config:
            raise InvalidSubject(f'Subject "{subject_name}" is not present in configuration: "{self.path}"')
        cert_path = subject_config.get(self.CERTIFICATE_PATH)
        if not cert_path:
            raise InvalidSubject(f'Subject "{subject_name}" is mis-configured, '
                                 f'"{self.CERTIFICATE_PATH}" key missing from config: "{self.path}"')
        if not isfile(cert_path):
            raise FileNotFoundError(f'The certificate file for subject "{subject_name}" is missing from: "{cert_path}"')
        return open(cert_path, 'rb').read()  # bytes

    def write_certificate(self, subject_name, contents: str | bytes) -> str:
        # convert to bytes
        if isinstance(contents, str):
            contents = contents.encode()
        cred_path = self.create_certificate_path(subject_name)
        with open(cred_path, 'wb') as fp:
            fp.write(contents)

        set_file_permissions(cred_path, mode=0o640)

        return cred_path

    def get_default(self, directory: str = None):
        """
        Required be the parent implementation

        Return default configuration options for this configuration class.
        JWT Subjeccts Config has no default options.
        """
        return {}

    def add_subject(self, sub: JwtSubject):
        """
        Add a new subject to the jwt credentials file
        """
        if not sub.certificate:
            raise ValueError('Certificate cannot be empty')

        cert_path = self.write_certificate(sub.subject, sub.certificate)

        self.config[sub.subject] = {
            self.CERTIFICATE_PATH: cert_path,
            self.CREATED_KEY: sub.created
        }

        try:
            self.update()
        except Exception as e:
            # if we failed to update the config, don't create the certificate on disk either
            os.unlink(cert_path)
            raise

    def remove_subject(self, subject: str):
        """
        Delete a subject from credentials file and remove public key from disk
        """
        conf = self.config
        if subject not in conf:
            raise InvalidSubject(f'Subject not found: "{subject}" in subjects config: "{self.path}"')
        cert_path = conf[subject][self.CERTIFICATE_PATH]
        del conf[subject]

        if isfile(cert_path):
            os.unlink(cert_path)

        self.update()

    def get_subject(self, subject: str) -> JwtSubject:
        """
        Return a subject object, if you want to retrieve a subject and the associated public key
        this is the only method you need to call.

        `jwt.decode` can be called with the returned public key.
        """
        try:
            s = self.config[subject]
        except KeyError:
            raise InvalidSubject(subject)

        cert_contents = self.read_certificate(subject)

        return JwtSubject(subject=subject,
                          certificate=cert_contents,
                          created=s['created'])


class IJwtCredential(ICredentials):
    pass


@implementer(IJwtCredential)
class JwtCredential:

    def __init__(self, token, payload, public_key):
        if not isinstance(public_key, bytes):
            public_key = public_key.encode()
        self.token = token  # the raw jwt token from the client
        self.payload: dict = payload  # the un-verified payload from the client
        self.secret = public_key  # public key, or shared secret
        self.audience = payload.get(AUDIENCE_KEY)
        self.issuer = payload.get(ISSUER_KEY)
        self.subject = payload.get(SUBJECT_KEY)
        self.jwt_id = payload.get(JWT_ID_KEY)


@implementer(ICredentialsChecker)
class JwtTokenChecker:
    credentialInterfaces = (IJwtCredential,)

    def __init__(self, audience: list[str], issuer: str, leeway: int = 300, algorithms: list[str] = None):
        """
        :param audience: Valid audience values in jwt client token (Audience = who the token is for)
        :param issuer: Valid issuer value expected in jwt client token (Issuer = who generated the token)
        :param leeway: The number of seconds of leeway in the validation of the tokens timing
                       (this helps prevent replay attacks)
        """
        self.valid_audience = audience
        self.valid_issuer = issuer
        self.leeway = leeway
        self.algorithms = algorithms
        if self.algorithms is None:
            self.algorithms = ['RS256']  # default is asymmetric encryption
        self._log = Logger(self.__class__.__name__)

    def requestAvatarId(self, credentials: JwtCredential):
        # what to do with the user profile? local avatar registry?
        # try/catch to return Failure on bad signature...
        try:
            public_key = serialization.load_pem_public_key(credentials.secret)
        except Exception as e:
            raise RuntimeError(f'public key for subject: "{credentials.subject}" could not be read') from e

        try:
            payload = jwt.decode(credentials.token,
                                 audience=self.valid_audience,
                                 issuer=self.valid_issuer,
                                 key=public_key,
                                 algorithms=self.algorithms,
                                 leeway=self.leeway)
        except PyJWTError as e:
            self._log.info(f'JWT credential error: {str(e)}')
            self._log.debug(str(json.dumps(credentials.payload, indent=4)))
            self._log.debug(f'valid audience: {self.valid_audience}')
            self._log.debug(f'valid issuer: {self.valid_issuer}')
            return defer.fail(error.UnauthorizedLogin())
        except ValueError as e:
            self._log.info(f'{str(e)} SUBJECT: {credentials.subject}, JWT Public Key:\n{credentials.secret}')
            self._log.info(traceback.format_exc())
            return defer.fail(error.UnauthorizedLogin())

        # The JWT Subject field is typically used as the Client USER/ACCOUNT ID
        return defer.succeed(credentials.subject.encode('utf-8'))


@implementer(ICredentialFactory)
class JwtCredentialFactory:
    scheme = b'bearer'  # required by ICredentialFactory

    def __init__(self, credentials: JwtFileCredentials):
        """
        credentials: JWT Credential configuration - clients will be authenticated using asymmetric keys
                     and subjects identified in this configuration.
        """
        self._creds = credentials
        self._log = Logger(self.__class__.__name__)

    @staticmethod
    def getChallenge(address):
        """
        Generate the challenge for use in the WWW-Authenticate header
        @param request: The L{twisted.web.http.Request}
        @return: The C{dict} that can be used to generate a WWW-Authenticate
            header.
        """
        # Implement http://self-issued.info/docs/draft-ietf-oauth-v2-bearer.html#authn-header
        return {}

    def decode(self, response: str, request) -> JwtCredential:
        """
        :param response: Response from the client (jwt token)
        :param request: JWT token request (unused)
        """

        """
        You can read the payload of a JWT token without verifying its signature.
        This is useful when you might want to know one of the fields in the payload section
        of the JWT token from the client without actually verifying the token.
        In our case, we have an assymetric key per-user.  
        
        The job of the credential factory is just to grab the credential not to validate it.
        """
        raw_payload = response
        # read the payload without validating its symmetric encryption
        self._log.debug(f'Decoding token: {raw_payload}')
        try:
            unverified = jwt.decode(raw_payload, options={"verify_signature": False})
        except Exception as e:
            self._log.info(f'{e.__class__.__name__} - failed read subject from token: {str(e)}')
        subject_name = unverified.get('sub')

        try:
            subject = self._creds.get_subject(subject_name)
        except InvalidSubject as e:
            self._log.info(f'{e.__class__.__name__} - {str(e)}')
            raise

        cred = JwtCredential(response, unverified, subject.certificate)
        self._log.debug(f'returning credential object {cred}')
        return cred


