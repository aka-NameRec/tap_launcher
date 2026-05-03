"""Daemon process management for tap-launcher.

Uses fcntl.flock for exclusive locking and standard POSIX double-fork
for daemonization. Zero external dependencies.
"""

import errno
import fcntl
import os
import signal
import sys
import time
from pathlib import Path

from common.runtime_state import PID_FILE
from common.runtime_state import LaunchRuntimeState
from common.runtime_state import read_launch_runtime_state
from common.runtime_state import remove_launch_runtime_state
from common.runtime_state import write_launch_runtime_state


class DaemonManager:
    """Manage daemon process with PID file and exclusive lock.

    This class handles:
    - Preventing multiple instances via fcntl.flock
    - Writing PID file for process identification
    - Stopping daemon process
    - Automatic lock cleanup on process exit
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
            pid_file = PID_FILE
        self.pid_file = pid_file
        self._pid_fd: int | None = None

        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self) -> bool:
        """Acquire exclusive lock on PID file.

        Opens the PID file and acquires an exclusive lock using fcntl.flock.
        If successful, writes the current PID. The file descriptor is kept
        open to maintain the lock. The lock is released by the kernel when
        the process exits.

        Returns:
            bool: True if lock acquired, False if another instance is running
        """
        try:
            self._pid_fd = os.open(
                self.pid_file,
                os.O_CREAT | os.O_RDWR,
                0o600,
            )

            fcntl.flock(self._pid_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            os.ftruncate(self._pid_fd, 0)
            os.write(self._pid_fd, f'{os.getpid()}\n'.encode())
            os.fsync(self._pid_fd)

            return True  # noqa: TRY300
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                if self._pid_fd is not None:
                    os.close(self._pid_fd)
                    self._pid_fd = None
                return False
            raise

    def daemonize(self, foreground: bool = False) -> None:
        """Daemonize the process using POSIX double-fork.

        For background mode: forks into background, detaches from terminal,
        redirects stdio to /dev/null, and updates PID on the inherited
        locked file descriptor.

        For foreground mode: no-op (lock already held, PID already written
        by acquire_lock()).

        Args:
            foreground: If True, skip daemonization

        Raises:
            RuntimeError: If fork fails
        """
        if foreground:
            return

        try:
            pid = os.fork()
            if pid > 0:
                os._exit(0)
        except OSError as e:
            raise RuntimeError(f'First fork failed: {e}') from e  # noqa: TRY003

        os.chdir('/')
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                os._exit(0)
        except OSError as e:
            raise RuntimeError(f'Second fork failed: {e}') from e  # noqa: TRY003

        sys.stdout.flush()
        sys.stderr.flush()

        with Path('/dev/null').open() as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with Path('/dev/null').open('w') as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())

        self._update_pid()

    def _update_pid(self) -> None:
        """Update PID in the locked file after fork.

        Called after double-fork to write the new (daemon child) PID.
        The file descriptor with the lock is inherited through fork.
        """
        if self._pid_fd is not None:
            os.lseek(self._pid_fd, 0, os.SEEK_SET)
            os.ftruncate(self._pid_fd, 0)
            os.write(self._pid_fd, f'{os.getpid()}\n'.encode())
            os.fsync(self._pid_fd)

    def is_running(self) -> bool:
        """Check if another instance is running.

        Uses a separate file descriptor to probe the lock without
        interfering with the lock held by acquire_lock().

        Returns:
            bool: True if another instance holds the lock
        """
        if not self.pid_file.exists():
            return False

        try:
            test_fd = os.open(self.pid_file, os.O_RDWR)
            try:
                fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(test_fd, fcntl.LOCK_UN)
                os.close(test_fd)
                return False  # noqa: TRY300
            except OSError as e:
                os.close(test_fd)
                if e.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                    return True
                raise
        except (FileNotFoundError, OSError):
            return False

    def get_pid(self) -> int | None:
        """Get PID from PID file.

        Returns:
            int: PID if available, None otherwise
        """
        if self.pid_file.exists():
            try:
                return int(self.pid_file.read_text().strip())
            except (ValueError, OSError):
                pass
        return None

    def stop(self) -> bool:
        """Stop the daemon process.

        Sends SIGTERM and waits up to 5 seconds, then SIGKILL.

        Returns:
            bool: True if process was stopped, False if not running
        """
        if not self.pid_file.exists():
            self.remove_runtime_state()
            return False

        try:
            pid = int(self.pid_file.read_text().strip())

            os.kill(pid, signal.SIGTERM)

            timeout = 5.0
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    self.pid_file.unlink(missing_ok=True)
                    self.remove_runtime_state()
                    return True

            try:
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)
                self.pid_file.unlink(missing_ok=True)
                self.remove_runtime_state()
                return True  # noqa: TRY300
            except ProcessLookupError:
                self.pid_file.unlink(missing_ok=True)
                self.remove_runtime_state()
                return True

        except (ProcessLookupError, ValueError):
            self.pid_file.unlink(missing_ok=True)
            self.remove_runtime_state()
            return False

        except PermissionError:
            return False

    def cleanup(self) -> None:
        """Release lock and clean up PID file.

        The lock is automatically released by the kernel when the process
        exits, so this is mainly for explicit cleanup.
        """
        if self._pid_fd is not None:
            try:
                fcntl.flock(self._pid_fd, fcntl.LOCK_UN)
                os.close(self._pid_fd)
            except OSError:
                pass
            finally:
                self._pid_fd = None

        self.pid_file.unlink(missing_ok=True)
        self.remove_runtime_state()

    def write_runtime_state(self, state: LaunchRuntimeState) -> None:
        """Persist launcher startup parameters for later restoration."""
        write_launch_runtime_state(state)

    def read_runtime_state(self) -> LaunchRuntimeState | None:
        """Read persisted launcher startup parameters."""
        return read_launch_runtime_state()

    def remove_runtime_state(self) -> None:
        """Remove persisted launcher startup parameters."""
        remove_launch_runtime_state()
