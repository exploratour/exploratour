import threading

class IdAllocator(object):
    def __init__(self):
        self.cond = threading.Condition()
        self.nextid = 1

    def get(self):
        self.cond.acquire()
        try:
            ret = self.nextid
            self.nextid += 1
            return ret;
        finally:
            self.cond.release()

g_allocator = IdAllocator()

class ImportContext(object):
    id = None
    error = None

    def set_error(self, msg):
        self.error = msg
        return self

    def setup(self, **kwargs):
        self.id = g_allocator.get()
        for k, v in kwargs.iteritems():
            setattr(self, k, v)
