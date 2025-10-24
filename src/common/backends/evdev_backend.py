"""Evdev-based keyboard backend for Wayland.

This backend reads keyboard events directly from /dev/input/event* devices
using the evdev library. It works on both X11 and Wayland, but is primarily
intended for Wayland where pynput is not available.

Requires:
- evdev library installed
- User in 'input' group or appropriate permissions for /dev/input/
"""

import logging
import threading
from typing import Any, Callable

from .base import BackendNotAvailableError
from .key_mapping import evdev_to_pynput_key


class EvdevBackend:
    """Keyboard backend using evdev (Wayland/X11 compatible).
    
    This backend conforms to KeyboardBackend protocol through structural
    subtyping. No inheritance required.
    
    Reads keyboard events directly from /dev/input/event* devices and
    translates them to pynput-compatible Key/KeyCode objects for compatibility
    with existing tap detection logic.
    """
    
    def __init__(self, device_path: str | None = None) -> None:
        """Initialize evdev backend.
        
        Args:
            device_path: Optional path to specific input device.
                        If None, will auto-detect keyboard device.
        
        Raises:
            BackendNotAvailableError: If evdev is not available or
                                     initialization fails.
        """
        self.logger = logging.getLogger('common.backend.evdev')
        self.device_path = device_path
        self.device: Any = None  # Will be evdev.InputDevice
        self._stop_event = threading.Event()
        
        # Check if evdev is available
        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev or uv add --optional wayland evdev'
            ) from e
        
        self.logger.debug('EvdevBackend initialized')
    
    def _find_keyboard_device(self) -> Any:
        """Find a keyboard device in /dev/input/.
        
        Returns:
            evdev.InputDevice: The keyboard device to use.
        
        Raises:
            BackendNotAvailableError: If no keyboard found or access denied.
        """
        import evdev
        from evdev import ecodes
        
        # Try to list devices
        try:
            device_paths = evdev.list_devices()
        except PermissionError as e:
            raise BackendNotAvailableError(
                'Permission denied accessing /dev/input/. '
                'Add user to "input" group:\n'
                '  sudo usermod -a -G input $USER\n'
                'Then log out and back in for changes to take effect.'
            ) from e
        
        if not device_paths:
            raise BackendNotAvailableError(
                'No input devices found in /dev/input/. '
                'This might indicate a system configuration issue.'
            )
        
        # Find devices with keyboard capabilities
        keyboards = []
        for path in device_paths:
            try:
                device = evdev.InputDevice(path)
                caps = device.capabilities()
                
                # Check if device has keyboard capabilities
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    # Verify it has common modifier keys (to distinguish from mouse buttons)
                    if (ecodes.KEY_LEFTCTRL in keys or 
                        ecodes.KEY_RIGHTCTRL in keys or
                        ecodes.KEY_LEFTALT in keys or
                        ecodes.KEY_A in keys):
                        keyboards.append(device)
                        self.logger.debug(
                            f'Found keyboard device: {device.name} at {path}'
                        )
            except (OSError, PermissionError) as e:
                # Skip devices we can't access
                self.logger.debug(f'Skipping device {path}: {e}')
                continue
        
        if not keyboards:
            raise BackendNotAvailableError(
                'No keyboard devices found. '
                'Found input devices, but none have keyboard capabilities. '
                'This might indicate a permission or configuration issue.'
            )
        
        # Use the first keyboard found
        selected = keyboards[0]
        self.logger.info(f'Using keyboard device: {selected.name} ({selected.path})')
        return selected
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening for keyboard events using evdev.
        
        This method reads events from /dev/input/event* device, converts them
        to pynput-compatible Key/KeyCode objects, and calls the appropriate
        callback for each event.
        
        Args:
            on_press: Callback for key press events.
                     Receives pynput-compatible Key or KeyCode object.
            on_release: Callback for key release events.
                       Receives pynput-compatible Key or KeyCode object.
        """
        from evdev import categorize, ecodes
        
        # Find or open device
        if self.device_path:
            import evdev
            try:
                self.device = evdev.InputDevice(self.device_path)
                self.logger.info(f'Using specified device: {self.device_path}')
            except (OSError, PermissionError) as e:
                raise BackendNotAvailableError(
                    f'Cannot access device {self.device_path}: {e}'
                ) from e
        else:
            self.device = self._find_keyboard_device()
        
        self.logger.info(f'Starting evdev keyboard listener: {self.device.name}')
        self._stop_event.clear()
        
        # Note: We don't call device.grab() to allow other applications
        # to receive keyboard events (same behavior as pynput)
        
        try:
            # Read events in a loop
            for event in self.device.read_loop():
                # Check if we should stop
                if self._stop_event.is_set():
                    self.logger.debug('Stop event set, exiting read loop')
                    break
                
                # Process only keyboard events (EV_KEY)
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    keycode = key_event.keycode
                    
                    # Convert evdev keycode to pynput Key/KeyCode object
                    try:
                        pynput_key = evdev_to_pynput_key(keycode)
                    except KeyError:
                        # Unknown key - log and skip
                        self.logger.debug(f'Unknown keycode: {keycode}')
                        continue
                    
                    # Call appropriate callback based on key state
                    if key_event.keystate == key_event.key_down:
                        # Key pressed
                        on_press(pynput_key)
                    elif key_event.keystate == key_event.key_up:
                        # Key released
                        on_release(pynput_key)
                    # key_hold (keystate=2) is ignored - we only care about press/release
        
        except OSError as e:
            self.logger.error(f'Error reading from device: {e}')
            raise BackendNotAvailableError(
                f'Error reading keyboard events: {e}'
            ) from e
        
        finally:
            # Clean up
            if self.device:
                try:
                    self.device.close()
                except Exception as e:  # noqa: BLE001
                    self.logger.debug(f'Error closing device: {e}')
                self.device = None
    
    def stop(self) -> None:
        """Stop the evdev listener.
        
        This sets the stop event flag, which causes the read_loop in start()
        to exit. The device is closed in the finally block of start().
        """
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        
        # Close device if still open
        # (usually closed in start() finally block, but just in case)
        if self.device:
            try:
                self.device.close()
            except Exception as e:  # noqa: BLE001
                self.logger.debug(f'Error closing device in stop(): {e}')
            self.device = None
    
    def get_backend_name(self) -> str:
        """Return backend name for logging."""
        return 'evdev (Wayland/X11)'

