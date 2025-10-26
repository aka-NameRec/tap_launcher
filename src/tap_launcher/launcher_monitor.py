"""Keyboard monitoring with command execution for tap-launcher.

This module integrates tap detection with command execution.
"""

import logging
from typing import Any

from common.key_normalizer import format_keys_display
from common.tap_monitor import TapMonitor

from .command_executor import CommandExecutor
from .hotkey_matcher import HotkeyMatcher
from .models import AppConfig


class LauncherMonitor:
    """Monitor keyboard for taps and execute commands.

    This class integrates:
    - TapMonitor from tap_detector (detects taps)
    - HotkeyMatcher (matches taps to hotkeys)
    - CommandExecutor (executes commands)
    """

    def __init__(
        self,
        config: AppConfig,
        matcher: HotkeyMatcher,
        executor: CommandExecutor,
    ) -> None:
        """Initialize the launcher monitor.

        Args:
            config: Application configuration
            matcher: Hotkey matcher for finding matching hotkeys
            executor: Command executor for running commands
        """
        self.config = config
        self.matcher = matcher
        self.executor = executor
        self.logger = logging.getLogger('tap_launcher.monitor')

        # Track emulated events to prevent re-processing
        # Format: {(key, is_press): count}
        self._emulated_events: dict[tuple[Any, bool], int] = {}

        # Create TapMonitor from tap_detector with validation
        self.tap_monitor = TapMonitor(
            timeout=config.tap_timeout,
            verbose=config.verbose_logging,
            on_keys_detected=self._on_tap_detected,
            on_tap_invalid=None,  # We don't need invalid tap notifications
            check_timer_delay=self._check_timer_delay,  # Check if timer should be delayed
        )

    def start(self) -> None:
        """Start monitoring keyboard (blocking call).

        This method will block until interrupted (Ctrl+C or SIGTERM).
        """
        self.logger.info(
            f'Starting tap launcher with timeout {self.config.tap_timeout}s'
        )
        self.logger.info(
            f'Monitoring {len(self.config.hotkeys)} hotkey combination(s)'
        )

        if self.config.debug_mode:
            self.logger.debug('Debug mode enabled')
            # Log all configured hotkeys
            for hotkey in self.config.hotkeys:
                keys_str = '+'.join(sorted(hotkey.keys))
                self.logger.debug(
                    f"  {keys_str} → {hotkey.command} {' '.join(hotkey.args)}"
                )

        # Create wrappers for event interception
        original_on_press = self.tap_monitor._on_press
        original_on_release = self.tap_monitor._on_release
        
        def on_press_wrapper(key: Any) -> None:
            """Wrapper for on_press with emulation checking."""
            event_key = (key, True)  # (key, is_press)
            
            # Check if this is our own emulated event
            if event_key in self._emulated_events and self._emulated_events[event_key] > 0:
                self._emulated_events[event_key] -= 1
                if self._emulated_events[event_key] == 0:
                    del self._emulated_events[event_key]
                # Skip - this is our own emulation
                self.logger.debug(f'Skipping emulated press: {key}')
                return
            
            # Emit ALL keys to test
            self.logger.debug(f'Emitting press: {key}')
            self._emit_key(key, is_press=True)
            
            # Process in TapMonitor
            original_on_press(key)
        
        def on_release_wrapper(key: Any) -> None:
            """Wrapper for on_release with emulation checking."""
            event_key = (key, False)  # (key, is_press)
            
            # Check if this is our own emulated event
            if event_key in self._emulated_events and self._emulated_events[event_key] > 0:
                self._emulated_events[event_key] -= 1
                if self._emulated_events[event_key] == 0:
                    del self._emulated_events[event_key]
                # Skip - this is our own emulation
                self.logger.debug(f'Skipping emulated release: {key}')
                return
            
            # Emit ALL releases to test
            self.logger.debug(f'Emitting release: {key}')
            self._emit_key(key, is_press=False)
            
            # Process in TapMonitor (state management)
            original_on_release(key)

        # Start the tap monitor with wrappers (this blocks)
        try:
            self.tap_monitor.backend.start(
                on_press=on_press_wrapper,
                on_release=on_release_wrapper
            )
        except KeyboardInterrupt:
            self.logger.info('Received interrupt signal, shutting down...')
            raise

    def stop(self) -> None:
        """Stop monitoring keyboard gracefully.

        This method stops the tap monitor listener, allowing
        the monitoring loop to exit cleanly.
        """
        if self.tap_monitor:
            self.tap_monitor.stop()
            self.logger.info('Tap monitor stopped')

    def _check_timer_delay(self, first_key_normalized: str) -> bool:
        """Check if timer should be delayed for the given first key.

        This callback is called by TapMonitor when the first key is pressed
        to determine if the tap timer should be delayed until the second key.

        Args:
            first_key_normalized: Normalized name of the first pressed key

        Returns:
            bool: True if timer should be delayed, False otherwise
        """
        return self.matcher.should_delay_timer_start(first_key_normalized)

    def _emit_key(self, key: Any, is_press: bool) -> None:
        """Emit (re-inject) a keyboard event with counter protection.
        
        Args:
            key: The key to emit
            is_press: True for press, False for release
        """
        event_key = (key, is_press)
        
        # Increment counter BEFORE emulation
        if event_key not in self._emulated_events:
            self._emulated_events[event_key] = 0
        self._emulated_events[event_key] += 1
        
        # Emit the event
        backend = self.tap_monitor.backend
        if hasattr(backend, 'emit_key_event'):
            backend.emit_key_event(key, is_press)
        else:
            # Fallback: use pynput Controller for pynput backend
            try:
                from pynput.keyboard import Controller
                controller = Controller()
                if is_press:
                    controller.press(key)
                else:
                    controller.release(key)
            except Exception as e:
                self.logger.error(f'Failed to emit key event: {e}')

    def _on_tap_detected(
        self,
        keys: set[Any],
        duration: float,
        trigger_key: Any,
        has_non_modifier: bool
    ) -> None:
        """Callback when a valid tap is detected.

        Args:
            keys: Set of pynput Key/KeyCode objects that were pressed
            duration: Duration of the tap in seconds
            trigger_key: The key that triggered completion
            has_non_modifier: True if tap contains non-modifier keys
        """
        # Try to match against configured hotkeys
        hotkey = self.matcher.match(keys)

        if hotkey:
            # Found a matching hotkey
            keys_str = '+'.join(sorted(hotkey.keys))

            if hotkey.description:
                self.logger.info(
                    f'Tap detected: {hotkey.description} '
                    f'(keys: {keys_str}, duration: {duration:.3f}s)'
                )
            else:
                self.logger.info(
                    f'Tap detected: {keys_str} (duration: {duration:.3f}s)'
                )

            # Execute the command
            success = self.executor.execute(hotkey)

            if not success:
                self.logger.warning(
                    f'Command execution failed for hotkey: {keys_str}'
                )

            # Hotkey matched - suppress trigger key
            # (Don't re-emit the non-modifier)
            if self.config.debug_mode:
                self.logger.debug(f'Hotkey matched - trigger key suppressed')

        else:
            # No matching hotkey - re-emit trigger key
            if has_non_modifier and trigger_key:
                if self.config.debug_mode:
                    keys_str = format_keys_display(keys)
                    self.logger.debug(
                        f'Tap detected but no matching hotkey: {keys_str} '
                        f'(duration: {duration:.3f}s) - re-emitting trigger key'
                    )
                # Re-emit the press event (release already handled)
                self._emit_key(trigger_key, is_press=True)
            elif self.config.debug_mode:
                keys_str = format_keys_display(keys)
                self.logger.debug(
                    f'Modifier-only tap, no matching hotkey: {keys_str} '
                    f'(duration: {duration:.3f}s)'
                )


