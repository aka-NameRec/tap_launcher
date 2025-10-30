"""Configuration loader for tap-launcher.

This module handles loading and validating TOML configuration files.
"""

import tomllib
from pathlib import Path
from typing import ClassVar

from .models import AppConfig
from .models import HotkeyConfig


class ConfigLoader:
    """Load and validate TOML configuration files."""

    DEFAULT_PATHS: ClassVar[list[Path]] = [
        Path.home() / '.config/tap-launcher/config.toml',
        Path('/etc/tap-launcher/config.toml'),
    ]

    @staticmethod
    def load(config_path: Path | None = None) -> tuple[AppConfig, Path]:
        """Load configuration from TOML file.

        Args:
            config_path: Path to config file. If None, tries default paths.

        Returns:
            tuple[AppConfig, Path]: Parsed configuration and path to loaded file

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If configuration is invalid
            tomllib.TOMLDecodeError: If TOML syntax is invalid
        """
        if config_path:
            if not config_path.exists():
                raise FileNotFoundError(f'Config file not found: {config_path}')  # noqa: TRY003
            config = ConfigLoader._load_from_path(config_path)
            return (config, config_path.resolve())

        # Try default paths
        for path in ConfigLoader.DEFAULT_PATHS:
            if path.exists():
                config = ConfigLoader._load_from_path(path)
                return (config, path.resolve())

        paths_str = ', '.join(str(p) for p in ConfigLoader.DEFAULT_PATHS)
        raise FileNotFoundError(  # noqa: TRY003
            f'Config file not found. Tried: {paths_str}\n'
            f'Create a config file at one of these locations.'
        )

    @staticmethod
    def _load_from_path(path: Path) -> AppConfig:
        """Load and parse TOML from specific path.

        Args:
            path: Path to TOML config file

        Returns:
            AppConfig: Parsed configuration

        Raises:
            ValueError: If configuration is invalid
            tomllib.TOMLDecodeError: If TOML syntax is invalid
        """
        try:
            with path.open('rb') as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise tomllib.TOMLDecodeError(  # noqa: TRY003
                f'Invalid TOML syntax in {path}: {e}'
            ) from e

        return ConfigLoader._parse_config(data)

    @staticmethod
    def _parse_config(data: dict) -> AppConfig:
        """Parse TOML data into AppConfig.

        Args:
            data: Parsed TOML data

        Returns:
            AppConfig: Validated configuration object

        Raises:
            ValueError: If configuration is invalid
        """
        # Parse app section
        app_data = data.get('app', {})

        tap_timeout = app_data.get('tap_timeout', 0.2)
        log_level = app_data.get('log_level', 'INFO').upper()
        log_file_str = app_data.get('log_file')
        debug_mode = app_data.get('debug_mode', False)
        verbose_logging = app_data.get('verbose_logging', False)

        # Parse log file path
        log_file = None
        if log_file_str:
            log_file = Path(log_file_str).expanduser()

        # Parse hotkeys
        hotkeys_data = data.get('hotkeys', [])
        if not hotkeys_data:
            raise ValueError('Configuration must have at least one [[hotkeys]] section')  # noqa: TRY003

        hotkeys = []
        for idx, hk_data in enumerate(hotkeys_data, 1):
            try:
                hotkey = ConfigLoader._parse_hotkey(hk_data)
                hotkeys.append(hotkey)
            except ValueError as e:
                raise ValueError(f'Error in hotkey #{idx}: {e}') from e  # noqa: TRY003

        # Create and validate AppConfig
        try:
            config = AppConfig(
                tap_timeout=tap_timeout,
                log_level=log_level,
                log_file=log_file,
                debug_mode=debug_mode,
                verbose_logging=verbose_logging,
                hotkeys=hotkeys,
            )
        except ValueError as e:
            raise ValueError(f'Invalid configuration: {e}') from e  # noqa: TRY003

        return config

    @staticmethod
    def _parse_hotkey(data: dict) -> HotkeyConfig:
        """Parse hotkey configuration from TOML data.

        Args:
            data: Hotkey section from TOML

        Returns:
            HotkeyConfig: Parsed hotkey configuration

        Raises:
            ValueError: If hotkey configuration is invalid
        """
        keys = data.get('keys')
        if not keys:
            raise ValueError("Hotkey must have 'keys' field")  # noqa: TRY003
        if not isinstance(keys, list):
            raise TypeError("'keys' must be a list")  # noqa: TRY003
        if not all(isinstance(k, str) for k in keys):
            raise ValueError('All keys must be strings')  # noqa: TRY003

        command = data.get('command')
        if not command:
            raise ValueError("Hotkey must have 'command' field")  # noqa: TRY003
        if not isinstance(command, str):
            raise TypeError("'command' must be a string")  # noqa: TRY003

        args = data.get('args', [])
        if not isinstance(args, list):
            raise TypeError("'args' must be a list")  # noqa: TRY003
        if not all(isinstance(arg, str) for arg in args):
            raise ValueError('All args must be strings')  # noqa: TRY003

        description = data.get('description', '')
        if not isinstance(description, str):
            raise TypeError("'description' must be a string")  # noqa: TRY003

        start_timer_from_second_key = data.get('start_timer_from_second_key', False)
        if not isinstance(start_timer_from_second_key, bool):
            raise TypeError("'start_timer_from_second_key' must be a boolean")  # noqa: TRY003

        return HotkeyConfig(
            keys=keys,
            command=command,
            args=args,
            description=description,
            start_timer_from_second_key=start_timer_from_second_key,
        )


