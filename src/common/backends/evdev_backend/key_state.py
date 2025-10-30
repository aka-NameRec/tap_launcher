from __future__ import annotations

from typing import Set, Tuple

DeviceId = int
KeyRef = Tuple[DeviceId, int]


class KeyState:
    """Tracks per-device pressed keys and one-shot suppression state."""

    def __init__(self) -> None:
        self.pressed: Set[KeyRef] = set()
        self.suppressed: Set[KeyRef] = set()
        self.buffered: Set[KeyRef] = set()

    def register_press(self, ref: KeyRef) -> None:
        self.pressed.add(ref)

    def discard_press(self, ref: KeyRef) -> None:
        self.pressed.discard(ref)

    def discard_buffered(self, ref: KeyRef) -> None:
        self.buffered.discard(ref)

    def mark_suppressed_for_active(self, keycode: int) -> int:
        to_mark = [r for r in self.pressed if r[1] == keycode]
        for r in to_mark:
            self.suppressed.add(r)
        return len(to_mark)

    def is_suppressed(self, ref: KeyRef, value: int) -> bool:
        if ref in self.suppressed:
            if value == 0:
                self.suppressed.discard(ref)
            return True
        return False


