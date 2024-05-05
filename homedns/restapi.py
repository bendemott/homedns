from dataclasses import asdict
import sys
from ipaddress import IPv4Address

from twisted.names import dns
from twisted.names.dns import Record_A
from twisted.internet import threads

from klein import Klein
import json
from twisted.web.http import Request
from twisted.web.error import Error
from twisted.web._responses import BAD_REQUEST, OK, CREATED, NOT_FOUND
from twisted.logger import Logger, textFileLogObserver

from homedns.store import IRecordStorage, HostnameAndRecord


# headers = { 'Authorization' : 'Basic %s' % base64.b64encode("username:password") }


class DNSRestApi:
    """
    REST API to update, delete, create DNS Records dynamically without the need for zone files
    """
    app = Klein()

    def __init__(self, store: IRecordStorage, default_ttl=300):
        self.store = store
        self.log = Logger(self.__class__.__name__, observer=textFileLogObserver(sys.stdout))
        self._ttl = default_ttl

    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    @app.route('/ip4', methods=['GET'])
    def ip4_address(self, request: Request):
        request.setHeader(b'Content-Type', b'application/text')
        client_addr = request.getClientAddress()
        return json.dumps({'address': str(client_addr.host)})

    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    @app.route('/upsert/a/<hostname>', methods=['PUT'])
    async def upsert_a_record(self, request: Request, hostname: str):
        request.setHeader(b'Content-Type', b'application/text')

        payload = request.content.read().decode()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise Error(BAD_REQUEST, f'Bad JSON Body {e}'.encode(), str(e).encode())

        try:
            address = data['address']
            ttl = data.get('ttl', self._ttl)
        except KeyError as e:
            raise Error(BAD_REQUEST, f'Missing field in payload: {e.args[0]}'.encode())

        record = Record_A(address=address, ttl=ttl)
        # try to find an existing record
        result: list[HostnameAndRecord] = await threads.deferToThread(self.store.get_record_by_hostname,
                                                                      fqdn=hostname, record_type=dns.A)
        if result:
            mode = 'updated'
            await threads.deferToThread(self.store.update_record, record=record, fqdn=hostname)
            request.setResponseCode(OK)
        else:
            mode = 'created'
            await threads.deferToThread(self.store.create_record, record=record, fqdn=hostname)
            request.setResponseCode(CREATED)

        return json.dumps({'success': True, mode: True}, indent=4).encode()

    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    @app.route('/update/a/<hostname>', methods=['PUT'])
    async def update_a_record(self, request: Request, hostname: str):
        request.setHeader(b'Content-Type', b'application/text')

        payload = request.content.read().decode()
        self.log.debug('received payload: {json}', json=payload)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise Error(BAD_REQUEST, f'Bad JSON Body {e}'.encode(), str(e).encode())

        try:
            address = data['address']
            ttl = data.get('ttl', self._ttl)
        except KeyError as e:
            raise Error(BAD_REQUEST, f'Missing field in payload: {e.args[0]}'.encode())

        record = Record_A(address=address, ttl=ttl)
        await threads.deferToThread(self.store.update_record, record=record, fqdn=hostname)
        request.setResponseCode(201)
        return json.dumps({'success': True}, indent=4)

    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    @app.route('/create/a/<hostname>', methods=['POST'])
    async def create_a_record(self, request: Request, hostname: str):
        request.setHeader(b'Content-Type', b'application/text')
        payload = request.content.read().decode()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise Error(BAD_REQUEST, f'Bad JSON Body {e}'.encode(), str(e).encode())
        try:
            address = data['address']
            ttl = data.get('ttl', self._ttl)
        except KeyError as e:
            raise Error(BAD_REQUEST, f'Missing field in payload: {e.args[0]}'.encode())

        record = Record_A(address=address, ttl=ttl)
        await threads.deferToThread(self.store.create_record, record=record, fqdn=hostname)
        request.setResponseCode(CREATED)
        return json.dumps({'success': True}, indent=4)

    # ////////////////////////////////////////////       GET      //////////////////////////////////////////////////////

    @app.route('/hostname/a/<hostname>', methods=['GET'])
    async def get_a_by_hostname(self, request: Request, hostname: str):
        request.setHeader(b'Content-Type', b'application/text')
        result: list[HostnameAndRecord] = await threads.deferToThread(self.store.get_record_by_hostname,
                                                                      fqdn=hostname, record_type=dns.A)
        data = []
        for r in result:
            data.append({'hostname': r.hostname, 'address': r.record.dottedQuad(), 'modified': r.modified})
        return json.dumps(data, indent=4)

    # ///////////////////////////////////////////     DELETE     ///////////////////////////////////////////////////////

    @app.route('/hostname/a/<hostname>', methods=['DELETE'])
    async def delete_a_by_hostname(self, request: Request, hostname: str):
        request.setHeader(b'Content-Type', b'application/text')
        count: list[HostnameAndRecord] = await threads.deferToThread(self.store.delete_record_by_hostname,
                                                                      fqdn=hostname, record_type=dns.A)
        if not count:
            request.setResponseCode(NOT_FOUND)
        return json.dumps({'deleted': count, 'success': bool(count)}, indent=4)


