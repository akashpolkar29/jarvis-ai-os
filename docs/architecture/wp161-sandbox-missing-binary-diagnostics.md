# Config/environment diagnostics: missing bwrap binary (WP-161, 2026-09-12)

## Status

Real, implemented. No ADR — a new adapter-level exception, not a new
capability/`Effect`/`Tier`.

## What was investigated

`jarvis doctor` already checks for the real `bwrap` binary
proactively, but nothing prevented a caller from running any
sandboxed capability (`coding.run_task`, `draft`'s coding-loop reuse)
anyway, ignoring or never having run `doctor` first. **Confirmed
live, before fixing, not assumed**: with `bwrap` removed from `PATH`,
`BwrapSandboxAdapter.run()` raised a raw, unexplained
`FileNotFoundError: [Errno 2] No such file or directory: 'bwrap'` —
no indication of what "bwrap" is, that it's a sandboxing dependency,
or how to install it.

## What was built

`SandboxUnavailableError` (`ports/sandbox.py`, not a `JarvisError`
subclass — the same "adapter-level, real-world environment condition"
reasoning `GitCommandFailedError` already uses). `BwrapSandboxAdapter.run()`/
`.launch()` now catch `FileNotFoundError` from their own subprocess
call and re-raise it as a clean, actionable
`SandboxUnavailableError` naming the real binary, what it's for, and
an install command. Wired into `cli/main.py`'s existing broad except
tuple, mirroring every other adapter-level operational exception's own
identical treatment.

## What was deliberately not built

- No change to `_build_bwrap_argv`, the real sandbox flags, or any
  containment logic — this only wraps the "binary missing" failure
  mode, entirely orthogonal to whether a working sandbox actually
  contains a command correctly.
- No new `jarvis doctor` check — one already exists; this closes the
  gap for the runtime path that doesn't consult `doctor` first.
- No config file, no configuration framework — this project has none,
  confirmed directly, matching its own established finding.

## Testing

Two new adapter-level tests (injected `run_subprocess`/
`launch_subprocess` functions raising `FileNotFoundError`) prove both
`run()` and `launch()` re-raise the clean, actionable error. One new
CLI-level test proves `jarvis code` reports it via the existing
`Error: ...`/exit-1 path, not a raw traceback.
