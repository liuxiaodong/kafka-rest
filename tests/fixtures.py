import types
from collections import defaultdict, namedtuple
from uuid import uuid4

from mock import Mock, patch

from kafka_rest.client import KafkaRESTClient

class Callback(namedtuple('Callback', ['fn', 'args', 'kwargs'])):
    def run(self):
        return self.fn(*self.args, **self.kwargs)

class Later(namedtuple('Later', ['handle', 'seconds', 'callback'])):
    pass

def _mock_emitter(obj, event, *args, **kwargs):
    obj.event_mocks[event](*args, **kwargs)

class MockClient(KafkaRESTClient):
    @classmethod
    def with_basic_setup(cls):
        instance = cls(None, None, shutdown_timeout_seconds=0)
        instance.event_mocks = defaultdict(lambda: Mock())
        instance.registrar.emit = types.MethodType(_mock_emitter, instance)
        return instance

    def install_mock_io_loop(self):
        self.io_loop.stop()
        self.io_loop = TestingIOLoop()

        self.io_loop_patch = patch('kafka_rest.producer.IOLoop.current')
        self.io_loop_mock = self.io_loop_patch.start()
        self.io_loop_mock.return_value = self.io_loop

    def teardown_mock_io_loop(self):
        self.io_loop_patch.stop()

    def reset_mocks(self):
        for mock in self.event_mocks.values():
            mock.reset_mock()

    def mock_for(self, event):
        return self.event_mocks[event]

class TestingIOLoop(object):
    def __init__(self):
        self.callbacks = []
        self.later = []

    def add_callback(self, cb, *args, **kwargs):
        self.callbacks.append(Callback(cb, args, kwargs))

    def call_later(self, seconds, cb, *args, **kwargs):
        handle = uuid4()
        self.later.append(Later(handle, seconds, Callback(cb, args, kwargs)))
        return handle

    def remove_timeout(self, handle):
        self.later = filter(lambda later: later.handle != handle, self.later)

    @property
    def next_callback(self):
        if self.callbacks:
            return self.callbacks[0]

    @property
    def next_later(self):
        if self.later:
            return self.later[0]

    def run_next(self):
        if self.callbacks:
            self.callbacks[0].run()

    @property
    def finished(self):
        return not bool(self.callbacks or self.later)
