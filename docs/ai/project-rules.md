# Project-Specific AI Rules

## Project Identity

- **tap-launcher** — Linux application for detecting keyboard tap combinations and launching commands.
- Two independent CLI apps sharing a common module: `detect` (key discovery) and `launch` (background daemon).
- Python 3.13, uv package manager, hatchling build system.

## Architecture

- `src/common/` — shared code: backends, key normalization, tap monitor, logging, version.
- `src/detector/` — `detect` CLI entry point (Typer).
- `src/launcher/` — `launch` CLI entry point (Typer), daemon, config, hotkey matching.
- Keyboard input is abstracted through a Protocol-based backend layer (`common/backends/`).
- Currently evdev-only (Linux). Backend abstraction exists for future extensions.

## Build & Run

- Install: `uv sync`
- Run commands via wrapper: `./tap detect --verbose`, `./tap launch start`
- Run commands via uv: `uv run detect`, `uv run launch start`

## Code Style

- Ruff: line-length 120, single quotes, isort with `force-single-line = true`.
- mypy: Python 3.13, `disallow_untyped_defs`, `no_implicit_optional`, `ignore_missing_imports`, `follow_imports=skip`.
- Lint: `ruff check src/`
- Format: `ruff format src/`
- Typecheck: `mypy src/`

## Testing

- No test framework is configured yet. Do not generate pytest tests unless asked.

## Configuration

- Format: TOML.
- Location: `~/.config/tap-launcher/config.toml`.
- Example: `config/tap-launcher.toml.example`.
- Sections: `[app]` (log_level, log_file, debug_mode, verbose_logging) and `[[hotkeys]]` (keys, command, args, description).

## Runtime

- Linux only. X11 and Wayland display servers.
- Requires input group membership for `/dev/input` access.
- Auto-detects display server via `XDG_SESSION_TYPE`.

## ConPort

- ConPort data stored in `context_portal/` (gitignored).
- Load ConPort context at the start of each session.
