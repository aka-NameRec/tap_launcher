# Tap Launcher

**Tap Launcher** is a Linux application for detecting keyboard tap combinations and launching commands. It consists of two main components: a tap detector utility and a background daemon for executing commands.

## Overview

A "tap" is a brief press of a key combination. The application monitors keyboard events and executes configured commands when a valid tap is detected.

## Features

- **Real-time key detection** with no time restrictions
- **Background daemon** for continuous monitoring
- **X11 and Wayland support** with automatic backend detection
- **TOML configuration** for easy setup
- **Left/right modifier distinction** (e.g., `ctrl_l` vs `ctrl_r`)
- **Comprehensive key support** (modifiers, function keys, navigation, characters)
- **Verbose logging** for debugging
- **CLI management** (start/stop/restart/status)
- **Autostart support** for system integration

## Quick Start

1. **Install dependencies:**

   ```bash
   git clone https://github.com/aka-NameRec/tap_launcher.git
   cd tap_launcher
   uv sync
   ```

2. **Set up the `tap` wrapper script (optional but recommended):**

   ```bash
   # Create a symlink in your PATH
   ln -s $(pwd)/tap ~/.local/bin/tap
   
   # Or use directly from project directory
   ./tap
   ```

3. **Discover key combinations:**

   ```bash
   tap detect
   # Or without wrapper: uv run detect
   ```

4. **Configure and start:**

   ```bash
   # Copy example config
   mkdir -p ~/.config/tap-launcher
   cp config/tap-launcher.toml.example ~/.config/tap-launcher/config.toml
   
   # Edit config with your desired key combinations
   nano ~/.config/tap-launcher/config.toml
   
   # Start the launcher
   tap launch start
   # Or without wrapper: uv run launch start
   ```

## Components

### Tap Wrapper Script

The `tap` wrapper script simplifies command execution by automatically detecting the project path and handling symlinks. This eliminates the need to type the full `uv run --project /path/to/project` command.

**Setup:**

```bash
# Create a symlink in your PATH for system-wide access
ln -s /path/to/tap_launcher/tap ~/.local/bin/tap

# Verify it works
tap launch status
```

The script:
- Automatically detects project path even when called via symlink
- Validates `uv` availability
- Passes all arguments to `uv run`

### tap-detector (now `detect`)

Interactive utility for discovering key combinations. Displays detected keys in real-time and provides ready-to-use TOML configuration fragments.

**Usage:**

```bash
# With tap wrapper (recommended)
tap detect
tap detect --verbose

# Without wrapper
uv run detect
uv run detect --verbose
```

### tap-launcher (now `launch`)

Background daemon that monitors for configured taps and executes commands.

**Usage:**

```bash
# With tap wrapper (recommended)
tap launch start
tap launch status
tap launch stop
tap launch restart
tap launch check-config

# Without wrapper
uv run launch start
uv run launch status
uv run launch stop
uv run launch restart
uv run launch check-config
```

## Configuration

Create `~/.config/tap-launcher/config.toml`:

```toml
[app]
log_level = "INFO"

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

### Configuration Format

Each hotkey entry consists of:

- **`keys`** - Array of key names that must be pressed together (see [Key Mapping](docs/key-mapping.md))
- **`command`** - Executable name (must be in PATH or absolute path)
- **`args`** - Array of command arguments (each argument as a separate string)
- **`description`** - Optional human-readable description

**Important:** The `command` field should contain **only the executable name**, not the full command line. Arguments must be in the `args` array.

**Correct:**
```toml
[[hotkeys]]
keys = ["ctrl_r", "/"]
command = "xdotool"
args = ["key", "Menu"]
```

**Incorrect:**
```toml
[[hotkeys]]
keys = ["ctrl_r", "/"]
command = "xdotool key Menu"  # ❌ Don't put arguments here
args = []
```

## Documentation

- **[Usage Guide](docs/tap-launcher-usage.md)** - Complete usage documentation
- **[Quick Start](docs/quickstart.md)** - Getting started with tap-detector
- **[Key Mapping](docs/key-mapping.md)** - Complete key reference
- **[Troubleshooting](docs/troubleshooting-keyboard.md)** - Keyboard detection issues
- **[Wayland Deployment](docs/20251024-052851-proposal-wayland_support/WAYLAND-DEPLOYMENT.md)** - Wayland setup and troubleshooting

## Requirements

- Python 3.13+
- Linux with X11 or Wayland
- uv package manager

### Display Server Support

- **X11**: Fully supported out of the box
- **Wayland**: Fully supported (requires additional setup, see [Wayland Support](#wayland-support))

The application automatically detects your session type and uses the appropriate backend.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/aka-NameRec/tap_launcher.git
   cd tap_launcher
   ```

2. **Install dependencies:**

   ```bash
   # Standard installation (works on X11)
   uv sync
   
   # For Wayland support, install additional dependencies:
   uv pip install -e ".[wayland]"
   ```

3. **Activate virtual environment:**

   ```bash
   source .venv/bin/activate
   ```

4. **Wayland users only** - Configure permissions:

   ```bash
   sudo usermod -a -G input $USER
   # Logout and login for changes to take effect
   ```

   See [Wayland Support](#wayland-support) section below for details.

## Wayland Support

Starting from version 2.0, both `tap_detector` and `tap_launcher` natively support **Wayland** display servers through an automatic backend abstraction layer.

### Quick Setup for Wayland

1. **Install Wayland dependencies:**

   ```bash
   uv pip install -e ".[wayland]"
   ```

2. **Grant input device access:**

   ```bash
   sudo usermod -a -G input $USER
   ```

3. **Logout and login** (required for group changes to take effect)

4. **Verify setup:**

   ```bash
   groups  # Should show "input" in the list
   echo $XDG_SESSION_TYPE  # Should show "wayland"
   ```

### Backend Selection

The application automatically detects your display server:

- **X11 session** → Uses `pynput` backend (no setup required)
- **Wayland session** → Uses `evdev` backend (requires setup above)

Check your session type:

```bash
echo $XDG_SESSION_TYPE
```

### Troubleshooting

#### Permission Error on Wayland?

- Verify you're in the `input` group: `groups`
- Ensure you logged out and back in after adding the group
- Test with: `python docs/20251024-052851-proposal-wayland_support/poc-evdev-test.py`

#### X11 Users

- No setup required - everything works out of the box
- No need to install `[wayland]` dependencies

For detailed information, see the [Wayland Deployment Guide](docs/20251024-052851-proposal-wayland_support/WAYLAND-DEPLOYMENT.md).

## Development

This project uses:

- **Python 3.13** for latest features and performance
- **Backend Abstraction** for X11 and Wayland support:
  - `pynput` for X11 sessions
  - `evdev` for Wayland sessions
- **Typer** for modern CLI interface
- **uv** for fast dependency management

### Project Structure

```text
tap_launcher/
├── src/
│   ├── common/                 # Shared code for both applications
│   │   ├── backends/           # Keyboard backend abstraction
│   │   │   ├── base.py         # KeyboardBackend Protocol
│   │   │   ├── pynput_backend.py  # X11 implementation
│   │   │   ├── evdev_backend.py   # Wayland implementation
│   │   │   ├── key_mapping.py     # evdev→pynput key translation
│   │   │   └── detector.py        # Auto-detection logic
│   │   └── key_normalizer.py  # Key normalization utilities
│   ├── tap_detector/           # Tap detector application
│   │   ├── main.py             # CLI entry point
│   │   ├── tap_monitor.py      # Core tap detection logic
│   │   ├── formatter.py        # Output formatting
│   │   └── constants.py        # Constants and version
│   └── tap_launcher/           # Main launcher daemon
│       ├── main.py             # CLI entry point
│       ├── launcher_monitor.py # Background monitoring
│       ├── command_executor.py # Command execution
│       ├── config_loader.py    # Configuration management
│       ├── hotkey_matcher.py   # Hotkey matching logic
│       └── daemon_manager.py   # Process management
├── config/
│   └── tap-launcher.toml.example  # Example configuration
├── docs/                        # Documentation
│   └── 20251024-052851-proposal-wayland_support/  # Wayland guides
├── pyproject.toml              # Project metadata and dependencies
└── README.md
```

## Example Use Cases

### Keyboard Layout Switching

```toml
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"
```

### Application Launching

```toml
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
args = []
description = "Open terminal"
```

### Media Control

```toml
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "p"]
command = "playerctl"
args = ["play-pause"]
description = "Play/pause media"
```

### Key Emulation

```toml
[[hotkeys]]
keys = ["ctrl_r", "/"]
command = "xdotool"
args = ["key", "Menu"]
description = "Emulate Menu key press"
```

### Volume Control

```toml
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "up"]
command = "pactl"
args = ["set-sink-volume", "@DEFAULT_SINK@", "+5%"]
description = "Increase volume by 5%"
```

## Performance

- **Memory**: ~15-30 MB RSS
- **CPU**: < 0.1% when idle
- **Latency**: < 10ms from tap to command execution

## Using the `tap` Wrapper Script

The project includes a convenient `tap` wrapper script that simplifies command execution:

### Benefits

- **Shorter commands**: `tap launch start` instead of `uv run --project /path/to/project launch start`
- **Works from anywhere**: No need to be in the project directory
- **Handles symlinks**: Automatically resolves the real project path
- **Validates environment**: Checks for `uv` and `pyproject.toml`

### Installation

**Option 1: Symlink to PATH (recommended)**

```bash
# Create symlink in a directory that's in your PATH
ln -s /path/to/tap_launcher/tap ~/.local/bin/tap

# Verify
which tap
tap launch status
```

**Option 2: Direct execution from project**

```bash
cd /path/to/tap_launcher
./tap launch start
```

### Usage Examples

```bash
# Start the launcher
tap launch start

# Check status
tap launch status

# Detect key combinations
tap detect --verbose

# Stop the launcher
tap launch stop
```

### Fallback: Direct uv Commands

If you prefer not to use the wrapper script, you can always use `uv` directly:

```bash
# From project directory
uv run launch start
uv run detect

# From anywhere with --project flag
uv run --project /path/to/tap_launcher launch start
```

## Security

Commands run with your user privileges. Ensure all commands in your config are from trusted sources. Keep your config file readable only by your user:

```bash
chmod 600 ~/.config/tap-launcher/config.toml
```

## License

This project is released into the public domain. The contents of this repository are free for any use without restrictions.

## Author

Created by [aka-NameRec](https://github.com/aka-NameRec) for personal use with full system access capabilities.
