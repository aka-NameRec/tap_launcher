"""Backend detection and factory.

This module creates evdev-based keyboard backend for all applications.
All applications (tap-detector and tap-launcher) now use evdev backend
which works on both X11 and Wayland with key suppression support.
"""

import logging
from typing import Any

from .base import BackendNotAvailableError, KeyboardBackend
from .evdev_backend import EvdevBackend


logger = logging.getLogger('common.backend')


def create_backend(
    backend_name: str | None = None,
    device_name: str | None = None,
    **kwargs: Any
) -> KeyboardBackend:
    """Create evdev keyboard backend.
    
    This factory function always creates EvdevBackend, which works on both
    X11 and Wayland. The backend_name parameter is kept for compatibility
    but is ignored (always creates evdev).
    
    Args:
        backend_name: Ignored for compatibility (always uses evdev).
                     Previously supported 'pynput', 'evdev', 'auto'.
        **kwargs: Additional arguments passed to EvdevBackend constructor
                 (e.g., device_path).
    
    Returns:
        KeyboardBackend: Initialized EvdevBackend instance.
    
    Raises:
        BackendNotAvailableError: If evdev backend cannot be initialized.
                 This can happen if:
                 - evdev library is not installed
                 - No keyboard devices found
                 - Permission denied accessing /dev/input/
    
    Examples:
        # Create backend (always evdev)
        backend = create_backend()
        
        # With custom device path
        backend = create_backend(device_path='/dev/input/event3')
        
    Note:
        Previous pynput backend support has been removed. All applications
        now use evdev backend for unified behavior and key suppression support.
    """
    # Always use evdev backend (works on both X11 and Wayland)
    if backend_name is not None and backend_name != 'evdev':
        logger.warning(
            f'backend_name="{backend_name}" is ignored. '
            f'Always using evdev backend.'
        )
    
    try:
        # Pass device_name to backend if provided
        if device_name:
            kwargs['device_name'] = device_name
        backend = EvdevBackend(**kwargs)
        logger.info(f'Created backend: {backend.get_backend_name()}')
        return backend
    except BackendNotAvailableError as e:
        error_msg = (
            f'Evdev backend is not available: {e}\n\n'
            f'Troubleshooting:\n'
            f'1. Install evdev library: pip install evdev or uv add evdev\n'
            f'2. Add user to input group:\n'
            f'   sudo usermod -a -G input $USER\n'
            f'   Then log out and back in.\n'
            f'3. For uinput support (key suppression):\n'
            f'   Create udev rule: sudo tee /etc/udev/rules.d/99-uinput.rules > /dev/null << EOF\n'
            f'   KERNEL=="uinput", MODE="0660", GROUP="input"\n'
            f'   EOF\n'
            f'   Then: sudo udevadm control --reload-rules && sudo udevadm trigger'
        )
        raise BackendNotAvailableError(error_msg) from e

