# coding: utf-8

class AbacaChatError(Exception):
    def __init__(self, error_code):
            super(AbacaChatError, self).__init__()
            self.error_code = error_code

class NickError(AbacaChatError):
    pass

class MessageError(AbacaChatError):
    pass

