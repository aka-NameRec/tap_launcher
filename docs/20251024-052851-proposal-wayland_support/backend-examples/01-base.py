"""Example: Base backend abstraction.

This is a demonstration of how the backend abstraction would be implemented.
This is NOT integrated into the project - it's for review purposes.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable


class KeyboardBackend(ABC):
    """Abstract interface for keyboard event sources.
    
    A backend is responsible for:
    - Listening to keyboard events from the system
    - Converting events to a unified format (pynput-compatible)
    - Calling callbacks for press/release events
    
    The unified format uses pynput Key/KeyCode objects so that
    the rest of the codebase doesn't need to change.
    """
    
    @abstractmethod
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening for keyboard events (blocking).
        
        This method should block until stop() is called.
        It reads keyboard events and calls the appropriate callback
        for each event.
        
        Args:
            on_press: Callback for key press events
                     Receives pynput Key or KeyCode object
            on_release: Callback for key release events
                       Receives pynput Key or KeyCode object
        
        Example:
            def handle_press(key):
                print(f"Key pressed: {key}")
            
            def handle_release(key):
                print(f"Key released: {key}")
            
            backend.start(handle_press, handle_release)
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop listening for keyboard events.
        
        This method should cause start() to unblock and return.
        It should clean up any resources (file descriptors, threads, etc).
        """
        pass
    
    @abstractmethod
    def get_backend_name(self) -> str:
        """Return the name of this backend.
        
        Used for logging and debugging purposes.
        
        Returns:
            str: Human-readable backend name (e.g., "pynput (X11)")
        """
        pass


class BackendNotAvailableError(Exception):
    """Raised when a backend cannot be initialized.
    
    This can happen for various reasons:
    - Required library not installed
    - No suitable input devices found
    - Permission denied
    - Incompatible system configuration
    """
    pass


# Example usage pattern:
if __name__ == '__main__':
    # This is how a backend would be used:
    
    # 1. Create backend instance
    # backend = SomeBackend()
    
    # 2. Define callbacks
    def on_key_press(key: Any) -> None:
        print(f"Pressed: {key}")
    
    def on_key_release(key: Any) -> None:
        print(f"Released: {key}")
    
    # 3. Start listening (this blocks)
    # backend.start(on_key_press, on_key_release)
    
    # 4. Stop when done (called from signal handler or another thread)
    # backend.stop()
    
    print("This is just an example - see other files for actual implementations")

