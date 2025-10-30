"""Logging utilities for consistent logger creation across the project.

This module provides a helper function for creating loggers with consistent
naming conventions based on module paths.
"""

import logging
from typing import Any


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


def setup_logging_for_module(module: Any, default_name: str | None = None) -> logging.Logger:
    """Set up logging for a module using its __name__ attribute.

    Convenience function that extracts logger name from module's __name__.

    Args:
        module: Module object (typically imported with `__import__` or passed directly)
        default_name: Fallback name if module.__name__ is not available

    Returns:
        logging.Logger: Configured logger instance

    Examples:
        >>> logger = setup_logging_for_module(sys.modules[__name__])
    """
    name = getattr(module, '__name__', None) or default_name or 'tap_launcher'
    return get_logger(name)

