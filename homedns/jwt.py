"""
JWT Cred module for Twisted

To understand how json web tokens work see: https://github.com/bendemott/homedns
"""
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

import jwt
from jwt import PyJWTError
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import ICredentials
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer
from twisted.logger import Logger
from twisted.web.iweb import ICredentialFactory
from twisted.cred import error
from zope.interface import implementer

from homedns.config import AbstractConfig
from homedns.constants import DEFAULT_JWT_SUBJECTS_PATH


@implementer(ICredentials)
class JwtCredential:
    AUDIENCE_KEY = 'aud'  # audience
    ISSUER_KEY = 'iss'    # who created the token
    SUBJECT_KEY = 'sub'   # user id / username
    ISSUED_AT_KEY = 'iat'
    EXPIRES_AT_KEY = 'exp'
    NOT_BEFORE_KEY = 'nbf'
    JWT_ID_KEY = 'jti'  # monotonically incrementing number (replay prevention) (optional)
    """
    IBearerToken credentials encapsulate a valid bearer token.
    Parameters:
        token   The bearer token str
        payload The decoded and valid token payload
    """
    def __init__(self, token: str, payload: dict[str, Any], secret: str):
        self.token = token  # the raw jwt token from the client
        self.payload: dict = payload  # the un-verified payload from the client
        self.secret = secret  # public key, or shared secret
        self.audience = payload.get(self.AUDIENCE_KEY)
        self.issuer = payload.get(self.ISSUER_KEY)
        self.subject = payload.get(self.SUBJECT_KEY)
        self.jwt_id = payload.get(self.JWT_ID_KEY)


@implementer(ICredentialsChecker)
class JwtTokenChecker:
    credentialInterfaces = (JwtCredential,)

    def __init__(self, audience: list[str], issuer: str, leeway: int = 300, algorithms:list[str] = None):
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
        self.log = Logger(self.__class__.__name__)
        if self.algorithms is None:
            self.algorithms = ['RS256']  # default is asymmetric encryption

    def requestAvatarId(self, credentials: JwtCredential):
        # what to do with the user profile? local avatar registry?
        # try/catch to return Failure on bad signature...
        try:
            payload = jwt.decode(credentials.token,
                                 audience=self.valid_audience,
                                 issuer=self.valid_issuer,
                                 key=credentials.secret,
                                 algorithms=self.algorithms,
                                 leeway=self.leeway)
        except PyJWTError as e:
            return defer.fail(error.UnauthorizedLogin())

        self.log.debug(payload)

        # The JWT Subject field is typically used as the Client USER/ACCOUNT ID
        return credentials.subject.encode('utf-8')


@implementer(ICredentialFactory)
class JwtCredentialFactory(object):
    SCHEME = 'bearer'
    ALGORITHM = 'RS256'  # asymmetric encryption

    def __init__(self, credentials: dict[str, str]):
        """
        algorithms  list. List of algorithms to check.
        keys    list. Auth0 keys
        """
        self._creds = credentials

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
        unverified = jwt.decode(raw_payload, options={"verify_signature": False})
        subject = unverified.get('sub')
        if not subject or subject not in self._creds:
            raise UnauthorizedLogin('invalid subject')

        public_key = self._creds[subject]

        return JwtCredential(token=response, payload=unverified, secret=public_key)


@dataclass
class JwtSubject:
    subject: str = None
    created: datetime = None
    certificate: str = None

    def __post_init__(self):
        if not self.subject:
            self.subject = JwtSubject.create_subject()
        if not self.created:
            datetime.now().timestamp()

    @classmethod
    def create_subject(cls):
        return str(uuid.uuid4())


class JwtFileCredentials(AbstractConfig):
    """
    Store JWT file credentials
    """

    def __init__(self, path: str = DEFAULT_JWT_SUBJECTS_PATH):
        # create the file if it doesn't exist
        open(path, 'a').close()
        # super will do the work
        super().__init__(path)

    def get_default(self, directory: str = None):
        return {}

    def add_subject(self, sub: JwtSubject):
        """
        Add a new subject to the jwt credentials file
        """
        if not sub.certificate:
            raise ValueError('Certificate cannot be empty')

        self.config[sub.subject] = asdict(sub)
        self.update()
