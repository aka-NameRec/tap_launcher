"""Daemon process management for tap-launcher.

This module handles PID file management and process control using python-daemon.
"""

import contextlib
import os
import signal
import time
from pathlib import Path

from daemon import DaemonContext
from daemon.pidfile import TimeoutPIDLockFile
from lockfile import AlreadyLocked
from lockfile import LockError

# Path to /dev/null for daemon stdio redirection
_DEV_NULL = '/dev/null'


class DaemonManager:
    """Manage daemon process with PID file and exclusive lock.

    This class handles:
    - Preventing multiple instances via file locking (python-daemon)
    - Writing PID file for process identification
    - Stopping daemon process
    - Automatic lock cleanup on process exit

    Uses python-daemon library for standard PEP 3143 daemonization.
    """

    def __init__(
        self,
        pid_file: Path | None = None,
    ) -> None:
        """Initialize daemon manager.

        Args:
            pid_file: Path to PID file (also used for locking)
        """
        if pid_file is None:
            pid_file = Path.home() / '.local/share/tap-launcher/tap-launcher.pid'
        self.pid_file = pid_file
        self._lock_file: TimeoutPIDLockFile | None = None
        self._daemon_context: DaemonContext | None = None

        # Ensure parent directory exists
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self) -> bool:
        """Probe whether the PID file lock can be acquired.

        Creates a non-blocking probe lock, checks if another instance
        is running, and releases it immediately. This is a check-only
        operation — the actual lock is acquired later by daemonize()
        via DaemonContext.

        Returns:
            bool: True if no other instance is running, False otherwise
        """
        probe = TimeoutPIDLockFile(
            str(self.pid_file),
            timeout=0.0,
        )
        try:
            probe.acquire()
        except (AlreadyLocked, LockError, OSError):
            return False
        else:
            probe.release()
            return True

    def write_pid_file(self) -> None:
        """Write PID to file.

        This is used in foreground mode where PID needs to be written.
        Lock should be acquired via acquire_lock() before calling this.

        Raises:
            RuntimeError: If PID file cannot be written
        """
        try:
            with self.pid_file.open('w') as f:
                f.write(f'{os.getpid()}\n')
                f.flush()
        except OSError as e:
            raise RuntimeError(f'Failed to write PID file: {e}') from e  # noqa: TRY003

    def is_running(self) -> bool:
        """Check if another instance is running.

        Uses a separate probe lock to avoid interfering with the
        lock stored by acquire_lock().

        Returns:
            bool: True if another instance holds the lock, False otherwise
        """
        probe = TimeoutPIDLockFile(str(self.pid_file), timeout=0.0)
        try:
            probe.acquire()
            probe.release()
        except (AlreadyLocked, LockError, OSError):
            return True
        else:
            return False

    def get_pid(self) -> int | None:
        """Get PID from PID file.

        Returns:
            int: PID if available, None otherwise
        """
        if self.pid_file.exists():
            with contextlib.suppress(ValueError, OSError):
                pid_str = self.pid_file.read_text().strip()
                return int(pid_str)
        return None

    def stop(self) -> bool:
        """Stop the daemon process.

        Sends SIGTERM to the process and waits for it to exit gracefully.
        If the process doesn't exit within timeout, sends SIGKILL.

        Returns:
            bool: True if process was stopped, False if not running
        """
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())

            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit (up to 5 seconds)
            timeout = 5.0
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    # Check if process still exists
                    os.kill(pid, 0)  # This will raise ProcessLookupError if process doesn't exist
                    time.sleep(0.1)  # Wait a bit before checking again
                except ProcessLookupError:
                    # Process has exited
                    self.pid_file.unlink(missing_ok=True)
                    return True

            # Process didn't exit gracefully, send SIGKILL
            try:
                os.kill(pid, signal.SIGKILL)
                # Wait a bit more for SIGKILL to take effect
                time.sleep(0.5)
                self.pid_file.unlink(missing_ok=True)
                return True  # noqa: TRY300
            except ProcessLookupError:
                # Process already exited
                self.pid_file.unlink(missing_ok=True)
                return True

        except (ProcessLookupError, ValueError):
            # Process doesn't exist or invalid PID
            self.pid_file.unlink(missing_ok=True)
            return False

        except PermissionError:
            # Can't kill process (owned by different user?)
            return False

    def cleanup(self) -> None:
        """Release lock and clean up PID file.

        This should be called when the daemon is shutting down gracefully.
        Note: The lock is automatically released by the kernel when the
        process exits, so this is mainly for explicit cleanup.
        """
        # Close daemon context if open
        if self._daemon_context is not None:
            with contextlib.suppress(Exception):
                self._daemon_context.close()
            self._daemon_context = None

        # Release lock file if held
        if self._lock_file is not None:
            with contextlib.suppress(Exception):
                self._lock_file.release()
            self._lock_file = None

        # Remove PID file
        self.pid_file.unlink(missing_ok=True)

    def daemonize(self, foreground: bool = False) -> None:
        """Daemonize the process using python-daemon.

        For background mode: Creates a new TimeoutPIDLockFile and passes it
        to DaemonContext, which atomically acquires the lock and writes PID
        during open(). Uses DaemonContext.open() directly per PEP 3143 to
        return control to the caller after fork.

        For foreground mode: Writes PID file directly (lock was probed by
        acquire_lock() before this call).

        Args:
            foreground: If True, don't daemonize, just write PID file

        Raises:
            RuntimeError: If daemonization fails or lock cannot be acquired
        """
        if foreground:
            self.write_pid_file()
            return

        # Create a fresh lock file for DaemonContext.
        # DaemonContext.open() will atomically acquire the lock via
        # pidfile.acquire() and write the child PID after fork.
        # This must be a NEW lock — PIDLockFile.acquire() uses O_EXCL
        # and fails if the PID file already exists.
        self._lock_file = TimeoutPIDLockFile(
            str(self.pid_file),
            timeout=0.0,
        )

        # Open /dev/null files for stdio redirection
        devnull_read = open(_DEV_NULL)  # noqa: SIM115, PTH123
        devnull_write = open(_DEV_NULL, 'w')  # noqa: SIM115, PTH123

        # DaemonContext will acquire the lock and write PID automatically
        self._daemon_context = DaemonContext(
            pidfile=self._lock_file,
            stdin=devnull_read,
            stdout=devnull_write,
            stderr=devnull_write,
        )

        # DaemonContext.open() forks — parent exits via os._exit(),
        # child continues. We call open() directly instead of 'with'
        # because we need the caller to regain control after fork.
        try:
            self._daemon_context.open()
        except (AlreadyLocked, OSError, BlockingIOError) as e:
            raise RuntimeError(f'Failed to daemonize: {e}') from e  # noqa: TRY003
