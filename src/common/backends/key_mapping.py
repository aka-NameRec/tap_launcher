"""Mapping between evdev key codes and canonical key names (str).

This module translates between evdev keycodes like 'KEY_LEFTCTRL' and
canonical names like 'ctrl_l', and provides reverse mapping to evdev ecodes
for emission (suppression).
"""

from typing import Any


EVDEV_TO_NAME: dict[str, str] = {
    # Modifiers - Left/Right
    'KEY_LEFTCTRL': 'ctrl_l', 'KEY_RIGHTCTRL': 'ctrl_r',
    'KEY_LEFTSHIFT': 'shift_l', 'KEY_RIGHTSHIFT': 'shift_r',
    'KEY_LEFTALT': 'alt_l', 'KEY_RIGHTALT': 'alt_r',
    'KEY_LEFTMETA': 'super_l', 'KEY_RIGHTMETA': 'super_r',

    # Special keys
    'KEY_ESC': 'esc', 'KEY_ENTER': 'enter', 'KEY_TAB': 'tab',
    'KEY_BACKSPACE': 'backspace', 'KEY_DELETE': 'delete', 'KEY_INSERT': 'insert',
    'KEY_SPACE': 'space',

    # Navigation
    'KEY_HOME': 'home', 'KEY_END': 'end', 'KEY_PAGEUP': 'page_up', 'KEY_PAGEDOWN': 'page_down',
    'KEY_UP': 'up', 'KEY_DOWN': 'down', 'KEY_LEFT': 'left', 'KEY_RIGHT': 'right',

    # Function keys
    'KEY_F1': 'f1','KEY_F2': 'f2','KEY_F3': 'f3','KEY_F4': 'f4','KEY_F5': 'f5','KEY_F6': 'f6',
    'KEY_F7': 'f7','KEY_F8': 'f8','KEY_F9': 'f9','KEY_F10': 'f10','KEY_F11': 'f11','KEY_F12': 'f12',
    'KEY_F13': 'f13','KEY_F14': 'f14','KEY_F15': 'f15','KEY_F16': 'f16','KEY_F17': 'f17','KEY_F18': 'f18',
    'KEY_F19': 'f19','KEY_F20': 'f20',

    # Lock keys
    'KEY_CAPSLOCK': 'caps_lock', 'KEY_NUMLOCK': 'num_lock', 'KEY_SCROLLLOCK': 'scroll_lock',

    # Media keys
    'KEY_MUTE': 'media_volume_mute', 'KEY_VOLUMEDOWN': 'media_volume_down', 'KEY_VOLUMEUP': 'media_volume_up',
    'KEY_PLAYPAUSE': 'media_play_pause', 'KEY_PREVIOUSSONG': 'media_previous', 'KEY_NEXTSONG': 'media_next',

    # Print screen/Pause
    'KEY_SYSRQ': 'print_screen', 'KEY_PAUSE': 'pause',

    # Menu
    'KEY_MENU': 'menu',

    # Symbols
    'KEY_SLASH': '/', 'KEY_DOT': '.', 'KEY_COMMA': ',', 'KEY_MINUS': '-', 'KEY_EQUAL': '=',
    'KEY_LEFTBRACE': '[', 'KEY_RIGHTBRACE': ']', 'KEY_SEMICOLON': ';', "KEY_APOSTROPHE": "'",
    'KEY_BACKSLASH': '\\', 'KEY_GRAVE': '`',

    # Numpad (names kept distinct)
    'KEY_KP0': 'kp0','KEY_KP1': 'kp1','KEY_KP2': 'kp2','KEY_KP3': 'kp3','KEY_KP4': 'kp4',
    'KEY_KP5': 'kp5','KEY_KP6': 'kp6','KEY_KP7': 'kp7','KEY_KP8': 'kp8','KEY_KP9': 'kp9',
    'KEY_KPENTER': 'kpenter','KEY_KPPLUS': 'kpplus','KEY_KPMINUS': 'kpminus',
    'KEY_KPASTERISK': 'kpasterisk','KEY_KPSLASH': 'kpslash','KEY_KPDOT': 'kpdot',
}


def evdev_to_key_name(keycode: str | list[str]) -> str:
    """Convert evdev keycode to canonical key name (str)."""
    if isinstance(keycode, list):
        if not keycode:
            raise KeyError('Empty keycode list')
        keycode = keycode[0]
    if keycode in EVDEV_TO_NAME:
        return EVDEV_TO_NAME[keycode]
    if keycode.startswith('KEY_') and len(keycode) == 5:
        ch = keycode[4].lower()
        if ch.isalnum():
            return ch
    suffix = keycode[4:] if keycode.startswith('KEY_') else keycode
    if suffix.isdigit():
        return suffix
    raise KeyError(f'Unknown evdev keycode: {keycode}')


NAME_TO_EVDEV_KEY: dict[str, str] = {v: k for k, v in EVDEV_TO_NAME.items()}


def key_name_to_evdev_code(name: Any) -> int:
    """Convert canonical key name (str) to evdev code (int)."""
    from evdev import ecodes
    s = str(name).lower()
    # Letters
    if len(s) == 1 and s.isalpha():
        return getattr(ecodes, f'KEY_{s.upper()}')
    # Digits
    if len(s) == 1 and s.isdigit():
        return getattr(ecodes, f'KEY_{s}')
    # Symbols
    symbol_map = {
        '/': ecodes.KEY_SLASH,'.': ecodes.KEY_DOT, ',': ecodes.KEY_COMMA,
        '-': ecodes.KEY_MINUS,'=': ecodes.KEY_EQUAL,'[': ecodes.KEY_LEFTBRACE,
        ']': ecodes.KEY_RIGHTBRACE,';': ecodes.KEY_SEMICOLON, "'": ecodes.KEY_APOSTROPHE,
        '\\': ecodes.KEY_BACKSLASH,'`': ecodes.KEY_GRAVE,'+': ecodes.KEY_KPPLUS,
        '*': ecodes.KEY_KPASTERISK,
    }
    if s in symbol_map:
        return symbol_map[s]
    # Named keys via reverse table
    if s in NAME_TO_EVDEV_KEY:
        ev_name = NAME_TO_EVDEV_KEY[s]
        return getattr(ecodes, ev_name)
    raise KeyError(f'Cannot convert key name to evdev code: {name}')

