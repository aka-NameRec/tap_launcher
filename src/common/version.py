"""Version information for tap-launcher.

This module provides functionality to read version information from pyproject.toml.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path


def _find_pyproject_toml() -> Path | None:
    """Find pyproject.toml file in the project root.

    Returns:
        Path to pyproject.toml if found, None otherwise.
    """
    # Start from current file and go up to find project root
    current = Path(__file__).resolve()
    # Go up: common/ -> src/ -> project root
    project_root = current.parent.parent.parent
    
    pyproject_path = project_root / 'pyproject.toml'
    if pyproject_path.exists():
        return pyproject_path
    
    # Fallback: try from current working directory
    cwd = Path.cwd()
    pyproject_path = cwd / 'pyproject.toml'
    if pyproject_path.exists():
        return pyproject_path
    
    return None


@dataclass
class VersionInfo:
    """Version information dataclass.
    
    Attributes:
        version: Version string (e.g., "4")
        release_date: Release date string in ISO format (e.g., "2025-11-01"), or None
    """
    
    version: str
    release_date: str | None = None
    
    def __str__(self) -> str:
        """Format version information.
        
        Returns:
            Formatted version string: "v{version} ({release_date})" if date exists,
            or "v{version}" if date is None.
        """
        if self.release_date:
            return f'v{self.version} ({self.release_date})'
        return f'v{self.version}'


def get_version_info() -> VersionInfo:
    """Get version information from pyproject.toml.
    
    Returns:
        VersionInfo instance with version and release_date from pyproject.toml.
        If version is not found, returns VersionInfo with version='unknown'.
    """
    pyproject_path = _find_pyproject_toml()
    if pyproject_path is None:
        return VersionInfo(version='unknown')
    
    try:
        with pyproject_path.open('rb') as f:
            data = tomllib.load(f)
        
        project_data = data.get('project', {})
        version = project_data.get('version')
        release_date = project_data.get('release_date')
        
        version_str = str(version) if version else 'unknown'
        release_date_str = str(release_date) if release_date else None
        
        return VersionInfo(version=version_str, release_date=release_date_str)
    except Exception:  # noqa: BLE001
        # If anything goes wrong, return unknown version
        return VersionInfo(version='unknown')


# Export version for backward compatibility
def get_version() -> str:
    """Get version string from pyproject.toml (backward compatibility).
    
    Returns:
        Version string from pyproject.toml, or 'unknown' if not found.
    """
    return get_version_info().version


__version__ = get_version()

