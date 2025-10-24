"""Example: How TapMonitor would integrate with backends.

This demonstrates the minimal changes needed in TapMonitor to
support the backend abstraction.

This is NOT integrated into the project - it's for review purposes.
"""

import os
from typing import Any, Callable


# Mock imports (in real code these would be actual imports)
class KeyboardBackend:
    """Mock backend base class."""
    def start(self, on_press: Callable, on_release: Callable) -> None:
        pass
    
    def stop(self) -> None:
        pass


def create_backend(backend_name: str | None = None) -> KeyboardBackend:
    """Mock backend factory.
    
    In real code this would auto-detect session type and create
    the appropriate backend.
    """
    session_type = os.environ.get('XDG_SESSION_TYPE', 'x11').lower()
    print(f"Detected session: {session_type}")
    
    if session_type == 'wayland':
        print("→ Would use EvdevBackend")
    else:
        print("→ Would use PynputBackend")
    
    return KeyboardBackend()  # Mock


class TapMonitorWithBackend:
    """Example: TapMonitor with backend support.
    
    This shows the MINIMAL changes needed to TapMonitor to support
    the backend abstraction. Compare with current tap_monitor.py.
    """
    
    def __init__(
        self,
        timeout: float | None = None,
        verbose: bool = False,
        on_keys_detected: Callable | None = None,
        on_tap_invalid: Callable | None = None,
        backend: KeyboardBackend | None = None,  # ← NEW parameter
    ) -> None:
        """Initialize tap monitor.
        
        Args:
            timeout: Tap timeout in seconds
            verbose: Enable verbose logging
            on_keys_detected: Callback for valid taps
            on_tap_invalid: Callback for invalid taps
            backend: Keyboard backend (auto-created if None)  # ← NEW
        """
        self.timeout = timeout
        self.verbose = verbose
        self.on_keys_detected = on_keys_detected
        self.on_tap_invalid = on_tap_invalid
        
        # Create or use provided backend
        # This is the ONLY new line in __init__
        self.backend = backend or create_backend()
        
        # Rest of initialization stays the same
        self.state = {}  # Mock TapState
        # ... (all other initialization code unchanged)
    
    def start(self) -> None:
        """Start monitoring keyboard events (blocking).
        
        BEFORE (current code):
            from pynput import keyboard
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False
            )
            self.listener.start()
            self.listener.join()
        
        AFTER (with backend):
            self.backend.start(
                on_press=self._on_press,
                on_release=self._on_release
            )
        """
        # Use backend instead of creating pynput Listener
        self.backend.start(
            on_press=self._on_press,
            on_release=self._on_release
        )
    
    def stop(self) -> None:
        """Stop monitoring keyboard events.
        
        BEFORE (current code):
            if self.listener:
                self.listener.stop()
        
        AFTER (with backend):
            self.backend.stop()
        """
        self.backend.stop()
    
    def _on_press(self, key: Any) -> None:
        """Handle key press.
        
        This method DOES NOT CHANGE AT ALL!
        It receives the same pynput Key/KeyCode objects regardless
        of which backend is used.
        """
        # All existing logic stays exactly the same
        print(f"_on_press called with: {key}")
        # ... (existing tap detection logic)
    
    def _on_release(self, key: Any) -> None:
        """Handle key release.
        
        This method DOES NOT CHANGE AT ALL!
        """
        # All existing logic stays exactly the same
        print(f"_on_release called with: {key}")
        # ... (existing tap detection logic)


# Example usage
if __name__ == '__main__':
    print("Example: TapMonitor integration with backends")
    print("="*60)
    print()
    
    print("Changes required in TapMonitor:")
    print("  1. Add 'backend' parameter to __init__")
    print("  2. Create backend: self.backend = backend or create_backend()")
    print("  3. In start(): Replace pynput Listener with backend.start()")
    print("  4. In stop(): Replace listener.stop() with backend.stop()")
    print()
    print("Methods that DON'T change:")
    print("  ✓ _on_press()  - receives same Key objects")
    print("  ✓ _on_release() - receives same Key objects")
    print("  ✓ All tap detection logic - completely unchanged!")
    print()
    
    # Create monitor (auto-detects backend)
    monitor = TapMonitorWithBackend(
        timeout=0.2,
        verbose=True
    )
    
    print("\nMonitor created with auto-detected backend")
    print()
    
    # Show how explicit backend selection would work
    print("Alternative: Explicit backend selection:")
    print("  # Force evdev backend (for Wayland)")
    print("  from backends.evdev_backend import EvdevBackend")
    print("  backend = EvdevBackend()")
    print("  monitor = TapMonitor(..., backend=backend)")
    print()
    print("  # Force pynput backend (for X11)")
    print("  from backends.pynput_backend import PynputBackend")
    print("  backend = PynputBackend()")
    print("  monitor = TapMonitor(..., backend=backend)")
    print()
    
    print("Summary:")
    print("  ✓ Minimal changes to TapMonitor (4 lines)")
    print("  ✓ All tap detection logic stays the same")
    print("  ✓ Backward compatible (backend auto-created)")
    print("  ✓ Works on X11 and Wayland transparently")

