# Built-in core skills (WP-173)

## Status

Real, implemented. No ADR (see WP-171's own note -- unchanged here).

## What was built

`jarvis.kernel.skills.build_default_skill_registry()` -- mirrors
`kernel/capabilities.py::build_default_registry()` exactly. Registers
the first six built-in skills, one per domain named as "already
implemented and stable": **Filesystem**, **Tasks**, **Memory**,
**Calendar**, **Email**, **Browser**. Each is pure `SkillDescriptor`
metadata grouping real, already-registered `CapabilityId` values --
nothing new was implemented underneath any of them.

Validated at construction time via WP-172's `validate_skill_registry`
against a real `CapabilityRegistry` (defaulting to
`build_default_registry()`, overridable for tests) -- construction
itself is the proof every skill only ever names real capabilities.

## Real, deliberate choices, stated plainly

- **Tasks has no `task.*` capability id**, because none is
  statically registered anywhere in this codebase -- `kernel/tasks.py`
  is built on `memory.write`/`memory.update` (dynamic-effect, never
  registered) plus `memory.get`/`memory.retrieve`/`planning.run_plan`
  (registered). The Tasks skill names exactly those three real,
  registered ids rather than inventing a capability that doesn't
  exist, per the hard rule against new `CapabilityId`s without a real
  architectural need.
- **Calendar and Email are read-only skills** -- `communications.send_email`/
  `communications.create_calendar_event` are dynamic-effect
  capabilities (ADR-0057/ADR-0059), never statically registered, so
  they cannot appear in a skill's `capability_ids` either.
- **Scoped to exactly the six named domains**, not all 45 registered
  capabilities. Desktop control, coding, job search, and audit history
  are equally real and stable but adding skills for them here would be
  scope creep beyond what this work package named -- purely additive
  future work, one more `registry.register(...)` call.
- **No new capabilities were created** to make any skill "look more
  complete" -- every `capability_ids` tuple above is a strict subset
  of what `kernel/capabilities.py::build_default_registry()` already
  registers.

## A real bug found and fixed during this work package's own tests

`build_default_skill_registry`'s original implementation used
`capabilities or build_default_registry()` to supply a default. Since
`CapabilityRegistry` defines `__len__`, an explicitly-passed *empty*
registry (`CapabilityRegistry()`, `len() == 0`) is falsy in Python --
so passing one to prove `validate_skill_registry` actually fires
silently fell through to a freshly-built, fully-populated default
registry instead, masking the exact test this work package wrote to
prove the validation is real. Caught by
`test_build_default_skill_registry_raises_when_a_capability_is_actually_missing`
failing in the full suite; fixed with an explicit `is not None` check.

## Testing

`tests/unit/test_skills.py`: exact skill-id-set assertion, per-skill
domain/capability_ids assertions for all six skills (including that
Calendar/Email carry no write capability), a redundant cross-check
that every skill's capability ids are members of the real capability
registry, and the regression test for the bug above.
