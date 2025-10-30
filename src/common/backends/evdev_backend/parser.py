from __future__ import annotations

from typing import Any
from evdev import ecodes, categorize

from .types import ParsedEvent
from ..key_mapping import evdev_to_key_name


def parse_event(device: Any, event: Any) -> ParsedEvent | None:
    """Parse raw evdev event into ParsedEvent.

    Returns None for non-keyboard events.
    """
    if event.type != ecodes.EV_KEY:
        return None
    key_event = categorize(event)
    keycode = event.code
    value = event.value
    device_id = device.fileno() if hasattr(device, 'fileno') else id(device)
    key_ref = (device_id, keycode)
    key_name: str | None
    try:
        key_name = evdev_to_key_name(key_event.keycode)
    except Exception:
        key_name = None
    return ParsedEvent(device_id, key_ref, keycode, value, key_name)


