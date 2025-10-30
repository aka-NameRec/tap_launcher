from __future__ import annotations

import logging
from typing import Any, Callable

from .types import ParsedEvent, KeyRef


class EventProcessor:
    """Processes keyboard events and handles suppression, callbacks, and emission."""

    def __init__(
        self,
        logger: Any,
        key_state: Any,
        uinput_writer: Any,
    ) -> None:
        self.logger = logger
        self.key_state = key_state
        self.uinput_writer = uinput_writer

    def _safe_call(self, label: str, fn: Callable[[Any], None], arg: Any) -> None:
        """Safely call a callback, logging any errors."""
        try:
            fn(arg)
        except Exception as e:
            self.logger.error(f'Error in {label} callback: {e}')
            import traceback
            self.logger.debug(traceback.format_exc())

    def handle_unknown(self, evt: ParsedEvent) -> bool:
        """Fallback for unknown keycodes. Returns True if handled (consumed)."""
        if evt.key_name is not None:
            return False
        if evt.value == 1:  # Press
            self.key_state.register_press(evt.key_ref)
            if self.uinput_writer:
                self.uinput_writer.emit_press(evt.keycode)
            return True
        if evt.value == 0:  # Release
            if self.uinput_writer:
                self.uinput_writer.emit_release(evt.keycode)
            self.key_state.discard_press(evt.key_ref)
            self.key_state.discard_buffered(evt.key_ref)
            # Ensure cleanup of suppression state
            self.key_state.suppressed_keys.discard(evt.key_ref)
            return True
        if evt.value == 2:  # Repeat
            if self.uinput_writer:
                self.uinput_writer.emit_repeat(evt.keycode)
            return True
        return True

    def process(
        self,
        evt: ParsedEvent,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None],
    ) -> None:
        """Process a parsed keyboard event.

        Handles key press/release/repeat events, calls callbacks, checks for suppression,
        and emits events to the system if not suppressed.
        """
        if self.handle_unknown(evt):
            return

        key_ref: KeyRef = evt.key_ref
        keycode = evt.keycode
        value = evt.value
        key_name = evt.key_name

        if value == 1:  # Press
            self.key_state.register_press(key_ref)
            self._safe_call('on_press', on_press, key_name)
            if self.key_state.is_suppressed(key_ref, value):
                self.logger.debug(f'Suppressing press: keycode={keycode}, key={key_name}')
                return
            if self.uinput_writer:
                self.uinput_writer.emit_press(keycode)

        elif value == 0:  # Release
            self._safe_call('on_release', on_release, key_name)
            if self.key_state.is_suppressed(key_ref, value):
                self.logger.debug(f'Suppressing release: keycode={keycode}, key={key_name}')
                self.key_state.discard_press(key_ref)
                self.key_state.discard_buffered(key_ref)
                return
            if self.uinput_writer:
                self.uinput_writer.emit_release(keycode)
            self.key_state.discard_press(key_ref)
            self.key_state.discard_buffered(key_ref)

        elif value == 2:  # Repeat
            if self.key_state.is_suppressed(key_ref, value):
                self.logger.debug(f'Suppressing repeat: keycode={keycode}, key={key_name}')
                return
            if self.uinput_writer:
                self.uinput_writer.emit_repeat(keycode)


