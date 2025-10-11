"""Data models for tap-launcher configuration."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HotkeyConfig:
    """Configuration for a single hotkey combination.
    
    Attributes:
        keys: List of normalized key names (e.g., ["ctrl_l", "shift_l"])
        command: Path to command to execute
        args: Command-line arguments for the command
        description: Human-readable description of the hotkey action
    """
    keys: list[str]
    command: str
    args: list[str] = field(default_factory=list)
    description: str = ""
    
    def keys_set(self) -> frozenset[str]:
        """Return keys as a frozen set for comparison.
        
        This is used for matching detected tap combinations against
        configured hotkeys.
        
        Returns:
            frozenset[str]: Immutable set of key names
        """
        return frozenset(self.keys)
    
    def __post_init__(self):
        """Validate the hotkey configuration."""
        if not self.keys:
            raise ValueError("Hotkey must have at least one key")
        if not self.command:
            raise ValueError("Hotkey must have a command")


@dataclass
class AppConfig:
    """Application configuration.
    
    Attributes:
        tap_timeout: Maximum duration in seconds for a valid tap
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (None for no file logging)
        debug_mode: Enable debug mode with additional logging
        verbose_logging: Enable verbose logging of tap detection
        hotkeys: List of configured hotkey combinations
    """
    tap_timeout: float = 0.2
    log_level: str = "INFO"
    log_file: Path | None = None
    debug_mode: bool = False
    verbose_logging: bool = False
    hotkeys: list[HotkeyConfig] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate the application configuration."""
        if self.tap_timeout <= 0:
            raise ValueError(f"tap_timeout must be positive, got {self.tap_timeout}")
        
        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ValueError(f"Invalid log_level: {self.log_level}")
        
        if not self.hotkeys:
            raise ValueError("Configuration must have at least one hotkey")
        
        # Check for duplicate key combinations
        seen_keys = set()
        for hotkey in self.hotkeys:
            keys_set = hotkey.keys_set()
            if keys_set in seen_keys:
                keys_str = "+".join(sorted(hotkey.keys))
                raise ValueError(f"Duplicate hotkey combination: {keys_str}")
            seen_keys.add(keys_set)


