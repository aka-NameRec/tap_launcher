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
import queue
import signal
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable
from contextlib import suppress
from evdev import ecodes, categorize

from .base import BackendNotAvailableError
from .key_mapping import evdev_to_key_name, key_name_to_evdev_code


class EvdevBackend:
    """Keyboard backend using evdev (Wayland/X11 compatible).
    
    This backend conforms to KeyboardBackend protocol through structural
    subtyping. No inheritance required.
    
    Reads keyboard events directly from /dev/input/event* devices and
    translates them to pynput-compatible Key/KeyCode objects for compatibility
    with existing tap detection logic.
    """
    
    def _is_modifier_code(self, code: int) -> bool:
        from evdev import ecodes
        return code in {
            ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
            ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
            ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
            ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA,
        }
    
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
        self.devices: list[Any] = []  # List of evdev.InputDevice objects
        self.uinput_device: Any = None  # Will be evdev.UInput
        self._stop_event = threading.Event()
        self._device_threads: list[threading.Thread] = []
        self._event_queue: queue.Queue[tuple[Any, Any]] = queue.Queue(maxsize=1000)
        # Per-device/press key state
        self.suppressed_keys: set[tuple[int, int]] = set()  # (device_id, keycode)
        self.pressed_keys: set[tuple[int, int]] = set()
        self.buffered_presses: set[tuple[int, int]] = set()
        
        # Check if evdev is available
        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev or uv add --optional wayland evdev'
            ) from e
        
        self.logger.debug('EvdevBackend initialized')

    # -------------------- Helper types and utilities --------------------
    @dataclass(slots=True)
    class ParsedEvent:
        device_id: int
        key_ref: tuple[int, int]
        keycode: int
        value: int  # 0 release, 1 press, 2 repeat
        key_name: str | None

    @staticmethod
    def _device_has_keyboard_caps(device: Any) -> bool:
        from evdev import ecodes
        caps = device.capabilities()
        if ecodes.EV_KEY not in caps:
            return False
        keys = caps[ecodes.EV_KEY]
        return (
            ecodes.KEY_LEFTCTRL in keys
            or ecodes.KEY_RIGHTCTRL in keys
            or ecodes.KEY_LEFTALT in keys
            or ecodes.KEY_A in keys
        )

    @staticmethod
    def _is_virtual_uinput(device: Any, path: str) -> bool:
        name_l = device.name.lower()
        path_l = str(path).lower()
        return 'uinput' in name_l or 'uinput' in path_l

    def _emit(self, code: int, value: int) -> None:
        if not self.uinput_device:
            self.logger.error('No uinput device! Events will not be emulated back to system!')
            return
        from evdev import ecodes
        self.uinput_device.write(ecodes.EV_KEY, code, value)
        self.uinput_device.syn()

    def _emit_press(self, code: int) -> None:
        self._emit(code, 1)

    def _emit_release(self, code: int) -> None:
        self._emit(code, 0)

    def _emit_repeat(self, code: int) -> None:
        self._emit(code, 2)

    def _safe_call(self, label: str, fn: Callable[[Any], None], arg: Any) -> None:
        try:
            fn(arg)
        except Exception as e:  # noqa: BLE001
            self.logger.error(f'Error in {label} callback: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())

    def _parse_event(self, device: Any, event: Any) -> 'EvdevBackend.ParsedEvent | None':
        if event.type != ecodes.EV_KEY:
            return None
        key_event = categorize(event)
        keycode = event.code
        value = event.value
        device_id = device.fileno() if hasattr(device, 'fileno') else id(device)
        key_ref = (device_id, keycode)
        key_name: str | None = None
        try:
            key_name = evdev_to_key_name(key_event.keycode)
        except Exception:  # неизвестный keycode — обработаем отдельно
            key_name = None
        return EvdevBackend.ParsedEvent(device_id, key_ref, keycode, value, key_name)

    def _handle_unknown_key(self, parsed: 'EvdevBackend.ParsedEvent') -> bool:
        """Fallback обработка неизвестного keycode. Возвращает True, если обработано."""
        if parsed.key_name is not None:
            return False
        # Регистрация press до эмиссии (для suppression)
        if parsed.value == 1:
            self.pressed_keys.add(parsed.key_ref)
            self._emit_press(parsed.keycode)
            return True
        if parsed.value == 0:
            self._emit_release(parsed.keycode)
            self.pressed_keys.discard(parsed.key_ref)
            self.suppressed_keys.discard(parsed.key_ref)
            return True
        if parsed.value == 2:
            self._emit_repeat(parsed.keycode)
            return True
        return True

    def _handle_suppressed(self, key_ref: tuple[int, int], value: int) -> bool:
        if self._should_suppress_event(key_ref, value):
            # На release также очищаем слоты
            if value == 0:
                self.pressed_keys.discard(key_ref)
                self.buffered_presses.discard(key_ref)
                self.suppressed_keys.discard(key_ref)
            return True
        return False
        
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
        
        if not self.devices:
            raise RuntimeError('Cannot create uinput: no devices initialized')
        
        try:
            from evdev import UInput, ecodes
            
            # Combine capabilities from all devices
            all_keys: set[int] = set()
            for device in self.devices:
                if ecodes.EV_KEY in device.capabilities():
                    all_keys.update(device.capabilities()[ecodes.EV_KEY])
            
            capabilities = {
                ecodes.EV_KEY: list(all_keys)
            }
            self.uinput_device = UInput(capabilities)
            self.logger.info('Created uinput virtual device for event emulation')
        except OSError as e:
            self.logger.error(
                f'Failed to create uinput device: {e}. '
                f'This is required for key suppression. See README.md (UInput setup).'
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
                if not self._device_has_keyboard_caps(device):
                    continue
                if self._is_virtual_uinput(device, path):
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
        
        # Return all physical keyboards (or virtual if none found)
        selected = physical_keyboards if physical_keyboards else virtual_keyboards
        device_type = 'physical' if physical_keyboards else 'virtual'
        self.logger.info(
            f'Found {len(selected)} {device_type} keyboard device(s)'
        )
        for device in selected:
            self.logger.info(f'  - {device.name} ({device.path})')
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
                if not self._device_has_keyboard_caps(device):
                    continue
                device_name_lower = device.name.lower()
                if name_lower in device_name_lower:
                    matching_devices.append(device)
            except (OSError, PermissionError):
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
        selected = physical if physical else matching_devices
        
        self.logger.info(
            f'Found {len(selected)} keyboard device(s) matching "{name}"'
        )
        for device in selected:
            self.logger.info(f'  - {device.name} ({device.path})')
        return selected
    
    def _cleanup_devices(self) -> None:
        """Internal cleanup method to close all devices."""
        # Stop all device threads
        self._stop_event.set()
        
        # Wait for threads to finish
        for thread in self._device_threads:
            if thread.is_alive():
                with suppress(Exception):
                    thread.join(timeout=1.0)
        self._device_threads.clear()
        
        # Ungrab and close all devices
        for device in self.devices:
            with suppress(Exception):
                if hasattr(device, 'ungrab'):
                    device.ungrab()
            with suppress(Exception):
                device.close()
        self.devices.clear()
        
        if self.uinput_device:
            with suppress(Exception):
                self.uinput_device.close()
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
        import evdev
        
        # Find or open devices
        if self.device_name:
            # Search by device name (can match multiple devices)
            devices_found = self._find_keyboard_by_name(self.device_name)
            if not devices_found:
                raise BackendNotAvailableError(
                    f'No keyboard device found matching name "{self.device_name}"'
                )
            self.devices = devices_found if isinstance(devices_found, list) else [devices_found]
        elif self.device_path:
            # Use specified path (single device)
            try:
                device = evdev.InputDevice(self.device_path)
                self.devices = [device]
                self.logger.info(f'Using specified device path: {self.device_path}')
            except (OSError, PermissionError) as e:
                raise BackendNotAvailableError(
                    f'Cannot access device {self.device_path}: {e}'
                ) from e
        else:
            # Auto-detect: use ALL physical keyboards
            devices_found = self._find_keyboard_device()
            if not devices_found:
                raise BackendNotAvailableError('No keyboard devices found')
            self.devices = devices_found if isinstance(devices_found, list) else [devices_found]
        
        # Log device information for user visibility
        if len(self.devices) == 1:
            device_info = f'{self.devices[0].name} ({self.devices[0].path})'
            self.logger.info(f'Using keyboard device: {device_info}')
        else:
            self.logger.info(f'Using {len(self.devices)} keyboard device(s)')
            for device in self.devices:
                self.logger.info(f'  - {device.name} ({device.path})')
        
        self._stop_event.clear()
        
        # Grab all devices - intercept all events before they reach system
        grabbed_devices = []
        try:
            for device in self.devices:
                try:
                    device.grab()
                    grabbed_devices.append(device)
                    self.logger.debug(f'Device grabbed: {device.name}')
                except OSError as e:
                    self.logger.warning(
                        f'Failed to grab device {device.name}: {e}. '
                        f'Events may reach system before processing.'
                    )
            
            if not grabbed_devices:
                raise BackendNotAvailableError(
                    'Failed to grab any keyboard devices. All devices may be busy.'
                )
        except Exception as e:
            # Clean up any grabbed devices
            for device in grabbed_devices:
                with suppress(Exception):
                    device.ungrab()
            raise
        
        # Always create uinput for emulating events back to system
        try:
            self._create_uinput_device()
        except OSError:
            # If uinput creation fails, we can't continue
            # Clean up grabbed devices
            for device in grabbed_devices:
                with suppress(Exception):
                    device.ungrab()
            raise BackendNotAvailableError(
                'Failed to create uinput device. This is required for event emulation. '
                'See setup instructions for uinput permissions.'
            )
        
        try:
            # Start reading threads for all devices
            self.logger.info(f'Starting event read threads for {len(self.devices)} device(s)...')
            for device in self.devices:
                thread = threading.Thread(
                    target=self._read_device_loop,
                    args=(device,),
                    daemon=True,
                    name=f'evdev-read-{device.name}'
                )
                thread.start()
                self._device_threads.append(thread)
            
            # Main event processing loop - read from queue
            event_count = 0
            self.logger.info('Starting main event processing loop...')
            while not self._stop_event.is_set():
                try:
                    # Get event from queue (with timeout to check stop event)
                    device, event = self._event_queue.get(timeout=0.1)
                except queue.Empty:
                    # Timeout - check stop event and continue
                    continue
                
                try:
                    event_count += 1
                    if event_count == 1:
                        self.logger.info('First event received - event loop is working')
                    
                    parsed = self._parse_event(device, event)
                    if not parsed:
                        if event_count <= 3:
                            self.logger.debug(f'Non-keyboard event: type={event.type}, code={event.code}')
                        continue
                    key_ref = parsed.key_ref
                    keycode = parsed.keycode
                    value = parsed.value
                    key_name = parsed.key_name
                    if event_count <= 5:
                        self.logger.debug(
                            f'Keyboard event #{event_count}: code={keycode}, value={value}, name={key_name}'
                        )
                    # Unknown key fallback
                    if self._handle_unknown_key(parsed):
                        continue
                    
                    # Process event based on state
                    if value == 1:  # Press
                        # Register press before callback to allow synchronous suppression to target this press
                        self.pressed_keys.add(key_ref)
                        # CRITICAL: Call callback BEFORE emulation
                        # This allows suppression to happen before event reaches system
                        if event_count <= 5:
                            self.logger.debug(f'Calling on_press({key_name})')
                        self._safe_call('on_press', on_press, key_name)
                            # Continue processing - don't let callback errors break event loop
                        
                        # After callback, check if we should suppress
                        if self._handle_suppressed(key_ref, value):
                            self.logger.debug(f'Suppressing press: keycode={keycode}')
                            continue  # Don't emulate
                        
                        # Emulate press immediately with syn for all keys
                        if event_count <= 5:
                            self.logger.debug(f'Emulating press for keycode {keycode}')
                        self._emit_press(keycode)
                        # pressed_keys was added before; keep it until release
                    
                    elif value == 0:  # Release
                        # Call callback
                        self._safe_call('on_release', on_release, key_name)
                            # Continue processing - don't let callback errors break event loop
                        
                        # Check suppression AFTER callback
                        if self._handle_suppressed(key_ref, value):
                            self.logger.debug(f'Suppressing release: keycode={keycode}')
                            continue  # Don't emulate
                        
                        # Emulate release immediately with syn for all keys
                        self._emit_release(keycode)
                        self.pressed_keys.discard(key_ref)
                        self.buffered_presses.discard(key_ref)
                    
                    elif value == 2:  # Repeat
                        # Check suppression
                        if self._handle_suppressed(key_ref, value):
                            self.logger.debug(f'Suppressing repeat: keycode={keycode}')
                            continue
                        
                        # Emulate repeat - send with sync
                        self._emit_repeat(keycode)
                
                except Exception as e:
                    # Error processing single event - log and continue
                    self.logger.error(f'Error processing event: {e}')
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    continue
        
        except Exception as e:
            self.logger.error(f'Error in main event loop: {e}')
            raise BackendNotAvailableError(
                f'Error processing keyboard events: {e}'
            ) from e
        
        finally:
            # Clean up devices
            self._cleanup_devices()
    
    def _read_device_loop(self, device: Any) -> None:
        """Read events from a single device in a separate thread.
        
        This method runs in a background thread and reads events from one
        keyboard device, putting them into the shared event queue.
        
        Args:
            device: evdev.InputDevice to read from
        """
        from evdev import ecodes
        
        try:
            for event in device.read_loop():
                if self._stop_event.is_set():
                    break
                
                # Put event in queue for main thread to process
                try:
                    self._event_queue.put((device, event), timeout=0.1)
                except queue.Full:
                    self.logger.warning(
                        f'Event queue full, dropping event from {device.name}'
                    )
        except OSError as e:
            self.logger.error(f'Error reading from device {device.name}: {e}')
            # Device may have been disconnected - stop reading from it
        except Exception as e:
            self.logger.error(
                f'Unexpected error in read loop for {device.name}: {e}'
            )
    
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
    
    def _should_suppress_event(self, key_ref: tuple[int, int], value: int) -> bool:
        """Determine if event should be suppressed.
        
        Args:
            keycode: Evdev key code
            value: Event value (0=release, 1=press, 2=repeat)
        
        Returns:
            True if event should be suppressed
        """
        if key_ref in self.suppressed_keys:
            # Suppress all events (press, release, repeat)
            if value == 0:  # Release - remove after suppression (one-time)
                self.suppressed_keys.discard(key_ref)
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
        try:
            keycode = key_name_to_evdev_code(key)
            # Suppress all presses for this key that are currently active,
            # i.e. mark all pressed_keys that match code across all devices
            to_mark = [ref for ref in self.pressed_keys if ref[1] == keycode]
            for ref in to_mark:
                self.suppressed_keys.add(ref)
            self.logger.debug(f'Suppressing keycode {keycode} (all active presses: {len(to_mark)})')
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

