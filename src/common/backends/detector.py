"""Backend detection and factory.

This module provides auto-detection of the appropriate keyboard backend based
on the current session type (X11 vs Wayland) and automatic fallback logic.
"""

import logging
import os
from typing import Any

from .base import BackendNotAvailableError, KeyboardBackend
from .evdev_backend import EvdevBackend
from .pynput_backend import PynputBackend


logger = logging.getLogger('common.backend')


def detect_session_type() -> str:
    """Detect current display server type.
    
    Returns:
        str: 'wayland', 'x11', or 'unknown'
    
    Detection strategy:
    1. Check XDG_SESSION_TYPE environment variable (most reliable)
    2. Fallback to WAYLAND_DISPLAY for Wayland
    3. Fallback to DISPLAY for X11
    4. Return 'unknown' if detection fails
    """
    # Primary method: XDG_SESSION_TYPE
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    
    if session_type:
        logger.debug(f'Detected session type from XDG_SESSION_TYPE: {session_type}')
        return session_type
    
    # Fallback: check for Wayland display
    if os.environ.get('WAYLAND_DISPLAY'):
        logger.debug('Detected Wayland from WAYLAND_DISPLAY')
        return 'wayland'
    
    # Fallback: check for X11 display
    if os.environ.get('DISPLAY'):
        logger.debug('Detected X11 from DISPLAY')
        return 'x11'
    
    # Could not detect
    logger.warning('Could not detect session type from environment variables')
    return 'unknown'


def create_backend(
    backend_name: str | None = None,
    **kwargs: Any
) -> KeyboardBackend:
    """Create appropriate keyboard backend.
    
    This factory function handles:
    - Auto-detection of session type (X11 vs Wayland)
    - Automatic backend selection based on environment
    - Fallback logic if primary backend is unavailable
    - Error handling with informative messages
    
    Args:
        backend_name: Explicitly specify backend ('pynput', 'evdev', 'auto').
                     If None or 'auto', will auto-detect based on session type.
        **kwargs: Additional arguments passed to backend constructor
                 (e.g., device_path for EvdevBackend).
    
    Returns:
        KeyboardBackend: Initialized backend instance that conforms to
                        KeyboardBackend protocol.
    
    Raises:
        BackendNotAvailableError: If no suitable backend is available.
    
    Examples:
        # Auto-detect (recommended)
        backend = create_backend()
        
        # Force specific backend
        backend = create_backend('evdev')
        
        # With custom device path
        backend = create_backend('evdev', device_path='/dev/input/event3')
    """
    # Auto-detect if not specified
    if backend_name is None or backend_name == 'auto':
        session_type = detect_session_type()
        
        if session_type == 'wayland':
            backend_name = 'evdev'
            logger.debug('Session is Wayland, selecting evdev backend')
        elif session_type == 'x11':
            backend_name = 'pynput'
            logger.debug('Session is X11, selecting pynput backend')
        else:
            # Unknown session - try pynput first (most compatible)
            logger.warning(
                'Unknown session type, trying pynput backend first '
                '(will fallback to evdev if needed)'
            )
            backend_name = 'pynput'
    
    # Try to create the specified backend
    if backend_name == 'pynput':
        try:
            backend = PynputBackend(**kwargs)
            logger.info(f'Created backend: {backend.get_backend_name()}')
            return backend
        except BackendNotAvailableError as e:
            # If explicitly requested and failed, try fallback to evdev
            logger.warning(f'pynput backend not available: {e}')
            logger.info('Attempting fallback to evdev backend')
            backend_name = 'evdev'
    
    if backend_name == 'evdev':
        try:
            backend = EvdevBackend(**kwargs)
            logger.info(f'Created backend: {backend.get_backend_name()}')
            return backend
        except BackendNotAvailableError as e:
            # No fallback for evdev - it's the last resort
            error_msg = (
                f'No suitable keyboard backend available. '
                f'Last error: {e}\n\n'
                f'Troubleshooting:\n'
                f'1. For X11: Install pynput (pip install pynput)\n'
                f'2. For Wayland: Install evdev (pip install evdev) and '
                f'add user to input group:\n'
                f'   sudo usermod -a -G input $USER\n'
                f'   Then log out and back in.'
            )
            raise BackendNotAvailableError(error_msg) from e
    
    # Invalid backend name
    raise BackendNotAvailableError(
        f'Unknown backend name: {backend_name}. '
        f'Valid options: "pynput", "evdev", "auto"'
    )

