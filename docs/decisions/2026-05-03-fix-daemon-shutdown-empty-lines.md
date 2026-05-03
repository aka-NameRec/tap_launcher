# Decision: Fix daemon shutdown producing empty lines in terminal

**Date:** 2026-05-03
**Status:** Accepted
**Scope:** `src/common/backends/evdev_backend/__init__.py`

## Context

Running `tap launch stop` or `tap launch restart` intermittently produced dozens of empty
lines in the terminal output. The issue did not occur with `tap launch start`.

Analysis of a console artifact showed ~48 empty lines between "Stopping tap launcher..."
and "✓ Stopped" during a restart, followed by ~60 repeated shell prompts after the command
completed.

## Root Cause

`EvdevBackend._cleanup_devices()` performed cleanup in the wrong order:

1. **Ungrabbed keyboard devices first**, then **closed uinput last**.

Between ungrab and uinput close, the kernel received events directly from the physical
keyboard while the uinput virtual device was still alive. If any key had been pressed
through uinput (emit_press) without a matching release (emit_release), the kernel treated
that key as held down. The kernel's auto-repeat then generated repeated key events that
reached the terminal — Enter auto-repeat appeared as empty lines.

The issue was intermittent because it depended on which keys were in pressed state at the
exact moment SIGTERM arrived.

Additionally, `thread.join(timeout=1.0)` per keyboard device made shutdown unnecessarily
slow (up to N seconds for N devices), extending the window for auto-repeat to produce
output.

## Decision

Three changes in `_cleanup_devices()`:

1. **New method `_release_pressed_keys()`** — emits release events for all keys tracked in
   `key_state.pressed_keys` before closing uinput, preventing stuck keys.
2. **Reordered cleanup** — changed from (ungrab devices → close devices → close uinput) to
   (emit releases → close uinput → join threads → ungrab + close devices). Uinput is now
   destroyed before keyboard devices are ungrabbed, ensuring the kernel cleans up key state
   before direct event flow resumes.
3. **Reduced thread join timeout** — from 1.0s to 0.2s per device to speed up shutdown and
   minimize the window for spurious terminal output.

## Rationale

The original order was derived from general "close resources in reverse order of creation"
thinking, without considering the interaction between the evdev grab and uinput device
lifecycles. The kernel's input subsystem requires uinput to be destroyed first so that all
key states originating from it are cleaned up before the physical keyboard resumes direct
event delivery.

Emitting explicit releases before uinput close is a defensive measure: even if the kernel
cleans up key states on device destruction, the explicit release ensures correct state
transition regardless of kernel version or configuration.

## Consequences

- **Positive:** Eliminates the intermittent empty lines / repeated prompts during
  stop and restart.
- **Positive:** Daemon shutdown is faster (0.2s vs 1.0s per device for thread joins).
- **Positive:** No behavior change for normal operation (start, monitoring, hotkey detection).
- **Negative:** None identified. The new cleanup order is strictly more correct.

## References

- `src/common/backends/evdev_backend/__init__.py` — `_cleanup_devices()`,
  `_release_pressed_keys()`
- `src/common/backends/evdev_backend/key_state.py` — `pressed_keys` tracking
- `src/common/backends/evdev_backend/uinput_writer.py` — `emit_release()`
- `docs/20260502-155704-stop-restart-artifacts/20260502-155747-console.txt` — original
  console artifact
- ConPort decision #30 — this decision
