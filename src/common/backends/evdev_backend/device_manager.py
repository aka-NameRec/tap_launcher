from __future__ import annotations

from contextlib import suppress
from typing import Any, Iterable

import evdev
from evdev import ecodes


class DeviceManager:
    def __init__(self, logger: Any, capability_check, virtual_check) -> None:
        self.logger = logger
        self._capability_check = capability_check
        self._virtual_check = virtual_check

    def list_devices(self) -> list[str]:
        return evdev.list_devices()

    def discover_auto(self) -> list[Any]:
        devices = []
        for path in self.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if not self._capability_check(dev):
                    continue
                devices.append(dev)
            except (OSError, PermissionError):
                continue
        # Prefer physical
        physical = [d for d in devices if not self._virtual_check(d, d.path)]
        return physical or devices

    def discover_by_name(self, name: str) -> list[Any]:
        name_l = name.lower()
        matches = []
        for path in self.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if not self._capability_check(dev):
                    continue
                if name_l in dev.name.lower():
                    matches.append(dev)
            except (OSError, PermissionError):
                continue
        physical = [d for d in matches if not self._virtual_check(d, d.path)]
        return physical or matches

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

    def start_reader_threads(self, devices: Iterable[Any], queue_put, stop_event) -> list[Any]:
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
                except Exception:  # noqa: BLE001
                    self.logger.warning(f'Event queue put failed for {device.name}')
        except OSError as e:
            self.logger.error(f'Error reading from device {device.name}: {e}')
        except Exception as e:  # noqa: BLE001
            self.logger.error(f'Unexpected error in read loop for {device.name}: {e}')


