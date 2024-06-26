import os
import json
import sys
from typing import Any, Dict, Optional, Tuple, Union

import attr
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.portal import IRealm
from twisted.web._auth.wrapper import HTTPAuthSessionWrapper, UnauthorizedResource
from twisted.web.resource import IResource, _UnsafeErrorPage
from zope.interface import implementer

from twisted.cred import error
from twisted.cred.credentials import (
    IUsernameHashedPassword,
    IUsernamePassword, Anonymous,
)
from twisted.internet import defer
from twisted.internet.defer import Deferred, succeed
from twisted.logger import Logger, textFileLogObserver
from twisted.python import failure
from twisted.web import util


@implementer(IRealm)
@attr.s
class PassthroughKleinRealm(object):
    """
    A realm which passes through resources that are authenticated
    users, works with Klein
    """
    resource = attr.ib()

    def requestAvatar(self, avatarId, mind, *interfaces):
        return succeed((IResource, self.resource, lambda: None))


@implementer(ICredentialsChecker)
class JsonPasswordDB:
    """
    A file-based, text-based username/password database.

    Records in the datafile for this class are delimited by a particular
    string.  The username appears in a fixed field of the columns delimited
    by this string, as does the password.  Both fields are specifiable.  If
    the passwords are not stored plaintext, a hash function must be supplied
    to convert plaintext passwords to the form stored on disk and this
    CredentialsChecker will only be able to check L{IUsernamePassword}
    credentials.  If the passwords are stored plaintext,
    L{IUsernameHashedPassword} credentials will be checkable as well.
    """

    cache = False
    _credCache: Optional[Dict[bytes, bytes]] = None
    _cacheTimestamp: float = 0
    _log = Logger()

    def __init__(
            self,
            filename,
            case_sensitive=True,
            hash_fn=None,
            cache=False,
    ):
        """
        @type filename: L{str}
        @param filename: The name of the file from which to read username and
        password information.

        @type caseSensitive: L{bool}
        @param caseSensitive: If true, consider the case of the username when
        performing a lookup.  Ignore it otherwise.

        @type hash_fn: Three-argument callable or L{None} `hash(user, password, file-password)`
        @param hash_fn: A function used to transform the plaintext password
        received over the network to a format suitable for comparison
        against the version stored on disk.  The arguments to the callable
        are the username, the network-supplied password, and the in-file
        version of the password.  If the return value compares equal to the
        version stored on disk, the credentials are accepted.

        @type cache: L{bool}
        @param cache: If true, maintain an in-memory cache of the
        contents of the password file.  On lookups, the mtime of the
        file will be checked, and the file will only be re-parsed if
        the mtime is newer than when the cache was generated.
        """
        self.filename = filename
        self.caseSensitive = case_sensitive
        self.hash = hash_fn
        self.cache = cache

        if self.hash is None:
            # The passwords are stored plaintext.  We can support both
            # plaintext and hashed passwords received over the network.
            self.credentialInterfaces = (
                IUsernamePassword,
                IUsernameHashedPassword,
            )
        else:
            # The passwords are hashed on disk.  We can support only
            # plaintext passwords received over the network.
            self.credentialInterfaces = (IUsernamePassword,)

        self._loadCredentials()

    def __getstate__(self):
        d = dict(vars(self))
        for k in "_credCache", "_cacheTimestamp":
            try:
                del d[k]
            except KeyError:
                pass
        return d

    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def _loadCredentials(self):
        """
        Loads the credentials from the configured file.

        @return: An iterable of C{username, password} couples.
        @rtype: C{iterable}

        @raise UnauthorizedLogin: when failing to read the credentials from the
            file.
        """

        try:
            with open(self.filename, 'r') as fp:
                data = json.load(fp)
                if not isinstance(data, dict):
                    raise ValueError(f'credentials database has invalid format: "{self.filename}"')

                for user, credential in data.items():
                    if self.caseSensitive:
                        yield user, credential
                    else:
                        yield user.lower(), credential
        except OSError as e:
            self._log.error("Unable to load credentials db: {e!r}", e=e)
            raise error.UnauthorizedLogin()

    def getUser(self, username: bytes) -> Tuple[bytes, bytes]:
        """
        Look up the credentials for a username.

        @param username: The username to look up.
        @type username: L{bytes}

        @returns: Two-tuple of the canonicalicalized username (i.e. lowercase
        if the database is not case sensitive) and the associated password
        value, both L{bytes}.
        @rtype: L{tuple}

        @raises KeyError: When lookup of the username fails.
        """
        if not self.caseSensitive:
            username = username.lower()

        if self.cache:
            if self._credCache is None or os.path.getmtime(self.filename) > self._cacheTimestamp:
                self._cacheTimestamp = os.path.getmtime(self.filename)
                self._credCache = dict(self._loadCredentials())
            return username, self._credCache[username]
        else:
            for u, p in self._loadCredentials():
                if u == username:
                    return u, p
            raise KeyError(username)

    def requestAvatarId(self, credentials: IUsernamePassword) -> Deferred[Union[bytes, Tuple[()]]]:
        try:
            user, password = self.getUser(credentials.username)
        except KeyError:
            return defer.fail(error.UnauthorizedLogin())
        else:
            up = IUsernamePassword(credentials, None)
            if self.hash:
                # if using a hashing algorithm
                if up is not None:
                    hashed_password = self.hash(up.username, up.password, p)
                    if hashed_password == password:
                        return defer.succeed(user)
                return defer.fail(error.UnauthorizedLogin())
            else:
                return defer.maybeDeferred(credentials.checkPassword, password).addCallback(
                    self._cbPasswordMatch, user
                )


@implementer(IResource)
class RestAuthWrapper(HTTPAuthSessionWrapper):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _authorizedResource(self, request):
        """
        Get the L{IResource} which the given request is authorized to receive.
        If the proper authorization headers are present, the resource will be
        requested from the portal.  If not, an anonymous login attempt will be
        made.
        """
        authheader = request.getHeader(b"authorization")
        if not authheader:
            self._log.info(f'authorization header missing')
            return util.DeferredResource(self._login(Anonymous()))

        factory, respString = self._selectParseHeader(authheader)
        if factory is None:
            self._log.error(f'No credential factory was matched, login will fail')
            return UnauthorizedResource(self._credentialFactories)
        try:
            self._log.debug(f'calling {factory.__class__.__name__}.decode(<{factory.scheme} token>, request={request.uri})')
            credentials = factory.decode(respString, request)
        except error.LoginFailed:
            self._log.error(f'Credential Factory [{factory.__class__.__name__}] login failed')
            return UnauthorizedResource(self._credentialFactories)
        except BaseException:
            self._log.failure("Unexpected failure from credentials factory")
            return _UnsafeErrorPage(500, "Internal Error", "")
        else:
            assert credentials
            return util.DeferredResource(self._login(credentials))

    def _selectParseHeader(self, header):
        """
        Choose an C{ICredentialFactory} from C{_credentialFactories}
        suitable to use to decode the given I{Authenticate} header.

        @return: A two-tuple of a factory and the remaining portion of the
            header value to be decoded or a two-tuple of L{None} if no
            factory can decode the header value.
        """
        elements = header.split(b" ")
        scheme = elements[0].lower()
        for fact in self._credentialFactories:
            if fact.scheme == scheme:
                self._log.debug(f'Credential factory [{fact.__class__.__name__}] matches scheme: "{scheme}"')
                return (fact, b" ".join(elements[1:]))

        self._log.debug(f'No credential factory found for scheme: "{scheme}"')
        return (None, None)