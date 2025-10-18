"""Keyboard monitoring with command execution for tap-launcher.

This module integrates tap detection with command execution.
"""

import logging
from typing import Any

from tap_detector.key_normalizer import format_keys_display
from tap_detector.tap_monitor import TapMonitor

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

        # Start the tap monitor (this blocks)
        try:
            self.tap_monitor.start()
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

    def _on_tap_detected(self, keys: set[Any], duration: float) -> None:
        """Callback when a valid tap is detected.

        This is called by TapMonitor when all keys are released
        within the timeout period.

        Args:
            keys: Set of pynput Key/KeyCode objects that were pressed
            duration: Duration of the tap in seconds
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

        # Tap detected but no matching hotkey
        # This is only logged in debug mode to avoid spam
        elif self.config.debug_mode:
            keys_str = format_keys_display(keys)
            self.logger.debug(
                f'Tap detected but no matching hotkey: {keys_str} '
                f'(duration: {duration:.3f}s)'
            )


