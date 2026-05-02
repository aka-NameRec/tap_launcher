"""Main entry point for tap-launcher CLI application."""

import signal
import sys
from pathlib import Path
from typing import Any

import typer

from common.logging_utils import get_logger
from common.logging_utils import setup_logging_handler
from common.version import get_version_info

from .command_executor import CommandExecutor
from .config_loader import ConfigLoader
from .daemon_manager import DaemonManager
from .hotkey_matcher import HotkeyMatcher
from .models import AppConfig
from .monitor import LauncherMonitor

app = typer.Typer(
    help='🚀 Tap Launcher - Launch commands on keyboard tap combinations',
    no_args_is_help=True,
)


def setup_logging(config: AppConfig, foreground: bool, debug: bool = False) -> None:
    """Setup logging configuration.

    Args:
        config: Application configuration with logging settings
        foreground: Whether running in foreground mode (True = console, False = file)
        debug: Whether to force debug logging settings
    """
    if debug:
        config.log_level = 'DEBUG'
        config.debug_mode = True
        config.verbose_logging = True

    logger = get_logger('tap_launcher')

    setup_logging_handler(
        logger=logger,
        log_level=config.log_level,
        foreground=foreground,
        log_file=config.log_file if not foreground else None,
    )


def setup_signal_handlers(monitor: LauncherMonitor, daemon: DaemonManager, is_foreground: bool) -> None:
    """Setup signal handlers for graceful shutdown.

    Args:
        monitor: LauncherMonitor instance to stop
        daemon: DaemonManager instance for cleanup
        is_foreground: Whether running in foreground mode
    """
    def signal_handler(signum: int, _frame: Any) -> None:
        """Handle SIGINT (Ctrl-C) and SIGTERM signals."""
        logger = get_logger('tap_launcher')
        logger.info(f'Received signal {signum}, shutting down...')

        monitor.stop()
        daemon.cleanup()

        if is_foreground and sys.stderr.isatty():
            typer.echo('\n\n👋 Stopping tap launcher...')

        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def _validate_config(config: Path | None, debug: bool = False) -> AppConfig:
    """Validate configuration and return AppConfig."""
    try:
        app_config, _config_path = ConfigLoader.load(config)
    except FileNotFoundError as e:
        typer.echo(f'❌ Config file not found: {e}', err=True)
        typer.echo('\n💡 Tip: Create a config file at:', err=True)
        typer.echo('   ~/.config/tap-launcher/config.toml', err=True)
        typer.echo('   See config/tap-launcher.toml.example for reference', err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f'❌ Failed to load config: {e}', err=True)
        raise typer.Exit(1) from e

    if debug:
        app_config.log_level = 'DEBUG'
        app_config.debug_mode = True
        app_config.verbose_logging = True

    executor_temp = CommandExecutor(log_commands=False)
    for hotkey in app_config.hotkeys:
        if not executor_temp.check_command_exists(hotkey.command):
            typer.echo(
                f'⚠️  Warning: Command not found: {hotkey.command}',
                err=True,
            )

    return app_config


def _start_daemon(
    daemon: DaemonManager,
    app_config: AppConfig,
    foreground: bool,
    debug: bool = False,
) -> None:
    """Start the daemon process."""
    if not foreground:
        typer.echo('✓ Starting tap launcher in background...')
        try:
            daemon.daemonize(foreground=False)
        except RuntimeError as e:
            typer.echo(f'❌ Failed to start daemon: {e}', err=True)
            raise typer.Exit(1) from e
    else:
        typer.echo('✓ Starting tap launcher in foreground...')
        typer.echo('   Press Ctrl+C to stop')
        daemon.daemonize(foreground=True)

    setup_logging(app_config, foreground, debug)

    matcher = HotkeyMatcher(app_config.hotkeys)
    executor = CommandExecutor(log_commands=True)
    monitor = LauncherMonitor(app_config, matcher, executor)

    setup_signal_handlers(monitor, daemon, foreground)

    try:
        monitor.start()
    except KeyboardInterrupt:
        if foreground:
            typer.echo('\n\n👋 Stopping tap launcher...')
        daemon.cleanup()
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        get_logger('tap_launcher').error(f'Fatal error: {e}', exc_info=True)
        daemon.cleanup()
        sys.exit(1)


def _run_launcher(
    config: Path | None,
    foreground: bool,
    debug: bool = False,
) -> None:
    """Core launcher startup logic, shared by start and restart commands."""
    daemon = DaemonManager()

    if not daemon.acquire_lock():
        typer.echo('❌ Another instance of tap-launcher is already running', err=True)

        pid = daemon.get_pid()
        if pid:
            typer.echo(f'   PID: {pid}', err=True)

        typer.echo("   Use 'tap-launcher stop' to stop it first", err=True)
        raise typer.Exit(1)

    app_config = _validate_config(config, debug)

    _start_daemon(daemon, app_config, foreground, debug)


@app.command()  # type: ignore[misc]
def start(
    config: Path | None = typer.Option(None, help='Path to config file'),  # noqa: B008
    foreground: bool = typer.Option(False, '--foreground', help='Run in foreground'),
    debug: bool = typer.Option(False, '--debug', help='Enable debug logging'),
) -> None:
    """Start the tap launcher daemon.

    By default, the launcher runs as a background daemon process.
    Use --foreground to run in the current terminal (useful for testing).
    Use --debug to enable detailed debug logging.
    All available keyboard devices are automatically detected and monitored.

    Examples:
        tap-launcher start
        tap-launcher start --foreground
        tap-launcher start --debug
        tap-launcher start --config /path/to/config.toml --debug
    """
    typer.echo(f'🚀 Tap Launcher {get_version_info()}')

    _run_launcher(config, foreground, debug)


@app.command()  # type: ignore[misc]
def stop() -> None:
    """Stop the tap launcher daemon.

    This command stops the running tap launcher daemon process.
    If no daemon is running, an error message will be displayed.

    Examples:
        tap-launcher stop
    """
    daemon = DaemonManager()

    if not daemon.is_running():
        typer.echo('❌ Tap launcher is not running', err=True)
        raise typer.Exit(1)

    pid = daemon.get_pid()
    typer.echo(f'Stopping tap launcher (PID: {pid})...')

    if daemon.stop():
        typer.echo('✓ Tap launcher stopped')
        if pid:
            typer.echo(f'   Stopped PID: {pid}')
    else:
        typer.echo('❌ Failed to stop tap launcher', err=True)
        typer.echo('   The process may have already exited', err=True)
        raise typer.Exit(1)


@app.command()  # type: ignore[misc]
def restart(
    config: Path | None = typer.Option(None, help='Path to config file'),  # noqa: B008
) -> None:
    """Restart the tap launcher daemon.

    This is equivalent to 'stop' followed by 'start'.
    If no daemon is running, it will just start a new one.

    Examples:
        tap-launcher restart
        tap-launcher restart --config /path/to/config.toml
    """
    daemon = DaemonManager()

    if daemon.is_running():
        typer.echo('Stopping tap launcher...')
        if not daemon.stop():
            typer.echo('❌ Failed to stop tap launcher', err=True)
            raise typer.Exit(1)
        typer.echo('✓ Stopped')

    typer.echo('Starting tap launcher...')
    _run_launcher(config, foreground=False)


@app.command()  # type: ignore[misc]
def status() -> None:
    """Show tap launcher status.

    This command displays the current status of the tap launcher daemon.
    It shows whether the daemon is running, its PID, memory usage, and CPU usage.

    Examples:
        tap-launcher status
    """
    daemon = DaemonManager()

    if daemon.is_running():
        pid = daemon.get_pid()
        typer.echo('✓ Tap launcher is running')
        if pid:
            typer.echo(f'   PID: {pid}')

            try:
                import psutil  # noqa: PLC0415

                process = psutil.Process(pid)
                typer.echo(f'   Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB')
                typer.echo(f'   CPU: {process.cpu_percent(interval=0.1):.1f}%')
            except ImportError:
                pass
            except Exception:  # noqa: BLE001, S110
                pass
    else:
        typer.echo('❌ Tap launcher is not running')
        raise typer.Exit(1)


@app.command()  # type: ignore[misc]
def check_config(
    config: Path | None = typer.Option(None, help='Path to config file'),  # noqa: B008
) -> None:
    """Validate configuration file.

    This command checks if the configuration file is valid and
    displays all configured hotkeys. It also validates that
    all configured commands exist and are executable.

    Examples:
        tap-launcher check-config
        tap-launcher check-config --config /path/to/config.toml
    """
    try:
        app_config, config_path = ConfigLoader.load(config)
    except FileNotFoundError as e:
        typer.echo(f'❌ Config file not found: {e}', err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f'❌ Configuration error: {e}', err=True)
        raise typer.Exit(1) from e

    typer.echo('✓ Configuration is valid\n')

    typer.echo(f'Config file: {config_path}')
    typer.echo(f'Tap timeout: {app_config.tap_timeout}s')
    typer.echo(f'Log level: {app_config.log_level}')
    if app_config.log_file:
        typer.echo(f'Log file: {app_config.log_file}')
    typer.echo(f'Debug mode: {app_config.debug_mode}')
    typer.echo(f'Verbose logging: {app_config.verbose_logging}')

    typer.echo(f'\nConfigured hotkeys ({len(app_config.hotkeys)}):')

    for idx, hotkey in enumerate(app_config.hotkeys, 1):
        keys_str = '+'.join(sorted(hotkey.keys))
        cmd_str = hotkey.command
        if hotkey.args:
            cmd_str += ' ' + ' '.join(hotkey.args)

        typer.echo(f'\n{idx}. {keys_str}')
        typer.echo(f'   Command: {cmd_str}')
        if hotkey.description:
            typer.echo(f'   Description: {hotkey.description}')

        executor = CommandExecutor(log_commands=False)
        if not executor.check_command_exists(hotkey.command):
            typer.echo('   ⚠️  Warning: Command not found')


if __name__ == '__main__':
    app()
