from os.path import isdir, isfile
from socket import gethostname
import locale
from dataclasses import dataclass

from OpenSSL import crypto
from twisted.logger import Logger


@dataclass
class CertPairData:
    key: bytes
    cert: bytes


@dataclass
class KeyPairData:
    private: bytes
    public: bytes


class CertPair:
    """
    Generate self-signed certificate pairs
    """

    def __init__(self):
        self.log = Logger(self.__class__.__name__)
        self._length = 4096
        self._digest = 'sha256'
        self._hostname = gethostname()
        self._country = 'NA'
        self._state = 'NA'
        self._city = 'NA'
        self._company = 'NA'
        self._organization = 'NA'
        self._serial = 1
        self._valid_begin = 0
        self._valid_end = 10 * 365 * 24 * 60 * 60  # 10 years

        if not self._country:
            try:
                country = locale.getlocale(category=locale.LC_CTYPE)[0].split('_')[-1]
            except (TypeError, IndexError, AttributeError):
                pass

    def exists(self, private_key, public_key):
        """
        Check to see if the key pair exists
        """
        if isdir(private_key):
            raise IsADirectoryError(f'"{private_key}" is a directory, expected file')
        if isdir(public_key):
            raise IsADirectoryError(f'"{public_key}" is a directory, expected file')

        if isfile(private_key) and isfile(public_key):
            return True

        return False

    def options(self,
                length=None,
                digest=None,
                hostname=None,
                country=None,
                state=None,
                city=None,
                company=None,
                organization=None,
                serial=None,
                valid_begin=None,
                valid_end=None):
        """
        Configure cert options
        """
        self._length = length or self._length
        self._digest = digest or self._digest
        self._hostname = hostname or self._hostname
        self._country = country or self._country
        self._state = state or self._state
        self._city = city or self._city
        self._company = company or self._company
        self._organization = organization or self._organization
        self._serial = serial if serial is not None else self._serial
        self._valid_begin = valid_begin if valid_begin is not None else self._valid_end
        self._valid_end = valid_end or self._valid_end

    def generate(self) -> CertPairData:

        # create a key pair
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, self._length)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = self._country
        cert.get_subject().ST = self._state
        cert.get_subject().L = self._city
        cert.get_subject().O = self._company
        cert.get_subject().OU = self._organization
        cert.get_subject().CN = self._hostname
        cert.set_serial_number(self._serial)
        cert.gmtime_adj_notBefore(self._valid_begin)
        cert.gmtime_adj_notAfter(self._valid_end)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(key, self._digest)

        return CertPairData(
            key=crypto.dump_privatekey(crypto.FILETYPE_PEM, key),
            cert=crypto.dump_publickey(crypto.FILETYPE_PEM, cert)
        )

    def write(self, private_path: str, public_path: str):
        """
        Create a new self-signed key pair, overwrite if ones already exist.
        """
        pair = self.generate()

        with open(private_path, "wb") as fp:
            fp.write(pair.key)
            self.log.debug(f'PRIVATE KEY CREATED:\n{pair.key.decode()}')

        # Write the public and private key to disk
        with open(public_path, "wb") as fp:
            fp.write(pair.cert)
            self.log.debug(f'CERTIFICATE CREATED:\n{pair.cert.decode()}')


class KeyPair:
    def __init__(self):
        self._length = 4096

    def options(self, length=4096):
        self._length = length

    def generate(self):
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        return KeyPairData(
            private = crypto.dump_privatekey(crypto.FILETYPE_PEM, key),
            public = crypto.dump_publickey(crypto.FILETYPE_PEM, key)
        )