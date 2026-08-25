# ADR-0054: ClockPort and IdPort -- the time/identity adapters CLAUDE.md presupposes

## Status

Accepted

**Acceptance note (2026-08-26):** accepted directly during M4 implementation (WP-57) -- the gap below blocks WP-60's own retention mechanics (ADR-0051) from being written at all without violating an existing, tooling-enforced invariant, and the design is dictated almost entirely by that invariant's own text rather than requiring new debate. Accepted and built in the same pass, matching ADR-0042's own precedent for a comparable "already presupposed, never actually built" gap.

## Date

2026-08-26

## Source

Found while implementing ADR-0051 (memory retention): `CLAUDE.md`'s own "Invariants enforced by tooling, not convention" section states "No `datetime.now()`, `time.time()`, `time.monotonic()`, or `uuid.uuid4()` anywhere in `src/` — inject `ClockPort` / `IdPort` instead," and `ADR-0051`'s own Decision requires "`written_at`/`expires_at` are computed via `ClockPort`, never `datetime.now()` directly." Checked directly before writing a line of M4's retention code, not assumed: neither `ClockPort` nor `IdPort` exists anywhere in `src/jarvis/ports/` or `src/jarvis/adapters/` -- confirmed by a full search. The only place either name appears at all is a documentation sentence in `domain/__init__.py`'s own module docstring, restating the same rule.

This is the identical shape of gap ADR-0042 closed for `SecretPort`: a rule/port that a project document already presupposes, that nothing in the real repository had ever actually built, surfaced only once a real work package needed it for the first time. `tests/meta/test_source_invariants.py` had already, independently, anticipated this exact moment: `_CLOCK_ID_ADAPTER_ALLOWLIST: frozenset[Path] = frozenset()`, with its own comment reading "Future ClockPort/IdPort adapter implementations are the one place these calls are legitimate. Empty for now -- no adapters exist yet." The mechanism to exempt a real adapter from the banned-call scan already existed; only the adapter itself was missing.

## Decision

Two new, minimal ports, matching `FileSystemPort`'s own "only what a real caller needs" minimalism:

```python
# ports/clock.py
@runtime_checkable
class ClockPort(Protocol):
    def now(self) -> datetime:
        """Return the real, current wall-clock time (UTC, timezone-aware)."""
        ...
```

```python
# ports/identifier.py
@runtime_checkable
class IdPort(Protocol):
    def new_id(self) -> str:
        """Return a real, fresh, unique identifier."""
        ...
```

Real adapters, each a single, small, real, untested-by-design-by-CI function wrapping exactly the one banned call this port exists to replace -- matching every other real-hardware/real-nondeterminism adapter's own shape in this repo:

```python
# adapters/clock.py
class SystemClockAdapter:
    def now(self) -> datetime:
        return datetime.now(UTC)  # noqa: TID251 -- the one call ClockPort exists to wrap
```

```python
# adapters/identifier.py
class UuidIdAdapter:
    def new_id(self) -> str:
        return str(uuid.uuid4())  # noqa: TID251 -- the one call IdPort exists to wrap
```

`tests/meta/test_source_invariants.py`'s `_CLOCK_ID_ADAPTER_ALLOWLIST` is populated with these two real file paths -- the first, and by design the only, files in `src/` permitted to make these calls. `# noqa: TID251` is also required on each real call site: ruff's own banned-api rule resolves the fully-qualified name regardless of import style (`from datetime import datetime; datetime.now(...)` still resolves to the banned `datetime.datetime.now`), so the AST meta-test's allowlist alone does not silence ruff -- both are real, independent gates and both need satisfying at the exact line, not the whole file, keeping the exemption as narrow as the one line that needs it.

`IdPort.new_id()` returns `str`, not `uuid.UUID` -- matching how every existing opaque identifier in this codebase (`WindowHandle.value`, `SyntheticInputSession.session_handle`) is already a plain string, not a richer type callers would need to know how to handle.

## Consequences

Every future milestone needing wall-clock time or a fresh random identifier now has a real port to inject, closing the gap `CLAUDE.md`'s own invariant already declared but nothing had built. `MemoryRecord` (ADR-0048/ADR-0051) is this repo's first real consumer of both.

**Deliberately minimal, not extended speculatively**: no `sleep`/timer functionality on `ClockPort` (this project already has a separate, established `sleep_fn`-injection convention for that, used throughout `adapters/desktop_window.py`/`application/desktop/terminal.py` -- conflating "what time is it" with "wait" would blur two already-distinct seams). No batch/sequence identifier generation on `IdPort` -- one identifier per call, matching the one real need this pass has.
