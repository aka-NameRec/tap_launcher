"""Key normalization utilities for tap detector.

This module operates on canonical key names (str), not pynput objects.
Canonical names examples: "ctrl_l", "shift_r", "a", "delete", "f1".
"""

from typing import Any


def normalize_key(key: Any) -> str:
    """Normalize a key to its canonical string name.

    This function assumes keys are already strings (canonical names) or
    simple characters. It lowercases alpha characters.

    Args:
        key: Canonical key name (str) or character-like object

    Returns:
        str: Canonical key name (e.g., "ctrl_l", "a", "f1")

    Examples:
        >>> normalize_key('ctrl_l')
        'ctrl_l'
        >>> normalize_key('A')
        'a'
        >>> normalize_key('f1')
        'f1'
    """
    if isinstance(key, str):
        return key.lower()
    if hasattr(key, 'char') and getattr(key, 'char'):
        return str(getattr(key, 'char')).lower()
    return str(key).lower()


def format_keys_display(keys: set[Any]) -> str:
    """Format keys for console display with + separator.

    Args:
        keys: Set of canonical key names (str)

    Returns:
        str: Formatted string like "ctrl_l+shift_l+a"

    Examples:
        >>> format_keys_display({'ctrl_l', 'shift_l'})
        'ctrl_l+shift_l'
    """
    normalized = [normalize_key(k) for k in keys]
    return '+'.join(sorted(normalized))


def is_modifier_key(key: Any) -> bool:
    """Check if a key is a modifier key.

    Modifier keys are: Ctrl, Shift, Alt, AltGr, Super/Win/Cmd
    
    Args:
        key: Canonical key name (str) or similar

    Returns:
        bool: True if the key is a modifier, False otherwise
    """
    name = normalize_key(key)
    return name in {
        'ctrl_l','ctrl_r','shift_l','shift_r','alt_l','alt_r','alt_gr','super','super_l','super_r'
    }


def format_keys_toml(keys: set[Any]) -> list[str]:
    """Format keys for TOML config with proper sorting.

    Sorting order: modifiers (alphabetically) → regular keys (alphabetically)

    Args:
        keys: Set of canonical key names (str)

    Returns:
        list[str]: Sorted list of normalized key names

    Examples:
        >>> format_keys_toml({'ctrl_l', 'shift_l', 'a'})
        ['ctrl_l', 'shift_l', 'a']
        >>> format_keys_toml({'alt_r', 't'})
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

