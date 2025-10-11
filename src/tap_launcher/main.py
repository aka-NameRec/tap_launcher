"""Main entry point for tap-launcher CLI application."""

import sys
import logging
from pathlib import Path
from typing import Optional

import typer

from .models import AppConfig
from .config_loader import ConfigLoader
from .hotkey_matcher import HotkeyMatcher
from .command_executor import CommandExecutor
from .daemon_manager import DaemonManager, daemonize
from .launcher_monitor import LauncherMonitor


app = typer.Typer(
    help="🚀 Tap Launcher - Launch commands on keyboard tap combinations"
)


def setup_logging(config: AppConfig):
    """Setup logging configuration.
    
    Args:
        config: Application configuration with logging settings
    """
    # Create logger
    logger = logging.getLogger("tap_launcher")
    logger.setLevel(getattr(logging, config.log_level))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler (only if not daemonized, i.e., if stderr is a tty)
    if sys.stderr.isatty():
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.log_level))
        console_formatter = logging.Formatter(
            "%(levelname)s: %(message)s"
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
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)


@app.command()
def start(
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to config file",
        exists=True,
        dir_okay=False,
    ),
    foreground: bool = typer.Option(
        False,
        "--foreground", "-f",
        help="Run in foreground (don't daemonize)",
    ),
):
    """Start the tap launcher daemon.
    
    By default, the launcher runs as a background daemon process.
    Use --foreground to run in the current terminal (useful for testing).
    """
    daemon = DaemonManager()
    
    # Check if already running
    if daemon.is_running():
        typer.echo("❌ Tap launcher is already running", err=True)
        pid = daemon.get_pid()
        if pid:
            typer.echo(f"   PID: {pid}", err=True)
        typer.echo("   Use 'tap-launcher stop' to stop it first", err=True)
        raise typer.Exit(1)
    
    # Load configuration
    try:
        app_config = ConfigLoader.load(config)
    except FileNotFoundError as e:
        typer.echo(f"❌ Config file not found: {e}", err=True)
        typer.echo("\n💡 Tip: Create a config file at:", err=True)
        typer.echo("   ~/.config/tap-launcher/config.toml", err=True)
        typer.echo("   See config/tap-launcher.toml.example for reference", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Failed to load config: {e}", err=True)
        raise typer.Exit(1)
    
    # Validate commands exist (optional check)
    executor_temp = CommandExecutor(log_commands=False)
    for hotkey in app_config.hotkeys:
        if not executor_temp.check_command_exists(hotkey.command):
            typer.echo(
                f"⚠️  Warning: Command not found: {hotkey.command}",
                err=True
            )
    
    # If not foreground, daemonize
    if not foreground:
        typer.echo("✓ Starting tap launcher in background...")
        daemonize()
        daemon.write_pid()
    else:
        typer.echo("✓ Starting tap launcher in foreground...")
        typer.echo("   Press Ctrl+C to stop")
    
    # Setup logging (after daemonization)
    setup_logging(app_config)
    
    # Create components
    matcher = HotkeyMatcher(app_config.hotkeys)
    executor = CommandExecutor(log_commands=True)
    monitor = LauncherMonitor(app_config, matcher, executor)
    
    # Start monitoring (this blocks)
    try:
        monitor.start()
    except KeyboardInterrupt:
        if foreground:
            typer.echo("\n\n👋 Stopping tap launcher...")
        daemon.cleanup()
        sys.exit(0)
    except Exception as e:
        logging.getLogger("tap_launcher").error(f"Fatal error: {e}", exc_info=True)
        daemon.cleanup()
        sys.exit(1)


@app.command()
def stop():
    """Stop the tap launcher daemon."""
    daemon = DaemonManager()
    
    if not daemon.is_running():
        typer.echo("❌ Tap launcher is not running", err=True)
        raise typer.Exit(1)
    
    pid = daemon.get_pid()
    
    if daemon.stop():
        typer.echo("✓ Tap launcher stopped")
        if pid:
            typer.echo(f"   Stopped PID: {pid}")
    else:
        typer.echo("❌ Failed to stop tap launcher", err=True)
        typer.echo("   The process may have already exited", err=True)
        raise typer.Exit(1)


@app.command()
def restart(
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to config file",
        exists=True,
        dir_okay=False,
    ),
):
    """Restart the tap launcher daemon.
    
    This is equivalent to 'stop' followed by 'start'.
    """
    daemon = DaemonManager()
    
    # Stop if running
    if daemon.is_running():
        typer.echo("Stopping tap launcher...")
        if not daemon.stop():
            typer.echo("❌ Failed to stop tap launcher", err=True)
            raise typer.Exit(1)
        typer.echo("✓ Stopped")
    
    # Start with new config
    typer.echo("Starting tap launcher...")
    start(config=config, foreground=False)


@app.command()
def status():
    """Show tap launcher status."""
    daemon = DaemonManager()
    
    if daemon.is_running():
        pid = daemon.get_pid()
        typer.echo("✓ Tap launcher is running")
        if pid:
            typer.echo(f"   PID: {pid}")
            
            # Try to get additional info
            try:
                import psutil
                process = psutil.Process(pid)
                typer.echo(f"   Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
                typer.echo(f"   CPU: {process.cpu_percent(interval=0.1):.1f}%")
            except ImportError:
                pass  # psutil not installed
            except Exception:
                pass  # Process info not available
    else:
        typer.echo("❌ Tap launcher is not running")
        raise typer.Exit(1)


@app.command()
def check_config(
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to config file",
        exists=True,
        dir_okay=False,
    ),
):
    """Validate configuration file.
    
    This command checks if the configuration file is valid and
    displays all configured hotkeys.
    """
    try:
        app_config = ConfigLoader.load(config)
    except FileNotFoundError as e:
        typer.echo(f"❌ Config file not found: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Configuration error: {e}", err=True)
        raise typer.Exit(1)
    
    typer.echo("✓ Configuration is valid\n")
    
    # Display configuration
    typer.echo(f"Tap timeout: {app_config.tap_timeout}s")
    typer.echo(f"Log level: {app_config.log_level}")
    if app_config.log_file:
        typer.echo(f"Log file: {app_config.log_file}")
    typer.echo(f"Debug mode: {app_config.debug_mode}")
    typer.echo(f"Verbose logging: {app_config.verbose_logging}")
    
    typer.echo(f"\nConfigured hotkeys ({len(app_config.hotkeys)}):")
    
    for idx, hotkey in enumerate(app_config.hotkeys, 1):
        keys_str = "+".join(sorted(hotkey.keys))
        cmd_str = hotkey.command
        if hotkey.args:
            cmd_str += " " + " ".join(hotkey.args)
        
        typer.echo(f"\n{idx}. {keys_str}")
        typer.echo(f"   Command: {cmd_str}")
        if hotkey.description:
            typer.echo(f"   Description: {hotkey.description}")
        
        # Check if command exists
        executor = CommandExecutor(log_commands=False)
        if not executor.check_command_exists(hotkey.command):
            typer.echo(f"   ⚠️  Warning: Command not found")


if __name__ == "__main__":
    app()


