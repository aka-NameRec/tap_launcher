"""Pynput-based keyboard backend for X11.

This backend wraps pynput.keyboard.Listener to provide keyboard event monitoring
on X11 sessions. It works only on X11 and is not compatible with Wayland.

No explicit inheritance from KeyboardBackend is required - structural subtyping.
"""

import logging
from typing import Any, Callable

from .base import BackendNotAvailableError


class PynputBackend:
    """Keyboard backend using pynput (X11 only).
    
    This backend automatically conforms to KeyboardBackend protocol through
    structural subtyping. No inheritance required.
    
    Wraps the existing pynput.keyboard.Listener that was previously used
    directly in TapMonitor, maintaining full backward compatibility.
    """
    
    def __init__(self) -> None:
        """Initialize pynput backend.
        
        Raises:
            BackendNotAvailableError: If pynput library is not installed.
        """
        self.logger = logging.getLogger('common.backend.pynput')
        self.listener: Any = None  # Will be pynput.keyboard.Listener
        
        # Check if pynput is available
        try:
            import pynput  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'pynput library is not installed. '
                'Install it with: pip install pynput'
            ) from e
        
        self.logger.debug('PynputBackend initialized successfully')
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening for keyboard events using pynput.
        
        This is essentially the same code that was in TapMonitor.start(),
        just moved into a separate backend class.
        
        Args:
            on_press: Callback for key press events.
                     Receives pynput Key or KeyCode object.
            on_release: Callback for key release events.
                       Receives pynput Key or KeyCode object.
        """
        from pynput import keyboard
        
        self.logger.info('Starting pynput keyboard listener (X11)')
        
        # Create the listener WITH suppress=True
        # This captures ALL events, we'll selectively re-emit via Controller
        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
            suppress=True  # Capture all events for selective re-emission
        )
        
        # Start and block (same as existing code)
        self.listener.start()
        self.listener.join()  # This blocks until stopped
    
    def stop(self) -> None:
        """Stop the pynput listener.
        
        This is called from signal handlers or when the application exits.
        """
        if self.listener:
            self.logger.info('Stopping pynput keyboard listener')
            self.listener.stop()
            self.listener = None
    
    def get_backend_name(self) -> str:
        """Return backend name for logging."""
        return 'pynput (X11)'

