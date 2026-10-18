"""Finite PM3 wire transcript; no substring matching or repeated last reply."""
from collections import deque
import threading


class Transcript:
    def __init__(self, steps):
        self.steps = deque(steps)
        self.pending = b''
        self.commands = []
        self.violations = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.blocked = False
        self.connections = []

    def connect(self, address):
        self.connections.append(address)
        if address != ('127.0.0.1', 8888):
            self.reject('Unexpected transport endpoint: ' + repr(address))

    def reject(self, message):
        self.violations.append(message)
        raise AssertionError(message)

    def settimeout(self, value):
        pass

    def sendall(self, data):
        self.commands.append(data.decode('utf-8'))
        if self.pending:
            self.reject('New command before the previous response was consumed')
        if not self.steps:
            self.reject('Unexpected command after transcript exhaustion: ' + repr(data))
        step = self.steps.popleft()
        expected = ('Nikola.D.CMD = ' + step['command'] + '\n').encode()
        if data != expected:
            self.reject('Expected %r, received %r' % (expected, data))
        self.pending = step['response'].encode('utf-8')
        self.blocked = step.get('blocked', False)

    def recv(self, size):
        if self.blocked:
            self.entered.set()
            if not self.release.wait(5):
                self.reject('Test did not release the in-flight hardware response')
            self.blocked = False
        if not self.pending:
            self.reject('Read beyond the scripted response')
        result, self.pending = self.pending[:size], self.pending[size:]
        return result

    def close(self):
        pass

    def verify(self):
        assert not self.violations, self.violations
        assert not self.steps, 'Expected commands were not sent: ' + repr(list(self.steps))
        assert not self.pending, 'The final response was not consumed'
