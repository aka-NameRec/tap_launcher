"""Logging utilities for consistent logger creation across the project.

This module provides a helper function for creating loggers with consistent
naming conventions based on module paths.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def get_logger(name: str | None = None) -> logging.Logger:
    """Create or retrieve a logger with consistent naming.

    This function creates loggers following the project's naming convention:
    - Module paths are used as logger names (e.g., 'tap_launcher.monitor')
    - Ensures consistent logging configuration across the project

    Args:
        name: Logger name. If None, attempts to infer from calling module.
             Defaults to None for auto-detection.

    Returns:
        logging.Logger: Configured logger instance

    Examples:
        >>> logger = get_logger('tap_launcher.monitor')
        >>> logger.info('Message')

        >>> # Auto-detect from module name
        >>> logger = get_logger()  # Uses __name__ of calling module
    """
    if name is None:
        import inspect
        frame = inspect.currentframe()
        if frame is not None and frame.f_back is not None:
            module_name = frame.f_back.f_globals.get('__name__', 'unknown')
            name = module_name
        else:
            name = 'tap_launcher'

    return logging.getLogger(name)


class ISOFormatter(logging.Formatter):
    """Log formatter with ISO timestamp including milliseconds.

    Formats log messages as:
        <ISO-datetime-with-ms> <log-level> [<module>:<lineno>]: <message>
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with ISO timestamp."""
        # Generate ISO timestamp with milliseconds
        timestamp = datetime.fromtimestamp(record.created).isoformat(timespec='milliseconds')
        
        # Format: <timestamp> <level> [<module>:<lineno>]: <message>
        return f'{timestamp} {record.levelname} [{record.module}:{record.lineno}]: {record.getMessage()}'


def setup_logging_handler(
    logger: logging.Logger,
    log_level: str = 'INFO',
    foreground: bool = True,
    log_file: Path | None = None,
) -> None:
    """Set up logging handler based on foreground/background mode.

    Args:
        logger: Logger instance to configure
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        foreground: If True, log to console. If False, log to file (if log_file provided)
        log_file: Path to log file (used only when foreground=False)
    """
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter with ISO timestamp
    formatter = ISOFormatter()
    
    if foreground:
        # Console handler for foreground mode
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    elif log_file:
        # File handler for background mode
        # Create parent directory if needed
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
