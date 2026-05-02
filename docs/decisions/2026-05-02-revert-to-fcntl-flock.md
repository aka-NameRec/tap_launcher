# Decision: Revert to fcntl.flock daemonization, remove python-daemon

**Date:** 2026-05-02
**Status:** Accepted
**Supersedes:** `docs/decisions/2026-05-02-daemon-lock-probe-pattern.md`
**Scope:** `src/launcher/daemon_manager.py`, `src/launcher/main.py`, `pyproject.toml`

## Context

Branch `feature/20251101-044641-Better_daemonize` replaced hand-rolled `fcntl.flock` + double-fork
daemonization with `python-daemon` library (PEP 3143). The goal was to use a standardized solution
instead of "reinventing the wheel."

During implementation, a fundamental incompatibility was discovered:
`PIDLockFile.acquire()` (from the `lockfile` package) uses `O_CREAT | O_EXCL` flags, which means
it cannot re-acquire a lock if the PID file already exists — even if the lock is held by the same
process or its forked child. This forced a **probe-then-acquire** pattern:

1. `acquire_lock()` probes the lock (acquire → release) without holding it.
2. `daemonize()` creates a **fresh** `TimeoutPIDLockFile` for `DaemonContext`, which acquires
   the lock atomically during `open()`.

This pattern introduces a race window between steps 1 and 2, which the original `fcntl.flock` code
did not have.

## Decision

Revert to `fcntl.flock`-based daemonization with an improved API:

1. `acquire_lock()` — acquires and **holds** the lock via `fcntl.flock` on `pid_fd`. Writes PID.
2. `daemonize(foreground)` — double-fork for background mode, updates PID on inherited `pid_fd`.
   No-op for foreground mode (lock already held, PID already written).
3. Remove `python-daemon` and `lockfile` dependencies entirely.

## Rationale

### Why python-daemon was a net negative

| Aspect | fcntl.flock (original) | python-daemon (feature branch) |
|---|---|---|
| External dependencies | 0 | `python-daemon` + `lockfile` |
| Race conditions | none | probe-then-acquire window |
| Regressions during development | 0 | 1 (daemon crash after fork) |
| Lock semantics across fork | inherited via fd | incompatible (O_EXCL) |
| Maintenance of lockfile package | N/A | unmaintained since ~2015 |
| Lines of code in daemon_manager.py | ~245 | ~244 |
| Complexity of acquire_lock() | acquire → hold | probe → release → recreate → acquire |

### Why fcntl.flock is correct for this use case

1. **Survives fork:** `fcntl.flock` on an open file descriptor is inherited by child processes
   through `fork()`. The lock remains valid in both parent and child.
2. **Kernel-managed cleanup:** The kernel releases the lock when the process exits (even on crash).
   No stale lock files.
3. **Truly atomic:** Lock is held continuously from `acquire_lock()` through `daemonize()` —
   no window for concurrent processes.
4. **Standard library:** Zero external dependencies, available on all Linux systems.

### API improvement over the original main-branch code

The original code on `main` had a module-level `daemonize()` function called separately from
`daemon.write_pid_file()`. The new implementation:

- Makes `daemonize()` a method on `DaemonManager` (consistent with the class API).
- Updates PID via the inherited `pid_fd` after fork (atomic, no separate file open).
- Accepts `foreground` parameter to handle both modes in one call.

## Consequences

- **Positive:** Zero race conditions, zero external daemonization dependencies.
- **Positive:** Simpler code — no probe-then-acquire, no workarounds for library limitations.
- **Positive:** Lock semantics are correct by construction (kernel-managed, fd-inherited).
- **Negative:** Double-fork implementation is "hand-rolled" (~30 lines), but it is a well-known
  POSIX pattern with no ambiguity.
- **Negative:** Not PEP 3143 compliant — but PEP 3143's lock mechanism (`PIDLockFile`) is
  incompatible with our requirements, making compliance impossible without workarounds.

## References

- `src/launcher/daemon_manager.py` — implementation
- ConPort decision #27 — this decision
- ConPort decision #26 — superseded (probe-then-acquire pattern)
- PEP 3143 — Standard daemon process library
