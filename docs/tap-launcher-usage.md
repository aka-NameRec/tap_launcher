# Tap Launcher Usage Guide

## Overview

`tap-launcher` is the main daemon application that monitors for configured tap combinations and executes corresponding commands.

## Installation

After installing the project with `uv sync`, two commands are available:
- `tap-detector` - Interactive utility for discovering tap combinations
- `tap-launcher` - Daemon for launching commands on taps

## Configuration

### Create Config File

1. Create the configuration directory:
```bash
mkdir -p ~/.config/tap-launcher
```

2. Copy the example configuration:
```bash
cp config/tap-launcher.toml.example ~/.config/tap-launcher/config.toml
```

3. Edit the configuration file:
```bash
nano ~/.config/tap-launcher/config.toml
```

### Configuration Structure

```toml
[app]
tap_timeout = 0.2              # Maximum tap duration in seconds
log_level = "INFO"             # DEBUG, INFO, WARNING, ERROR
log_file = "~/.local/share/tap-launcher/tap-launcher.log"
debug_mode = false             # Enable debug logging
verbose_logging = false        # Enable verbose tap detection logging

[[hotkeys]]
keys = ["ctrl_l", "shift_l"]   # Key combination (use tap-detector to find)
command = "setxkbmap"          # Command to execute
args = ["us"]                  # Command arguments
description = "Switch to English layout"  # Optional description
```

### Discovering Key Combinations

Use `tap-detector` to find the canonical names for your desired key combinations:

```bash
tap-detector
```

Press your desired key combination, and it will show you the exact `keys` array to use in your config.

## Commands

### Start the Launcher

```bash
# Start as background daemon (default)
tap-launcher start

# Start in foreground (for testing/debugging)
tap-launcher start --foreground
```

### Stop the Launcher

```bash
tap-launcher stop
```

### Restart the Launcher

```bash
# Useful after changing configuration
tap-launcher restart
```

### Check Status

```bash
tap-launcher status
```

### Validate Configuration

```bash
# Check if config file is valid
tap-launcher check-config

# Check specific config file
tap-launcher check-config --config /path/to/config.toml
```

## Logging

Logs are written to `~/.local/share/tap-launcher/tap-launcher.log` by default (configurable in config file).

View logs:
```bash
tail -f ~/.local/share/tap-launcher/tap-launcher.log
```

Log format:
```
2025-10-11 20:05:23 [tap_launcher.monitor] INFO: Starting tap launcher with timeout 0.2s
2025-10-11 20:05:23 [tap_launcher.monitor] INFO: Monitoring 4 hotkey combination(s)
2025-10-11 20:05:30 [tap_launcher.monitor] INFO: Tap detected: Switch to English layout (keys: ctrl_l+shift_l, duration: 0.165s)
2025-10-11 20:05:30 [tap_launcher.executor] INFO: Executing: setxkbmap us (Switch to English layout)
```

## Autostart

To start tap-launcher automatically on login:

### Method 1: XDG Autostart (recommended for GNOME/KDE/XFCE)

Create `~/.config/autostart/tap-launcher.desktop`:

```desktop
[Desktop Entry]
Type=Application
Name=Tap Launcher
Comment=Launch commands on keyboard tap combinations
Exec=/home/YOUR_USERNAME/.local/bin/tap-launcher start
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

Replace `/home/YOUR_USERNAME/.local/bin/tap-launcher` with the actual path to the tap-launcher binary.

To find the path:
```bash
which tap-launcher
# or
readlink -f $(which tap-launcher)
```

### Method 2: Shell Startup Script

Add to `~/.profile` or `~/.bash_profile`:

```bash
# Start tap-launcher on login
if ! pgrep -f "tap-launcher" > /dev/null; then
    tap-launcher start
fi
```

## Troubleshooting

### Launcher Won't Start

1. Check if already running:
```bash
tap-launcher status
```

2. Try starting in foreground to see errors:
```bash
tap-launcher start --foreground
```

3. Check configuration:
```bash
tap-launcher check-config
```

### Commands Not Executing

1. Check logs:
```bash
tail -20 ~/.local/share/tap-launcher/tap-launcher.log
```

2. Verify commands exist:
```bash
tap-launcher check-config
```
This will warn about commands that are not found.

3. Test command manually:
```bash
# Try running the command directly
setxkbmap us
```

### Taps Not Detected

1. Check timeout setting in config (may be too short):
```toml
[app]
tap_timeout = 0.3  # Increase timeout
```

2. Enable debug mode to see all tap attempts:
```toml
[app]
debug_mode = true
verbose_logging = true
```

3. Test with tap-detector to verify key detection:
```bash
tap-detector --verbose
```

### Permission Issues

Some commands may require specific permissions. For example:
- Brightness control may need user in `video` group
- Backlight control may need udev rules

Check command-specific documentation for permission requirements.

## Example Use Cases

### Keyboard Layout Switching

```toml
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

### Application Launching

```toml
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
args = []
description = "Open terminal"

[[hotkeys]]
keys = ["super_l", "alt_l"]
command = "firefox"
args = ["--new-window"]
description = "Open Firefox"
```

### Custom Scripts

```toml
[[hotkeys]]
keys = ["super_l", "shift_l"]
command = "/home/user/scripts/screenshot.sh"
args = []
description = "Take screenshot"
```

### Media Control

```toml
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "p"]
command = "playerctl"
args = ["play-pause"]
description = "Play/pause media"

[[hotkeys]]
keys = ["ctrl_l", "alt_l", "n"]
command = "playerctl"
args = ["next"]
description = "Next track"
```

## Advanced Configuration

### Multiple Commands for Same Tap

If you need to run multiple commands, create a shell script:

```bash
#!/bin/bash
# ~/scripts/multi-action.sh

notify-send "Action triggered"
firefox --new-window
```

Then configure:
```toml
[[hotkeys]]
keys = ["super_l", "f"]
command = "/home/user/scripts/multi-action.sh"
args = []
description = "Multi-action"
```

### Command with Environment Variables

Create a wrapper script that sets environment variables:

```bash
#!/bin/bash
# ~/scripts/app-with-env.sh

export MY_VAR=value
/path/to/app "$@"
```

### Conditional Execution

Use a script with conditional logic:

```bash
#!/bin/bash
# ~/scripts/toggle-thing.sh

if pgrep -x "app" > /dev/null; then
    pkill app
else
    app &
fi
```

## Performance

Tap launcher is designed to be lightweight:
- **Memory**: ~15-30 MB RSS
- **CPU**: < 0.1% when idle
- **Latency**: < 10ms from tap to command execution

## Security Considerations

1. **Command Validation**: tap-launcher runs commands with your user privileges. Ensure all commands in your config are from trusted sources.

2. **Config File Permissions**: Keep your config file readable only by your user:
```bash
chmod 600 ~/.config/tap-launcher/config.toml
```

3. **Log File**: Logs may contain information about your usage patterns. Consider:
```bash
chmod 600 ~/.local/share/tap-launcher/tap-launcher.log
```

## Uninstalling

1. Stop the launcher:
```bash
tap-launcher stop
```

2. Remove autostart entry (if configured):
```bash
rm ~/.config/autostart/tap-launcher.desktop
```

3. Remove config and logs (optional):
```bash
rm -rf ~/.config/tap-launcher
rm -rf ~/.local/share/tap-launcher
```

4. Uninstall the package:
```bash
cd /path/to/tapper_launch
uv sync --uninstall tap-launcher
```


