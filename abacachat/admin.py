# config: utf-8

from router import EventRouter


class AdminMixin(object):

    router = EventRouter()

    def admin_auth(self, content):
        """
        Check if current user is admin
        """
        if content.get('nick') == 'caue':
            self.set_admin()

    def set_admin(self):
        self.locals.user['is_admin'] = True
        self.send('info', 'you_are_admin', None)

    def has_permission(self, event):
        error_code = None

        if (getattr(self, 'chat_blocked', False)
                and not self.locals.user.get('is_admin')):
            error_code = 'chat_blocked'

        elif self.locals.user['data']['id'] in self._muted_clients:
            error_code = 'you_are_muted'

        if error_code:
            self.send_error_response(error_code,
                                     event.get('id'),
                                     event.get('content'))
            return False

        return True

    def process_admin_event(self,
                            action_func,
                            _id,
                            content,
                            broadcast_event=None,
                            broadcast_filter=None):

        if self.locals.user['is_admin']:
            action_func and action_func(_id, content)
            self.send('response', 'success', content, replying=_id)

            if broadcast_event:
                self.broadcast('event', broadcast_event, {
                    'sender': self.locals.user['data']
                }, filter=broadcast_filter)

        else:
            self.send('response', 'error', {
                'code': 'not_admin',
                'content': content,
            }, replying=_id)

    @router.register('clear_chat')
    def handle_clear_chat_event(self, name, _id, content):
        self.process_admin_event(None, _id, content, broadcast_event='chat_cleared')

    @router.register(['block_chat', 'unblock_chat'])
    def handle_block_events(self, name, _id, content):

        action = {
            'block_chat': [True, 'chat_blocked'],
            'unblock_chat': [False, 'chat_unblocked'],
        }[name]

        def do_action(_id, content):
            self.chat_blocked = action[0]

        self.process_admin_event(do_action, _id, content,
                                 broadcast_event=action[1])

    @router.register(['mute_user', 'unmute_user'])
    def handle_mute_events(self, name, _id, content):
        client_id = content.get('id')

        def mute_user(_id, content):
            if client_id not in self._muted_clients:
                self._muted_clients.append(client_id)

        def unmute_user(_id, content):
            if client_id in self._muted_clients:
                self._muted_clients.remove(client_id)

        def filter_user(user):
            return user.get('data').get('id') == client_id

        broadcast_event = {
            'mute_user': 'muted',
            'unmute_user': 'unmuted',
        }[name]

        action = locals().get(name)

        self.process_admin_event(action, _id, content,
                                 broadcast_event=broadcast_event,
                                 broadcast_filter=filter_user)