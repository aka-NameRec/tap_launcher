"""Example: PynputBackend implementation for X11.

This demonstrates how the existing pynput code would be wrapped
in a backend interface. This maintains backward compatibility.

This is NOT integrated into the project - it's for review purposes.
"""

import logging
from typing import Any, Callable


# Import the base abstraction from example 01
# In real code: from .base import KeyboardBackend, BackendNotAvailableError
class KeyboardBackend:
    """Mock base class for this example."""
    pass


class BackendNotAvailableError(Exception):
    """Mock exception for this example."""
    pass


class PynputBackend(KeyboardBackend):
    """Keyboard backend using pynput (X11 only).
    
    This backend wraps the existing pynput.keyboard.Listener
    that we're already using. It works well on X11 but is not
    compatible with Wayland.
    
    This backend requires no special permissions or setup.
    """
    
    def __init__(self) -> None:
        """Initialize pynput backend.
        
        Raises:
            BackendNotAvailableError: If pynput is not installed
        """
        self.logger = logging.getLogger('tap_detector.backend.pynput')
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
        """Start listening using pynput.
        
        This is essentially the same code we already have in TapMonitor.start(),
        just moved into a separate class.
        
        Args:
            on_press: Callback for key press (receives pynput Key/KeyCode)
            on_release: Callback for key release (receives pynput Key/KeyCode)
        """
        from pynput import keyboard
        
        self.logger.info('Starting pynput keyboard listener (X11)')
        
        # Create the listener (same as current code)
        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
            suppress=False  # Don't suppress events for other apps
        )
        
        # Start and block (same as current code)
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
        """Return backend name."""
        return 'pynput (X11)'


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    print("Example: PynputBackend usage")
    print("="*60)
    print()
    
    # Create backend
    try:
        backend = PynputBackend()
        print(f"✓ Backend created: {backend.get_backend_name()}")
    except BackendNotAvailableError as e:
        print(f"✗ Backend not available: {e}")
        exit(1)
    
    # Define callbacks (same as we already have in TapMonitor)
    def on_press(key: Any) -> None:
        print(f"  [PRESS  ] {key}")
    
    def on_release(key: Any) -> None:
        print(f"  [RELEASE] {key}")
    
    # Start listening
    print("\nPress some keys (Ctrl+C to stop)...\n")
    try:
        backend.start(on_press, on_release)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        backend.stop()
        print("✓ Stopped")
    
    print("\nNote: This backend works on X11 but NOT on Wayland")

