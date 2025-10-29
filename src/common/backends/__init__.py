"""Keyboard backend abstraction for X11 and Wayland support.

This module provides backend abstraction for keyboard event handling,
allowing tap_detector and tap_launcher to work on both X11 and Wayland.
"""

from .base import BackendNotAvailableError, KeyboardBackend
from .detector import create_backend

__all__ = [
    'KeyboardBackend',
    'BackendNotAvailableError',
    'create_backend',
]

