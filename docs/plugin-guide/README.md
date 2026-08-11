# Plugin Guide

This is a real guide for adding a new capability to JARVIS today, as
of Milestone 0. It is not a guide for third-party plugin authors —
`jarvis.plugin_api` has no real content yet, and dynamic plugin
loading from disk doesn't exist (see `docs/threat-model/v0.md`). Every
capability today is registered directly in this source tree. This
document will need a real rewrite once external plugin loading lands;
until then, it describes exactly how the two existing real capability
families were built, so a third can be added the same way.

The worked example throughout is `kernel/music.py`
(`music.play`/`music.pause`/`music.next`/`music.previous`), the
simplest full example of the pattern. `kernel/files.py`
(`fs.read_file`) is referenced separately at the end for the one case
music doesn't cover: a capability whose danger scales with an
argument, not just its `Effect`.

## 1. Decide the `CapabilityDescriptor`

Every capability is a `CapabilityDescriptor`
(`domain/capability.py`): an `id` (a single token, e.g.
`"music.pause"`), a set of `Effect` flags, and a human-readable
`description`. The `id` and `description` are yours to choose. The
`Effect` set is the one real design decision — it determines the
`Tier` the policy engine will require, via `_EFFECT_TIER_FLOOR`
(`domain/capability.py`):

| Effect | Floor tier |
| --- | --- |
| `READ_LOCAL`, `EGRESS_LOCAL` | `ALLOW` |
| `WRITE_LOCAL`, `EXECUTE`, `EGRESS_SENSITIVE` | `CONFIRM` |
| `DESTRUCTIVE`, `IRREVERSIBLE`, `CREDENTIAL`, `EGRESS_SECRET` | `MANUAL_ONLY` |

Ask what your capability *actually does*, not what feels risky in the
abstract. `music.pause` sends a command that mutates a running
process's playback state — not a read — so `WRITE_LOCAL` is the
honest choice, landing it at `CONFIRM`. Don't reach for a higher
effect than what's true just to get a stricter tier: the taxonomy is
closed (ADR-0004, extended only via a new ADR, never ad hoc), and
picking a dishonest effect to manufacture a gate you want is exactly
the kind of thing this project has consistently rejected — see
`kernel/files.py`'s own reasoning for why `fs.read_file` is
`EGRESS_LOCAL` and not `WRITE_LOCAL`, even though a stricter tier
might feel more "correct" for a capability that exposes file content.

If your capability's danger scales with an *argument value* rather
than its effect type as a whole (a path, a URL, a target), a tier
increase is probably the wrong tool — see step 6.

## 2. If you're integrating a new external system, define a port first

If your capability talks to something outside this process — a D-Bus
service, a filesystem, a future network API — it needs a `Protocol` in
`ports/` before anything in `adapters/` or `kernel/` may reference the
real technology by name. This is true even for "boring" cases: local
file I/O got exactly this treatment (`ports/file_system.py` +
`adapters/file_system.py`), not just genuinely remote systems like
D-Bus (`ports/media_player.py` + `adapters/media_player.py`). Nothing
outside `adapters/` is allowed to name a vendor or specific technology
— `kernel/` composes ports and adapters together, it does not import
`jeepney` or call `open()` directly.

If your capability's failure modes are genuinely new (not already one
of Python's standard exceptions), give the port its own exception type
— see `ports/media_player.py`'s `NoMediaPlayerRunningError`/
`MediaPlayerCommandFailedError` for the pattern, including why they
are deliberately *not* `JarvisError` subclasses (they're adapter-layer
operational conditions, not domain concerns — `JarvisError`'s own
docstring scopes itself to exceptions raised from within
`jarvis.domain`). If a failure is already a clear, standard exception
(`FileNotFoundError`, `PermissionError`), let it propagate unwrapped —
don't invent a wrapper that adds no information
(`adapters/file_system.py`'s own docstring states this reasoning).

## 3. Register it in `kernel/capabilities.py`

All known capabilities are declared in one place,
`build_default_registry()` (`kernel/capabilities.py`) — not
constructed inline inside whichever kernel function will use them.
Add your `CapabilityId` as a module-level constant, add a
`CapabilityDescriptor.register()` call inside `build_default_registry()`.
That's it — `CapabilityRegistry.register()` already raises
`CapabilityAlreadyRegistered` if your new id collides with an existing
one, so a typo'd duplicate id fails loudly at the first test run, not
silently.

## 4. Write the kernel composition function

Every kernel composition function (`authorize_ping`,
`authorize_and_run_music_command`, `authorize_and_read_file`) follows
the same shape:

```python
# your_port is optional, only if you added a port in step 2.
# Return type: Decision, or a small dataclass wrapping it if you need
# to return more (see FileReadOutcome).
def authorize_and_do_the_thing(
    # ...your capability's real arguments...
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    your_port: YourPort | None = None,
) -> Decision:
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        YOUR_CAPABILITY_ID,
        Tainted(your_arguments, Provenance.user()),  # or a different provenance -- see step 5
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            port = your_port if your_port is not None else RealAdapter()
            # ... actually do the thing ...
    finally:
        storage.save(chain)

    return decision
```

Two rules here are non-negotiable, not stylistic:

- **Authorization happens strictly before any real-world action.** The
  real action only ever happens inside `if decision.granted:`. A
  denied decision must never reach your port/adapter at all — this is
  the entire point of having a policy engine rather than checking
  permissions after the fact.
- **The `try`/`finally` around `storage.save(chain)` is mandatory, not
  a style preference.** `orchestrator.authorize_by_id()` already
  appended the decision to the in-memory chain before your code runs
  the real action. If that action then raises (the file doesn't
  exist, the D-Bus service rejects the call, whatever), and you don't
  wrap it in `try`/`finally`, the already-decided, already-granted
  record is silently lost from disk — never persisted, with no error
  telling you it happened. This exact bug was caught and fixed during
  work package 14 (see `kernel/music.py`'s module docstring for the
  full story) and is now the standard pattern everywhere.

If your capability has an injectable port parameter (only add one if
you actually added a port in step 2), default it to `None` and
construct the real adapter inside the function, exactly like
`media_player`/`file_system` above — not an injectable
`CapabilityRegistry`, though: see `kernel/capabilities.py`'s own
docstring for why the registry itself is deliberately *not*
injectable (nothing today needs it, and adding it later is
non-breaking if something ever does).

## 5. Decide the argument provenance

Anything typed directly by the user at the CLI is `Provenance.user()`
— that's every capability so far. If your capability's arguments (not
its *results* — see `kernel/files.py`'s content-provenance handling
for that distinction) could plausibly come from somewhere the user
didn't directly type right now, use `Provenance.external(source, classification)`
instead, and read ADR-0011 first: an `UNTRUSTED_EXTERNAL`-tainted
argument automatically escalates the required tier by one step,
whatever your capability's base tier is.

## 6. If danger scales with an argument, not your `Effect`

`fs.read_file` is the example: `Effect.EGRESS_LOCAL` alone would let
it read any file the process has permission to read, and no tier
increase fixes that (tier escalation is a per-*taint* step, not
per-argument-value, and there is no honest `Effect` for "arbitrary
path access" in the current taxonomy). Instead, `kernel/files.py`
resolves and validates the path *before* calling `authorize_by_id()`
at all, raising a dedicated exception (not a `Decision`) if it's out
of bounds. Read `kernel/files.py`'s module docstring and
`PathOutsideAllowedScopeError`'s docstring in full before doing this
for a new capability — in particular the audit-trail gap this
approach creates (a rejected-before-authorization request leaves no
record in the chain at all), which is now Gap 4 in
`docs/threat-model/v0.md`. This is the right tool only when the
danger is structural (which paths/targets are even reachable), not
when it's about how much confirmation an otherwise-bounded action
needs.

## 7. Wire it into the CLI

Add a subcommand in `cli/main.py` (`_build_parser()`), sharing the
common flags via `_add_common_flags()`. If your kernel function can
raise a new exception type, add it to `main()`'s `except (...)` tuple
— every exception a user can hit must produce a clean `Error: ...`
message on stderr and exit code `1`, never a raw traceback. `cli/main.py`
itself must stay thin: it parses argv, calls exactly one kernel
function, and formats the result. It does not decide policy.

## 8. Tests expected

- **A contract test**, if you added a new port: `isinstance(RealAdapter(), YourPort)` is `True`, and a deliberately non-conforming object is `False` — proves the `isinstance` check is meaningful, not tautological.
- **Adapter unit tests.** Mock only what genuinely requires a resource unavailable in CI (a live D-Bus bus, per `adapters/media_player.py`) — real local filesystem I/O against `tmp_path` needs no mocking at all (per `adapters/file_system.py`). Be explicit in the test file's own docstring about what's mocked and why; don't leave it implicit.
- **Kernel composition function tests**, using a stub port with call-tracking (not the real adapter): granted calls the port; denied never touches the port at all (assert an empty call log, not just the `Decision`); a granted-but-then-failing action still persists the audit record (the `try`/`finally` proof — see `tests/unit/test_music.py`'s `test_audit_record_is_saved_even_when_the_media_player_raises` for the exact shape).
- **CLI tests.** If your kernel function's real default touches something outside test control (a real bus, a real home directory), monkeypatch the kernel-level call at the CLI layer via `sys.modules["jarvis.cli.main"]` (see `tests/unit/test_cli_main.py`'s own "Patching note" docstring for why the naive `monkeypatch.setattr("jarvis.cli.main.X", ...)` form silently patches the wrong object here) rather than letting it run for real.
- **`build_default_registry()`'s own test file** doesn't need touching for a new capability unless you want to extend its "exactly these ids" assertion — reasonable, but not required.

If you can follow steps 1 through 8 above for a genuinely new
capability without needing anything not described here, this guide is
doing its job. If you hit a real gap, that's a sign this document
needs updating, not that you did something wrong.
