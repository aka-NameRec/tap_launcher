"""Daemon process management for tap-launcher.

This module handles PID file management and process control.
"""

import os
import signal
import sys
from pathlib import Path


class DaemonManager:
    """Manage daemon process with PID file.
    
    This class handles:
    - Checking if daemon is running
    - Writing PID file
    - Stopping daemon process
    - Cleaning up stale PID files
    """
    
    def __init__(
        self,
        pid_file: Path = Path.home() / ".local/share/tap-launcher/tap-launcher.pid"
    ):
        """Initialize daemon manager.
        
        Args:
            pid_file: Path to PID file
        """
        self.pid_file = pid_file
        
        # Ensure parent directory exists
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
    
    def is_running(self) -> bool:
        """Check if daemon process is running.
        
        Returns:
            bool: True if process is running, False otherwise
        """
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            
            # Check if process exists
            # os.kill with signal 0 doesn't kill, just checks existence
            os.kill(pid, 0)
            return True
            
        except (ProcessLookupError, ValueError, PermissionError):
            # Process doesn't exist, invalid PID, or permission denied
            # Clean up stale PID file
            self.pid_file.unlink(missing_ok=True)
            return False
    
    def get_pid(self) -> int | None:
        """Get PID of running daemon process.
        
        Returns:
            int: PID if daemon is running, None otherwise
        """
        if not self.is_running():
            return None
        
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, FileNotFoundError):
            return None
    
    def write_pid(self):
        """Write current process PID to file.
        
        This should be called after the daemon process is started.
        """
        pid = os.getpid()
        self.pid_file.write_text(str(pid))
    
    def stop(self) -> bool:
        """Stop the daemon process.
        
        Sends SIGTERM to the process and cleans up PID file.
        
        Returns:
            bool: True if process was stopped, False if not running
        """
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Clean up PID file
            self.pid_file.unlink()
            
            return True
            
        except (ProcessLookupError, ValueError):
            # Process doesn't exist or invalid PID
            self.pid_file.unlink(missing_ok=True)
            return False
        
        except PermissionError:
            # Can't kill process (owned by different user?)
            return False
    
    def cleanup(self):
        """Clean up PID file.
        
        This should be called when the daemon is shutting down.
        """
        self.pid_file.unlink(missing_ok=True)


def daemonize():
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
        sys.stderr.write(f"Fork #1 failed: {e}\n")
        sys.exit(1)
    
    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)
    
    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process, exit
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork #2 failed: {e}\n")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Redirect stdin to /dev/null
    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    
    # Redirect stdout and stderr to /dev/null
    # (logging will go to file if configured)
    with open("/dev/null", "w") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


