# Troubleshooting: Keyboard Events Not Detected

## Problem

`tap-launcher` starts successfully but doesn't detect keyboard taps.

## Cause

`pynput` requires proper X11 display access to monitor keyboard events. When running from:
- IDE terminals (like Cursor)
- Background processes without proper X11 setup
- SSH sessions without X11 forwarding

...the keyboard listener may not receive events.

## Solution

### 1. Run from Native Terminal

Open a **native terminal** (not IDE terminal):
- GNOME Terminal
- Konsole
- xterm
- Any terminal emulator that's not embedded in IDE

Then run:
```bash
cd /home/shtirliz/workspace/myself/tapper_launch
uv run tap-launcher start --foreground
```

### 2. Test Keyboard Access

Before running tap-launcher, test if pynput can access keyboard:

```bash
cd /home/shtirliz/workspace/myself/tapper_launch
./test-keyboard.sh
```

If you see key press/release events, keyboard access is working!

### 3. Check X11 Display

Ensure `DISPLAY` environment variable is set:
```bash
echo $DISPLAY
```

Should output something like `:0` or `:1`

### 4. Run as Daemon

If foreground mode doesn't work, try daemon mode (which runs in background properly):

```bash
# Start daemon
uv run tap-launcher start

# Check status
uv run tap-launcher status

# View logs
tail -f ~/.local/share/tap-launcher/tap-launcher.log
```

Then test your taps and check logs for detection.

### 5. Enable Verbose Logging

Edit `~/.config/tap-launcher/config.toml`:

```toml
[app]
debug_mode = true
verbose_logging = true
log_level = "DEBUG"
```

Then check logs after making taps:
```bash
tail -30 ~/.local/share/tap-launcher/tap-launcher.log
```

You should see traces like:
```
[TRACE] 0.000s: Key.ctrl_l pressed
[TRACE] 0.052s: Key.shift_l pressed
[TRACE] 0.145s: Key.ctrl_l released
...
```

## Expected Behavior

When working correctly, you should see in logs:
1. Application start message
2. Key press/release events (in verbose mode)
3. "Tap detected" messages
4. Command execution messages

## Alternative: Run from Autostart

If manual testing is problematic, configure autostart and reboot:

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/tap-launcher.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Tap Launcher
Exec=/home/shtirliz/workspace/myself/tapper_launch/.venv/bin/tap-launcher start
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
```

After reboot, the launcher will start with proper X11 session context.

## Still Not Working?

1. Check if `xdotool` can see keystrokes (alternative test):
```bash
xdotool key --delay 100 ctrl+shift
```

2. Check system logs:
```bash
journalctl --user -f | grep tap-launcher
```

3. Try running tap-detector (should work if tap-launcher works):
```bash
uv run tap-detector --verbose
```

4. Check pynput documentation for X11 requirements:
https://pynput.readthedocs.io/en/latest/

## Quick Test Checklist

- [ ] Running from native terminal (not IDE)?
- [ ] `DISPLAY` variable set?
- [ ] X11 session active (`echo $XDG_SESSION_TYPE` shows `x11`)?
- [ ] test-keyboard.sh shows key events?
- [ ] Debug mode enabled in config?
- [ ] Logs show application started?
- [ ] No permission errors in logs?

If all checked and still not working, there may be a system-specific X11 configuration issue.


