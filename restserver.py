from twisted.names.dns import Record_A
from twisted.web import server, resource
from twisted.internet import reactor, defer, threads
from pprint import pprint
import base64
import klein

from klein import Klein
import json
from twisted.internet import defer
from twisted.web.http import Request
from twisted.web.error import Error
from twisted.web._responses import BAD_REQUEST
from twisted.logger import Logger

from homedns.store import IRecordStorage


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




'''
from klein import Klein
from twisted.web import http, server
from twisted.internet import reactor


#----- Subclasses -----#
class KleinHTTPRequest(server.Request):
    """ Request subclass """

    def getter(self, key, default=None):
        # ...

    def getOne(self, key, default=None):
        # ...

    def getOneCast(self, key, cast, default=None, decoding=None):
       # ...

class KleinSite(server.Site):
    """ Site subclass """

    def buildProtocol(self, addr):
        channel = http.HTTPFactory.buildProtocol(self, addr)
        channel.requestFactory = KleinHTTPRequest            # produce subclassed Request
        channel.site = self
        return channel


#----- Routes -----#
app = Klein()

@app.route('/hello', methods=['POST'])
def home(request):
    return b'hello ' + request.getOne('name', 'world')


#----- Start server -----#
reactor.listenTCP(8000, KleinSite(app.resource()), interface='localhost')
reactor.run()
'''



"""
from klein import Klein

class NotFound(Exception):
    pass


class ItemStore:
    app = Klein()

    @app.handle_errors(NotFound)
    def notfound(self, request, failure):
        request.setResponseCode(404)
        return 'Not found, I say'

    @app.route('/droid/<string:name>')
    def droid(self, request, name):
        if name in ['R2D2', 'C3P0']:
            raise NotFound()
        return 'Droid found'

    @app.route('/bounty/<string:target>')
    def bounty(self, request, target):
        if target == 'Han Solo':
            return '150,000'
        raise NotFound()


if __name__ == '__main__':
    store = ItemStore()
    store.app.run('localhost', 8080)
"""