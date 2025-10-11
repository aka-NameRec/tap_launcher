# Tap Launcher

**Tap Launcher** is an application for detecting keyboard tap combinations and launching commands in Linux (X11/Wayland).

## Overview

A "tap" is a brief press of a key combination (by default within 0.2 seconds). The application monitors keyboard events and executes configured commands when a valid tap is detected.

## Project Structure

This project consists of two phases:

### Phase 0: `tap-detector` (Current)
An interactive utility to help users identify tap combinations. It displays detected taps in real-time and provides ready-to-use TOML configuration fragments.

**Usage:**
```bash
tap-detector                  # Run with default timeout (0.2s)
tap-detector --timeout 0.3    # Custom timeout
tap-detector --verbose        # Verbose output for debugging
```

### Phase 1: `tap-launcher` (Future)
The main daemon application that monitors for configured taps and executes commands.

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
- **click** for CLI interface
- **uv** for fast dependency management

## Configuration

Configuration will be stored in `~/.config/tap-launcher/config.toml` (Phase 1).

Example configuration structure:
```toml
[app]
tap_timeout = 0.2      # seconds
log_level = "INFO"

[[hotkeys]]
keys = ["ctrl", "alt"]
command = "gnome-terminal"
args = []
description = "Open terminal"
```

## License

[License to be determined]

## Author

Created for personal use with full system access capabilities.

