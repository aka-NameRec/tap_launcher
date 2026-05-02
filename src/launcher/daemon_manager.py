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
        """Check if lock can be acquired (check for running instance).

        This method checks if another instance is already running by
        attempting to acquire a lock on the PID file. This does NOT
        keep the lock - it's just a check.

        For actual lock acquisition and PID writing, use daemonize().

        Returns:
            bool: True if lock can be acquired (no other instance running),
            False if another instance is already running
        """
        try:
            lock_file = TimeoutPIDLockFile(
                str(self.pid_file),
                timeout=0.0,  # Non-blocking
            )
            # Try to acquire lock
            with lock_file:
                # Lock acquired → no one is running, we can proceed
                return True
        except (OSError, BlockingIOError):
            # Lock is already held by another process
            return False
        except Exception:
            # Other errors - assume we can't proceed
            return False

    def write_pid_file(self) -> None:
        """Write PID to file.

        This is used in foreground mode where PID needs to be written.
        Lock checking should be done via acquire_lock() before calling this.

        Raises:
            RuntimeError: If PID file cannot be written
        """
        try:
            # Write PID to file
            pid_bytes = f'{os.getpid()}\n'.encode()
            with self.pid_file.open('w') as f:
                f.write(pid_bytes.decode())
                f.flush()
        except OSError as e:
            raise RuntimeError(f'Failed to write PID file: {e}') from e  # noqa: TRY003

    def is_running(self) -> bool:
        """Check if another instance is running.

        This method tries to acquire a lock on the PID file. If the lock
        is already held, another instance is running.

        Returns:
            bool: True if another instance holds the lock, False otherwise
        """
        return not self.acquire_lock()

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

        # Release lock file reference
        self._lock_file = None

        # Remove PID file
        self.pid_file.unlink(missing_ok=True)

    def daemonize(self, foreground: bool = False) -> None:
        """Daemonize the process using python-daemon.

        For background mode: Uses DaemonContext as context manager per PEP 3143.
        The context manager handles fork, detach, and PID file locking.

        For foreground mode: Just writes PID file (lock check should be
        done via acquire_lock() before calling this).

        Args:
            foreground: If True, don't daemonize, just write PID file

        Raises:
            RuntimeError: If lock cannot be acquired or daemonization fails
        """
        if foreground:
            # In foreground mode, just write PID file
            # Lock should already be checked via acquire_lock()
            self.write_pid_file()
            return

        # For background mode, use DaemonContext as context manager
        # Create lock file - DaemonContext will manage it
        self._lock_file = TimeoutPIDLockFile(
            str(self.pid_file),
            timeout=0.0,  # Non-blocking - will raise if locked
        )

        # Open /dev/null files for stdio redirection
        devnull_read = open(_DEV_NULL, 'r')  # noqa: SIM115
        devnull_write = open(_DEV_NULL, 'w')  # noqa: SIM115

        # Create daemon context with pidfile
        # DaemonContext will acquire the lock and write PID automatically
        # If lock cannot be acquired, it will raise an exception
        self._daemon_context = DaemonContext(
            pidfile=self._lock_file,
            stdin=devnull_read,
            stdout=devnull_write,
            stderr=devnull_write,
        )

        # According to PEP 3143, DaemonContext should be used as context manager
        # The __enter__ method calls open() which forks - parent exits, child continues
        # After fork, we're in the daemon (child) process inside the with block
        # However, we can't use 'with' here because we need to return to caller
        # So we call open() directly, which is equivalent to entering the context
        try:
            # This will fork and detach from terminal
            # Parent process exits here via os._exit() in detach_process_context()
            # Child process continues execution after this call
            self._daemon_context.open()
            # After this point, we're in the daemon (child) process
        except (OSError, BlockingIOError) as e:
            raise RuntimeError(f'Failed to daemonize: {e}') from e  # noqa: TRY003


def daemonize() -> None:
    """Daemonize the current process using python-daemon.

    This function is a compatibility wrapper that creates a temporary
    DaemonManager and uses it for daemonization.

    Note: It's recommended to use DaemonManager.daemonize() instead.
    """
    manager = DaemonManager()
    manager.daemonize(foreground=False)
