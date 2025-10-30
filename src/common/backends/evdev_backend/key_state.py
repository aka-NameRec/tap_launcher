from __future__ import annotations

from typing import Any, Set, Tuple

DeviceId = int
KeyRef = Tuple[DeviceId, int]


class KeyState:
    """Tracks per-device pressed keys and one-shot suppression state."""

    def __init__(self, logger: Any) -> None:
        self.logger = logger
        self.pressed_keys: Set[KeyRef] = set()
        self.suppressed_keys: Set[KeyRef] = set()
        self.buffered_presses: Set[KeyRef] = set()

    def register_press(self, ref: KeyRef) -> None:
        self.pressed_keys.add(ref)

    def discard_press(self, ref: KeyRef) -> None:
        self.pressed_keys.discard(ref)

    def discard_buffered(self, ref: KeyRef) -> None:
        self.buffered_presses.discard(ref)

    def mark_suppressed_for_active(self, key_name: str) -> None:
        """Mark all currently pressed keys with the given name for suppression.

        Args:
            key_name: Canonical key name (e.g., 'ctrl_l', 'delete')
        """
        from ..key_mapping import key_name_to_evdev_code
        try:
            keycode = key_name_to_evdev_code(key_name)
            to_mark = [ref for ref in self.pressed_keys if ref[1] == keycode]
            for ref in to_mark:
                self.suppressed_keys.add(ref)
            self.logger.debug(f'Suppressing keycode {keycode} (key: {key_name}, active presses: {len(to_mark)})')
        except KeyError:
            self.logger.warning(f'Cannot suppress key {key_name}: no evdev mapping')

    def is_suppressed(self, ref: KeyRef, value: int) -> bool:
        """Check if a key event should be suppressed.

        Args:
            ref: Key reference (device_id, keycode)
            value: Event value (0=release, 1=press, 2=repeat)

        Returns:
            True if the event should be suppressed
        """
        if ref in self.suppressed_keys:
            if value == 0:  # On release, clear suppression for this specific key_ref
                self.suppressed_keys.discard(ref)
            return True
        return False


