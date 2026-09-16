# Skill registry (WP-172)

## Status

Real, implemented. No ADR (see WP-171's own note -- unchanged here).

## What was built

`jarvis.domain.skill_registry.SkillRegistry` -- mirrors
`jarvis.domain.registry.CapabilityRegistry` exactly: an in-memory,
append-only-by-id, no-I/O collection of `SkillDescriptor`, keyed by
`SkillId`. `register()` rejects a duplicate id
(`SkillAlreadyRegistered`); `get()` raises `SkillNotRegistered` on a
miss; `__contains__`/`__len__`/`__iter__` round out the shape.

`validate_skill_registry(skills, capabilities)` is the one real piece
of logic beyond that mirror: it reuses the existing, real
`CapabilityRegistry` directly (per the hard rule: "existing
plugin/capability registry should be reused where practical") to
confirm every registered skill's `capability_ids` names something that
genuinely exists, raising `SkillReferencesUnknownCapability` otherwise.
This is a free function, not folded into `register()`, since
validating against a capability registry requires one already fully
built -- `kernel.skills.build_default_skill_registry()` (WP-173) will
call it once, after both registries are constructed.

## What was deliberately not built

- No dynamic/out-of-tree skill loading from disk -- matches
  `CapabilityRegistry`'s own identical, already-stated scope
  boundary. Registering a skill still means editing a file in this
  source tree.
- No arbitrary code execution of any kind -- `SkillDescriptor` is pure
  data (id/name/description/domain/capability_ids/instructions/tags);
  there is nothing here to execute.
- No second capability registry -- `validate_skill_registry` reads the
  real one, never constructs or duplicates its contents.
- No authorization bypass -- neither `SkillRegistry` nor
  `validate_skill_registry` can invoke a capability; they only ever
  describe and cross-check identifiers.

## Testing

`tests/unit/test_skill_registry.py`: register/get round-trip,
duplicate rejection, unregistered lookup, `__contains__`/`__len__`/
`__iter__`, and `validate_skill_registry`'s pass/fail cases (all
capabilities real, one unknown capability on a single-capability
skill, one unknown capability on a multi-capability skill, and the
trivial empty/empty case).
