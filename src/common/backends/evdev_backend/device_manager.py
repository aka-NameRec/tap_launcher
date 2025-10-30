from __future__ import annotations

from contextlib import suppress
from typing import Any, Iterable, Callable

import evdev
from evdev import ecodes


class DeviceManager:
    def __init__(self, logger: Any) -> None:
        self.logger = logger

    @staticmethod
    def device_has_keyboard_caps(device: Any) -> bool:
        """Return True if the evdev device exposes keyboard capabilities."""
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
    def is_virtual_uinput(device: Any, path: str) -> bool:
        name_l = device.name.lower()
        path_l = str(path).lower()
        return 'uinput' in name_l or 'uinput' in path_l

    def list_devices(self) -> list[str]:
        return evdev.list_devices()

    def discover_auto(self) -> list[Any]:
        devices = []
        for path in self.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if not self.device_has_keyboard_caps(dev):
                    continue
                devices.append(dev)
            except (OSError, PermissionError):
                continue
        # Prefer physical
        physical = [d for d in devices if not self.is_virtual_uinput(d, d.path)]
        return physical or devices

    def grab_all(self, devices: Iterable[Any]) -> list[Any]:
        grabbed = []
        for dev in devices:
            try:
                dev.grab()
                grabbed.append(dev)
                self.logger.debug(f'Device grabbed: {dev.name}')
            except OSError as e:
                self.logger.warning(f'Failed to grab device {dev.name}: {e}. Events may reach system before processing.')
        return grabbed

    def ungrab_all(self, devices: Iterable[Any]) -> None:
        for dev in devices:
            with suppress(Exception):
                dev.ungrab()

    def start_reader_threads(
        self,
        devices: Iterable[Any],
        queue_put: Callable[[tuple[Any, Any]], None],
        stop_event,
    ) -> list[Any]:
        """Start reader threads for devices.

        queue_put: Callable that accepts (device, event). Should raise queue.Full on overflow.
        stop_event: threading.Event-like with is_set().
        """
        import threading
        threads = []
        for dev in devices:
            t = threading.Thread(
                target=self._reader_loop,
                args=(dev, queue_put, stop_event),
                daemon=True,
                name=f'evdev-read-{dev.name}'
            )
            t.start()
            threads.append(t)
        return threads

    def _reader_loop(self, device: Any, queue_put, stop_event) -> None:
        try:
            for event in device.read_loop():
                if stop_event.is_set():
                    break
                try:
                    queue_put((device, event))
                except Exception as e:  # catch queue.Full if propagated
                    self.logger.warning(f'Event queue put failed for {device.name}: {e}')
        except OSError as e:
            self.logger.error(f'Error reading from device {device.name}: {e}')
        except Exception as e:  # noqa: BLE001
            self.logger.error(f'Unexpected error in read loop for {device.name}: {e}')


