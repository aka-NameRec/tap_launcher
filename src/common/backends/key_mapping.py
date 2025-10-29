"""Mapping between evdev key codes and pynput Key objects.

This module provides translation from evdev key codes (used in Wayland) to
pynput Key/KeyCode objects, ensuring compatibility with existing tap detection logic.

Based on Linux input event codes: /usr/include/linux/input-event-codes.h
"""

from typing import Any


# Import pynput Key classes for mapping
try:
    from pynput.keyboard import Key, KeyCode
except ImportError:
    # If pynput not available, create dummy classes for type hints
    class Key:  # type: ignore
        pass
    
    class KeyCode:  # type: ignore
        pass


# Mapping from evdev key codes to pynput Key objects
# This covers modifiers, function keys, and special keys
EVDEV_TO_PYNPUT_KEY: dict[str, Any] = {
    # Modifiers - Left side
    # Note: pynput has ctrl/shift/alt/cmd (not ctrl_l) and ctrl_r/shift_r/alt_r/cmd_r
    'KEY_LEFTCTRL': Key.ctrl,
    'KEY_LEFTSHIFT': Key.shift,
    'KEY_LEFTALT': Key.alt,
    'KEY_LEFTMETA': Key.cmd,  # Super/Win key
    
    # Modifiers - Right side
    'KEY_RIGHTCTRL': Key.ctrl_r,
    'KEY_RIGHTSHIFT': Key.shift_r,
    'KEY_RIGHTALT': Key.alt_r,
    'KEY_RIGHTMETA': Key.cmd_r,
    
    # Special keys
    'KEY_ESC': Key.esc,
    'KEY_ENTER': Key.enter,
    'KEY_TAB': Key.tab,
    'KEY_BACKSPACE': Key.backspace,
    'KEY_DELETE': Key.delete,
    'KEY_INSERT': Key.insert,
    'KEY_SPACE': Key.space,
    
    # Navigation
    'KEY_HOME': Key.home,
    'KEY_END': Key.end,
    'KEY_PAGEUP': Key.page_up,
    'KEY_PAGEDOWN': Key.page_down,
    'KEY_UP': Key.up,
    'KEY_DOWN': Key.down,
    'KEY_LEFT': Key.left,
    'KEY_RIGHT': Key.right,
    
    # Function keys
    'KEY_F1': Key.f1,
    'KEY_F2': Key.f2,
    'KEY_F3': Key.f3,
    'KEY_F4': Key.f4,
    'KEY_F5': Key.f5,
    'KEY_F6': Key.f6,
    'KEY_F7': Key.f7,
    'KEY_F8': Key.f8,
    'KEY_F9': Key.f9,
    'KEY_F10': Key.f10,
    'KEY_F11': Key.f11,
    'KEY_F12': Key.f12,
    'KEY_F13': Key.f13,
    'KEY_F14': Key.f14,
    'KEY_F15': Key.f15,
    'KEY_F16': Key.f16,
    'KEY_F17': Key.f17,
    'KEY_F18': Key.f18,
    'KEY_F19': Key.f19,
    'KEY_F20': Key.f20,
    
    # Lock keys
    'KEY_CAPSLOCK': Key.caps_lock,
    'KEY_NUMLOCK': Key.num_lock,
    'KEY_SCROLLLOCK': Key.scroll_lock,
    
    # Media keys (only those available in pynput)
    'KEY_MUTE': Key.media_volume_mute,
    'KEY_VOLUMEDOWN': Key.media_volume_down,
    'KEY_VOLUMEUP': Key.media_volume_up,
    'KEY_PLAYPAUSE': Key.media_play_pause,
    # Note: Key.media_stop doesn't exist in pynput, skipping
    'KEY_PREVIOUSSONG': Key.media_previous,
    'KEY_NEXTSONG': Key.media_next,
    
    # Print screen/Pause
    'KEY_SYSRQ': Key.print_screen,  # Print Screen (SysRq)
    'KEY_PAUSE': Key.pause,
    
    # Menu key
    'KEY_MENU': Key.menu,
    
    # Symbol keys
    'KEY_SLASH': KeyCode.from_char('/'),
    'KEY_DOT': KeyCode.from_char('.'),
    'KEY_COMMA': KeyCode.from_char(','),
    'KEY_MINUS': KeyCode.from_char('-'),
    'KEY_EQUAL': KeyCode.from_char('='),
    'KEY_LEFTBRACE': KeyCode.from_char('['),
    'KEY_RIGHTBRACE': KeyCode.from_char(']'),
    'KEY_SEMICOLON': KeyCode.from_char(';'),
    'KEY_APOSTROPHE': KeyCode.from_char("'"),
    'KEY_BACKSLASH': KeyCode.from_char('\\'),
    'KEY_GRAVE': KeyCode.from_char('`'),
    
    # Numpad keys (as special keys, not as numbers)
    'KEY_KP0': KeyCode.from_vk(96),  # Numpad 0
    'KEY_KP1': KeyCode.from_vk(97),  # Numpad 1
    'KEY_KP2': KeyCode.from_vk(98),  # Numpad 2
    'KEY_KP3': KeyCode.from_vk(99),  # Numpad 3
    'KEY_KP4': KeyCode.from_vk(100), # Numpad 4
    'KEY_KP5': KeyCode.from_vk(101), # Numpad 5
    'KEY_KP6': KeyCode.from_vk(102), # Numpad 6
    'KEY_KP7': KeyCode.from_vk(103), # Numpad 7
    'KEY_KP8': KeyCode.from_vk(104), # Numpad 8
    'KEY_KP9': KeyCode.from_vk(105), # Numpad 9
    'KEY_KPENTER': Key.enter,
    'KEY_KPPLUS': KeyCode.from_char('+'),
    'KEY_KPMINUS': KeyCode.from_char('-'),
    'KEY_KPASTERISK': KeyCode.from_char('*'),
    'KEY_KPSLASH': KeyCode.from_char('/'),
    'KEY_KPDOT': KeyCode.from_char('.'),
}


def evdev_to_pynput_key(keycode: str | list[str]) -> Any:
    """Convert evdev keycode to pynput Key/KeyCode object.
    
    This function translates evdev key codes (strings like 'KEY_LEFTCTRL')
    to pynput Key or KeyCode objects, maintaining compatibility with existing
    tap detection logic that expects pynput objects.
    
    Args:
        keycode: Evdev keycode string (e.g., 'KEY_LEFTCTRL') or list of
                keycodes for multi-key events (takes first one).
    
    Returns:
        pynput Key or KeyCode object corresponding to the evdev keycode.
    
    Raises:
        KeyError: If keycode is not recognized. Caller should handle this
                 gracefully (e.g., log and skip unknown keys).
    
    Examples:
        >>> evdev_to_pynput_key('KEY_LEFTCTRL')
        <Key.ctrl_l: ...>
        
        >>> evdev_to_pynput_key('KEY_A')
        KeyCode.from_char('a')
        
        >>> evdev_to_pynput_key(['KEY_LEFTCTRL', 'KEY_RIGHTCTRL'])
        <Key.ctrl_l: ...>  # takes first
    """
    # Handle multi-key events (take first one)
    if isinstance(keycode, list):
        if not keycode:
            raise KeyError('Empty keycode list')
        keycode = keycode[0]
    
    # Check if it's a special key (modifier, function, etc.)
    if keycode in EVDEV_TO_PYNPUT_KEY:
        return EVDEV_TO_PYNPUT_KEY[keycode]
    
    # Handle alphanumeric keys: KEY_A ... KEY_Z
    if keycode.startswith('KEY_') and len(keycode) == 5:
        char = keycode[4].lower()
        if char.isalpha():
            return KeyCode.from_char(char)
    
    # Handle number keys: KEY_0 ... KEY_9
    if keycode.startswith('KEY_') and len(keycode) == 5:
        char = keycode[4]
        if char.isdigit():
            return KeyCode.from_char(char)
    
    # Handle longer alphanumeric keys (KEY_10, KEY_11, etc.)
    if keycode.startswith('KEY_'):
        suffix = keycode[4:]
        if suffix.isdigit():
            # These are rare - just use the digit
            return KeyCode.from_char(suffix[0])
    
    # Unknown keycode - raise error for caller to handle
    raise KeyError(f'Unknown evdev keycode: {keycode}')


# Reverse mapping: from pynput Key/KeyCode to evdev ecodes
# Used for event emulation via uinput
PYNPUT_TO_EVDEV_CODE: dict[Any, str] = {v: k for k, v in EVDEV_TO_PYNPUT_KEY.items() if not isinstance(v, KeyCode)}


def pynput_to_evdev_code(key: Any) -> int:
    """Convert pynput Key/KeyCode to evdev key code.
    
    Args:
        key: pynput Key or KeyCode object
        
    Returns:
        int: evdev key code (from evdev.ecodes)
        
    Raises:
        KeyError: If key is not mapped
        
    Example:
        >>> pynput_to_evdev_code(Key.ctrl_l)
        29  # KEY_LEFTCTRL
    """
    from evdev import ecodes
    
    # For KeyCode with char
    if isinstance(key, KeyCode) and key.char:
        # Map character to evdev code
        char = key.char  # Use original char (case-sensitive for symbols)
        char_lower = char.lower()
        
        if char_lower.isalpha():
            # Convert 'a' -> KEY_A = 30, 'b' -> KEY_B = 48, etc.
            offset = ord(char_lower) - ord('a')
            return ecodes.KEY_A + offset
        elif char.isdigit():
            # Convert '0' -> KEY_0 = 11, '1' -> KEY_1 = 2, etc.
            if char == '0':
                return ecodes.KEY_0
            else:
                return ecodes.KEY_1 + int(char) - 1
        else:
            # Map symbols to evdev codes
            symbol_map = {
                '/': ecodes.KEY_SLASH,
                '.': ecodes.KEY_DOT,
                ',': ecodes.KEY_COMMA,
                '-': ecodes.KEY_MINUS,
                '=': ecodes.KEY_EQUAL,
                '[': ecodes.KEY_LEFTBRACE,
                ']': ecodes.KEY_RIGHTBRACE,
                ';': ecodes.KEY_SEMICOLON,
                "'": ecodes.KEY_APOSTROPHE,
                '\\': ecodes.KEY_BACKSLASH,
                '`': ecodes.KEY_GRAVE,
            }
            if char in symbol_map:
                return symbol_map[char]
    
    # For special keys (Key objects), use reverse mapping
    # Try to get from mapping first
    try:
        evdev_keyname = PYNPUT_TO_EVDEV_CODE[key]
        # Get the actual code from ecodes
        return getattr(ecodes, evdev_keyname)
    except KeyError:
        pass
    
    raise KeyError(f'Cannot convert pynput key to evdev code: {key}')

