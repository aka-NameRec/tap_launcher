from __future__ import annotations

from typing import Any, Iterable
from evdev import ecodes


class UInputWriter:
    """Thin wrapper around evdev.UInput to emit key events with syn()."""

    def __init__(self, ui: Any, logger: Any) -> None:
        self.ui = ui
        self.logger = logger

    @staticmethod
    def create_from_devices(devices: Iterable[Any], logger: Any) -> 'UInputWriter':
        from evdev import UInput
        all_keys: set[int] = set()
        for device in devices:
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                all_keys.update(caps[ecodes.EV_KEY])
        ui = UInput({ecodes.EV_KEY: list(all_keys)})
        logger.info('Created uinput virtual device for event emulation')
        return UInputWriter(ui, logger)

    def emit(self, code: int, value: int) -> None:
        self.ui.write(ecodes.EV_KEY, code, value)
        self.ui.syn()

    def emit_press(self, code: int) -> None:
        self.emit(code, 1)

    def emit_release(self, code: int) -> None:
        self.emit(code, 0)

    def emit_repeat(self, code: int) -> None:
        self.emit(code, 2)

    def close(self) -> None:
        try:
            self.ui.close()
        except Exception:  # noqa: BLE001
            pass


