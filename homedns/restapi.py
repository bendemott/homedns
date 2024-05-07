from dataclasses import asdict
import sys
from ipaddress import IPv4Address

from twisted.names import dns
from twisted.names.dns import Record_A, Record_CNAME
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

    def __init__(self, store: IRecordStorage, soa_domains: list[str] = None, default_ttl=600):
        self.store = store
        self.log = Logger(self.__class__.__name__, observer=textFileLogObserver(sys.stdout))
        self._ttl = default_ttl
        self._soa_domains = soa_domains or []
        self._soa = {tuple(d.split('.')) for d in soa_domains}

    def is_soa_domain(self, name) -> bool:
        domain = name.split('.')
        if not len(domain) < 2:
            return False

        return tuple(domain[-2:]) in self._soa

    def error_response(self, msg, code, request):
        request.setResponseCode(code)
        return json.dumps({'error': msg, 'ok': False, 'code': code})

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

        if not self.is_soa_domain(hostname):
            return self.error_response(f'Not a soa domain: "{hostname}"', BAD_REQUEST, request)

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

        if not self.is_soa_domain(hostname):
            return self.error_response(f'Not a soa domain: "{hostname}"', BAD_REQUEST, request)

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

        if not self.is_soa_domain(hostname):
            return self.error_response(f'Not a soa domain: "{hostname}"', BAD_REQUEST, request)

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

    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    @app.route('/hostname/cname/<hostname>', methods=['GET'])
    async def get_a_by_hostname(self, request: Request, hostname: str):
        """
        Lookup CNAME record by the domain name.
        The domain name is what the cname is resolved by
        The alias is what the cname points to, another domain
        """
        request.setHeader(b'Content-Type', b'application/text')
        result: list[HostnameAndRecord] = await threads.deferToThread(self.store.get_record_by_hostname,
                                                                      fqdn=hostname, record_type=dns.CNAME)
        data = []
        for r in result:
            data.append({'hostname': r.hostname, 'alias': r.record.name.name.decode(), 'modified': r.modified})
        return json.dumps(data, indent=4)

    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    @app.route('/create/cname/<hostname>', methods=['POST'])
    async def create_cname_record(self, request: Request, hostname: str):
        request.setHeader(b'Content-Type', b'application/text')

        if not self.is_soa_domain(hostname):
            return self.error_response(f'Not a soa domain: "{hostname}"', BAD_REQUEST, request)

        payload = request.content.read().decode()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise Error(BAD_REQUEST, f'Bad JSON Body {e}'.encode(), str(e).encode())
        try:
            alias = data['alias']  # alias is the domain that the name record redirects to
            ttl = data.get('ttl', self._ttl)
        except KeyError as e:
            raise Error(BAD_REQUEST, f'Missing field in payload: {e.args[0]}'.encode())

        record = Record_CNAME(name=alias, ttl=ttl)
        await threads.deferToThread(self.store.create_record, record=record, fqdn=hostname)
        request.setResponseCode(CREATED)
        return json.dumps({'success': True}, indent=4)