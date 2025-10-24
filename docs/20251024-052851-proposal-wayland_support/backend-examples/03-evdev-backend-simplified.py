"""Example: Simplified EvdevBackend for Wayland.

This demonstrates the core concept of the evdev backend without
all the complexity. The full implementation would include error
handling, device selection, etc.

This is NOT integrated into the project - it's for review purposes.
"""

import logging
import threading
from typing import Any, Callable


# Mock base classes for this example
class KeyboardBackend:
    pass


class BackendNotAvailableError(Exception):
    pass


class EvdevBackendSimplified(KeyboardBackend):
    """Simplified evdev backend to demonstrate the concept.
    
    The real implementation would be more robust, but this shows
    the essential idea: read events from /dev/input/event* and
    convert them to pynput-compatible Key objects.
    """
    
    def __init__(self) -> None:
        """Initialize evdev backend.
        
        Raises:
            BackendNotAvailableError: If evdev not available or no permissions
        """
        self.logger = logging.getLogger('tap_detector.backend.evdev')
        self.device: Any = None
        self._stop_event = threading.Event()
        
        # Check evdev availability
        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev'
            ) from e
        
        self.logger.debug('EvdevBackend initialized')
    
    def _find_keyboard(self) -> Any:
        """Find keyboard device in /dev/input/.
        
        Returns:
            evdev.InputDevice: Keyboard device
        
        Raises:
            BackendNotAvailableError: If no keyboard found or permission denied
        """
        import evdev
        from evdev import ecodes
        
        # Try to list devices
        try:
            device_paths = evdev.list_devices()
        except PermissionError as e:
            raise BackendNotAvailableError(
                'Permission denied accessing /dev/input/. '
                'Add user to "input" group: sudo usermod -a -G input $USER'
            ) from e
        
        # Find keyboards
        for path in device_paths:
            device = evdev.InputDevice(path)
            caps = device.capabilities()
            
            # Check for keyboard capabilities
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                # Verify it has modifier keys (actual keyboard, not mouse)
                if ecodes.KEY_LEFTCTRL in keys or ecodes.KEY_LEFTALT in keys:
                    self.logger.info(f'Found keyboard: {device.name} at {path}')
                    return device
        
        raise BackendNotAvailableError('No keyboard device found')
    
    def _evdev_to_pynput(self, keycode: str) -> Any:
        """Convert evdev keycode to pynput Key object.
        
        This is a simplified mapping - the real one would be much larger.
        
        Args:
            keycode: Evdev keycode (e.g., 'KEY_LEFTCTRL')
        
        Returns:
            pynput Key object
        
        Raises:
            KeyError: If keycode unknown
        """
        from pynput.keyboard import Key, KeyCode
        
        # Handle multi-key events (lists)
        if isinstance(keycode, list):
            keycode = keycode[0]
        
        # Simplified mapping (real one would be comprehensive)
        mapping = {
            'KEY_LEFTCTRL': Key.ctrl_l,
            'KEY_RIGHTCTRL': Key.ctrl_r,
            'KEY_LEFTALT': Key.alt_l,
            'KEY_RIGHTALT': Key.alt_r,
            'KEY_LEFTSHIFT': Key.shift_l,
            'KEY_RIGHTSHIFT': Key.shift_r,
            'KEY_LEFTMETA': Key.cmd_l,  # Super/Win
            'KEY_RIGHTMETA': Key.cmd_r,
            'KEY_SPACE': Key.space,
            'KEY_ENTER': Key.enter,
            'KEY_ESC': Key.esc,
            'KEY_TAB': Key.tab,
        }
        
        # Check mapping
        if keycode in mapping:
            return mapping[keycode]
        
        # Handle letter keys (KEY_A -> 'a')
        if keycode.startswith('KEY_') and len(keycode) == 5 and keycode[4].isalpha():
            char = keycode[4].lower()
            return KeyCode.from_char(char)
        
        # Unknown key
        raise KeyError(f'Unknown keycode: {keycode}')
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening using evdev.
        
        This is the core logic: read events from device, convert to
        pynput format, and call the appropriate callback.
        
        Args:
            on_press: Callback for key press
            on_release: Callback for key release
        """
        from evdev import categorize, ecodes
        
        # Find keyboard device
        self.device = self._find_keyboard()
        
        self.logger.info('Starting evdev keyboard listener (Wayland/X11)')
        self._stop_event.clear()
        
        try:
            # Read events in a loop
            for event in self.device.read_loop():
                # Check if we should stop
                if self._stop_event.is_set():
                    break
                
                # Process only keyboard events
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    keycode = key_event.keycode
                    
                    # Convert to pynput format
                    try:
                        pynput_key = self._evdev_to_pynput(keycode)
                    except KeyError:
                        # Unknown key, skip
                        self.logger.debug(f'Unknown key: {keycode}')
                        continue
                    
                    # Call appropriate callback
                    if key_event.keystate == key_event.key_down:
                        on_press(pynput_key)
                    elif key_event.keystate == key_event.key_up:
                        on_release(pynput_key)
        
        finally:
            if self.device:
                self.device.close()
    
    def stop(self) -> None:
        """Stop the evdev listener."""
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        
        if self.device:
            self.device.close()
            self.device = None
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return 'evdev (Wayland/X11)'


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    print("Example: Simplified EvdevBackend usage")
    print("="*60)
    print()
    
    # Create backend
    try:
        backend = EvdevBackendSimplified()
        print(f"✓ Backend created: {backend.get_backend_name()}")
    except BackendNotAvailableError as e:
        print(f"✗ Backend not available: {e}")
        exit(1)
    
    # Define callbacks (same interface as pynput!)
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
    
    print("\nNote: This backend works on BOTH X11 and Wayland!")
    print("Key insight: callbacks receive pynput-compatible objects,")
    print("so TapMonitor doesn't need to change!")

