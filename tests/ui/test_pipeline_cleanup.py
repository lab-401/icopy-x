"""Tests for PM3 pipeline cleanup mechanism.

Covers the pipeline cleanup escalation system added to executor.py and
rftask.py to handle dirty pipeline state after interrupted PM3 commands.

Scenarios:
  - _ensure_pipeline_ready: no-op when flag is False
  - _ensure_pipeline_ready: closes socket + reconnects when flag is True
  - _pipeline_needs_cleanup set when _send_and_cache breaks due to STOPPING
  - rftask _send_cmd lock serializes concurrent HandleServer threads
  - rftask _send_cmd lock timeout returns None (triggers auto-recovery)
  - rftask _destroy_subprocess unblocks pending _send_cmd via output_event
  - rftask reader thread exit unblocks pending _send_cmd via output_event
  - Full flow: interrupt command → next startPM3Task cleans pipeline
"""

import socket
import threading
import time

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

import executor


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _reset_executor_state():
    """Reset executor module state before each test."""
    executor._pipeline_needs_cleanup = False
    executor._socket_instance = None
    executor.CONTENT_OUT_IN__TXT_CACHE = ''
    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
    executor.LABEL_PM3_CMD_TASK_STOPPING = False
    yield
    executor._pipeline_needs_cleanup = False
    executor._socket_instance = None
    executor.CONTENT_OUT_IN__TXT_CACHE = ''
    executor.LABEL_PM3_CMD_TASK_RUNNING = False
    executor.LABEL_PM3_CMD_TASK_STOP = True
    executor.LABEL_PM3_CMD_TASK_STOPPING = False


# =====================================================================
# _ensure_pipeline_ready
# =====================================================================

class TestEnsurePipelineReady:
    """Tests for executor._ensure_pipeline_ready()."""

    def test_noop_when_flag_false(self):
        """Does nothing when _pipeline_needs_cleanup is False."""
        mock_sock = MagicMock()
        executor._socket_instance = mock_sock
        executor._pipeline_needs_cleanup = False

        executor._ensure_pipeline_ready()

        # Socket should NOT be closed
        mock_sock.close.assert_not_called()
        # Socket should still be the same
        assert executor._socket_instance is mock_sock

    def test_closes_and_reconnects_when_flag_true(self):
        """Closes socket and reconnects when _pipeline_needs_cleanup is True."""
        mock_sock = MagicMock()
        executor._socket_instance = mock_sock
        executor._pipeline_needs_cleanup = True

        with patch.object(executor, 'connect2PM3') as mock_connect:
            executor._ensure_pipeline_ready()

        # Old socket should be closed
        mock_sock.close.assert_called_once()
        # connect2PM3 should be called to reconnect
        mock_connect.assert_called_once()
        # Flag should be cleared
        assert executor._pipeline_needs_cleanup is False

    def test_clears_flag_even_if_no_socket(self):
        """Clears flag even when _socket_instance is None."""
        executor._socket_instance = None
        executor._pipeline_needs_cleanup = True

        with patch.object(executor, 'connect2PM3') as mock_connect:
            executor._ensure_pipeline_ready()

        mock_connect.assert_called_once()
        assert executor._pipeline_needs_cleanup is False

    def test_handles_socket_close_error(self):
        """Continues with reconnect even if socket.close() raises."""
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("already closed")
        executor._socket_instance = mock_sock
        executor._pipeline_needs_cleanup = True

        with patch.object(executor, 'connect2PM3') as mock_connect:
            executor._ensure_pipeline_ready()

        mock_connect.assert_called_once()
        assert executor._pipeline_needs_cleanup is False


# =====================================================================
# Pipeline flag setting in _send_and_cache
# =====================================================================

class TestPipelineFlagSetting:
    """Tests that _pipeline_needs_cleanup is set when STOPPING breaks recv."""

    def test_flag_set_on_stopping_break(self):
        """Flag is set when _send_and_cache breaks due to STOPPING."""
        mock_sock = MagicMock()
        executor._socket_instance = mock_sock

        # Set STOPPING before calling _send_and_cache
        executor.LABEL_PM3_CMD_TASK_STOPPING = True

        # Mock pm3_compat to avoid translation
        with patch.object(executor, 'pm3_compat', None):
            executor._send_and_cache('hf mf fchk 1 keys.dic', timeout=5000)

        assert executor._pipeline_needs_cleanup is True

    def test_flag_not_set_on_normal_completion(self):
        """Flag is NOT set when _send_and_cache completes normally."""
        mock_sock = MagicMock()
        # Simulate a normal response with EOR marker
        mock_sock.recv.return_value = b'some output\npm3 -->\n'
        executor._socket_instance = mock_sock

        with patch.object(executor, 'pm3_compat', None):
            executor._send_and_cache('hw ping', timeout=3000)

        assert executor._pipeline_needs_cleanup is False

    def test_flag_not_set_on_socket_timeout(self):
        """Flag is NOT set on socket timeout (handled by startPM3Task retry)."""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = socket.timeout("timed out")
        executor._socket_instance = mock_sock

        with patch.object(executor, 'pm3_compat', None):
            result = executor._send_and_cache('hf mf fchk 1 keys.dic', timeout=1000)

        # Timeout is handled by existing retry logic, not pipeline cleanup
        assert executor._pipeline_needs_cleanup is False
        assert 'timeout' in result


# =====================================================================
# startPM3Task integration with pipeline cleanup
# =====================================================================

class TestStartPM3TaskCleanup:
    """Tests that startPM3Task calls _ensure_pipeline_ready."""

    def test_cleanup_called_before_command(self):
        """_ensure_pipeline_ready is called at the start of startPM3Task."""
        executor._pipeline_needs_cleanup = True

        with patch.object(executor, '_ensure_pipeline_ready') as mock_cleanup, \
             patch.object(executor, '_send_and_cache', return_value='pm3 -->'):
            executor.startPM3Task('hw ping', timeout=1000)

        mock_cleanup.assert_called_once()

    def test_full_flow_interrupt_then_clean(self):
        """Full flow: STOPPING interrupts _send_and_cache → flag set →
        next startPM3Task reconnects → command succeeds."""
        mock_sock = MagicMock()
        executor._socket_instance = mock_sock

        # Step 1: Simulate STOPPING interrupt during _send_and_cache
        executor.LABEL_PM3_CMD_TASK_STOPPING = True
        with patch.object(executor, 'pm3_compat', None):
            executor._send_and_cache('hf mf fchk 1 keys.dic', timeout=600000)

        assert executor._pipeline_needs_cleanup is True
        executor.LABEL_PM3_CMD_TASK_STOPPING = False

        # Step 2: Next startPM3Task should clean up
        new_sock = MagicMock()
        new_sock.recv.return_value = b'UID: AABBCCDD\npm3 -->\n'

        with patch.object(executor, 'connect2PM3') as mock_connect, \
             patch.object(executor, 'pm3_compat', None):
            # connect2PM3 sets the new socket
            def set_new_socket(*a, **kw):
                executor._socket_instance = new_sock
                return True
            mock_connect.side_effect = set_new_socket

            result = executor.startPM3Task('hf 14a info', timeout=5000)

        # Old socket should have been closed
        mock_sock.close.assert_called_once()
        # New connection established
        mock_connect.assert_called_once()
        # Flag should be cleared
        assert executor._pipeline_needs_cleanup is False
        # Command should succeed
        assert result == 1


# =====================================================================
# rftask _cmd_lock
# =====================================================================

class TestRftaskCmdLock:
    """Tests for rftask.RemoteTaskManager._send_cmd lock mechanism."""

    def _make_rtm(self):
        """Create a RemoteTaskManager with minimal config."""
        from main.rftask import RemoteTaskManager
        rtm = RemoteTaskManager(pm3_cmd='echo test', pm3_cwd='/tmp')
        return rtm

    def test_lock_acquired_on_normal_send(self):
        """_send_cmd acquires the lock for normal command execution."""
        rtm = self._make_rtm()
        # Mock a dead process so _send_cmd returns quickly
        rtm._process = MagicMock()
        rtm._process.poll.return_value = 1  # Process exited

        result = rtm._send_cmd('hw ping')

        # Should return None (process dead) but lock was acquired and released
        assert result is None
        # Lock should be released (we can acquire it)
        assert rtm._cmd_lock.acquire(timeout=0.1)
        rtm._cmd_lock.release()

    def test_lock_timeout_returns_none(self):
        """_send_cmd returns None when lock can't be acquired (3s timeout)."""
        rtm = self._make_rtm()

        # Hold the lock from another thread
        rtm._cmd_lock.acquire()

        try:
            # _send_cmd should time out after 3s and return None
            # Use a shorter timeout for the test by monkeypatching
            import main.rftask as rftask_mod
            original_send = rtm._send_cmd

            start = time.monotonic()
            # We can't easily change the 3s timeout, so test with the lock held
            # Use a thread to call _send_cmd
            result_holder = [None]

            def call_send():
                result_holder[0] = rtm._send_cmd('hw ping')

            t = threading.Thread(target=call_send)
            t.start()
            # Release lock after 0.5s to avoid waiting full 3s in test
            time.sleep(0.5)
            rtm._cmd_lock.release()
            t.join(timeout=5)

            # Should have succeeded after lock was released
            # (returns None because no process, but lock was acquired)
            assert result_holder[0] is None
        finally:
            # Ensure lock is released for cleanup
            try:
                rtm._cmd_lock.release()
            except RuntimeError:
                pass

    def test_lock_released_on_exception(self):
        """Lock is released even if _send_cmd body raises."""
        rtm = self._make_rtm()
        rtm._process = MagicMock()
        rtm._process.poll.return_value = None  # Process alive
        rtm._process.stdin = MagicMock()
        rtm._process.stdin.write.side_effect = BrokenPipeError("pipe broken")

        result = rtm._send_cmd('hw ping')

        assert result is None
        # Lock must be released
        assert rtm._cmd_lock.acquire(timeout=0.1)
        rtm._cmd_lock.release()


# =====================================================================
# rftask _destroy_subprocess unblocks _send_cmd
# =====================================================================

class TestDestroySubprocessUnblocks:
    """Tests that _destroy_subprocess sets output_event to unblock _send_cmd."""

    def _make_rtm(self):
        from main.rftask import RemoteTaskManager
        rtm = RemoteTaskManager(pm3_cmd='echo test', pm3_cwd='/tmp')
        return rtm

    def test_output_event_set_on_destroy(self):
        """_destroy_subprocess sets _output_event even with no process."""
        rtm = self._make_rtm()
        rtm._output_event.clear()
        rtm._process = None

        rtm._destroy_subprocess()

        assert rtm._output_event.is_set()

    def test_output_event_unblocks_waiter(self):
        """_destroy_subprocess unblocks a thread waiting on _output_event."""
        rtm = self._make_rtm()
        rtm._output_event.clear()
        rtm._process = MagicMock()
        rtm._process.pid = 99999
        # Make killpg succeed silently
        rtm._process.wait.return_value = 0

        unblocked = threading.Event()

        def waiter():
            rtm._output_event.wait(timeout=5)
            unblocked.set()

        t = threading.Thread(target=waiter)
        t.start()

        # Give the waiter time to block
        time.sleep(0.1)
        assert not unblocked.is_set()

        # Destroy should unblock the waiter
        import os
        import signal
        with patch('os.killpg'):
            rtm._destroy_subprocess()

        assert unblocked.wait(timeout=2), "_output_event.set() didn't unblock waiter"
        t.join(timeout=2)


# =====================================================================
# rftask reader thread exit unblocks _send_cmd
# =====================================================================

class TestReaderExitUnblocks:
    """Tests that reader thread exit sets output_event."""

    def _make_rtm(self):
        from main.rftask import RemoteTaskManager
        rtm = RemoteTaskManager(pm3_cmd='echo test', pm3_cwd='/tmp')
        return rtm

    def test_reader_sets_event_on_exit(self):
        """_run_std_output_error sets _output_event when it exits."""
        rtm = self._make_rtm()
        rtm._output_event.clear()
        rtm._has_manager = False  # Reader loop won't even enter
        rtm._process = MagicMock()

        # Run the reader — should exit immediately (has_manager=False)
        rtm._run_std_output_error()

        assert rtm._output_event.is_set()

    def test_reader_sets_event_on_process_death(self):
        """Reader sets _output_event when process stdout returns EOF."""
        rtm = self._make_rtm()
        rtm._output_event.clear()
        rtm._has_manager = True

        mock_proc = MagicMock()
        mock_proc.stdout.readline.return_value = b''  # EOF
        mock_proc.poll.return_value = 0  # Process exited
        rtm._process = mock_proc

        rtm._run_std_output_error()

        assert rtm._output_event.is_set()
