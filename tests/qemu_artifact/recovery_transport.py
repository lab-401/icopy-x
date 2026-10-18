"""Explicit synthetic timeout/EOF faults at the executor's socket boundary.

This does not run the daemon or model RF timing. Real daemon/TCP integration
is covered by tests/ui/test_pm3_transport_recovery.py. Only these fault cases
shorten LF timeouts; normal acceptance cases retain production deadlines.
"""
import socket
import threading
import time

from strict_transport import Transcript


class RecoveryTranscript(Transcript):
    def __init__(self, steps):
        super().__init__(steps)
        self.timeout = 1
        self.ready_at = 0
        self.truncated = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, data):
        if not self.steps:
            self.reject('Unexpected command after recovery transcript exhaustion')
        step = self.steps[0]
        if 'control' in step:
            self.commands.append(data.decode())
            expected = ('Nikola.D.CTL = ' + step['control'] + '\n').encode()
            if self.pending or data != expected:
                self.reject('Expected recovery request %r, received %r' % (expected, data))
            self.steps.popleft()
            self.pending = step['response'].encode()
        else:
            super().sendall(data)
        self.ready_at = time.monotonic() + step.get('delay', 0)
        self.truncated = step.get('truncated', False)

    def recv(self, size):
        if time.monotonic() < self.ready_at:
            threading.Event().wait(min(self.timeout, self.ready_at - time.monotonic()))
            if time.monotonic() < self.ready_at:
                raise socket.timeout()
        if not self.pending and self.truncated:
            return b''  # peer closes after a useful-looking, incomplete body
        return super().recv(size)

    def close(self):
        if self.pending:
            self.reject('Socket closed before consuming its late response')
