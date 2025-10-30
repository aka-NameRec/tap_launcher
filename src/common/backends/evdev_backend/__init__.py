"""Evdev backend package.

Exports EvdevBackend while allowing internal helpers/modules to evolve.
"""

# For now, we keep the implementation here to preserve behavior.
# In subsequent steps, we will extract DeviceManager, EventRouter, KeyState,
# UInputWriter, and Processor into dedicated modules inside this package.

from __future__ import annotations

# Reuse the previous single-file implementation contents
# by importing from the legacy module path if needed.

# NOTE: Implementation is inlined below (copied from the prior module)
# so external imports `from common.backends.evdev_backend import EvdevBackend`
# remain stable.

import atexit
import logging
import os
import queue
import signal
from dataclasses import dataclass
from typing import Any, Callable
from contextlib import suppress
from evdev import ecodes, categorize

from ..base import BackendNotAvailableError
from ..key_mapping import evdev_to_key_name, key_name_to_evdev_code
from .types import ParsedEvent
from .uinput_writer import UInputWriter
from .key_state import KeyState
from .device_manager import DeviceManager
from .event_router import EventRouter
from .processor import EventProcessor
from .parser import parse_event
from .types import ParsedEvent
from .uinput_writer import UInputWriter
from .key_state import KeyState


class EvdevBackend:
    """Keyboard backend using evdev (Wayland/X11 compatible)."""

    def __init__(
        self,
        device_path: str | None = None,
        device_name: str | None = None
    ) -> None:
        self.logger = logging.getLogger('common.backend.evdev')
        self.device_path = device_path
        self.device_name = device_name
        self.devices: list[Any] = []
        self.uinput_device: UInputWriter | None = None
        import threading
        self._stop_event = threading.Event()
        self._device_threads: list[threading.Thread] = []
        self._event_queue: queue.Queue[tuple[Any, Any]] = queue.Queue(maxsize=1000)

        # Per-device/press key state
        self.state = KeyState()

        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev or uv add evdev'
            ) from e

        self.logger.debug('EvdevBackend initialized')

        # Global cleanup
        if not hasattr(EvdevBackend, '_instances'):
            EvdevBackend._instances = set()
        EvdevBackend._instances.add(self)
        if not hasattr(EvdevBackend, '_cleanup_registered'):
            atexit.register(EvdevBackend._global_cleanup)

            def signal_handler(signum: int, frame: Any) -> None:  # noqa: ARG001
                EvdevBackend._global_cleanup()
                signal.signal(signum, signal.SIG_DFL)
                os.kill(os.getpid(), signum)

            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            EvdevBackend._cleanup_registered = True

    # -------------------- Helper types and utilities --------------------
    @staticmethod
    def _device_has_keyboard_caps(device: Any) -> bool:
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

    def _parse_event(self, device: Any, event: Any) -> ParsedEvent | None:
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
        except Exception:
            key_name = None
        return ParsedEvent(device_id, key_ref, keycode, value, key_name)

    # Unknown-key handling is delegated to EventProcessor.handle_unknown

    def _handle_suppressed(self, key_ref: tuple[int, int], value: int) -> bool:
        return self.state.is_suppressed(key_ref, value)

    # -------------- uinput creation --------------
    def _create_uinput_device(self) -> None:
        if self.uinput_device is not None:
            return
        if not self.devices:
            raise RuntimeError('Cannot create uinput: no devices initialized')
        try:
            self.uinput_device = UInputWriter.create_from_devices(self.devices, self.logger)
        except OSError as e:
            self.logger.error(
                f'Failed to create uinput device: {e}. '
                f'This is required for key suppression. See README.md (UInput setup).'
            )
            raise

    # -------------- device discovery --------------
    def _find_keyboard_device(self) -> Any:
        import evdev
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
                self.logger.debug(f'Skipping device {path}: {e}')
                continue
        keyboards = physical_keyboards if physical_keyboards else virtual_keyboards
        if not keyboards:
            raise BackendNotAvailableError(
                'No keyboard devices found. '
                'Found input devices, but none have keyboard capabilities. '
                'This might indicate a permission or configuration issue.'
            )
        selected = physical_keyboards if physical_keyboards else virtual_keyboards
        device_type = 'physical' if physical_keyboards else 'virtual'
        self.logger.info(f'Found {len(selected)} {device_type} keyboard device(s)')
        for device in selected:
            self.logger.info(f'  - {device.name} ({device.path})')
        return selected

    def _find_keyboard_by_name(self, name: str) -> Any:
        import evdev
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
            available = []
            for path in device_paths:
                try:
                    device = evdev.InputDevice(path)
                    if self._device_has_keyboard_caps(device):
                        available.append(device.name)
                except (OSError, PermissionError):
                    continue
            available_str = '\n  - '.join(available) if available else '(none found)'
            raise BackendNotAvailableError(
                f'No keyboard device found matching name "{name}".\n'
                f'Available keyboard devices:\n  - {available_str}'
            )
        physical = [d for d in matching_devices if 'uinput' not in d.name.lower()]
        selected = physical if physical else matching_devices
        self.logger.info(
            f'Found {len(selected)} keyboard device(s) matching "{name}"'
        )
        for device in selected:
            self.logger.info(f'  - {device.name} ({device.path})')
        return selected

    @staticmethod
    def _global_cleanup() -> None:
        if hasattr(EvdevBackend, '_instances'):
            for instance in list(EvdevBackend._instances):
                try:
                    instance._cleanup_devices()
                except Exception:  # noqa: BLE001
                    pass

    def _cleanup_devices(self) -> None:
        self._stop_event.set()
        for thread in self._device_threads:
            if thread.is_alive():
                with suppress(Exception):
                    thread.join(timeout=1.0)
        self._device_threads.clear()
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

    # -------------------- Public API --------------------
    def start(self, on_press: Callable[[Any], None], on_release: Callable[[Any], None]) -> None:
        import evdev
        # Resolve devices via DeviceManager
        dm = DeviceManager(self.logger)
        if self.device_name:
            devices_found = dm.discover_by_name(self.device_name)
            if not devices_found:
                raise BackendNotAvailableError(
                    f'No keyboard device found matching name "{self.device_name}"'
                )
            self.devices = devices_found
        elif self.device_path:
            try:
                device = evdev.InputDevice(self.device_path)
                self.devices = [device]
                self.logger.info(f'Using specified device path: {self.device_path}')
            except (OSError, PermissionError) as e:
                raise BackendNotAvailableError(
                    f'Cannot access device {self.device_path}: {e}'
                ) from e
        else:
            devices_found = dm.discover_auto()
            if not devices_found:
                raise BackendNotAvailableError('No keyboard devices found')
            self.devices = devices_found

        if len(self.devices) == 1:
            device_info = f'{self.devices[0].name} ({self.devices[0].path})'
            self.logger.info(f'Using keyboard device: {device_info}')
        else:
            self.logger.info(f'Using {len(self.devices)} keyboard device(s)')
            for device in self.devices:
                self.logger.info(f'  - {device.name} ({device.path})')

        self._stop_event.clear()

        # Grab devices
        grabbed_devices = dm.grab_all(self.devices)
        if not grabbed_devices:
            raise BackendNotAvailableError('Failed to grab any keyboard devices. All devices may be busy.')

        # Create uinput
        try:
            self._create_uinput_device()
        except OSError:
            for device in grabbed_devices:
                with suppress(Exception):
                    device.ungrab()
            raise BackendNotAvailableError(
                'Failed to create uinput device. This is required for event emulation. '
                'See setup instructions for uinput permissions.'
            )

        try:
            # Start reader threads via DeviceManager
            self.logger.info(f'Starting event read threads for {len(self.devices)} device(s)...')
            self._device_threads = dm.start_reader_threads(self.devices, self._event_queue.put, self._stop_event)

            # Run router with processor
            processor = EventProcessor(
                logger=self.logger,
                state=self.state,
                emitter=self.uinput_device,
                handle_suppressed=self._handle_suppressed,
                safe_call=self._safe_call,
            )
            router = EventRouter(
                logger=self.logger,
                parse_event=parse_event,
                handle_unknown=processor.handle_unknown,
                handle_value=lambda evt: processor.process(evt, on_press, on_release),
            )
            router.run(self._event_queue.get, self._stop_event)
        except Exception as e:
            self.logger.error(f'Error in main event loop: {e}')
            raise BackendNotAvailableError(
                f'Error processing keyboard events: {e}'
            ) from e
        finally:
            self._cleanup_devices()

    def _read_device_loop(self, device: Any) -> None:
        try:
            for event in device.read_loop():
                if self._stop_event.is_set():
                    break
                try:
                    self._event_queue.put((device, event), timeout=0.1)
                except queue.Full:
                    self.logger.warning(
                        f'Event queue full, dropping event from {device.name}'
                    )
        except OSError as e:
            self.logger.error(f'Error reading from device {device.name}: {e}')
        except Exception as e:  # noqa: BLE001
            self.logger.error(
                f'Unexpected error in read loop for {device.name}: {e}'
            )

    def stop(self) -> None:
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        self._cleanup_devices()
        if hasattr(EvdevBackend, '_instances'):
            EvdevBackend._instances.discard(self)

    def _should_suppress_event(self, key_ref: tuple[int, int], value: int) -> bool:
        if key_ref in self.suppressed_keys:
            if value == 0:
                self.suppressed_keys.discard(key_ref)
            return True
        return False

    def suppress_key(self, key: Any) -> None:
        try:
            keycode = key_name_to_evdev_code(key)
            to_mark = [ref for ref in self.pressed_keys if ref[1] == keycode]
            for ref in to_mark:
                self.suppressed_keys.add(ref)
            self.logger.debug(f'Suppressing keycode {keycode} (all active presses: {len(to_mark)})')
        except KeyError:
            self.logger.warning(f'Cannot suppress key {key}: no evdev mapping')


