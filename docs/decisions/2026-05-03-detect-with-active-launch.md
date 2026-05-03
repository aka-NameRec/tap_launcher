# Decision: Allow detect to run while launch is active via temporary launcher restart

**Date:** 2026-05-03
**Task:** `0tegm2p`
**Scope:** `src/detector/main.py`, `src/launcher/main.py`, `src/launcher/daemon_manager.py`, `src/common/runtime_state.py`

## Context

`launch` uses the evdev backend with exclusive physical keyboard grabs. This is required for
key suppression: original keyboard events must not reach the OS or foreground applications until
the launcher decides whether a tap combination should be passed through via uinput or suppressed.

Because evdev grabs are exclusive, a second process running `detect` cannot grab the same physical
keyboard devices while `launch` is active. The observed failure was:

```text
Failed to grab any keyboard devices. All devices may be busy.
```

## Decision

Use a pragmatic stop-detect-restart workflow for `detect`:

1. `detect` checks whether `launch` is active through the sibling `launch status` CLI.
2. If active, `detect` stops it through `launch stop`.
3. `detect` runs the existing direct evdev detection path.
4. On exit, `detect` restarts `launch` through `launch start`.

To preserve restart parameters, `launch start` writes a runtime state file:

```text
~/.local/share/tap-launcher/tap-launcher.state.json
```

The PID file remains a plain numeric lock/PID file. Runtime state is stored separately and includes:

- PID
- resolved config path
- debug flag
- foreground flag
- runtime state format version

`detect` restores `--config` and `--debug` from this state. It does not restore `--foreground`;
automatic restoration always starts the launcher as a background daemon.

## Rationale

This avoids introducing a daemon control socket or `suspend`/`resume` state machine. Those designs
would be architecturally cleaner for future event streaming, but they require substantially more
backend lifecycle work: stopping reader threads, closing uinput, ungrabbing devices, clearing
key/tap state, and later reacquiring devices without terminating the daemon.

The chosen workflow keeps `detector` and `launcher` as independent CLI applications. They share
only common code and communicate through subprocess calls to the public `launch` CLI plus a shared
runtime state file.

Keeping runtime state out of the PID file preserves the PID file as a simple and robust daemon lock
artifact. This avoids breaking code and scripts that expect the PID file to contain only a number.

## Consequences

- **Positive:** `detect` works in the common case where `launch` is already active.
- **Positive:** Launcher config and debug startup options are preserved across detect sessions.
- **Positive:** No daemon IPC protocol or backend suspend/resume lifecycle is required.
- **Negative:** Launcher hotkeys are unavailable while `detect` is running.
- **Negative:** If the process is killed with an unrecoverable signal such as `SIGKILL`, launcher
  restoration cannot run.
- **Fallback:** If runtime state is unavailable, `detect` still restarts `launch` with default
  startup parameters.

## Signal Handling Note

`EvdevBackend` installs a global signal handler that performs backend cleanup and then re-sends the
signal to the process. In `detect`, this bypassed normal Python unwinding and prevented the launcher
restart path from running after Ctrl+C.

`detect` therefore reinstalls its own `SIGINT`/`SIGTERM` handlers after creating `TapMonitor`.
Those handlers raise `KeyboardInterrupt`, allowing the evdev backend to clean up through its normal
`finally` path and allowing `detect` to restart `launch` in its own `finally` block.
