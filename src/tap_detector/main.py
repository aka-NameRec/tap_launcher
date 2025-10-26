"""Main entry point for tap-detector CLI application."""

import sys
from typing import Any

import typer

from common.tap_monitor import TapMonitor

from .formatter import format_header
from .formatter import format_keys_detected
from .formatter import format_verbose_header

app = typer.Typer(help='🎹 Tap Detector - Detect keyboard key combinations')


@app.command()
def main(
    verbose: bool = typer.Option(
        False,
        '--verbose', '-v',
        help='Enable verbose output with detailed debug traces',
    ),
) -> None:
    """
    Detect keyboard key combinations and generate TOML config fragments.

    Displays simultaneously pressed keys after they are all released.
    No time restrictions - any key combination will be detected and displayed.

    Usage examples:

        $ tap-detector

        $ tap-detector --verbose

    Press Ctrl+C to exit the detector.
    """

    # Define callback for key detection
    def on_keys_detected(
        keys: set[Any],
        duration: float,
        trigger_key: Any,
        has_non_modifier: bool
    ) -> None:
        """Called when keys are detected."""
        sys.stdout.write(format_keys_detected(keys, duration))

    # Print header
    if verbose:
        sys.stdout.write(format_verbose_header())
    else:
        sys.stdout.write(format_header())

    # Create and start monitor (no timeout = display mode)
    monitor = TapMonitor(
        timeout=None,  # No validation - display all combinations
        verbose=verbose,
        on_keys_detected=on_keys_detected,
    )

    try:
        monitor.start()
    except KeyboardInterrupt:
        sys.stdout.write('\n\n👋 Exiting tap detector. Goodbye!')
        sys.exit(0)


if __name__ == '__main__':
    app()