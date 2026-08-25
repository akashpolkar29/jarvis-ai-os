# ADR-0048: MemoryWritePort and RetrievalPort -- the real M4 port shapes

## Status

Proposed

## Date

2026-08-25

## Source

M4 scoping pass (`docs/architecture/m4-scoping-notes.md`, answered by
the user 2026-08-25) and the resulting real design,
`docs/architecture/m4-memory-retrieval.md`. This ADR is a draft for the
user's own review and decision, not a decision made here -- per
CLAUDE.md's hard rule, no code implementing it exists yet and none
should until this is Accepted.

## Context

M4's own scoping pass confirmed (`m4-scoping-notes.md`'s technical map,
question 5) that no existing port in this codebase answers "search
past context for something relevant" -- a genuinely new kind of read
operation, distinct from `FileSystemPort.read_file`'s single-known-path
shape, and distinct from `DesktopWindowPort.read_visible_text`'s
"read whatever's currently on screen" shape. Similarly, no existing
port writes to a persistent, later-searchable store -- `WorkspacePort`
materializes a `Candidate`'s content as real files for a validator
(ADR-0043), a narrower, different-shaped concern.

Two separate concerns, two separate ports, not one combined
`MemoryPort` -- matching this project's own established precedent of
keeping ports narrowly scoped to one real capability shape each
(`SecretPort`'s own "only what the real caller needs" minimalism,
cited in ADR-0042, is the direct analogue): writing to memory and
reading from it are genuinely different operations with different
authorization stories (see ADR-0049/ADR-0050), and collapsing them
into one port would obscure that difference rather than express it.

## Decision

Two new, minimal ports:

```python
class MemoryWritePort(Protocol):
    def write(self, value: Tainted[object]) -> None:
        """Persist `value` to memory, provenance intact.

        Raises:
            MemoryWriteDeniedError: If Policy Engine evaluation
                (via memory_effect_for, ADR-0049) denies the write --
                most notably, unconditionally, for Classification.SECRET.
        """
        ...
```

```python
class RetrievalPort(Protocol):
    def retrieve(self, query: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        """Return up to `limit` MemoryRecords ranked by relevance to `query`.

        Each returned record carries its own real, unmodified
        Provenance -- this port does not gate anything based on
        classification; the caller re-evaluates each record's tier
        before using it (ADR-0050). Excludes records past their TTL
        and not pinned (ADR-0051) -- an expired, unpinned record is
        indistinguishable from one that was never written, from this
        port's own caller's perspective.
        """
        ...
```

`MemoryRecord` (`domain/memory.py`) wraps a `Tainted[object]` plus
storage metadata (a real, stable identifier; write timestamp via
`ClockPort`, never `datetime.now()` directly, per this project's own
banned-API rule; TTL/pin state). No new `Trust`/`Classification`
vocabulary -- `domain/provenance.py`'s existing types are reused
exactly as `domain/desktop.py`'s own precedent already established for
`WindowHandle`/`SyntheticInputSession`.

`write()`'s own real authorization path: the capability invocation
wrapping this call resolves `memory_effect_for(value.provenance.classification)`
(ADR-0049) into the invocation's declared `Effect` *before*
`AuthorizationOrchestrator.authorize_by_id()` runs -- the port method
itself performs no authorization; it is called only after a real,
granted `Decision`, the same "port is a pure mechanism, kernel/application
owns the authorization choke point" split every other port in this
repo already follows.

## Consequences

Two new ports join this repo's real port set; no existing port
(`WorkspacePort`, `SecretPort`, `DesktopWindowPort`, `SandboxPort`,
`GitPort`, `DockerPort`) is modified. `MemoryWritePort.write()`'s real
adapter needs a real vector store/embedding pipeline underneath it
(deliverable 5, `m4-memory-retrieval.md`) -- not decided by this ADR,
tracked as real, separate, benchmark-driven follow-up work.

`RetrievalPort.retrieve()` deliberately returns raw, unfiltered-by-tier
records -- this is a real, load-bearing design choice, not an
oversight: gating happens at the point of *use*, per ADR-0050, not at
the point of *return*, because this port has no way to know what the
caller intends to do with a record (display it to the user directly?
feed it into a cloud-bound prompt? use it only internally?) -- exactly
the kind of context-dependent authorization decision this project's
own architecture already reserves for the capability/application
layer, not the port layer, everywhere else.

**Not decided here, real, open**: whether `RetrievalPort` needs its
own `Effect`/`Tier` floor beyond `READ_LOCAL`/`ALLOW` for the bare act
of querying (as opposed to what a caller does with the result,
ADR-0050's own concern) -- `m4-memory-retrieval.md`'s worked example
assumes `ALLOW` for the query itself, but this ADR does not foreclose
revisiting that if a real implementation finds a reason to.
