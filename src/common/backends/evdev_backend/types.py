from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional

DeviceId = int
KeyRef = Tuple[DeviceId, int]


@dataclass(slots=True)
class ParsedEvent:
    device_id: DeviceId
    key_ref: KeyRef
    keycode: int
    value: int  # 0 release, 1 press, 2 repeat
    key_name: Optional[str]


