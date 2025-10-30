"""Evdev backend package.

Exports EvdevBackend while allowing internal helpers/modules to evolve.
"""

from __future__ import annotations

import atexit
import os
import queue
import signal
from typing import Any, Callable
from contextlib import suppress

from ..base import BackendNotAvailableError
from .device_manager import DeviceManager
from .event_router import EventRouter
from .key_state import KeyState
from .parser import parse_event
from .processor import EventProcessor
from .types import ParsedEvent
from .uinput_writer import UInputWriter


class EvdevBackend:
    """Keyboard backend using evdev (Wayland/X11 compatible)."""

    def __init__(
        self,
        device_path: str | None = None,
        device_name: str | None = None
    ) -> None:
        from common.logging_utils import get_logger
        self.logger = get_logger('common.backend.evdev')
        self.device_path = device_path
        self.device_name = device_name
        self.devices: list[Any] = []
        self.uinput_device: UInputWriter | None = None
        import threading
        self._stop_event = threading.Event()
        self._device_threads: list[threading.Thread] = []
        self._event_queue: queue.Queue[tuple[Any, Any]] = queue.Queue(maxsize=1000)

        # Per-device/press key state
        self.key_state = KeyState(self.logger)

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
                key_state=self.key_state,
                uinput_writer=self.uinput_device,
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

    def stop(self) -> None:
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        self._cleanup_devices()
        if hasattr(EvdevBackend, '_instances'):
            EvdevBackend._instances.discard(self)

    def suppress_key(self, key_name: str) -> None:
        """Suppress a key by its canonical name.

        Args:
            key_name: Canonical key name (e.g., 'ctrl_l', 'delete')
        """
        self.key_state.mark_suppressed_for_active(key_name)


