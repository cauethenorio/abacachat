# coding: utf-8

from datetime import datetime
import json
import sys
import uuid

from gevent import monkey
monkey.patch_all()

import gevent
from gevent import pywsgi
from gevent.local import local

from geventwebsocket.handler import WebSocketHandler
from geventwebsocket import WebSocketError

import errors
from admin import AdminMixin

from router import EventRouter


class AbacaChat(AdminMixin):

    BROADCAST_USERS_COUNT_INTERVAL = 10
    ANNOUNCE_ENTERS_AND_LEAVES = True

    MAX_MESSAGE_LEN = 256
    MAX_NICK_LEN = 32

    FLOOD_CONTROL = {
        'messages': 3,
        'delta_secs': 10,
        'cooldown': 10,
    }

    router = EventRouter()

    def __init__(self):
        self.locals = local()
        self._clients = []
        self._muted_clients = []
        self.broadcast_users_count(self.BROADCAST_USERS_COUNT_INTERVAL)


    @staticmethod
    def generate_id():
        return str(uuid.uuid4())

    def broadcast_users_count(self, interval_secs=10):

        def send_users_count():
            last_sent_count = None

            while True:
                users_count = len(self._clients)
                if last_sent_count != users_count:
                    self.broadcast('info', 'users_count', users_count)
                    last_sent_count = users_count

                gevent.sleep(seconds=interval_secs)

        if interval_secs:
            gevent.Greenlet.spawn(send_users_count)

    def broadcast(self, _type, name, content, _id=None, filter_fn=None):
        _id = _id or self.generate_id()

        for client in list(self._clients):
            if not filter_fn or filter_fn(client):
                self.send(_type, name, content, _id, ws=client['ws'])

    def remove_client(self):
        self._clients.remove(self.locals.user)

        if (self.ANNOUNCE_ENTERS_AND_LEAVES
                and self.locals.user['data'].get('nick')):

            self.broadcast('info', 'client_exited', {
                'sender': self.locals.user['data'],
                'id': self.generate_id(),
            })

        del self.locals.user

    def event_routing(self, ws, json_event):
        if ws.closed:
            return

        try:
            event = json.loads(json_event)
        except (ValueError, TypeError):
            self.send('error', 'malformed_json_container', json_event)
        else:

            if event.get('id'):
                if self.has_permission(event):
                    handle_func = self.router.route(event.get('name'))
                    handle_func(self,
                                event.get('name'),
                                event.get('id'),
                                event.get('content'))

            else:
                self.send('error', 'missing_id', event)


    def wsgi_app(self, environ, start_response):
        ws = environ.get('wsgi.websocket')

        if not ws:
            start_response("400 Bad Request", [])
            return ["Expected WebSocket request."]

        self.handle_connection(ws)

    def serve(self, host='127.0.0.1', port=8000):
        server = pywsgi.WSGIServer((host, port), self.wsgi_app,
                                   handler_class=WebSocketHandler)

        print('Serving {} on {}:{}...'.format(sys.argv[0], host, port))
        server.serve_forever()

    def handle_connection(self, ws):
        self.locals.user = {
            'start_ts': datetime.now(),
            'ws': ws,
            'data': {'id': self.generate_id()},
            'last_msgs_ts': [],
        }

        self._clients.append(self.locals.user)
        self.send('info', 'users_count', len(self._clients))

        while not ws.closed:
            self.event_routing(ws, ws.receive())

        self.remove_client()

    def send_error_response(self, code, _id, content):
        return self.send('response', 'error', {
            'code': code,
            'content': content,
        }, replying=_id)

    def send_success_response(self, _id, content):
        self.send('response', 'success', {'content': content}, replying=_id)

    @router.set_catch_all
    def handle_unknown_events(self, name, _id, content):
        self.send_error_response('unregistered_event', _id, {
            'content': content,
            'name': name
        })

    @router.register('new_message')
    def handle_new_messages(self, name, _id, content):

        try:
            self.validate_message(content)

        except errors.MessageError as e:
            self.send_error_response(e.error_code, _id, content)

        else:
            self.send_success_response(_id, content)
            self.broadcast('event', 'new_message', {
                'message': content,
                'sender': self.locals.user['data'],
                'id': self.generate_id(),
            })

    @router.register('login')
    def handle_login(self, name, _id, content):
        nick = content.get('nick')

        try:
            self.validate_nick(nick)
            self.authenticate(content)

            self.locals.user['data']['nick'] = nick
            self.send_success_response(_id, content)

        except errors.NickError as e:
            self.send_error_response(e.error_code, _id, content)

        else:
            if self.ANNOUNCE_ENTERS_AND_LEAVES:
                self.broadcast('info', 'client_entered', {
                    'sender': self.locals.user['data'],
                    'id': self.generate_id(),
                })

    def authenticate(self, content):
        """
        Check if current user is admin
        """
        if content.get('nick') == 'admin':
            self.set_admin()

        return True

    def nick_is_free(self, nick):
        for client in self._clients:
            if nick == client.get('data', {}).get('nick'):
                return False
        return True

    def validate_in_cooldown(self):
        """
        Check if the current user is in a flood cooldown period
        """

        cooldown_time = self.FLOOD_CONTROL.get('cooldown')
        cooldown_ts = self.locals.user.get('cooldown_ts')

        if not cooldown_ts or not cooldown_time:
            return False

        if (datetime.now() - cooldown_ts).total_seconds() > cooldown_time:
            # cooldown is over
            del self.locals.user['cooldown_ts']
            return False

        return True

    def validate_is_flooding(self):
        limits = self.FLOOD_CONTROL
        now = datetime.now()

        # there is no config to control floods
        if not limits.get('messages') or not limits.get('delta_secs'):
            return False

        def within_delta(ts):
            return (now - ts).total_seconds() < limits['delta_secs']

        msgs = [ts for ts in self.locals.user['last_msgs_ts']
                if within_delta(ts)]

        if len(msgs) + 1 > limits['messages']:
            self.locals.user['cooldown_ts'] = now
            self.send('info', 'cooldown_start', {
                'interval': self.FLOOD_CONTROL.get('cooldown')
            })
            return True

        msgs.append(now)
        self.locals.user['last_msgs_ts'] = msgs
        return False

    def validate_message(self, message):

        if not self.locals.user['data'].get('nick'):
            raise errors.MessageError('not_logged')

        if not message:
            raise errors.MessageError('empty_message')

        if len(message) > self.MAX_MESSAGE_LEN:
            raise errors.MessageError('message_length_too_long')

        if (not self.locals.user['data'].get('is_admin')
                and (self.validate_in_cooldown()
                     or self.validate_is_flooding())):
            raise errors.MessageError('too_many_msgs_in_short_time')

    def validate_nick(self, nick):

        if self.locals.user['data'].get('nick'):
            raise errors.NickError('nick_already_set')

        if not nick:
            raise errors.NickError('empty_nick')

        if not self.nick_is_free(nick):
            raise errors.NickError('nick_already_chosen')

        if len(nick) > self.MAX_NICK_LEN:
            raise errors.NickError('nick_length_too_long')

        if len(nick) < getattr(self, 'MIN_NICK_LEN', 0):
            raise errors.NickError('nick_length_too_short')

    def send(self, typ, name, content, _id=None, ws=None, replying=None):
        payload = {
            'id': _id or self.generate_id(),
            'type': typ,
            'name': name,
            'content': content
        }

        if replying:
            payload['replying'] = replying

        try:
            (ws or self.locals.user['ws']).send(json.dumps(payload))
        except WebSocketError:
            pass
