#!/bin/bash
# Test script for keyboard access

cd /home/shtirliz/workspace/myself/tapper_launch

echo "Testing keyboard access with pynput..."
echo "Press any key within 5 seconds..."
echo ""

timeout 5 uv run python3 << 'PYTHON_SCRIPT'
from pynput import keyboard
import time

def on_press(key):
    print(f'✓ Key pressed: {key}')

def on_release(key):
    print(f'✓ Key released: {key}')

print("Keyboard listener started. Press keys...")
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
time.sleep(5)
listener.stop()
print("\nTest complete!")
PYTHON_SCRIPT

echo ""
echo "If you saw key events above, pynput is working!"
echo "You can now run: uv run tap-launcher start --foreground"


