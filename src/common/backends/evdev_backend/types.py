from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional, Protocol, Any, Iterable, Callable, List

DeviceId = int
KeyRef = Tuple[DeviceId, int]


@dataclass(slots=True)
class ParsedEvent:
    device_id: DeviceId
    key_ref: KeyRef
    keycode: int
    value: int  # 0 release, 1 press, 2 repeat
    key_name: Optional[str]


class EmitterProtocol(Protocol):
    def emit_press(self, code: int) -> None: ...
    def emit_release(self, code: int) -> None: ...
    def emit_repeat(self, code: int) -> None: ...


class KeyStateProtocol(Protocol):
    def register_press(self, ref: KeyRef) -> None: ...
    def discard_press(self, ref: KeyRef) -> None: ...
    def discard_buffered(self, ref: KeyRef) -> None: ...
    def mark_suppressed_for_active(self, keycode: int) -> int: ...
    def is_suppressed(self, ref: KeyRef, value: int) -> bool: ...


class DeviceManagerProtocol(Protocol):
    def list_devices(self) -> List[str]: ...
    def discover_auto(self) -> List[Any]: ...
    def grab_all(self, devices: Iterable[Any]) -> List[Any]: ...
    def ungrab_all(self, devices: Iterable[Any]) -> None: ...
    def start_reader_threads(
        self,
        devices: Iterable[Any],
        queue_put: Callable[[tuple[Any, Any]], None],
        stop_event: Any,
    ) -> List[Any]: ...


class EventRouterProtocol(Protocol):
    def run(self, queue_get: Callable[..., Any], stop_event: Any) -> None: ...


