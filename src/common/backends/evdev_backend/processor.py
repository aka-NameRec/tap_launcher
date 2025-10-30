from __future__ import annotations

from typing import Any, Callable

from .types import ParsedEvent, KeyRef


class EventProcessor:
    def __init__(self, logger: Any, state, emitter, handle_suppressed, safe_call) -> None:
        self.logger = logger
        self.state = state
        self.emitter = emitter
        self._handle_suppressed = handle_suppressed
        self._safe_call = safe_call

    def process(self, evt: ParsedEvent, on_press: Callable[[Any], None], on_release: Callable[[Any], None]) -> None:
        key_ref: KeyRef = evt.key_ref
        keycode = evt.keycode
        value = evt.value
        key_name = evt.key_name

        if value == 1:  # Press
            self.state.register_press(key_ref)
            self._safe_call('on_press', on_press, key_name)
            if self._handle_suppressed(key_ref, value):
                self.logger.debug(f'Suppressing press: keycode={keycode}')
                return
            self.emitter.emit_press(keycode)

        elif value == 0:  # Release
            self._safe_call('on_release', on_release, key_name)
            if self._handle_suppressed(key_ref, value):
                self.logger.debug(f'Suppressing release: keycode={keycode}')
                return
            self.emitter.emit_release(keycode)
            self.state.discard_press(key_ref)
            self.state.discard_buffered(key_ref)

        elif value == 2:  # Repeat
            if self._handle_suppressed(key_ref, value):
                self.logger.debug(f'Suppressing repeat: keycode={keycode}')
                return
            self.emitter.emit_repeat(keycode)


