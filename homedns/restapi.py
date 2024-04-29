from twisted.names.dns import Record_A
from twisted.internet import threads

from klein import Klein
import json
from twisted.web.http import Request
from twisted.web.error import Error
from twisted.web._responses import BAD_REQUEST
from twisted.logger import Logger

from homedns.store import IRecordStorage

# headers = { 'Authorization' : 'Basic %s' % base64.b64encode("username:password") }


class DNSRestApi:
    app = Klein()

    def __init__(self, store: IRecordStorage):
        self.store = store
        self.log = Logger(self.__class__.__name__)

    @app.route('/')
    def home(self, request: Request):
        return request.getClientAddress()

    @app.route('/create/a', methods=['PUT'])
    async def create_a_record(self, request: Request):
        payload = request.content.read().decode()
        self.log.debug('received payload: {json}', json=payload)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise Error(BAD_REQUEST, f'Bad JSON Body {e}'.encode(), str(e).encode())
        try:
            hostname = data['name']
            address = data['address']
            replace = data['replace']
            ttl = data['ttl']
        except KeyError as e:
            raise Error(BAD_REQUEST, f'Missing field in payload: {e.args[0]}'.encode())

        record = Record_A(address=address, ttl=ttl)
        if replace:
            await threads.deferToThread(self.store.replace_record, record=record, fqdn=hostname)
        else:
            await threads.deferToThread(self.store.create_record, record=record, fqdn=hostname)

        await threads.deferToThread(self.store.log_table)

        request.setResponseCode(200)
        return 'OK'