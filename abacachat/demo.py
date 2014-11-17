# coding: utf-8

from os import path

from gevent import monkey; monkey.patch_all()

import bottle
from geventwebsocket.handler import WebSocketHandler

from chat import AbacaChat


class AbacaChatDemo(AbacaChat):

    def __init__(self, *args, **kwargs):
        self._debug = kwargs.pop('debug')
        super(AbacaChatDemo, self).__init__(*args, **kwargs)

        self._app = bottle.Bottle()
        self._route()

    def run(self, host='127.0.0.1', port=8000):
        bottle.debug(self._debug)
        bottle.run(host=host,
                   reloader=self._debug,
                   port=int(port),
                   server='gevent',
                   app=self._app,
                   handler_class=WebSocketHandler)

    def _route(self):
        self._app.mount('/chat-ws', self.wsgi_app)
        self._app.route('/<filename:path>', callback=self._send_html)

    @classmethod
    def _send_html(cls, filename):
        return bottle.static_file(
            filename,
            root=path.join(path.dirname(__file__), 'static'),
            mimetype='text/html')

if __name__ == '__main__':

    chat = AbacaChatDemo(debug=True)
    chat.run()
