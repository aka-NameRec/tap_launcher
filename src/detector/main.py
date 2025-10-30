"""Main entry point for tap-detector CLI application."""

import sys
from typing import Any

import typer

from common.backends.detector import create_backend
from common.tap_monitor import TapMonitor

from .formatter import format_header
from .formatter import format_keys_detected
from .formatter import format_verbose_header

app = typer.Typer(help='🎹 Tap Detector - Detect keyboard key combinations')


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    device_name: str | None = typer.Option(
        None,
        '--device-name',
        help='Force specific keyboard device by name (partial match, case-insensitive). '
             'If not specified, auto-detects the first physical keyboard.',
    ),
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

        $ tap-detector --device-name "A4tech"

    Press Ctrl+C to exit the detector.
    
    Use 'tap-detector device-list' to see available keyboard devices.
    """
    # If a subcommand was invoked, don't run detection
    if ctx.invoked_subcommand is not None:
        return

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

    # Create backend with optional device name
    backend = create_backend(device_name=device_name)
    
    # Log selected device name for user visibility
    if device_name:
        print(f'📍 Selected keyboard device (by name): {device_name}', file=sys.stderr)
    
    # The actual device name will be logged by backend in start() method
    
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
    import evdev
    from evdev import ecodes
    
    try:
        device_paths = evdev.list_devices()
    except PermissionError:
        typer.echo(
            '❌ Permission denied accessing /dev/input/\n'
            '   Add user to "input" group:\n'
            '   sudo usermod -a -G input $USER\n'
            '   Then log out and back in.',
            err=True
        )
        raise typer.Exit(1)
    
    if not device_paths:
        typer.echo('❌ No input devices found in /dev/input/')
        raise typer.Exit(1)
    
    physical_keyboards = []
    virtual_keyboards = []
    
    for path in device_paths:
        try:
            device = evdev.InputDevice(path)
            caps = device.capabilities()
            
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if (ecodes.KEY_LEFTCTRL in keys or 
                    ecodes.KEY_RIGHTCTRL in keys or
                    ecodes.KEY_LEFTALT in keys or
                    ecodes.KEY_A in keys):
                    
                    device_name_lower = device.name.lower()
                    path_lower = str(path).lower()
                    if 'uinput' in device_name_lower or 'uinput' in path_lower:
                        virtual_keyboards.append(device)
                    else:
                        physical_keyboards.append(device)
        except (OSError, PermissionError):
            continue
    
    if not physical_keyboards and not virtual_keyboards:
        typer.echo('❌ No keyboard devices found')
        typer.echo('   Found input devices, but none have keyboard capabilities.')
        raise typer.Exit(1)
    
    # Display physical keyboards first
    typer.echo('📱 Available keyboard devices:\n')
    
    if physical_keyboards:
        typer.echo('Physical keyboards:')
        for i, device in enumerate(physical_keyboards, 1):
            typer.echo(f'  {i}. {device.name}')
            typer.echo(f'     Path: {device.path}')
        typer.echo()
    
    if virtual_keyboards:
        typer.echo('Virtual keyboards (uinput):')
        for i, device in enumerate(virtual_keyboards, 1):
            typer.echo(f'  {i}. {device.name} [VIRTUAL]')
            typer.echo(f'     Path: {device.path}')
        typer.echo()
    
    # Show usage hint
    if physical_keyboards:
        example_name = physical_keyboards[0].name.split()[0] if physical_keyboards else None
        if example_name:
            typer.echo(f'💡 To use a specific device:\n   tap-detector --device-name "{example_name}"')


@app.command(name='device-list')
def device_list() -> None:
    """List all available keyboard devices.
    
    Displays physical and virtual keyboard devices found in the system.
    Use the device name with --device-name option to select a specific device.
    
    Example:
        $ tap-detector device-list
        $ tap-detector --device-name "A4tech"
    """
    _list_keyboard_devices()


if __name__ == '__main__':
    app()