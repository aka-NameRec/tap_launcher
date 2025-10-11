"""Tap monitoring and detection logic.

This module implements the core tap detection logic using pynput keyboard listener.
"""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, Optional

from pynput import keyboard

from .key_normalizer import normalize_key
from .formatter import (
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
        start_time: Timestamp when the first key was pressed (None if not active)
        is_active: Whether a tap is currently in progress
    """
    pressed_keys: set = field(default_factory=set)
    tap_combination: set = field(default_factory=set)
    start_time: Optional[float] = None
    is_active: bool = False
    
    def reset(self):
        """Reset the tap state to initial values."""
        self.pressed_keys.clear()
        self.tap_combination.clear()
        self.start_time = None
        self.is_active = False


class TapMonitor:
    """Monitor keyboard events and detect taps.
    
    A tap is a brief press-and-release of one or more keys within a timeout period.
    All keys must be released within the timeout for the tap to be valid.
    
    Args:
        timeout: Maximum duration in seconds for a valid tap
        verbose: Whether to output verbose debug information
        on_tap_detected: Callback when a valid tap is detected (keys, duration)
        on_tap_invalid: Callback when an invalid tap is detected (reason, keys, duration)
    """
    
    def __init__(
        self,
        timeout: float,
        verbose: bool = False,
        on_tap_detected: Optional[Callable[[set, float], None]] = None,
        on_tap_invalid: Optional[Callable[[str, set, float], None]] = None,
    ):
        self.timeout = timeout
        self.verbose = verbose
        self.state = TapState()
        self.on_tap_detected = on_tap_detected
        self.on_tap_invalid = on_tap_invalid
    
    def start(self):
        """Start monitoring keyboard events.
        
        This method blocks and listens for keyboard events until interrupted.
        """
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False  # Do NOT suppress events for other applications
        ) as listener:
            listener.join()
    
    def _on_press(self, key):
        """Handle key press event.
        
        Args:
            key: The pynput Key or KeyCode that was pressed
        """
        # Ignore auto-repeat (key already pressed)
        if key in self.state.pressed_keys:
            if self.verbose:
                print(f"[TRACE] {normalize_key(key)} already pressed (autorepeat), ignoring")
            return
        
        # If this is the first key, start the tap
        if not self.state.is_active:
            self.state.start_time = perf_counter()
            self.state.is_active = True
            
            if self.verbose:
                elapsed = 0.0
                print(format_verbose_press(normalize_key(key), elapsed, is_first=True))
        else:
            # Additional key in an ongoing tap
            if self.verbose:
                elapsed = perf_counter() - self.state.start_time
                print(format_verbose_press(normalize_key(key), elapsed, is_first=False))
        
        # Add key to pressed and combination sets
        self.state.pressed_keys.add(key)
        self.state.tap_combination.add(key)
        
        # Check if timeout already exceeded (while still pressing)
        if self.state.start_time:
            elapsed = perf_counter() - self.state.start_time
            if elapsed > self.timeout:
                if self.verbose:
                    print(f"[TRACE]        → Timeout exceeded during tap: {elapsed:.3f}s > {self.timeout:.3f}s")
                # Don't reset yet - wait for all keys to be released
    
    def _on_release(self, key):
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
                print(format_verbose_release(normalize_key(key), elapsed, all_released))
        
        # If all keys are released, check if this was a valid tap
        if not self.state.pressed_keys and self.state.is_active:
            end_time = perf_counter()
            duration = end_time - self.state.start_time
            
            if self.verbose:
                print(f"[DEBUG] All keys released, duration: {duration:.3f}s")
            
            # Validate tap
            is_valid = duration <= self.timeout
            
            if self.verbose:
                print(format_verbose_tap_result(is_valid, duration, self.timeout, self.state.tap_combination))
            
            if is_valid:
                # Valid tap detected!
                if self.on_tap_detected:
                    self.on_tap_detected(self.state.tap_combination.copy(), duration)
            else:
                # Invalid tap (timeout exceeded)
                if self.on_tap_invalid:
                    self.on_tap_invalid("timeout exceeded", self.state.tap_combination.copy(), duration)
            
            # Reset state
            self.state.reset()
            
            if self.verbose:
                print(format_verbose_waiting())

