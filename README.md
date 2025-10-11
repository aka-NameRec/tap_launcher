# Tap Launcher

**Tap Launcher** is an application for detecting keyboard tap combinations and launching commands in Linux (X11/Wayland).

## Overview

A "tap" is a brief press of a key combination (by default within 0.2 seconds). The application monitors keyboard events and executes configured commands when a valid tap is detected.

## Project Structure

This project consists of two phases:

### Phase 0: `tap-detector` (Current)

An interactive utility to help users identify tap combinations. It displays detected taps in real-time and provides ready-to-use TOML configuration fragments.

A tap is a brief press-and-release of one or more keys. All keys must be pressed and released within the timeout period for the tap to be valid.

**Features:**
- Real-time tap detection
- Generates ready-to-use TOML config fragments
- Distinguishes between left and right modifiers (e.g., `ctrl_l` vs `ctrl_r`)
- Supports all keyboard keys: modifiers, function keys, navigation keys, and regular characters
- Verbose mode for debugging and detailed traces

**Usage:**
```bash
# Run with default timeout (0.2s)
tap-detector

# Custom timeout (useful for slower taps)
tap-detector --timeout 0.3

# Verbose output for debugging
tap-detector --verbose

# Combine options
tap-detector --timeout 0.15 --verbose
```

**Example output:**
```
🎹 Tap Detector v0.1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detecting taps with timeout: 0.2s
Press Ctrl+C to exit

Listening for taps...

✓ Tap detected! Duration: 0.18s
  Keys: ctrl_l+shift_l
  
  📋 TOML config fragment (copy to config.toml):
  ────────────────────────────────────────────
  [[hotkeys]]
  keys = ["ctrl_l", "shift_l"]
  command = "your-command-here"
  args = []
  description = "Description here"
  ────────────────────────────────────────────

Listening for taps...
```

Simply copy the TOML fragment into your `config.toml` file and customize the command!

### Phase 1: `tap-launcher` (Current)

The main daemon application that monitors for configured taps and executes commands.

**Features:**
- Background daemon process
- TOML configuration file support
- Multiple hotkey combinations
- Command execution with arguments
- PID file management
- Logging support
- CLI for process control (start/stop/restart/status)

**Usage:**
```bash
# Check configuration
tap-launcher check-config

# Start daemon
tap-launcher start

# Check status
tap-launcher status

# Stop daemon
tap-launcher stop

# Restart (useful after config changes)
tap-launcher restart
```

**Configuration:**

Create `~/.config/tap-launcher/config.toml`:
```toml
[app]
tap_timeout = 0.2
log_level = "INFO"

[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"
```

See `docs/tap-launcher-usage.md` for complete documentation.

## Requirements

- Python 3.13+
- Linux with X11 (Wayland support planned)
- uv package manager

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd tapper_launch
```

2. Create virtual environment and install dependencies:
```bash
UV_LINK_MODE=symlink uv sync
```

3. Activate virtual environment:
```bash
source .venv/bin/activate
```

4. Run tap detector:
```bash
tap-detector
```

## Development

This project uses:
- **Python 3.13** for latest features and performance
- **pynput** for keyboard monitoring (X11)
- **Typer** for modern CLI interface
- **uv** for fast dependency management

### Project Structure

```
tapper_launch/
├── src/
│   └── tap_detector/           # Phase 0: Tap detector application
│       ├── __init__.py
│       ├── main.py             # CLI entry point (Typer)
│       ├── tap_monitor.py      # Core tap detection logic
│       ├── key_normalizer.py   # Key normalization and mapping
│       ├── formatter.py        # Output formatting
│       └── constants.py        # Constants and version
├── config/
│   └── tap-launcher.toml.example  # Example configuration with KEY_MAPPING reference
├── docs/
│   ├── key-mapping.md          # Complete key mapping reference
│   └── ...                     # Other documentation
├── pyproject.toml              # Project metadata and dependencies
└── README.md
```

### Key Mapping

The application distinguishes between left and right modifier keys. See:
- `docs/key-mapping.md` - Complete reference
- `config/tap-launcher.toml.example` - Quick reference in comments

Use `tap-detector` to discover the canonical names for any key combination!

## Configuration

Configuration will be stored in `~/.config/tap-launcher/config.toml` (Phase 1).

Example configuration structure:
```toml
[app]
tap_timeout = 0.2      # seconds
log_level = "INFO"

# Note: We distinguish left/right modifiers!
[[hotkeys]]
keys = ["ctrl_l", "alt_l"]
command = "gnome-terminal"
args = []
description = "Open terminal"

[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"

[[hotkeys]]
keys = ["ctrl_r", "shift_r"]
command = "setxkbmap"
args = ["ru"]
description = "Switch to Russian layout"
```

See `config/tap-launcher.toml.example` for a complete example with KEY_MAPPING reference.

## License

[License to be determined]

## Author

Created for personal use with full system access capabilities.

