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

2. **Discover key combinations:**

   ```bash
   tap-detector
   ```

3. **Configure and start:**

   ```bash
   # Copy example config
   mkdir -p ~/.config/tap-launcher
   cp config/tap-launcher.toml.example ~/.config/tap-launcher/config.toml
   
   # Edit config with your desired key combinations
   nano ~/.config/tap-launcher/config.toml
   
   # Start the launcher
   tap-launcher start
   ```

## Components

### tap-detector

Interactive utility for discovering key combinations. Displays detected keys in real-time and provides ready-to-use TOML configuration fragments.

**Usage:**

```bash
# Basic usage
tap-detector

# Verbose output
tap-detector --verbose
```

### tap-launcher

Background daemon that monitors for configured taps and executes commands.

**Usage:**

```bash
# Start daemon
tap-launcher start

# Check status
tap-launcher status

# Stop daemon
tap-launcher stop

# Restart (useful after config changes)
tap-launcher restart

# Validate configuration
tap-launcher check-config
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

## Performance

- **Memory**: ~15-30 MB RSS
- **CPU**: < 0.1% when idle
- **Latency**: < 10ms from tap to command execution

## Security

Commands run with your user privileges. Ensure all commands in your config are from trusted sources. Keep your config file readable only by your user:

```bash
chmod 600 ~/.config/tap-launcher/config.toml
```

## License

This project is released into the public domain. The contents of this repository are free for any use without restrictions.

## Author

Created by [aka-NameRec](https://github.com/aka-NameRec) for personal use with full system access capabilities.
