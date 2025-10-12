"""Main entry point for tap-launcher CLI application."""

import logging
import signal
import sys
from pathlib import Path
from typing import Any

import typer


from .command_executor import CommandExecutor
from .config_loader import ConfigLoader
from .daemon_manager import DaemonManager
from .daemon_manager import daemonize
from .hotkey_matcher import HotkeyMatcher
from .launcher_monitor import LauncherMonitor
from .models import AppConfig

app = typer.Typer(
    help='🚀 Tap Launcher - Launch commands on keyboard tap combinations',
    no_args_is_help=True
)


def setup_logging(config: AppConfig, debug: bool = False) -> None:
    """Setup logging configuration.

    Args:
        config: Application configuration with logging settings
        debug: Whether to force debug logging settings
    """
    # Apply debug settings if requested
    if debug:
        config.log_level = "DEBUG"
        config.debug_mode = True
        config.verbose_logging = True

    # Create logger
    logger = logging.getLogger('tap_launcher')
    logger.setLevel(getattr(logging, config.log_level))

    # Clear any existing handlers
    logger.handlers.clear()

    # Console handler (only if not daemonized, i.e., if stderr is a tty)
    if sys.stderr.isatty():
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.log_level))
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler (if log file is configured)
    if config.log_file:
        # Create parent directory if needed
        config.log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(getattr(logging, config.log_level))
        file_formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)


def setup_signal_handlers(monitor: LauncherMonitor, daemon: DaemonManager, is_foreground: bool) -> None:
    """Setup signal handlers for graceful shutdown.

    Args:
        monitor: LauncherMonitor instance to stop
        daemon: DaemonManager instance for cleanup
        is_foreground: Whether running in foreground mode
    """
    def signal_handler(signum: int, _frame: Any) -> None:
        """Handle SIGINT (Ctrl-C) and SIGTERM signals."""
        logger = logging.getLogger('tap_launcher')
        logger.info(f'Received signal {signum}, shutting down...')

        # Stop the monitor
        monitor.stop()

        # Cleanup daemon resources
        daemon.cleanup()

        # Print message in foreground mode
        if is_foreground and sys.stderr.isatty():
            typer.echo('\n\n👋 Stopping tap launcher...')

        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl-C
    signal.signal(signal.SIGTERM, signal_handler)  # kill command


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

    # Apply debug settings if requested
    if debug:
        app_config.log_level = "DEBUG"
        app_config.debug_mode = True
        app_config.verbose_logging = True

    # Validate commands exist (optional check)
    executor_temp = CommandExecutor(log_commands=False)
    for hotkey in app_config.hotkeys:
        if not executor_temp.check_command_exists(hotkey.command):
            typer.echo(
                f'⚠️  Warning: Command not found: {hotkey.command}',
                err=True
            )

    return app_config


def _start_daemon(daemon: DaemonManager, app_config: AppConfig, foreground: bool, debug: bool = False) -> None:
    """Start the daemon process."""
    # If not foreground, daemonize
    if not foreground:
        typer.echo('✓ Starting tap launcher in background...')
        daemonize()
        # Write PID file in daemon process
        daemon.write_pid_file()
    else:
        typer.echo('✓ Starting tap launcher in foreground...')
        typer.echo('   Press Ctrl+C to stop')

    # Setup logging (after daemonization)
    setup_logging(app_config, debug)

    # Create components
    matcher = HotkeyMatcher(app_config.hotkeys)
    executor = CommandExecutor(log_commands=True)
    monitor = LauncherMonitor(app_config, matcher, executor)

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(monitor, daemon, foreground)

    # Start monitoring (this blocks)
    try:
        monitor.start()
    except KeyboardInterrupt:
        # Handled by signal handler, but may still propagate
        if foreground:
            typer.echo('\n\n👋 Stopping tap launcher...')
        daemon.cleanup()
        sys.exit(0)
    except Exception as e:
        logging.getLogger('tap_launcher').error(f'Fatal error: {e}', exc_info=True)
        daemon.cleanup()
        sys.exit(1)


@app.command()
def start(
    config: Path | None = typer.Option(None, help="Path to config file"),
    foreground: bool = typer.Option(False, "--foreground", help="Run in foreground"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Start the tap launcher daemon.

    By default, the launcher runs as a background daemon process.
    Use --foreground to run in the current terminal (useful for testing).
    Use --debug to enable detailed debug logging.
    
    Examples:
        tap-launcher start
        tap-launcher start --foreground
        tap-launcher start --debug
        tap-launcher start --config /path/to/config.toml --debug
    """
    
    daemon = DaemonManager()

    # Try to acquire exclusive lock (prevents multiple instances)
    if not daemon.acquire_lock():
        typer.echo('❌ Another instance of tap-launcher is already running', err=True)

        # Try to get PID of running instance
        pid = daemon.get_pid()
        if pid:
            typer.echo(f'   PID: {pid}', err=True)

        typer.echo("   Use 'tap-launcher stop' to stop it first", err=True)
        raise typer.Exit(1)

    # Load and validate configuration
    app_config = _validate_config(config, debug)

    # Start the daemon
    _start_daemon(daemon, app_config, foreground, debug)


@app.command()
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


@app.command()
def restart(
    config: Path | None = typer.Option(None, help="Path to config file"),
) -> None:
    """Restart the tap launcher daemon.

    This is equivalent to 'stop' followed by 'start'.
    If no daemon is running, it will just start a new one.
    
    Examples:
        tap-launcher restart
        tap-launcher restart --config /path/to/config.toml
    """
    
    daemon = DaemonManager()

    # Stop if running
    if daemon.is_running():
        typer.echo('Stopping tap launcher...')
        if not daemon.stop():
            typer.echo('❌ Failed to stop tap launcher', err=True)
            raise typer.Exit(1)
        typer.echo('✓ Stopped')

    # Start with new config
    typer.echo('Starting tap launcher...')
    start(config=config, foreground=False)


@app.command()
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

            # Try to get additional info
            try:
                import psutil  # noqa: PLC0415
                process = psutil.Process(pid)
                typer.echo(f'   Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB')
                typer.echo(f'   CPU: {process.cpu_percent(interval=0.1):.1f}%')
            except ImportError:
                pass  # psutil not installed
            except Exception:  # noqa: BLE001, S110
                pass  # Process info not available
    else:
        typer.echo('❌ Tap launcher is not running')
        raise typer.Exit(1)


@app.command()
def check_config(
    config: Path | None = typer.Option(None, help="Path to config file"),
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

    # Display configuration
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

        # Check if command exists
        executor = CommandExecutor(log_commands=False)
        if not executor.check_command_exists(hotkey.command):
            typer.echo('   ⚠️  Warning: Command not found')


if __name__ == '__main__':
    app()


