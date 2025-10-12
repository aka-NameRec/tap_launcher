"""Output formatting utilities for tap detector.

This module provides functions to format tap detection results for console output,
including TOML configuration fragments.
"""

from .constants import __version__
from .key_normalizer import format_keys_display
from .key_normalizer import format_keys_toml


def format_header(timeout: float) -> str:
    """Format the application header.

    Args:
        timeout: Tap timeout in seconds

    Returns:
        str: Formatted header string
    """
    return f"""🎹 Tap Detector v{__version__}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detecting taps with timeout: {timeout}s
Press Ctrl+C to exit

Listening for taps...
"""


def format_tap_detected(keys: set, duration: float) -> str:
    """Format a successful tap detection message.

    Args:
        keys: Set of pynput Key/KeyCode objects that were detected
        duration: Duration of the tap in seconds

    Returns:
        str: Formatted message with TOML config fragment
    """
    keys_display = format_keys_display(keys)
    keys_toml = format_keys_toml(keys)

    return f"""
✓ Tap detected! Duration: {duration:.2f}s
  Keys: {keys_display}

  📋 TOML config fragment (copy to config.toml):
  ────────────────────────────────────────────
  [[hotkeys]]
  keys = {keys_toml}
  command = "your-command-here"
  args = []
  description = "Description here"
  ────────────────────────────────────────────

Listening for taps...
"""


def format_tap_invalid(reason: str, keys: set, duration: float) -> str:
    """Format an invalid tap message.

    Args:
        reason: Reason why the tap was invalid
        keys: Set of pynput Key/KeyCode objects that were pressed
        duration: Duration attempted

    Returns:
        str: Formatted error message
    """
    keys_display = format_keys_display(keys)

    return f"""
✗ Invalid tap ({reason}: {duration:.2f}s)
  Keys: {keys_display}
  Hint: Release keys faster for a valid tap!

Listening for taps...
"""


def format_verbose_press(key_str: str, elapsed: float, is_first: bool) -> str:
    """Format a verbose key press event.

    Args:
        key_str: Normalized key string
        elapsed: Time elapsed since tap start
        is_first: Whether this is the first key in the tap

    Returns:
        str: Formatted trace message
    """
    if is_first:
        return f'[TRACE] {elapsed:.3f}s: {key_str} pressed\n[TRACE]        → Tap started'
    return f'[TRACE] {elapsed:.3f}s: {key_str} pressed'


def format_verbose_release(key_str: str, elapsed: float, all_released: bool) -> str:
    """Format a verbose key release event.

    Args:
        key_str: Normalized key string
        elapsed: Time elapsed since tap start
        all_released: Whether all keys have been released

    Returns:
        str: Formatted trace message
    """
    msg = f'[TRACE] {elapsed:.3f}s: {key_str} released'
    if all_released:
        msg += '\n[TRACE]        → All keys released'
    return msg


def format_verbose_tap_result(is_valid: bool, duration: float, timeout: float, keys: set) -> str:
    """Format verbose tap validation result.

    Args:
        is_valid: Whether the tap is valid
        duration: Tap duration in seconds
        timeout: Configured timeout
        keys: Set of keys in the tap

    Returns:
        str: Formatted debug message
    """
    keys_display = format_keys_display(keys)

    if is_valid:
        return f'[DEBUG] Tap valid! Duration: {duration:.3f}s < {timeout:.3f}s'
    return (
        f'[DEBUG] Tap invalid: timeout exceeded ({duration:.3f}s > {timeout:.3f}s)\n'
        f'[DEBUG] Keys attempted: {keys_display}'
    )


def format_verbose_header(timeout: float) -> str:
    """Format the verbose mode header.

    Args:
        timeout: Tap timeout in seconds

    Returns:
        str: Formatted header string
    """
    return f"""🎹 Tap Detector v{__version__} (verbose mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detecting taps with timeout: {timeout}s

[DEBUG] Waiting for key events...
"""


def format_verbose_waiting() -> str:
    """Format the verbose waiting message.

    Returns:
        str: Formatted waiting message
    """
    return '\n[DEBUG] Waiting for key events...'

