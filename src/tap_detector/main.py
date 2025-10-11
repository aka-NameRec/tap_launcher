"""Main entry point for tap-detector CLI application."""

import sys

import typer

from .constants import DEFAULT_TIMEOUT
from .formatter import (
    format_header,
    format_tap_detected,
    format_tap_invalid,
    format_verbose_header,
)
from .tap_monitor import TapMonitor


app = typer.Typer(help="🎹 Tap Detector - Detect keyboard tap combinations")


@app.command()
def main(
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT,
        "--timeout", "-t",
        help="Tap timeout in seconds (maximum duration for a valid tap)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose output with detailed debug traces",
    ),
):
    """
    Detect keyboard tap combinations and generate TOML config fragments.
    
    A tap is a brief press-and-release of one or more keys within the timeout period.
    All keys must be released within the timeout for the tap to be valid.
    
    Usage examples:
    
        $ tap-detector
        
        $ tap-detector --timeout 0.3
        
        $ tap-detector --verbose
    
    Press Ctrl+C to exit the detector.
    """
    
    # Define callbacks for tap events
    def on_tap_detected(keys: set, duration: float):
        """Called when a valid tap is detected."""
        print(format_tap_detected(keys, duration))
    
    def on_tap_invalid(reason: str, keys: set, duration: float):
        """Called when an invalid tap is detected."""
        print(format_tap_invalid(reason, keys, duration))
    
    # Print header
    if verbose:
        print(format_verbose_header(timeout))
    else:
        print(format_header(timeout))
    
    # Create and start monitor
    monitor = TapMonitor(
        timeout=timeout,
        verbose=verbose,
        on_tap_detected=on_tap_detected,
        on_tap_invalid=on_tap_invalid,
    )
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting tap detector. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    app()

