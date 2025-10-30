"""Tap monitoring and detection logic.

This module implements the core tap detection logic using keyboard backend abstraction.
Uses evdev backend which works on both X11 and Wayland.
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from time import perf_counter
from typing import Any

from common.backends import KeyboardBackend, create_backend
from common.key_normalizer import is_modifier_key, normalize_key
from common.logging_utils import get_logger
from common.verbose_formatter import (
    format_verbose_press,
    format_verbose_release,
    format_verbose_tap_result,
    format_verbose_waiting,
)


@dataclass
class TapState:
    """State of the current tap being monitored.

    Attributes:
        pressed_keys: Set of currently pressed keys
        tap_combination: Set of all keys that have been pressed during this tap
        start_time: Timestamp when the tap timer started (None if not started yet)
        is_active: Whether a tap is currently in progress
        timer_delayed: True if timer start is delayed until second key press
    """
    pressed_keys: set[Any] = field(default_factory=set)
    tap_combination: set[Any] = field(default_factory=set)
    start_time: float | None = None
    is_active: bool = False
    timer_delayed: bool = False

    def reset(self) -> None:
        """Reset the tap state to initial values."""
        self.pressed_keys.clear()
        self.tap_combination.clear()
        self.start_time = None
        self.is_active = False
        self.timer_delayed = False


class TapMonitor:
    """Monitor keyboard events and detect key combinations.

    Can operate in two modes:
    1. Validation mode (timeout provided): Validates taps against timeout
    2. Display mode (no timeout): Shows all key combinations without validation

    Tap Semantics (important):
    - Taps with non-modifiers complete when FIRST NON-MODIFIER is pressed
      (Delete, letters, numbers, etc.)
    - Taps with ONLY modifiers complete when FIRST key is released
      (Ctrl+Shift uses old semantics)
    - "Simultaneous" means all keys were pressed before completion event
    - Duration is measured from first press to completion event
    - This enables event suppression for hotkeys

    Args:
        timeout: Maximum duration in seconds for a valid tap (None = no validation)
        verbose: Whether to output verbose debug information
        on_keys_detected: Callback when keys are detected
            (keys, duration, trigger_key, has_non_modifier)
        on_tap_invalid: Callback when an invalid tap is detected (reason, keys, duration)
        check_timer_delay: Optional callback to check if timer should be delayed for a key.
            Takes normalized key name (str), returns True to delay timer start.
        backend: Optional keyboard backend to use (auto-detects X11/Wayland if None)
    """

    def __init__(
        self,
        timeout: float | None = None,
        verbose: bool = False,
        on_keys_detected: Callable[[set[Any], float, Any, bool], None] | None = None,
        on_tap_invalid: Callable[[str, set[Any], float], None] | None = None,
        check_timer_delay: Callable[[str], bool] | None = None,
        backend: KeyboardBackend | None = None,
    ) -> None:
        self.timeout = timeout
        self.validate_timeout = timeout is not None
        self.verbose = verbose
        self.state = TapState()
        self.on_keys_detected = on_keys_detected
        self.on_tap_invalid = on_tap_invalid
        self.check_timer_delay = check_timer_delay
        self.logger = get_logger('common.tap_monitor')
        
        # Create or use provided backend (auto-detects X11 vs Wayland)
        self.backend = backend or create_backend()

    def start(self) -> None:
        """Start monitoring keyboard events.

        This method blocks and listens for keyboard events until interrupted.
        Uses the configured evdev backend (works on both X11 and Wayland).
        """
        self.backend.start(
            on_press=self._on_press,
            on_release=self._on_release
        )

    def stop(self) -> None:
        """Stop monitoring keyboard events.

        This method stops the keyboard listener, allowing the monitoring
        loop to exit cleanly.
        """
        self.backend.stop()

    def _on_press(self, key: Any) -> None:
        """Handle key press event.

        Args:
            key: Canonical key name (str) like 'ctrl_l', 'a', 'delete'
        """
        # Ignore auto-repeat (key already pressed)
        if key in self.state.pressed_keys:
            if self.verbose:
                self.logger.debug(f'{normalize_key(key)} already pressed (autorepeat), ignoring')
            return

        current_time = perf_counter()
        normalized_key = normalize_key(key)

        # If this is the first key, check if we should delay timer start
        if not self.state.is_active:
            # Check if timer should be delayed (only in validation mode)
            should_delay = (self.validate_timeout and 
                          self.check_timer_delay and 
                          self.check_timer_delay(normalized_key))

            if should_delay:
                # Delay timer start until second key
                self.state.is_active = True
                self.state.timer_delayed = True
                self.state.start_time = None

                if self.verbose:
                    self.logger.debug('0.000s: %s pressed → Tap started, timer delayed until second key', normalized_key)
            else:
                # Start timer immediately (or no timer in display mode)
                self.state.start_time = current_time if self.validate_timeout else None
                self.state.is_active = True

                if self.verbose:
                    if self.validate_timeout:
                        self.logger.debug(format_verbose_press(normalized_key, 0.0, is_first=True))
                    else:
                        self.logger.debug('0.000s: %s pressed → Tap started (no validation)', normalized_key)

        # Additional key in an ongoing tap
        else:
            # If timer was delayed and not started yet, start it now (second key)
            if (self.validate_timeout and 
                self.state.timer_delayed and 
                self.state.start_time is None):
                self.state.start_time = current_time
                self.state.timer_delayed = False

                if self.verbose:
                    self.logger.debug('0.000s: %s pressed → Timer started NOW (second key)', normalized_key)

            # Timer is already running (validation mode)
            elif self.validate_timeout and self.state.start_time is not None:
                elapsed = current_time - self.state.start_time

                # Check if timeout already exceeded
                if elapsed > self.timeout:
                    if self.verbose:
                        self.logger.debug('Timeout exceeded during tap: %.3fs > %.3fs', elapsed, self.timeout)

                    # Reset state and start a new tap
                    self.state.reset()
                    self.state.start_time = current_time
                    self.state.is_active = True

                    if self.verbose:
                        self.logger.debug(format_verbose_press(normalized_key, 0.0, is_first=True))
                elif self.verbose:
                    self.logger.debug(format_verbose_press(normalized_key, elapsed, is_first=False))

            # Display mode - just log the key
            elif not self.validate_timeout and self.verbose:
                self.logger.debug('%s pressed', normalized_key)

        # Add key to pressed and combination sets
        self.state.pressed_keys.add(key)
        self.state.tap_combination.add(key)

        # NEW SEMANTIC: If non-modifier key, complete tap immediately
        if not is_modifier_key(key) and self.state.is_active:
            # Calculate duration
            end_time = perf_counter()
            duration = end_time - self.state.start_time if self.state.start_time else 0.0

            if self.verbose:
                self.logger.debug('Non-modifier pressed, completing tap, duration: %.3fs', duration)

            # Validation mode: check timeout
            if self.validate_timeout:
                # If timer never started (only one key with delayed timer)
                if self.state.start_time is None:
                    if self.verbose:
                        self.logger.debug('Tap invalid: timer never started (insufficient keys)')

                    if self.on_tap_invalid:
                        self.on_tap_invalid('insufficient keys', self.state.tap_combination.copy(), 0.0)

                    self.state.reset()
                    if self.verbose:
                        self.logger.debug(format_verbose_waiting())
                    return

                is_valid = duration <= self.timeout

                if self.verbose:
                    self.logger.debug(format_verbose_tap_result(is_valid, duration, self.timeout, self.state.tap_combination))

                if is_valid:
                    # Valid tap detected!
                    if self.on_keys_detected:
                        self.on_keys_detected(
                            self.state.tap_combination.copy(),
                            duration,
                            key,  # trigger_key
                            True  # has_non_modifier
                        )
                elif self.on_tap_invalid:
                    self.on_tap_invalid('timeout exceeded', self.state.tap_combination.copy(), duration)

            # Display mode: always show combination
            else:
                if self.on_keys_detected:
                    self.on_keys_detected(
                        self.state.tap_combination.copy(),
                        duration,
                        key,  # trigger_key
                        True  # has_non_modifier
                    )

            # Reset state
            self.state.reset()

            if self.verbose:
                self.logger.debug(format_verbose_waiting())

    def _on_release(self, key: Any) -> None:
        """Handle key release event.

        Args:
            key: Canonical key name (str) like 'ctrl_l', 'a', 'delete'
        """
        # NEW SEMANTIC: Check if this is a release during an active tap
        # Tap completes on FIRST key release, not when all keys are released
        should_process_tap = (key in self.state.pressed_keys and self.state.is_active)
        
        # Remove from pressed keys
        if key in self.state.pressed_keys:
            self.state.pressed_keys.remove(key)

            if self.verbose:
                elapsed = perf_counter() - self.state.start_time if self.state.start_time else 0.0
                all_released = len(self.state.pressed_keys) == 0
                self.logger.debug(format_verbose_release(normalize_key(key), elapsed, all_released))

        # Process the combination on FIRST key release (not when all keys are released)
        # This solves "stuck keys" problem and provides more natural tap semantics
        if should_process_tap:
            # If timer was never started (only one key pressed with delayed timer)
            if self.validate_timeout and self.state.start_time is None:
                if self.verbose:
                    self.logger.debug('Tap invalid: timer never started (insufficient keys)')

                # This is an invalid tap - combination requires at least 2 keys
                if self.on_tap_invalid:
                    self.on_tap_invalid('insufficient keys', self.state.tap_combination.copy(), 0.0)

                # Reset state
                self.state.reset()

                if self.verbose:
                    self.logger.debug(format_verbose_waiting())
                return

            # Calculate duration
            end_time = perf_counter()
            duration = end_time - self.state.start_time if self.state.start_time else 0.0

            if self.verbose:
                self.logger.debug('Modifier-only tap, first key released, duration: %.3fs', duration)

            # Validation mode: check timeout
            if self.validate_timeout:
                is_valid = duration <= self.timeout

                if self.verbose:
                    self.logger.debug(format_verbose_tap_result(is_valid, duration, self.timeout, self.state.tap_combination))

                if is_valid:
                    # Valid tap detected (modifier-only)!
                    if self.on_keys_detected:
                        self.on_keys_detected(
                            self.state.tap_combination.copy(),
                            duration,
                            key,  # trigger_key (released key)
                            False  # has_non_modifier (modifier-only tap)
                        )
                # Invalid tap (timeout exceeded)
                elif self.on_tap_invalid:
                    self.on_tap_invalid('timeout exceeded', self.state.tap_combination.copy(), duration)

            # Display mode: always show the combination
            else:
                if self.on_keys_detected:
                    self.on_keys_detected(
                        self.state.tap_combination.copy(),
                        duration,
                        key,  # trigger_key (released key)
                        False  # has_non_modifier (modifier-only tap)
                    )

            # Reset state
            self.state.reset()

            if self.verbose:
                self.logger.debug(format_verbose_waiting())