from dataclasses import asdict

from twisted.names import dns
from twisted.names.dns import Record_A
from twisted.internet import threads

from klein import Klein
import json
from twisted.web.http import Request
from twisted.web.error import Error
from twisted.web._responses import BAD_REQUEST, OK
from twisted.logger import Logger

from homedns.store import IRecordStorage, HostnameAndRecord


# headers = { 'Authorization' : 'Basic %s' % base64.b64encode("username:password") }


class DNSRestApi:
    app = Klein()

    def __init__(self, store: IRecordStorage, default_ttl=300):
        self.store = store
        self.log = Logger(self.__class__.__name__)
        self._ttl = default_ttl

    @app.route('/ip4', methods=['GET'])
    def home(self, request: Request):
        request.setHeader(b'Content-Type', b'application/text')
        return request.getClientAddress()

    @app.route('/create/a', methods=['POST'])
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
            ttl = data.get('ttl', self._ttl)
        except KeyError as e:
            raise Error(BAD_REQUEST, f'Missing field in payload: {e.args[0]}'.encode())

        record = Record_A(address=address, ttl=ttl)
        await threads.deferToThread(self.store.create_record, record=record, fqdn=hostname)
        request.setResponseCode(OK)
        return {'ok': True}

    @app.route('/a/hostname/<hostname>', methods=['POST'])
    async def get_a_by_hostname(self, request: Request, hostname: bytes):
        hostname = hostname.decode()

        result: list[HostnameAndRecord] = await threads.deferToThread(self.store.get_record_by_hostname, fqdn=hostname, record_type=dns.A)
        data = []
        for r in result:
            data.append({'hostname': r.hostname, 'address': r.record.address, 'modified': r.modified})

        return json.dumps(data)