"""Output formatting utilities for tap detector.

This module provides detector-specific formatting functions for console output,
including TOML configuration fragments. Generic verbose formatting is provided
by common.verbose_formatter.
"""

from .constants import __version__
from common.key_normalizer import format_keys_display
from common.key_normalizer import format_keys_toml
from common.verbose_formatter import (
    format_verbose_press,
    format_verbose_release,
    format_verbose_tap_result,
    format_verbose_waiting,
)


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


def format_keys_detected(keys: set[str], duration: float) -> str:
    """Format a key combination detection message.

    Args:
        keys: Set of canonical key names (strings) that were detected
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


# Verbose formatting functions are imported from common.verbose_formatter
# Re-export them for backward compatibility with detector code that imports from here


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


# format_verbose_tap_result and format_verbose_waiting are imported from common.verbose_formatter