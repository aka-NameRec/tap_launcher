"""Main entry point for tap-detector CLI application."""

import sys

import typer

from common.backends.detector import create_backend
from common.backends.device_listing import list_keyboard_devices
from common.logging_utils import get_logger
from common.tap_monitor import TapMonitor

from .formatter import format_header
from .formatter import format_keys_detected
from .formatter import format_verbose_header

app = typer.Typer(help='🎹 Tap Detector - Detect keyboard key combinations')


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
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
    
    Use 'tap-detector device-list' to see available keyboard devices.
    """
    # If a subcommand was invoked, don't run detection
    if ctx.invoked_subcommand is not None:
        return

    # Define callback for key detection
    def on_keys_detected(
        keys: set[str],
        duration: float,
        trigger_key: str,
        has_non_modifier: bool
    ) -> None:
        """Called when keys are detected."""
        sys.stdout.write(format_keys_detected(keys, duration))

    # Print header
    if verbose:
        sys.stdout.write(format_verbose_header())
    else:
        sys.stdout.write(format_header())

    # Create backend (auto-detects all available keyboards)
    backend = create_backend()
    
    # Create and start monitor (no timeout = display mode)
    monitor = TapMonitor(
        timeout=None,  # No validation - display all combinations
        verbose=verbose,
        on_keys_detected=on_keys_detected,
        backend=backend,  # Use the configured backend
    )

    try:
        monitor.start()
    except KeyboardInterrupt:
        sys.stdout.write('\n\n👋 Exiting tap detector. Goodbye!')
        sys.exit(0)


def _list_keyboard_devices() -> None:
    """List all available keyboard devices."""
    try:
        devices = list_keyboard_devices()
    except PermissionError as e:
        typer.echo(
            f'❌ {e}\n'
            '   Add user to "input" group:\n'
            '   sudo usermod -a -G input $USER\n'
            '   Then log out and back in.',
            err=True
        )
        raise typer.Exit(1)
    except OSError as e:
        typer.echo(f'❌ Error listing devices: {e}', err=True)
        raise typer.Exit(1)
    
    if not devices:
        typer.echo('❌ No keyboard devices found')
        typer.echo('   Found input devices, but none have keyboard capabilities.')
        raise typer.Exit(1)
    
    # Separate physical and virtual devices
    physical_keyboards = [d for d in devices if not d['is_virtual']]
    virtual_keyboards = [d for d in devices if d['is_virtual']]
    
    # Display physical keyboards first
    typer.echo('📱 Available keyboard devices:\n')
    
    if physical_keyboards:
        typer.echo('Physical keyboards:')
        for i, device in enumerate(physical_keyboards, 1):
            typer.echo(f'  {i}. {device["name"]}')
            typer.echo(f'     Path: {device["path"]}')
        typer.echo()
    
    if virtual_keyboards:
        typer.echo('Virtual keyboards (uinput):')
        for i, device in enumerate(virtual_keyboards, 1):
            typer.echo(f'  {i}. {device["name"]} [VIRTUAL]')
            typer.echo(f'     Path: {device["path"]}')
        typer.echo()
    


@app.command(name='device-list')
def device_list() -> None:
    """List all available keyboard devices.
    
    Displays physical and virtual keyboard devices found in the system.
    
    Example:
        $ tap-detector device-list
    """
    _list_keyboard_devices()


if __name__ == '__main__':
    app()