from __future__ import annotations

from typing import Any


class EventRouter:
    def __init__(self, logger: Any, parse_event, handle_unknown, handle_value) -> None:
        self.logger = logger
        self._parse_event = parse_event
        self._handle_unknown = handle_unknown
        self._handle_value = handle_value

    def run(self, queue_get, stop_event) -> None:
        event_count = 0
        self.logger.info('Starting main event processing loop...')
        while not stop_event.is_set():
            try:
                device, event = queue_get(timeout=0.1)
            except Exception:
                continue
            try:
                event_count += 1
                if event_count == 1:
                    self.logger.info('First event received - event loop is working')
                parsed = self._parse_event(device, event)
                if not parsed:
                    if event_count <= 3:
                        self.logger.debug(f'Non-keyboard event: type={getattr(event,"type",None)}, code={getattr(event,"code",None)}')
                    continue
                if event_count <= 5:
                    self.logger.debug(
                        f'Keyboard event #{event_count}: code={parsed.keycode}, value={parsed.value}, name={parsed.key_name}'
                    )
                if self._handle_unknown(parsed):
                    continue
                self._handle_value(parsed)
            except Exception as e:  # noqa: BLE001
                self.logger.error(f'Error processing event: {e}')
                import traceback
                self.logger.debug(traceback.format_exc())
                continue


