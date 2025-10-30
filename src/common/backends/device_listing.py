"""Public API for listing keyboard devices.

This module provides backend-agnostic functions for discovering and listing
keyboard devices. Applications (detector, launcher) should use these functions
instead of directly accessing backend implementation details.
"""

from __future__ import annotations

from typing import Any


def list_keyboard_devices() -> list[dict[str, str]]:
    """List all available keyboard devices in the system.

    Returns a list of device dictionaries with 'name' and 'path' keys.
    Physical keyboards are listed first, followed by virtual keyboards (uinput).

    Returns:
        list[dict[str, str]]: List of device info dictionaries.
            Each dict contains:
            - 'name': Device name (str)
            - 'path': Device path (str)
            - 'is_virtual': Whether device is virtual/uinput (bool)

    Raises:
        PermissionError: If access to /dev/input/ is denied
        OSError: If device listing fails for other reasons

    Example:
        >>> devices = list_keyboard_devices()
        >>> for dev in devices:
        ...     print(f"{dev['name']} at {dev['path']}")
    """
    import evdev
    from evdev import ecodes

    try:
        device_paths = evdev.list_devices()
    except PermissionError as e:
        raise PermissionError(
            'Permission denied accessing /dev/input/. '
            'Add user to "input" group:\n'
            '  sudo usermod -a -G input $USER\n'
            'Then log out and back in for changes to take effect.'
        ) from e

    if not device_paths:
        return []

    physical_keyboards = []
    virtual_keyboards = []

    for path in device_paths:
        try:
            device = evdev.InputDevice(path)
            
            if not _device_has_keyboard_caps(device):
                continue
            
            is_virtual = _is_virtual_uinput(device, path)
            device_info = {
                'name': device.name,
                'path': device.path,
                'is_virtual': is_virtual,
            }
            
            if is_virtual:
                virtual_keyboards.append(device_info)
            else:
                physical_keyboards.append(device_info)
        except (OSError, PermissionError):
            continue

    # Return physical keyboards first, then virtual
    return physical_keyboards + virtual_keyboards


def _device_has_keyboard_caps(device: Any) -> bool:
    """Check if an evdev device has keyboard capabilities.
    
    This is an internal helper function used by list_keyboard_devices().
    It checks if the device supports keyboard events by looking for
    common modifier keys (Ctrl, Alt) or letter keys (A).
    
    Args:
        device: evdev InputDevice instance
        
    Returns:
        bool: True if device appears to be a keyboard
    """
    from evdev import ecodes
    
    caps = device.capabilities()
    if ecodes.EV_KEY not in caps:
        return False
    keys = caps[ecodes.EV_KEY]
    return (
        ecodes.KEY_LEFTCTRL in keys
        or ecodes.KEY_RIGHTCTRL in keys
        or ecodes.KEY_LEFTALT in keys
        or ecodes.KEY_A in keys
    )


def _is_virtual_uinput(device: Any, path: str) -> bool:
    """Check if a device is a virtual uinput device.
    
    This is an internal helper function used by list_keyboard_devices().
    
    Args:
        device: evdev InputDevice instance
        path: Device path (str)
        
    Returns:
        bool: True if device is virtual/uinput
    """
    name_l = device.name.lower()
    path_l = str(path).lower()
    return 'uinput' in name_l or 'uinput' in path_l

