"""Key normalization utilities for tap detector.

This module provides functions to normalize keyboard keys from pynput
to canonical string names, with proper support for left/right modifiers.
"""

from typing import Any

from pynput.keyboard import Key

# Full key mapping from pynput Key objects to canonical names
# IMPORTANT: We distinguish left and right modifiers (ctrl_l != ctrl_r)
KEY_MAPPING = {
    # Modifiers (CRITICAL: distinguish sides!)
    Key.ctrl_l: 'ctrl_l',
    Key.ctrl_r: 'ctrl_r',
    Key.shift_l: 'shift_l',
    Key.shift_r: 'shift_r',
    Key.alt_l: 'alt_l',
    Key.alt_r: 'alt_r',
    Key.alt_gr: 'alt_gr',
    Key.cmd: 'super',  # Generic (if system doesn't distinguish)
    Key.cmd_l: 'super_l',  # Win/Super left
    Key.cmd_r: 'super_r',  # Win/Super right

    # Function keys
    Key.f1: 'f1',
    Key.f2: 'f2',
    Key.f3: 'f3',
    Key.f4: 'f4',
    Key.f5: 'f5',
    Key.f6: 'f6',
    Key.f7: 'f7',
    Key.f8: 'f8',
    Key.f9: 'f9',
    Key.f10: 'f10',
    Key.f11: 'f11',
    Key.f12: 'f12',
    Key.f13: 'f13',
    Key.f14: 'f14',
    Key.f15: 'f15',
    Key.f16: 'f16',
    Key.f17: 'f17',
    Key.f18: 'f18',
    Key.f19: 'f19',
    Key.f20: 'f20',

    # Navigation
    Key.up: 'up',
    Key.down: 'down',
    Key.left: 'left',
    Key.right: 'right',
    Key.home: 'home',
    Key.end: 'end',
    Key.page_up: 'page_up',
    Key.page_down: 'page_down',
    Key.insert: 'insert',
    Key.delete: 'delete',

    # Special keys
    Key.space: 'space',
    Key.enter: 'enter',
    Key.tab: 'tab',
    Key.backspace: 'backspace',
    Key.esc: 'esc',
    Key.caps_lock: 'caps_lock',
    Key.print_screen: 'print_screen',
    Key.scroll_lock: 'scroll_lock',
    Key.pause: 'pause',
    Key.menu: 'menu',

    # Numpad
    Key.num_lock: 'num_lock',
}


def normalize_key(key: Any) -> str:
    """Normalize a key to its canonical string name.

    This function handles:
    1. Special keys (Key.*) - uses KEY_MAPPING with fallback to key.name
    2. Regular character keys (KeyCode) - uses the character itself
    3. Unknown keys - converts to string as fallback

    Args:
        key: A pynput Key or KeyCode object

    Returns:
        str: Canonical key name (e.g., "ctrl_l", "a", "f1")

    Examples:
        >>> normalize_key(Key.ctrl_l)
        'ctrl_l'
        >>> normalize_key(KeyCode.from_char('a'))
        'a'
        >>> normalize_key(Key.f1)
        'f1'
    """
    # Case 1: Special key (Key.*)
    if isinstance(key, Key):
        # Check our mapping first
        if key in KEY_MAPPING:
            return KEY_MAPPING[key]

        # FALLBACK: Use built-in name from pynput
        # This handles keys we might have missed in KEY_MAPPING
        # Examples: Key.media_play_pause -> "media_play_pause"
        return key.name

    # Case 2: Regular character key (KeyCode with .char attribute)
    if hasattr(key, 'char') and key.char:
        return key.char.lower()

    # Case 3: Unknown key (shouldn't happen often)
    # FALLBACK: just convert to string
    return str(key)


def format_keys_display(keys: set[Any]) -> str:
    """Format keys for console display with + separator.

    Args:
        keys: Set of pynput Key/KeyCode objects

    Returns:
        str: Formatted string like "ctrl_l+shift_l+a"

    Examples:
        >>> format_keys_display({Key.ctrl_l, Key.shift_l})
        'ctrl_l+shift_l'
    """
    normalized = [normalize_key(k) for k in keys]
    return '+'.join(sorted(normalized))


def format_keys_toml(keys: set[Any]) -> list[str]:
    """Format keys for TOML config with proper sorting.

    Sorting order: modifiers (alphabetically) → regular keys (alphabetically)

    Args:
        keys: Set of pynput Key/KeyCode objects

    Returns:
        list[str]: Sorted list of normalized key names

    Examples:
        >>> format_keys_toml({Key.ctrl_l, Key.shift_l, KeyCode.from_char('a')})
        ['ctrl_l', 'shift_l', 'a']
        >>> format_keys_toml({Key.alt_r, KeyCode.from_char('t')})
        ['alt_r', 't']
    """
    normalized = [normalize_key(k) for k in keys]

    # Separate modifiers from regular keys
    modifiers = []
    regular = []

    modifier_prefixes = ('ctrl', 'shift', 'alt', 'super')

    for key in normalized:
        if any(key.startswith(m) for m in modifier_prefixes):
            modifiers.append(key)
        else:
            regular.append(key)

    # Return sorted: modifiers first, then regular keys
    return sorted(modifiers) + sorted(regular)

