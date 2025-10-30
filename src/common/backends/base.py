"""Base keyboard backend abstraction using Protocol.

This module defines the KeyboardBackend protocol that all backends must implement.
Using Protocol instead of ABC allows for structural subtyping (duck typing + type checking)
without requiring explicit inheritance.
"""

from typing import Any, Callable, Protocol


class KeyboardBackend(Protocol):
    """Protocol for keyboard event sources.
    
    Backends must implement these methods to be compatible with tap_detector
    and tap_launcher. No explicit inheritance required - structural subtyping.
    
    Example:
        class MyBackend:  # No inheritance needed!
            def start(self, on_press, on_release) -> None: ...
            def stop(self) -> None: ...
            def get_backend_name(self) -> str: ...
        
        # Automatically conforms to KeyboardBackend protocol
        backend: KeyboardBackend = MyBackend()
    
    This approach provides:
    - Structural subtyping (more Pythonic)
    - No forced inheritance
    - Easier testing with mocks
    - Type safety with mypy
    """
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening for keyboard events (blocking call).
        
        This method should block until stop() is called from another thread
        or signal handler. It reads keyboard events and calls the appropriate
        callback for each event.
        
        Args:
            on_press: Callback for key press events.
                     Receives canonical key name (str) like 'ctrl_l', 'a', 'delete'.
            on_release: Callback for key release events.
                       Receives canonical key name (str) like 'ctrl_l', 'a', 'delete'.
        
        Note:
            The callbacks receive canonical key names (strings) regardless of the
            underlying backend. This ensures compatibility with tap detection logic.
        """
        ...
    
    def stop(self) -> None:
        """Stop listening for keyboard events.
        
        This method should cause start() to unblock and return.
        It should clean up any resources (file descriptors, threads, etc).
        """
        ...
    
    def get_backend_name(self) -> str:
        """Return the name of this backend for logging and debugging.
        
        Returns:
            Human-readable backend name (e.g., "evdev (Wayland/X11)")
        """
        ...


class BackendNotAvailableError(Exception):
    """Raised when a backend cannot be initialized.
    
    This can happen for various reasons:
    - Required library not installed (e.g., evdev)
    - No suitable input devices found (for evdev)
    - Permission denied (for evdev /dev/input/ access)
    - Incompatible system configuration
    
    The error message should provide actionable guidance for the user.
    """
    pass

