"""Main entry point for tap-detector CLI application."""

import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from types import FrameType

import typer

from common.backends.detector import create_backend
from common.backends.device_listing import list_keyboard_devices
from common.logging_utils import get_logger
from common.logging_utils import setup_logging_handler
from common.runtime_state import LaunchRuntimeState
from common.runtime_state import read_launch_runtime_state
from common.tap_monitor import TapMonitor

from .formatter import format_header
from .formatter import format_keys_detected
from .formatter import format_verbose_header

app = typer.Typer(help='🎹 Tap Detector - Detect keyboard key combinations')


@dataclass(frozen=True)
class ManagedLauncher:
    """Information needed to restore a launcher stopped by detector."""

    state: LaunchRuntimeState | None


def _launch_command(*args: str) -> list[str]:
    """Build a subprocess command for the sibling launch CLI."""
    return [sys.executable, '-m', 'launcher.main', *args]


def _run_launch_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the launch CLI without coupling detector to launcher internals."""
    return subprocess.run(  # noqa: S603
        _launch_command(*args),
        check=False,
        capture_output=True,
        text=True,
    )


def _get_running_launcher() -> ManagedLauncher | None:
    """Return launcher metadata when the launcher CLI reports an active daemon."""
    status_result = _run_launch_command(('status',))
    if status_result.returncode != 0:
        return None
    return ManagedLauncher(state=read_launch_runtime_state())


def _stop_launcher_for_detection() -> ManagedLauncher | None:
    """Stop a running launcher so detector can grab keyboard devices."""
    managed_launcher = _get_running_launcher()
    if managed_launcher is None:
        return None

    typer.echo('Tap launcher is running; stopping it temporarily for detection...')
    stop_result = _run_launch_command(('stop',))
    if stop_result.returncode != 0:
        typer.echo('❌ Failed to stop tap launcher before detection.', err=True)
        if stop_result.stderr:
            typer.echo(stop_result.stderr.strip(), err=True)
        raise typer.Exit(1)
    return managed_launcher


def _restart_launcher_after_detection(managed_launcher: ManagedLauncher | None) -> None:
    """Restart launcher after detector exits."""
    if managed_launcher is None:
        return

    typer.echo('\nRestarting tap launcher...')
    args = ['start']
    if managed_launcher.state:
        args.extend(('--config', str(managed_launcher.state.config_path)))
        if managed_launcher.state.debug:
            args.append('--debug')
    start_result = _run_launch_command(args)
    if start_result.returncode != 0:
        typer.echo('❌ Failed to restart tap launcher.', err=True)
        if start_result.stderr:
            typer.echo(start_result.stderr.strip(), err=True)
        manual_args = ' '.join(_launch_command(*args))
        typer.echo(f'Run manually: {manual_args}', err=True)


def _install_detector_signal_handlers() -> None:
    """Ensure detector shutdown uses Python unwinding so launcher restoration runs."""

    def signal_handler(_signum: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        '--verbose',
        '-v',
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

    # Setup logging (detector always runs in foreground, so log to console)
    logger = get_logger('tap_detector')
    setup_logging_handler(
        logger=logger,
        log_level='INFO',
        foreground=True,
    )

    # Define callback for key detection
    def on_keys_detected(keys: set[str], duration: float, _trigger_key: str, _has_non_modifier: bool) -> None:
        """Called when keys are detected."""
        sys.stdout.write(format_keys_detected(keys, duration))

    launcher_state = _stop_launcher_for_detection()

    try:
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
        _install_detector_signal_handlers()

        monitor.start()
    except KeyboardInterrupt:
        sys.stdout.write('\n\n👋 Exiting tap detector. Goodbye!')
        sys.exit(0)
    finally:
        _restart_launcher_after_detection(launcher_state)


def _list_keyboard_devices() -> None:
    """List all available keyboard devices."""
    try:
        devices = list_keyboard_devices()
    except PermissionError as e:
        typer.echo(
            f'❌ {e}\n   Add user to "input" group:\n   sudo usermod -a -G input $USER\n   Then log out and back in.',
            err=True,
        )
        raise typer.Exit(1) from e
    except OSError as e:
        typer.echo(f'❌ Error listing devices: {e}', err=True)
        raise typer.Exit(1) from e

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
