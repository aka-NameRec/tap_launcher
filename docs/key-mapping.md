# Key Mapping Reference for Tap Launcher

This document describes the canonical key names used in `tap-launcher` configuration files.

## Overview

The `tap-detector` application normalizes keyboard keys from `pynput` to canonical string names that you use in your `config.toml` file.

**Important:** We distinguish between left and right modifiers (e.g., `ctrl_l` and `ctrl_r` are different keys).

## Modifier Keys

**Left and Right modifiers are distinguished!**

| Key | Canonical Name | Notes |
|-----|---------------|-------|
| Left Control | `ctrl_l` | Left Ctrl key |
| Right Control | `ctrl_r` | Right Ctrl key |
| Left Shift | `shift_l` | Left Shift key |
| Right Shift | `shift_r` | Right Shift key |
| Left Alt | `alt_l` | Left Alt key |
| Right Alt | `alt_r` | Right Alt key (may be AltGr on some keyboards) |
| AltGr | `alt_gr` | Right Alt with special function |
| Left Super | `super_l` | Left Windows/Super/Command key |
| Right Super | `super_r` | Right Windows/Super/Command key |
| Generic Super | `super` | When system doesn't distinguish left/right |

### Example Use Cases

```toml
# Switch to English layout with LEFT Shift + LEFT Ctrl
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"

# Switch to Russian layout with RIGHT Shift + RIGHT Ctrl
[[hotkeys]]
keys = ["ctrl_r", "shift_r"]
command = "setxkbmap"
args = ["ru"]
description = "Switch to Russian layout"
```

## Function Keys

| Key | Canonical Name |
|-----|---------------|
| F1 - F20 | `f1`, `f2`, ..., `f20` |

Example:
```toml
[[hotkeys]]
keys = ["ctrl_l", "f1"]
command = "xdg-open"
args = ["https://docs.example.com"]
description = "Open documentation"
```

## Navigation Keys

| Key | Canonical Name |
|-----|---------------|
| Up Arrow | `up` |
| Down Arrow | `down` |
| Left Arrow | `left` |
| Right Arrow | `right` |
| Home | `home` |
| End | `end` |
| Page Up | `page_up` |
| Page Down | `page_down` |
| Insert | `insert` |
| Delete | `delete` |

## Special Keys

| Key | Canonical Name |
|-----|---------------|
| Space | `space` |
| Enter/Return | `enter` |
| Tab | `tab` |
| Backspace | `backspace` |
| Escape | `esc` |
| Caps Lock | `caps_lock` |
| Print Screen | `print_screen` |
| Scroll Lock | `scroll_lock` |
| Pause/Break | `pause` |
| Menu | `menu` |
| Num Lock | `num_lock` |

## Regular Character Keys

Regular keys (letters, numbers, symbols) are represented by their lowercase character:

| Key | Canonical Name | Notes |
|-----|---------------|-------|
| A - Z | `a`, `b`, ..., `z` | Always lowercase |
| 0 - 9 | `0`, `1`, ..., `9` | Number keys |
| Other | Various | Symbols like `,`, `.`, `/`, etc. |

Example:
```toml
# Ctrl+Alt+T opens terminal (classic Linux shortcut)
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
args = []
description = "Open terminal"
```

## Unknown/Special Keys

For keys not explicitly listed in the mapping, `tap-detector` will use the key name provided by `pynput`. This includes:
- Media keys (e.g., `media_play_pause`, `media_volume_up`)
- Special keyboard buttons
- Custom programmable keys

These keys will appear in the `tap-detector` output with their system-provided names.

## Using tap-detector

To discover the canonical name for any key combination:

```bash
# Run tap-detector
$ tap-detector

# Press your desired key combination
# The output will show the canonical names:

✓ Tap detected! Duration: 0.18s
  Keys: ctrl_l+shift_l+a
  
  📋 TOML config fragment (copy to config.toml):
  ────────────────────────────────────────────
  [[hotkeys]]
  keys = ["ctrl_l", "shift_l", "a"]
  command = "your-command-here"
  args = []
  description = "Description here"
  ────────────────────────────────────────────
```

Simply copy the `keys` array from the output into your `config.toml` file!

## Full KEY_MAPPING Reference

For the complete technical mapping from `pynput` Key objects to canonical names, see:
- `src/tap_detector/key_normalizer.py` in the source code

The mapping covers:
- All standard modifier keys (with left/right distinction)
- Function keys F1-F20
- Navigation keys
- Special keys
- Fallback handling for unknown keys

