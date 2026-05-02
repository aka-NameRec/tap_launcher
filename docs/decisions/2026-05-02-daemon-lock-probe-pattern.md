# Decision: Probe-then-acquire pattern for daemon lock management

**Date:** 2026-05-02
**Status:** Accepted
**Scope:** `src/launcher/daemon_manager.py`

## Context

When replacing hand-rolled fork/flock daemonization with `python-daemon` (PEP 3143), we needed to decide how to coordinate the lock check (`acquire_lock()`) with the actual daemonization (`DaemonContext.open()`).

The original hand-rolled code held a `fcntl.flock` across both operations: the lock was acquired once, held through the double fork, and the PID was updated in the locked file after fork. This was atomic — no window for concurrent processes.

With `python-daemon`, the lock is managed by `TimeoutPIDLockFile` (from the `lockfile` package), and daemonization is handled by `DaemonContext.open()`.

## Decision

Use a **probe-then-acquire** pattern:

1. `acquire_lock()` probes the lock: acquires a `TimeoutPIDLockFile`, immediately releases it, returns `True`/`False`.
2. `daemonize(foreground=False)` creates a **fresh** `TimeoutPIDLockFile` and passes it to `DaemonContext`, which atomically acquires the lock during `open()`.
3. `daemonize(foreground=True)` writes the PID file directly (no lock needed — probe already confirmed no other instance).

This creates a theoretical race window between the probe (step 1) and the actual lock acquisition (step 2). We accept this trade-off.

## Rationale

### Why we cannot hold the lock across acquire→daemonize

`PIDLockFile.acquire()` (the parent class of `TimeoutPIDLockFile`) uses `os.open()` with `O_CREAT | O_EXCL | O_WRONLY` flags to create the PID file. This means:

- If the PID file **does not exist** → creates it, writes PID, lock acquired.
- If the PID file **already exists** → `O_EXCL` causes `EEXIST` → raises `AlreadyLocked`.

There is **no** check for "am I already holding this lock?" (`i_am_locking()` is never consulted in `acquire()`). The function is purely file-system-level: file exists → locked, file doesn't exist → not locked.

Therefore, if `acquire_lock()` creates the PID file first, `DaemonContext.open()` cannot acquire it again — even from the same process or its forked child. The child process crashes immediately after fork with `AlreadyLocked`, while the parent has already exited via `os._exit()`. Result: stale PID file, no daemon process.

This was confirmed experimentally: after `tap launch start`, `ps` showed no running process, but `tap launch status` reported "running" because `is_running()` found the stale PID file.

### Why the race window is acceptable

Between `acquire_lock()` (probe) and `DaemonContext.open()` (actual acquire), another process could theoretically start and grab the lock. However:

1. The window is extremely short (microseconds between Python function calls).
2. If the race occurs, `DaemonContext.open()` raises `AlreadyLocked` → caught as `RuntimeError` → user sees a clear error message.
3. The alternative (holding the lock) is **not possible** with this library, as shown above.
4. The original hand-rolled code avoided this by using `fcntl.flock` (advisory lock on an open fd), which survives fork and can be re-acquired by the child. `python-daemon` uses a different mechanism (exclusive file creation) that is incompatible with this pattern.

## Consequences

- **Positive:** Clean integration with `python-daemon`'s expected usage pattern.
- **Positive:** Daemon starts and stops reliably.
- **Negative:** Theoretical race condition between lock probe and acquisition. In practice, this is not observed because the window is too short and the failure mode is clear (error message, not silent corruption).
- **Negative:** `is_running()` uses a separate probe lock that can give stale results if a daemon process crashed without cleanup. This is a pre-existing limitation of PID-file-based detection, not introduced by this decision.

## References

- `src/launcher/daemon_manager.py` — implementation
- `docs/20251101-044641-change-plan-better-daemonize.md` — review findings and fix history
- PEP 3143 — Standard daemon process library
- `lockfile.pidlockfile.PIDLockFile.acquire()` — uses `O_CREAT | O_EXCL`
