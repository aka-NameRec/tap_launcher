"""Hotkey matching logic for tap-launcher.

This module handles matching detected tap combinations against
configured hotkey combinations.
"""

from typing import Any

from tap_detector.key_normalizer import normalize_key

from .models import HotkeyConfig


class HotkeyMatcher:
    """Match detected tap combinations against configured hotkeys.

    This class builds an efficient lookup structure from the configured
    hotkeys and provides fast matching of detected key combinations.
    """

    def __init__(self, hotkeys: list[HotkeyConfig]) -> None:
        """Initialize the matcher with configured hotkeys.

        Args:
            hotkeys: List of configured hotkey combinations
        """
        # Build a map from key sets to hotkey configs for O(1) lookup
        self._hotkey_map: dict[frozenset[str], HotkeyConfig] = {
            hk.keys_set(): hk for hk in hotkeys
        }

        # Build index for delayed timer start feature
        # Map: first key name -> list of hotkeys with start_timer_from_second_key=True
        self._delayed_start_map: dict[str, list[HotkeyConfig]] = {}
        for hk in hotkeys:
            if hk.start_timer_from_second_key and len(hk.keys) >= 2:
                # Index by each key in the combination
                for key in hk.keys:
                    if key not in self._delayed_start_map:
                        self._delayed_start_map[key] = []
                    self._delayed_start_map[key].append(hk)

    def match(self, detected_keys: set[Any]) -> HotkeyConfig | None:
        """Match detected keys against configured hotkeys.

        Args:
            detected_keys: Set of pynput Key/KeyCode objects detected in tap

        Returns:
            HotkeyConfig if a matching hotkey is found, None otherwise

        Example:
            >>> matcher = HotkeyMatcher([
            ...     HotkeyConfig(keys=["ctrl_l", "shift_l"], command="cmd1"),
            ...     HotkeyConfig(keys=["alt_l", "t"], command="cmd2"),
            ... ])
            >>> from pynput.keyboard import Key
            >>> keys = {Key.ctrl_l, Key.shift_l}
            >>> hotkey = matcher.match(keys)
            >>> hotkey.command
            'cmd1'
        """
        # Normalize the detected keys to canonical names
        normalized = self._normalize_keys(detected_keys)

        # Convert to frozen set for lookup
        keys_frozen = frozenset(normalized)

        # Look up in the hotkey map
        return self._hotkey_map.get(keys_frozen)

    def _normalize_keys(self, keys: set[Any]) -> list[str]:
        """Normalize pynput Key objects to canonical key names.

        This uses the key_normalizer from tap_detector to ensure
        consistent naming (e.g., Key.ctrl_l -> "ctrl_l").

        Args:
            keys: Set of pynput Key/KeyCode objects

        Returns:
            list[str]: List of normalized key names
        """
        return [normalize_key(key) for key in keys]

    def get_all_combinations(self) -> list[frozenset[str]]:
        """Get all configured key combinations.

        This is useful for debugging and displaying configured hotkeys.

        Returns:
            list[frozenset[str]]: List of all configured key combinations
        """
        return list(self._hotkey_map.keys())

    def should_delay_timer_start(self, first_key_normalized: str) -> bool:
        """Check if timer start should be delayed for the given first key.

        Returns True if there is at least one hotkey combination that:
        - Starts with the given key
        - Has start_timer_from_second_key=True

        This is used by TapMonitor to determine whether to delay the
        timer start when the first key is pressed.

        Args:
            first_key_normalized: Normalized name of the first pressed key

        Returns:
            bool: True if timer should be delayed, False otherwise

        Example:
            >>> matcher = HotkeyMatcher([
            ...     HotkeyConfig(
            ...         keys=["ctrl_l", "shift_l"],
            ...         command="cmd",
            ...         start_timer_from_second_key=True
            ...     )
            ... ])
            >>> matcher.should_delay_timer_start("ctrl_l")
            True
            >>> matcher.should_delay_timer_start("alt_l")
            False
        """
        return first_key_normalized in self._delayed_start_map


