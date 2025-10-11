"""Command execution for tap-launcher.

This module handles executing commands when tap combinations are detected.
"""

import logging
import subprocess
from pathlib import Path

from .models import HotkeyConfig


class CommandExecutor:
    """Execute commands in non-blocking mode.
    
    This class handles launching commands in the background when
    hotkey combinations are detected.
    """
    
    def __init__(self, log_commands: bool = True):
        """Initialize the command executor.
        
        Args:
            log_commands: Whether to log command execution
        """
        self.log_commands = log_commands
        self.logger = logging.getLogger("tap_launcher.executor")
    
    def execute(self, hotkey: HotkeyConfig) -> bool:
        """Execute the command associated with a hotkey.
        
        The command is executed in a new process group and detached from
        the parent process, so it continues running even if tap-launcher exits.
        
        Args:
            hotkey: Hotkey configuration containing command to execute
        
        Returns:
            bool: True if command was launched successfully, False on error
        
        Example:
            >>> executor = CommandExecutor()
            >>> hotkey = HotkeyConfig(
            ...     keys=["ctrl_l", "alt_l"],
            ...     command="echo",
            ...     args=["hello"],
            ...     description="Print hello"
            ... )
            >>> success = executor.execute(hotkey)
        """
        # Build full command
        cmd = [hotkey.command] + hotkey.args
        
        if self.log_commands:
            cmd_str = " ".join(cmd)
            if hotkey.description:
                self.logger.info(
                    f"Executing: {cmd_str} ({hotkey.description})"
                )
            else:
                self.logger.info(f"Executing: {cmd_str}")
        
        try:
            # Launch command in background
            # - stdout/stderr redirected to DEVNULL to avoid blocking
            # - start_new_session=True detaches from parent process
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            
            return True
            
        except FileNotFoundError:
            self.logger.error(
                f"Command not found: {hotkey.command}\n"
                f"Make sure the command exists and is in PATH"
            )
            return False
        
        except PermissionError:
            self.logger.error(
                f"Permission denied executing: {hotkey.command}\n"
                f"Check file permissions and executable flag"
            )
            return False
        
        except Exception as e:
            self.logger.error(
                f"Failed to execute command '{hotkey.command}': {e}"
            )
            return False
    
    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists and is executable.
        
        This can be used to validate commands at startup.
        
        Args:
            command: Command name or path
        
        Returns:
            bool: True if command exists and is executable
        """
        # If it's an absolute path, check directly
        if Path(command).is_absolute():
            path = Path(command)
            return path.exists() and path.is_file() and self._is_executable(path)
        
        # Otherwise, search in PATH
        import shutil
        return shutil.which(command) is not None
    
    @staticmethod
    def _is_executable(path: Path) -> bool:
        """Check if a file is executable.
        
        Args:
            path: Path to file
        
        Returns:
            bool: True if file is executable
        """
        import os
        return os.access(path, os.X_OK)


