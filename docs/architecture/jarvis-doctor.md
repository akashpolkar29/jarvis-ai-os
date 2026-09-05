# `jarvis doctor` -- real self-diagnostics (5 mixed real tasks, Task 4)

## Status

Real, working, tested. Date: 2026-09-05.

## What this is

A new, real CLI command, `jarvis doctor`, that checks this machine's
own real environment readiness -- the kind of question the 10-phase
combined pass's own Phase 10 first-run check and the 5-mixed-real-tasks
Task 2 dependency-portability audit both surfaced real, undocumented
requirements for (an NVIDIA GPU for real STT, `libportaudio2`,
PyGObject's own build-time headers), but neither gave a human a single
command to check all of them at once.

Real checks, each printed as `[OK]`/`[MISSING]` with a real, concrete
detail string, never a bare boolean:

- Python version (`>=3.12`).
- `git`/`docker`/`bwrap` binaries on `PATH` (needed for `git.*`/
  `docker.*` desktop-control capabilities and the sandboxed coding
  agent respectively).
- The real GTK4 typelib is importable (confirmation dialogs, Console
  UI).
- `libportaudio` is loadable (real microphone capture) -- the exact
  real gap Task 2 found undeclared in CI.
- `nvidia-smi` is on `PATH` (a real, practical proxy for "is there an
  NVIDIA GPU," the hard requirement Task 2 found undocumented for real
  speech-to-text).
- A local Ollama server is reachable at `localhost:11434` (the real,
  local-only default provider `coding.run_task`/`job_assistance.draft`
  both use).
- The default audit-chain directory is writable.

## A real, deliberate architectural choice, not an oversight

**`doctor` is not a capability.** It performs no action and reads no
sensitive data -- every check above reads only already-public,
non-secret local environment facts (binary presence on `PATH`, Python
version, whether a library is loadable, whether a local port is
reachable). It has no real `Effect` in this project's own taxonomy
(nothing is written, nothing leaves the machine beyond a `localhost`
probe, nothing is destructive), so it produces no audit record, the
same way a bare `jarvis --help` needs no authorization either. This
was a real, considered decision, not a silent shortcut -- stated
directly in the command's own docstring in `cli/main.py`, and proven
structurally by a real test (`--chain-path`/confirmation flags are not
even accepted; a real, empirical test confirms no `audit_chain.json`
file is ever created by running it).

Every check is read-only and safe to run repeatedly; the command
always exits `0` (it reports readiness, it does not gate anything).

## Real testing

Manually smoke-tested against this real development machine first (all
nine checks passed for real, confirming the command actually works
end to end) before writing automated tests. Six new automated tests:
the command always returns 0 and prints every real check name; it
rejects `--chain-path`/confirmation flags (structural proof it isn't a
capability); it never creates an audit-chain file; `_check_binary`
correctly reports both a real, guaranteed-present binary and a real,
guaranteed-absent one; `_check_ollama_reachable` correctly reports
"not reachable" against a real, monkeypatched connection failure.

## Conclusion

A real, working diagnostic tool now exists, directly informed by two
real gaps this same 5-mixed-real-tasks prompt's own Task 2 already
found (`libportaudio2`, the undocumented GPU requirement) -- a
contributor can now run one command to check all of them (plus several
others) at once, rather than discovering each one by hitting a real
failure.
