"""Runtime state shared by tap-launcher command-line applications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path.home() / '.local/share/tap-launcher'
PID_FILE = RUNTIME_DIR / 'tap-launcher.pid'
STATE_FILE = RUNTIME_DIR / 'tap-launcher.state.json'
STATE_VERSION = 1


@dataclass(frozen=True)
class LaunchRuntimeState:
    """Parameters needed to restore a running launcher process."""

    pid: int
    config_path: Path
    debug: bool
    foreground: bool
    version: int = STATE_VERSION

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> LaunchRuntimeState:
        """Create runtime state from JSON data."""
        return cls(
            pid=int(data['pid']),
            config_path=Path(str(data['config_path'])),
            debug=bool(data['debug']),
            foreground=bool(data['foreground']),
            version=int(data.get('version', STATE_VERSION)),
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            'pid': self.pid,
            'config_path': str(self.config_path),
            'debug': self.debug,
            'foreground': self.foreground,
            'version': self.version,
        }


def read_launch_runtime_state(state_file: Path = STATE_FILE) -> LaunchRuntimeState | None:
    """Read launcher runtime state if it is available and valid."""
    try:
        with state_file.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return LaunchRuntimeState.from_json_dict(data)
    except (FileNotFoundError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def write_launch_runtime_state(
    state: LaunchRuntimeState,
    state_file: Path = STATE_FILE,
) -> None:
    """Write launcher runtime state atomically."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = state_file.with_suffix(f'{state_file.suffix}.tmp')
    with tmp_file.open('w', encoding='utf-8') as f:
        json.dump(state.to_json_dict(), f, indent=2, sort_keys=True)
        f.write('\n')
    tmp_file.replace(state_file)


def remove_launch_runtime_state(state_file: Path = STATE_FILE) -> None:
    """Remove launcher runtime state if present."""
    state_file.unlink(missing_ok=True)
