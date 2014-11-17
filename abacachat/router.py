# coding: utf-8

from functools import wraps


class EventRouter(object):

    map = {}

    def register(self, ev_arg):
        def wrap(func):
            events = [ev_arg] if isinstance(ev_arg, basestring) else ev_arg
            for event in events:
                self.map[event] = func

            return func
        return wrap

    def set_catch_all(self, func):
        self.catch_all_func = func

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    def route(self, event_name):
        return self.map.get(event_name, self.catch_all_func)

