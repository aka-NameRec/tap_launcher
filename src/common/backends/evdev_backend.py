"""Evdev-based keyboard backend for Wayland.

This backend reads keyboard events directly from /dev/input/event* devices
using the evdev library. It works on both X11 and Wayland, but is primarily
intended for Wayland where pynput is not available.

Requires:
- evdev library installed
- User in 'input' group or appropriate permissions for /dev/input/
"""

import atexit
import logging
import os
import signal
import sys
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
    
    def __init__(
        self,
        device_path: str | None = None,
        device_name: str | None = None
    ) -> None:
        """Initialize evdev backend.
        
        Args:
            device_path: Optional path to specific input device.
                        If None, will auto-detect keyboard device.
            device_name: Optional name of the keyboard device to use.
                        If provided, will search for device with matching name.
                        Takes precedence over device_path if both are provided.
        
        Raises:
            BackendNotAvailableError: If evdev is not available or
                                     initialization fails.
        """
        self.logger = logging.getLogger('common.backend.evdev')
        self.device_path = device_path
        self.device_name = device_name
        self.device: Any = None  # Will be evdev.InputDevice
        self.uinput_device: Any = None  # Will be evdev.UInput
        self._stop_event = threading.Event()
        
        # Key suppression state
        self.suppressed_keycodes: set[int] = set()  # evdev keycodes to suppress
        self.pressed_keycodes: set[int] = set()  # Currently pressed keycodes
        self.buffered_presses: dict[int, bool] = {}  # Press events waiting for release
        
        # Check if evdev is available
        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev or uv add --optional wayland evdev'
            ) from e
        
        self.logger.debug('EvdevBackend initialized')
        
        # Register cleanup handlers to ensure devices are closed even on crash
        # Store reference to self in module-level set to prevent garbage collection
        if not hasattr(EvdevBackend, '_instances'):
            EvdevBackend._instances = set()
        EvdevBackend._instances.add(self)
        
        # Register cleanup function (only once)
        if not hasattr(EvdevBackend, '_cleanup_registered'):
            atexit.register(EvdevBackend._global_cleanup)
            
            def signal_handler(signum: int, frame: Any) -> None:
                """Handle signals for cleanup."""
                EvdevBackend._global_cleanup()
                # Re-raise default handler
                signal.signal(signum, signal.SIG_DFL)
                os.kill(os.getpid(), signum)
            
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            EvdevBackend._cleanup_registered = True
    
    def _create_uinput_device(self) -> None:
        """Create uinput device for event emulation.
        
        Always created when start() is called, as we always grab the device
        and need to emulate all events back to the system.
        
        Raises:
            RuntimeError: If device is not initialized
            OSError: If uinput cannot be created (permissions)
        """
        if self.uinput_device is not None:
            return
        
        if self.device is None:
            raise RuntimeError('Cannot create uinput: device not initialized')
        
        try:
            from evdev import UInput, ecodes
            
            capabilities = {
                ecodes.EV_KEY: self.device.capabilities()[ecodes.EV_KEY]
            }
            self.uinput_device = UInput(capabilities)
            self.logger.info('Created uinput virtual device for event emulation')
        except OSError as e:
            self.logger.error(
                f'Failed to create uinput device: {e}\n'
                f'This is required for key suppression. '
                f'See docs/20251029-200001-proposal-key_suppression/'
                f'20251029-201331-doc-SETUP-PERMISSIONS.md for setup instructions.'
            )
            raise
    
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
        # Separate physical keyboards from virtual uinput devices
        physical_keyboards = []
        virtual_keyboards = []
        
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
                        
                        # Filter out virtual uinput devices (they have "uinput" in path or name)
                        device_name_lower = device.name.lower()
                        path_lower = str(path).lower()
                        if 'uinput' in device_name_lower or 'uinput' in path_lower:
                            virtual_keyboards.append(device)
                            self.logger.debug(
                                f'Found virtual keyboard device: {device.name} at {path} (skipping)'
                            )
                        else:
                            physical_keyboards.append(device)
                            self.logger.debug(
                                f'Found physical keyboard device: {device.name} at {path}'
                            )
            except (OSError, PermissionError) as e:
                # Skip devices we can't access
                self.logger.debug(f'Skipping device {path}: {e}')
                continue
        
        # Prefer physical keyboards, fallback to virtual if none found
        keyboards = physical_keyboards if physical_keyboards else virtual_keyboards
        
        if not keyboards:
            raise BackendNotAvailableError(
                'No keyboard devices found. '
                'Found input devices, but none have keyboard capabilities. '
                'This might indicate a permission or configuration issue.'
            )
        
        # Use the first keyboard found (preferably physical)
        selected = keyboards[0]
        device_type = 'physical' if physical_keyboards else 'virtual'
        self.logger.info(
            f'Using {device_type} keyboard device: {selected.name} ({selected.path})'
        )
        return selected
    
    def _find_keyboard_by_name(self, name: str) -> Any:
        """Find keyboard device by name.
        
        Args:
            name: Device name to search for (case-insensitive partial match)
        
        Returns:
            evdev.InputDevice: The keyboard device with matching name.
        
        Raises:
            BackendNotAvailableError: If no device with matching name found.
        """
        import evdev
        from evdev import ecodes
        
        # List all devices
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
        
        name_lower = name.lower()
        matching_devices = []
        
        # Search for devices with matching name
        for path in device_paths:
            try:
                device = evdev.InputDevice(path)
                caps = device.capabilities()
                
                # Check if device has keyboard capabilities
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    if (ecodes.KEY_LEFTCTRL in keys or 
                        ecodes.KEY_RIGHTCTRL in keys or
                        ecodes.KEY_LEFTALT in keys or
                        ecodes.KEY_A in keys):
                        
                        # Check if name matches (case-insensitive partial match)
                        device_name_lower = device.name.lower()
                        if name_lower in device_name_lower:
                            matching_devices.append(device)
                            
            except (OSError, PermissionError):
                # Skip devices we can't access
                continue
        
        if not matching_devices:
            # List available devices for user reference
            available = []
            for path in device_paths:
                try:
                    device = evdev.InputDevice(path)
                    caps = device.capabilities()
                    if ecodes.EV_KEY in caps:
                        keys = caps[ecodes.EV_KEY]
                        if (ecodes.KEY_LEFTCTRL in keys or 
                            ecodes.KEY_RIGHTCTRL in keys or
                            ecodes.KEY_LEFTALT in keys or
                            ecodes.KEY_A in keys):
                            available.append(device.name)
                except (OSError, PermissionError):
                    continue
            
            available_str = '\n  - '.join(available) if available else '(none found)'
            raise BackendNotAvailableError(
                f'No keyboard device found matching name "{name}".\n'
                f'Available keyboard devices:\n  - {available_str}'
            )
        
        # If multiple matches, prefer physical over virtual
        physical = [d for d in matching_devices if 'uinput' not in d.name.lower()]
        selected = physical[0] if physical else matching_devices[0]
        
        self.logger.info(
            f'Found keyboard device matching "{name}": {selected.name} ({selected.path})'
        )
        return selected
    
    def _cleanup_devices(self) -> None:
        """Internal cleanup method to close all devices."""
        if self.device:
            try:
                if hasattr(self.device, 'ungrab'):
                    self.device.ungrab()
            except Exception:  # noqa: BLE001
                pass
            try:
                self.device.close()
            except Exception:  # noqa: BLE001
                pass
            self.device = None
        
        if self.uinput_device:
            try:
                self.uinput_device.close()
            except Exception:  # noqa: BLE001
                pass
            self.uinput_device = None
    
    @staticmethod
    def _global_cleanup() -> None:
        """Global cleanup for all EvdevBackend instances."""
        if hasattr(EvdevBackend, '_instances'):
            for instance in list(EvdevBackend._instances):
                try:
                    instance._cleanup_devices()
                except Exception:  # noqa: BLE001
                    pass
    
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
        if self.device_name:
            # Search by device name
            self.device = self._find_keyboard_by_name(self.device_name)
        elif self.device_path:
            # Use specified path
            import evdev
            try:
                self.device = evdev.InputDevice(self.device_path)
                self.logger.info(f'Using specified device path: {self.device_path}')
            except (OSError, PermissionError) as e:
                raise BackendNotAvailableError(
                    f'Cannot access device {self.device_path}: {e}'
                ) from e
        else:
            # Auto-detect
            self.device = self._find_keyboard_device()
        
        # Log device information for user visibility
        device_info = f'{self.device.name} ({self.device.path})'
        self.logger.info(f'Starting evdev keyboard listener: {device_info}')
        # Also print to stderr for tap-detector visibility (when not daemonized)
        import sys
        if sys.stderr.isatty():
            print(f'📍 Using keyboard device: {self.device.name}', file=sys.stderr)
        self._stop_event.clear()
        
        # Grab device - intercept all events before they reach system
        try:
            self.device.grab()
            self.logger.debug('Device grabbed, events will be intercepted')
        except OSError as e:
            self.logger.warning(f'Failed to grab device: {e}. Events may reach system before processing.')
        
        # Always create uinput for emulating events back to system
        try:
            self._create_uinput_device()
        except OSError:
            # If uinput creation fails, we can't continue
            # Clean up grabbed device
            try:
                self.device.ungrab()
            except Exception:  # noqa: BLE001
                pass
            raise BackendNotAvailableError(
                'Failed to create uinput device. This is required for event emulation. '
                'See setup instructions for uinput permissions.'
            )
        
        try:
            self.logger.info('Starting event read loop...')
            event_count = 0
            # Read events in a loop
            for event in self.device.read_loop():
                event_count += 1
                if event_count == 1:
                    self.logger.info('First event received - event loop is working')
                
                # Check if we should stop
                if self._stop_event.is_set():
                    self.logger.debug('Stop event set, exiting read loop')
                    break
                
                # Process only keyboard events (EV_KEY)
                if event.type != ecodes.EV_KEY:
                    if event_count <= 3:
                        self.logger.debug(f'Non-keyboard event: type={event.type}, code={event.code}')
                    continue
                
                key_event = categorize(event)
                keycode = event.code
                value = event.value  # 0=release, 1=press, 2=repeat
                
                if event_count <= 5:
                    self.logger.debug(
                        f'Keyboard event #{event_count}: keycode={keycode}, '
                        f'keycode_str={key_event.keycode}, value={value}'
                    )
                
                # Convert evdev keycode to pynput Key/KeyCode object
                pynput_key = None
                try:
                    pynput_key = evdev_to_pynput_key(key_event.keycode)
                except KeyError as e:
                    # Unknown keycode - but we MUST emulate it back to system
                    # because device.grab() means we intercepted it before system
                    self.logger.warning(
                        f'Unknown keycode: {key_event.keycode} (raw code: {keycode}, value: {value}). '
                        f'Emulating raw keycode to system. Error: {e}'
                    )
                    # Fallback: emulate event using raw keycode without callback
                    # This ensures the key reaches the system even if we can't map it
                    if value == 1:  # Press
                        if self.uinput_device:
                            self.uinput_device.write(ecodes.EV_KEY, keycode, 1)
                            self.buffered_presses[keycode] = True
                            self.pressed_keycodes.add(keycode)
                        continue  # Skip callback (can't convert to pynput)
                    elif value == 0:  # Release
                        if self.uinput_device:
                            if keycode in self.buffered_presses:
                                self.uinput_device.write(ecodes.EV_KEY, keycode, 0)
                                self.uinput_device.syn()
                                self.buffered_presses.pop(keycode, None)
                        self.pressed_keycodes.discard(keycode)
                        continue  # Skip callback
                    elif value == 2:  # Repeat
                        if self.uinput_device:
                            self.uinput_device.write(ecodes.EV_KEY, keycode, 2)
                            self.uinput_device.syn()
                        continue  # Skip callback
                except Exception as e:
                    # Unexpected error during conversion
                    self.logger.error(
                        f'Error converting keycode {key_event.keycode}: {e}. '
                        f'Event code: {keycode}, value: {value}. '
                        f'Emulating raw keycode to prevent key loss.'
                    )
                    # Fallback: try to emulate even on unexpected errors
                    if value == 1:  # Press
                        if self.uinput_device:
                            self.uinput_device.write(ecodes.EV_KEY, keycode, 1)
                            self.buffered_presses[keycode] = True
                            self.pressed_keycodes.add(keycode)
                    elif value == 0:  # Release
                        if self.uinput_device:
                            if keycode in self.buffered_presses:
                                self.uinput_device.write(ecodes.EV_KEY, keycode, 0)
                                self.uinput_device.syn()
                                self.buffered_presses.pop(keycode, None)
                        self.pressed_keycodes.discard(keycode)
                    elif value == 2:  # Repeat
                        if self.uinput_device:
                            self.uinput_device.write(ecodes.EV_KEY, keycode, 2)
                            self.uinput_device.syn()
                    continue  # Skip callback
                
                # Process event based on state
                if value == 1:  # Press
                    # CRITICAL: Call callback BEFORE emulation
                    # This allows suppression to happen before event reaches system
                    try:
                        if event_count <= 5:
                            self.logger.debug(f'Calling on_press({pynput_key})')
                        on_press(pynput_key)
                        if event_count <= 5:
                            self.logger.debug(f'on_press returned successfully')
                    except Exception as e:
                        self.logger.error(f'Error in on_press callback: {e}')
                        import traceback
                        self.logger.debug(traceback.format_exc())
                        # Continue processing - don't let callback errors break event loop
                    
                    # After callback, check if we should suppress
                    if self._should_suppress_event(keycode, value):
                        self.logger.debug(f'Suppressing press: keycode={keycode}')
                        self.pressed_keycodes.add(keycode)
                        continue  # Don't emulate
                    
                    # Emulate press - accumulate in buffer, DON'T sync yet
                    if self.uinput_device:
                        if event_count <= 5:
                            self.logger.debug(f'Emulating press for keycode {keycode}')
                        self.uinput_device.write(ecodes.EV_KEY, keycode, 1)
                        self.buffered_presses[keycode] = True
                        self.pressed_keycodes.add(keycode)
                    else:
                        self.logger.error('No uinput device! Events will not be emulated back to system!')
                
                elif value == 0:  # Release
                    # Call callback
                    try:
                        on_release(pynput_key)
                    except Exception as e:
                        self.logger.error(f'Error in on_release callback: {e}')
                        import traceback
                        self.logger.debug(traceback.format_exc())
                        # Continue processing - don't let callback errors break event loop
                    
                    # Check suppression AFTER callback
                    if self._should_suppress_event(keycode, value):
                        self.logger.debug(f'Suppressing release: keycode={keycode}')
                        self.pressed_keycodes.discard(keycode)
                        continue  # Don't emulate
                    
                    # Emulate release - send complete packet [Press, Release]
                    if self.uinput_device:
                        if keycode in self.buffered_presses:
                            # Press was emulated - send complete packet
                            self.uinput_device.write(ecodes.EV_KEY, keycode, 0)
                            self.uinput_device.syn()  # CRITICAL: sync here
                            self.buffered_presses.pop(keycode, None)
                        # If press was suppressed, don't emulate release either
                        self.pressed_keycodes.discard(keycode)
                
                elif value == 2:  # Repeat
                    # Check suppression
                    if self._should_suppress_event(keycode, value):
                        self.logger.debug(f'Suppressing repeat: keycode={keycode}')
                        continue
                    
                    # Emulate repeat - send with sync
                    if self.uinput_device:
                        self.uinput_device.write(ecodes.EV_KEY, keycode, 2)
                        self.uinput_device.syn()
        
        except OSError as e:
            self.logger.error(f'Error reading from device: {e}')
            raise BackendNotAvailableError(
                f'Error reading keyboard events: {e}'
            ) from e
        
        finally:
            # Clean up devices
            self._cleanup_devices()
    
    def stop(self) -> None:
        """Stop the evdev listener.
        
        This sets the stop event flag, which causes the read_loop in start()
        to exit. The device is closed in the finally block of start().
        """
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        
        # Close device if still open
        # (usually closed in start() finally block, but just in case)
        self._cleanup_devices()
        
        # Remove from instances set when stopped
        if hasattr(EvdevBackend, '_instances'):
            EvdevBackend._instances.discard(self)
    
    def _should_suppress_event(self, keycode: int, value: int) -> bool:
        """Determine if event should be suppressed.
        
        Args:
            keycode: Evdev key code
            value: Event value (0=release, 1=press, 2=repeat)
        
        Returns:
            True if event should be suppressed
        """
        if keycode in self.suppressed_keycodes:
            # Suppress all events (press, release, repeat)
            if value == 0:  # Release - remove after suppression (one-time)
                self.suppressed_keycodes.discard(keycode)
            return True
        
        return False
    
    def suppress_key(self, key: Any) -> None:
        """Suppress a key after tap detection.
        
        This method is called when a tap is detected and matched to a hotkey.
        The trigger_key (non-modifier) should be suppressed to prevent it from
        reaching other applications.
        
        Args:
            key: pynput Key/KeyCode object to suppress (typically trigger_key)
        """
        from .key_mapping import pynput_to_evdev_code
        
        try:
            keycode = pynput_to_evdev_code(key)
            self.suppressed_keycodes.add(keycode)
            self.logger.debug(f'Suppressing keycode {keycode} (key: {key})')
        except KeyError:
            self.logger.warning(f'Cannot suppress key {key}: no evdev mapping')
    
    def emit_key_event(self, key: Any, is_press: bool) -> None:
        """Emit a keyboard event (placeholder - not implemented yet).
        
        TODO: Implement using uinput after permissions are configured.
        
        Args:
            key: The key to emit (pynput Key or KeyCode object)
            is_press: True for press, False for release
        """
        self.logger.debug(f'emit_key_event called but not implemented yet: {key}, is_press={is_press}')
    
    def get_backend_name(self) -> str:
        """Return backend name for logging."""
        return 'evdev (Wayland/X11)'

