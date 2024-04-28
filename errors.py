import json

from twisted.web import resource
from unicodedata import normalize
from twisted.logger import Logger

log = Logger('errors')

ACCEPT_HEADER = b'application/json'
CONTENT_TYPE_HEADER = b'application/json; charset=UTF-8'


class JsonErrorPage(resource.ErrorPage):
    """
    A custom version of ``twisted.web.resource.ErrorPage``

    Returns valid json documents instead of html, and checks for
    ``request.debug`` ... if present the ``detail`` argument is
    shown to the client.  The detail argument should contain
    private information like exceptions

    **Use Cases**

    Call Format::

        ErrorPage(http_code, generic_message, detail_message)

    :Note: You should never share any information in the middle-argument that would
           alert someone that Python is being used as the backend, or that might leak any
           exception information, even the exception type.  The string sent should always
           be generic or ambigious to some level.

           The last argument *debug_message* can be specified in every situation. This
           class intenlligently decides when to actually return it to the client based on
           if ``request.site.displayTracebacks`` is True.

    When using error page from an Exception::

        import traceback
        try:
            raise RuntimeError('Something Went Wrong')
        except Exception:
            ErrorPage(500, "Server Error", traceback.format_exc())

    OR if the traceback isn't important, because its an expected error,
    you might just want to show the exception message::

        try:
            raise UnicodeDecodeError('`email` field invalid utf-8')
        except Exception as e:
            ErrorPage(500, "utf-8 Decoding Error", str(e))

    """

    def __init__(self, status, brief, detail, encoding='utf-8', is_logged=True):
        """
        Note that the signature of this function and the names of the variables have been
        kept identical to the original version of this class.

        detail is conditionally shown

        :param status: Http Status Code
        :param brief: Error Type
        :param detail: Error Description
        :param encoding: Encoding to use when sending response
        :param is_logged: log the error to twisted logging mechanism.
        """
        # arguments are left identical to ErrorPage
        resource.Resource.__init__(self)

        self.code = status
        self.brief = brief
        self.detail = detail
        self.encoding = encoding
        self.is_logged = is_logged

    def render(self, request):
        """
        Format the exception and return a dictionary.
        """
        response = {
            "code": self.code,
            "error": self.brief.encode(self.encoding),
            "detail": self.detail.encode(self.encoding),
        }

        if not request.site.displayTracebacks:
            response['detail'] = None

        if self.is_logged:
            # ensure strings get represented in the logs even with nonsense in them
            # (un-encodable strings get saved still)
            brief = normalize('NFKD', self.brief).encode('ASCII', 'ignore')
            detail = normalize('NFKD', self.detail).encode('ASCII', 'ignore')

            # ErrorPage: [500] Invalid Name - Expected int,
            log.warn(f'{self.__class__.__name__}: [{self.code}] {brief} - {detail}')

        request.setResponseCode(self.code)
        request.setHeader(b'accept', ACCEPT_HEADER)
        request.setHeader(b'content-type', CONTENT_TYPE_HEADER % self.encoding)
        # dump a dict to get correctly formatted json
        rstr = json.dumps(
            response,
            allow_nan=False,
            check_circular=False,
            ensure_ascii=False,
            encoding=self.encoding,
            # -- pretty-print --
            sort_keys=True,
            indent=4)
        return rstr

    def __str__(self):
        return f'{self.__class__.__name__}: [{self.code}] {self.brief} - {self.detail}'
