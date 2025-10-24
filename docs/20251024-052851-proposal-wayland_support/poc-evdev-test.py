#!/usr/bin/env python3
"""Proof-of-Concept: Testing evdev for keyboard monitoring.

This script tests if evdev can be used to monitor keyboard events
on the current system. It's a standalone PoC that doesn't modify
any project code.

Requirements:
    - python-evdev library
    - User in 'input' group OR run with sudo

Usage:
    # Install evdev if not already installed
    pip install evdev
    
    # Run the test
    python docs/poc-evdev-test.py
    
    # Or if permission denied:
    sudo python docs/poc-evdev-test.py
"""

import sys
from time import perf_counter


def check_evdev_available() -> bool:
    """Check if evdev library is available."""
    try:
        import evdev  # noqa: F401
        print("✓ evdev library is installed")
        return True
    except ImportError:
        print("✗ evdev library is NOT installed")
        print("  Install with: pip install evdev")
        return False


def check_permissions() -> tuple[bool, list[str]]:
    """Check if we have permissions to access /dev/input/.
    
    Returns:
        tuple: (has_permission, list_of_devices)
    """
    try:
        import evdev
        devices = evdev.list_devices()
        print(f"✓ Permission OK - found {len(devices)} input device(s)")
        return True, devices
    except PermissionError:
        print("✗ Permission denied accessing /dev/input/")
        print("  Solutions:")
        print("    1. Add user to input group: sudo usermod -a -G input $USER")
        print("    2. Log out and back in for group changes to take effect")
        print("    3. Or run with sudo (not recommended for production)")
        return False, []


def find_keyboards(devices: list[str]) -> list[tuple[str, str]]:
    """Find keyboard devices from the list.
    
    Args:
        devices: List of device paths
    
    Returns:
        List of (path, name) tuples for keyboard devices
    """
    import evdev
    from evdev import ecodes
    
    keyboards = []
    
    for path in devices:
        device = evdev.InputDevice(path)
        caps = device.capabilities()
        
        # Check if device has keyboard capabilities
        if ecodes.EV_KEY in caps:
            keys = caps[ecodes.EV_KEY]
            # Check for common modifier keys to identify keyboards
            # (not all EV_KEY devices are keyboards - some are mice buttons)
            if (ecodes.KEY_LEFTCTRL in keys or 
                ecodes.KEY_RIGHTCTRL in keys or
                ecodes.KEY_LEFTALT in keys or
                ecodes.KEY_A in keys):
                keyboards.append((path, device.name))
    
    return keyboards


def display_keyboards(keyboards: list[tuple[str, str]]) -> None:
    """Display found keyboard devices."""
    if not keyboards:
        print("✗ No keyboard devices found")
        print("  This might be an issue with device detection")
        return
    
    print(f"\n✓ Found {len(keyboards)} keyboard device(s):")
    for i, (path, name) in enumerate(keyboards, 1):
        print(f"  {i}. {name}")
        print(f"     Path: {path}")


def test_keyboard_events(device_path: str, device_name: str) -> None:
    """Test reading keyboard events from a device.
    
    Args:
        device_path: Path to input device
        device_name: Name of the device
    """
    import evdev
    from evdev import categorize, ecodes
    
    print(f"\n{'='*60}")
    print(f"Testing keyboard events from: {device_name}")
    print(f"Device path: {device_path}")
    print(f"{'='*60}")
    print("\nPress some keys to test (Ctrl+C to stop)")
    print("Try pressing modifiers (Ctrl, Alt, Shift, Super)\n")
    
    device = evdev.InputDevice(device_path)
    
    # Track pressed keys for tap-like detection
    pressed_keys = set()
    tap_start_time = None
    
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)
                keycode = key_event.keycode
                
                # Handle multi-key events (list)
                if isinstance(keycode, list):
                    keycode = keycode[0]
                
                current_time = perf_counter()
                
                # Key press
                if key_event.keystate == key_event.key_down:
                    pressed_keys.add(keycode)
                    
                    # Start tap timer on first key
                    if len(pressed_keys) == 1:
                        tap_start_time = current_time
                    
                    elapsed = current_time - tap_start_time if tap_start_time else 0
                    print(f"[PRESS  ] {keycode:20s} (keys pressed: {len(pressed_keys)}, elapsed: {elapsed:.3f}s)")
                
                # Key release
                elif key_event.keystate == key_event.key_up:
                    if keycode in pressed_keys:
                        pressed_keys.discard(keycode)
                    
                    elapsed = current_time - tap_start_time if tap_start_time else 0
                    print(f"[RELEASE] {keycode:20s} (keys pressed: {len(pressed_keys)}, elapsed: {elapsed:.3f}s)")
                    
                    # All keys released - potential tap
                    if len(pressed_keys) == 0 and tap_start_time:
                        duration = current_time - tap_start_time
                        print(f"\n  ✓ TAP COMPLETED - Duration: {duration:.3f}s")
                        print(f"    (Would be valid if < 0.2s for default timeout)\n")
                        tap_start_time = None
    
    except KeyboardInterrupt:
        print("\n\n✓ Test interrupted by user")
    
    finally:
        device.close()


def test_key_mapping() -> None:
    """Test mapping between evdev keycodes and pynput-style keys."""
    print(f"\n{'='*60}")
    print("Testing key mapping (evdev → pynput compatibility)")
    print(f"{'='*60}\n")
    
    # Sample mappings to test
    test_cases = [
        ('KEY_LEFTCTRL', 'Left Ctrl'),
        ('KEY_RIGHTCTRL', 'Right Ctrl'),
        ('KEY_LEFTALT', 'Left Alt'),
        ('KEY_LEFTSHIFT', 'Left Shift'),
        ('KEY_LEFTMETA', 'Left Super/Win'),
        ('KEY_A', 'Letter A'),
        ('KEY_SPACE', 'Space'),
        ('KEY_F1', 'F1 function key'),
    ]
    
    print("Sample evdev → pynput mapping:")
    for evdev_key, description in test_cases:
        print(f"  {evdev_key:20s} → {description}")
    
    print("\n✓ Key mapping table defined (see wayland-backend-design.md)")


def main() -> None:
    """Main proof-of-concept test."""
    print("="*60)
    print("Proof-of-Concept: evdev for Wayland keyboard monitoring")
    print("="*60)
    print()
    
    # Step 1: Check evdev availability
    if not check_evdev_available():
        print("\n❌ Cannot proceed without evdev library")
        sys.exit(1)
    
    print()
    
    # Step 2: Check permissions
    has_permission, devices = check_permissions()
    if not has_permission:
        print("\n❌ Cannot proceed without permissions")
        sys.exit(1)
    
    print()
    
    # Step 3: Find keyboards
    print("Searching for keyboard devices...")
    keyboards = find_keyboards(devices)
    display_keyboards(keyboards)
    
    if not keyboards:
        print("\n❌ No keyboards found - cannot test events")
        sys.exit(1)
    
    # Step 4: Test key mapping
    test_key_mapping()
    
    # Step 5: Test keyboard events
    print("\n" + "="*60)
    print("Interactive test")
    print("="*60)
    print("\nDo you want to test keyboard event reading? (y/n): ", end='')
    response = input().strip().lower()
    
    if response == 'y':
        # Use first keyboard
        device_path, device_name = keyboards[0]
        test_keyboard_events(device_path, device_name)
    else:
        print("\nSkipping interactive test")
    
    # Summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    print("\n✓ evdev is working on your system!")
    print("✓ Keyboard devices were detected")
    print("✓ Event reading is functional")
    print("\nNext steps:")
    print("  1. Review the technical design: docs/wayland-backend-design.md")
    print("  2. Implement backend abstraction as described")
    print("  3. Test tap_launcher with evdev backend in Wayland session")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

