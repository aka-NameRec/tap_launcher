"""Daemon process management for tap-launcher.

This module handles PID file management and process control.
"""

import errno
import fcntl
import os
import signal
import sys
import time
from pathlib import Path


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
            pid_file = Path.home() / '.local/share/tap-launcher/tap-launcher.pid'
        self.pid_file = pid_file
        self.pid_fd: int | None = None  # File descriptor with lock

        # Ensure parent directory exists
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self) -> bool:
        """Acquire exclusive lock on PID file.

        This method opens the PID file and attempts to acquire an exclusive
        lock using fcntl.flock. If successful, it writes the current PID to
        the file. The file descriptor is kept open to maintain the lock.

        The lock is automatically released by the kernel when the process exits.

        Returns:
            bool: True if lock acquired successfully, False if another instance
            is already running
        """
        try:
            # Open PID file (create if doesn't exist)
            self.pid_fd = os.open(
                self.pid_file,
                os.O_CREAT | os.O_RDWR,
                0o600
            )

            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.pid_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Lock acquired! Write current PID to file
            os.ftruncate(self.pid_fd, 0)
            pid_bytes = f'{os.getpid()}\n'.encode()
            os.write(self.pid_fd, pid_bytes)
            os.fsync(self.pid_fd)

            # Keep file descriptor open to maintain the lock
            return True  # noqa: TRY300
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                # Lock is already held by another process
                if self.pid_fd is not None:
                    os.close(self.pid_fd)
                    self.pid_fd = None
                return False
            # Re-raise other errors
            raise

    def update_pid(self) -> None:
        """Update PID in the lock file.

        This should be called after daemonize() (fork) to update the PID
        in the file, since the PID changes after fork but the lock is
        maintained through the inherited file descriptor.
        """
        if self.pid_fd is None and not self.acquire_lock():
            raise RuntimeError('Failed to re-acquire lock in daemon process')  # noqa: TRY003

        # Write new PID to the already-locked file
        if self.pid_fd is not None:
            os.ftruncate(self.pid_fd, 0)
            pid_bytes = f'{os.getpid()}\n'.encode()
            os.write(self.pid_fd, pid_bytes)
            os.fsync(self.pid_fd)

    def write_pid_file(self) -> None:
        """Write PID to file without acquiring lock.

        This is used in daemon process where we don't need to acquire
        a new lock, just write the PID to the file.
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
        if not self.pid_file.exists():
            return False

        try:
            # Try to open and lock the file (non-blocking)
            test_fd = os.open(self.pid_file, os.O_RDWR)

            try:
                # Try to acquire lock
                fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired → no one is running
                fcntl.flock(test_fd, fcntl.LOCK_UN)
                os.close(test_fd)
                return False  # noqa: TRY300
            except OSError as e:
                # Lock is held → someone is running
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
        try:
            if self.pid_file.exists():
                pid_str = self.pid_file.read_text().strip()
                return int(pid_str)
        except (ValueError, OSError):
            pass
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
        # Release lock and close file descriptor
        if self.pid_fd is not None:
            try:
                fcntl.flock(self.pid_fd, fcntl.LOCK_UN)
                os.close(self.pid_fd)
            except OSError:
                pass  # Already released or error
            finally:
                self.pid_fd = None

        # Remove PID file
        self.pid_file.unlink(missing_ok=True)


def daemonize() -> None:
    """Daemonize the current process.

    This function forks the process into the background and detaches
    from the controlling terminal.

    Reference: https://www.python.org/dev/peps/pep-3143/
    """
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process, exit
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f'Fork #1 failed: {e}\n')
        sys.exit(1)

    # Decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)

    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process, exit
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f'Fork #2 failed: {e}\n')
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    # Redirect stdin to /dev/null
    with Path('/dev/null').open() as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    # Redirect stdout and stderr to /dev/null
    # (logging will go to file if configured)
    with Path('/dev/null').open('w') as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


