"""Output formatting utilities for tap detector.

This module provides functions to format key detection results for console output,
including TOML configuration fragments.
"""

from .constants import __version__
from common.key_normalizer import format_keys_display
from common.key_normalizer import format_keys_toml


def format_header() -> str:
    """Format the application header.
        
    Returns:
        str: Formatted header string
    """
    return f"""🎹 Tap Detector v{__version__}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detecting key combinations (no time restrictions)
Press Ctrl+C to exit

Listening for key combinations...
"""


def format_keys_detected(keys: set, duration: float) -> str:
    """Format a key combination detection message.

    Args:
        keys: Set of pynput Key/KeyCode objects that were detected
        duration: Duration of the key combination in seconds (ignored in display)

    Returns:
        str: Formatted message with TOML config fragment
    """
    keys_display = format_keys_display(keys)
    keys_toml = format_keys_toml(keys)

    return f"""
✓ Keys detected: {keys_display}

  📋 TOML config fragment (copy to config.toml):
  ────────────────────────────────────────────
  [[hotkeys]]
  keys = {keys_toml}
  command = "your-command-here"
  args = []
  description = "Description here"
  ────────────────────────────────────────────

Listening for key combinations...
"""


def format_verbose_press(key_str: str, elapsed: float, is_first: bool) -> str:
    """Format a verbose key press event.

    Args:
        key_str: Normalized key string
        elapsed: Time elapsed since combination start
        is_first: Whether this is the first key in the combination

    Returns:
        str: Formatted trace message
    """
    if is_first:
        return f'[TRACE] {elapsed:.3f}s: {key_str} pressed\n[TRACE]        → Combination started'
    return f'[TRACE] {elapsed:.3f}s: {key_str} pressed'


def format_verbose_release(key_str: str, elapsed: float, all_released: bool) -> str:
    """Format a verbose key release event.

    Args:
        key_str: Normalized key string
        elapsed: Time elapsed since combination start
        all_released: Whether all keys have been released

    Returns:
        str: Formatted trace message
    """
    msg = f'[TRACE] {elapsed:.3f}s: {key_str} released'
    if all_released:
        msg += '\n[TRACE]        → All keys released'
    return msg


def format_verbose_header() -> str:
    """Format the verbose mode header.

    Returns:
        str: Formatted header string
    """
    return f"""🎹 Tap Detector v{__version__} (verbose mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detecting key combinations (no time restrictions)

[DEBUG] Waiting for key events...
"""


def format_verbose_tap_result(is_valid: bool, duration: float, timeout: float, keys: set) -> str:
    """Format a verbose tap validation result.

    Args:
        is_valid: Whether the tap was valid
        duration: Duration of the tap in seconds
        timeout: Timeout threshold in seconds
        keys: Set of keys that were pressed

    Returns:
        str: Formatted validation result message
    """
    # format_keys_display already imported at module level
    keys_str = format_keys_display(keys)
    
    if is_valid:
        return f'[DEBUG] ✓ Valid tap: {keys_str} (duration: {duration:.3f}s ≤ {timeout:.3f}s)'
    else:
        return f'[DEBUG] ✗ Invalid tap: {keys_str} (duration: {duration:.3f}s > {timeout:.3f}s)'


def format_verbose_waiting() -> str:
    """Format the verbose waiting message.

    Returns:
        str: Formatted waiting message
    """
    return '\n[DEBUG] Waiting for key events...'