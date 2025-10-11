# Quick Start Guide - Tap Detector

## Installation

1. Navigate to the project directory:
```bash
cd /home/shtirliz/workspace/myself/tapper_launch
```

2. Sync dependencies (creates virtual environment automatically):
```bash
uv sync
```

## Running tap-detector

### Basic Usage

```bash
# Run with default settings (0.2s timeout)
uv run tap-detector

# Run with custom timeout
uv run tap-detector --timeout 0.3

# Run with verbose output for debugging
uv run tap-detector --verbose
```

### How to Use

1. Start the detector
2. Press and release a key combination quickly (within the timeout)
3. The detector will show you the detected tap and provide a TOML config fragment
4. Copy the TOML fragment into your `config.toml` file
5. Press Ctrl+C to exit

### Example Session

```
$ uv run tap-detector

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

## Important Notes

### Left vs Right Modifiers

The detector **distinguishes between left and right modifier keys**:
- `ctrl_l` ≠ `ctrl_r`
- `shift_l` ≠ `shift_r`
- `alt_l` ≠ `alt_r`
- `super_l` ≠ `super_r`

This is intentional and allows you to create different actions for different sides. For example:
- Left Shift + Left Ctrl → Switch to English layout
- Right Shift + Right Ctrl → Switch to Russian layout

### What is a Valid Tap?

A tap is valid when:
1. You press one or more keys
2. You release **all** keys within the timeout period (default: 0.2 seconds)
3. No additional keys were pressed during the tap

If you hold keys too long or press additional keys, the tap will be marked as invalid.

### Supported Keys

The detector supports all keyboard keys:
- **Modifiers**: ctrl_l, ctrl_r, shift_l, shift_r, alt_l, alt_r, super_l, super_r, alt_gr
- **Function keys**: f1, f2, ..., f20
- **Navigation**: up, down, left, right, home, end, page_up, page_down, insert, delete
- **Special keys**: space, enter, tab, backspace, esc, caps_lock, etc.
- **Regular keys**: a-z (lowercase), 0-9, and other characters

See `docs/key-mapping.md` for the complete reference.

## Troubleshooting

### Permission Issues

If you get permission errors accessing the keyboard:
- On X11: No special permissions needed
- On Wayland (future): You may need to add your user to the `input` group

### Keys Not Detected

1. Make sure your terminal/IDE doesn't capture the key combination first
2. Try with `--verbose` to see debug output
3. Check if the timeout is too short - try `--timeout 0.3`

### Application Doesn't Start

1. Make sure dependencies are installed: `uv sync`
2. Check Python version: `python --version` (requires 3.13+)
3. Try running with: `uv run python -m tap_detector.main`

## Next Steps

Once you've identified your desired key combinations:

1. Copy the example config:
```bash
mkdir -p ~/.config/tap-launcher
cp config/tap-launcher.toml.example ~/.config/tap-launcher/config.toml
```

2. Edit the config file and paste your TOML fragments
3. Wait for Phase 1 (`tap-launcher`) to be implemented 😊

## Getting Help

Run `tap-detector --help` for command-line options.

