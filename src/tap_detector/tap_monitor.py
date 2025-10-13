"""Tap monitoring and detection logic.

This module implements the core tap detection logic using pynput keyboard listener.
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from time import perf_counter
from typing import Any

from pynput import keyboard

from .formatter import format_verbose_press
from .formatter import format_verbose_release
from .formatter import format_verbose_tap_result
from .formatter import format_verbose_waiting
from .key_normalizer import normalize_key


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
    """Monitor keyboard events and detect taps.

    A tap is a brief press-and-release of one or more keys within a timeout period.
    All keys must be released within the timeout for the tap to be valid.

    Args:
        timeout: Maximum duration in seconds for a valid tap
        verbose: Whether to output verbose debug information
        on_tap_detected: Callback when a valid tap is detected (keys, duration)
        on_tap_invalid: Callback when an invalid tap is detected (reason, keys, duration)
        check_timer_delay: Optional callback to check if timer should be delayed for a key.
            Takes normalized key name (str), returns True to delay timer start.
    """

    def __init__(
        self,
        timeout: float,
        verbose: bool = False,
        on_tap_detected: Callable[[set[Any], float], None] | None = None,
        on_tap_invalid: Callable[[str, set[Any], float], None] | None = None,
        check_timer_delay: Callable[[str], bool] | None = None,
    ) -> None:
        self.timeout = timeout
        self.verbose = verbose
        self.state = TapState()
        self.on_tap_detected = on_tap_detected
        self.on_tap_invalid = on_tap_invalid
        self.check_timer_delay = check_timer_delay
        self.listener: keyboard.Listener | None = None  # Will be set when start() is called

    def start(self) -> None:
        """Start monitoring keyboard events.

        This method blocks and listens for keyboard events until interrupted.
        """
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False  # Do NOT suppress events for other applications
        )
        self.listener.start()
        self.listener.join()

    def stop(self) -> None:
        """Stop monitoring keyboard events.

        This method stops the keyboard listener, allowing the monitoring
        loop to exit cleanly.
        """
        if self.listener:
            self.listener.stop()

    def _on_press(self, key: Any) -> None:
        """Handle key press event.

        Args:
            key: The pynput Key or KeyCode that was pressed
        """
        # Ignore auto-repeat (key already pressed)
        if key in self.state.pressed_keys:
            if self.verbose:
                print(f'[TRACE] {normalize_key(key)} already pressed (autorepeat), ignoring')  # noqa: T201
            return

        current_time = perf_counter()
        normalized_key = normalize_key(key)

        # If this is the first key, check if we should delay timer start
        if not self.state.is_active:
            # Check if timer should be delayed
            should_delay = self.check_timer_delay and self.check_timer_delay(normalized_key)

            if should_delay:
                # Delay timer start until second key
                self.state.is_active = True
                self.state.timer_delayed = True
                self.state.start_time = None

                if self.verbose:
                    print(f'[TRACE] 0.000s: {normalized_key} pressed')  # noqa: T201
                    print('[TRACE]        → Tap started, timer delayed until second key')  # noqa: T201
            else:
                # Classic behavior: start timer immediately
                self.state.start_time = current_time
                self.state.is_active = True

                if self.verbose:
                    print(format_verbose_press(normalized_key, 0.0, is_first=True))  # noqa: T201

        # Additional key in an ongoing tap
        else:
            # If timer was delayed and not started yet, start it now (second key)
            if self.state.timer_delayed and self.state.start_time is None:
                self.state.start_time = current_time
                self.state.timer_delayed = False

                if self.verbose:
                    print(f'[TRACE] 0.000s: {normalized_key} pressed')  # noqa: T201
                    print('[TRACE]        → Timer started NOW (second key)')  # noqa: T201

            # Timer is already running
            elif self.state.start_time is not None:
                elapsed = current_time - self.state.start_time

                # Check if timeout already exceeded
                if elapsed > self.timeout:
                    if self.verbose:
                        print(f'[TRACE]        → Timeout exceeded during tap: {elapsed:.3f}s > {self.timeout:.3f}s')  # noqa: T201

                    # Reset state and start a new tap
                    self.state.reset()
                    self.state.start_time = current_time
                    self.state.is_active = True

                    if self.verbose:
                        print(format_verbose_press(normalized_key, 0.0, is_first=True))  # noqa: T201
                elif self.verbose:
                    print(format_verbose_press(normalized_key, elapsed, is_first=False))  # noqa: T201

        # Add key to pressed and combination sets
        self.state.pressed_keys.add(key)
        self.state.tap_combination.add(key)

    def _on_release(self, key: Any) -> None:
        """Handle key release event.

        Args:
            key: The pynput Key or KeyCode that was released
        """
        # Remove from pressed keys
        if key in self.state.pressed_keys:
            self.state.pressed_keys.remove(key)

            if self.verbose:
                elapsed = perf_counter() - self.state.start_time if self.state.start_time else 0.0
                all_released = len(self.state.pressed_keys) == 0
                print(format_verbose_release(normalize_key(key), elapsed, all_released))  # noqa: T201

        # If all keys are released, check if this was a valid tap
        if not self.state.pressed_keys and self.state.is_active:
            # If timer was never started (only one key pressed with delayed timer)
            if self.state.start_time is None:
                if self.verbose:
                    print('[DEBUG] Tap invalid: timer never started (insufficient keys)')  # noqa: T201

                # This is an invalid tap - combination requires at least 2 keys
                if self.on_tap_invalid:
                    self.on_tap_invalid('insufficient keys', self.state.tap_combination.copy(), 0.0)

                # Reset state
                self.state.reset()

                if self.verbose:
                    print(format_verbose_waiting())  # noqa: T201
                return

            # Normal validation with timer
            end_time = perf_counter()
            duration = end_time - self.state.start_time

            if self.verbose:
                print(f'[DEBUG] All keys released, duration: {duration:.3f}s')  # noqa: T201

            # Validate tap
            is_valid = duration <= self.timeout

            if self.verbose:
                print(format_verbose_tap_result(is_valid, duration, self.timeout, self.state.tap_combination))  # noqa: T201

            if is_valid:
                # Valid tap detected!
                if self.on_tap_detected:
                    self.on_tap_detected(self.state.tap_combination.copy(), duration)
            # Invalid tap (timeout exceeded)
            elif self.on_tap_invalid:
                self.on_tap_invalid('timeout exceeded', self.state.tap_combination.copy(), duration)

            # Reset state
            self.state.reset()

            if self.verbose:
                print(format_verbose_waiting())  # noqa: T201

