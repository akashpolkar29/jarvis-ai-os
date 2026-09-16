# A JARVIS-native Skill abstraction (WP-171)

## Status

Real, implemented (types + design only, per this work package's own
scope -- registry is WP-172, built-in skills are WP-173). No ADR: this
introduces no new `CapabilityId`, `Effect`, or `Tier`, and changes no
authorization semantics -- the same "no ADR needed" precedent already
established for WP-107 (Task/TaskStore), WP-108 (UI foundation), and
WP-111 (events).

## What problem this solves

M8-and-beyond work (this queue) wants JARVIS to be able to answer "what
can I do?" and to give a reasoning fallback compact, relevant context
instead of the whole system description (WP-174/175). Neither exists
today: the closest things are `CapabilityDescriptor` (one directly
invocable, effect/tier-classified unit -- no grouping concept) and
`docs/protocol/README.md` (a hand-maintained doc, not a runtime
structure a program can query).

OpenJarvis is cited as inspiration for a "skills" concept. This design
takes only the idea -- a named, discoverable grouping of what an agent
can do -- not its implementation. It does not import or adapt any
OpenJarvis code.

## Reconnaissance: what already exists (checked directly, not assumed)

- **Capability registry** (`domain/registry.py::CapabilityRegistry`,
  `kernel/capabilities.py::build_default_registry`): the single source
  of truth for real, invocable capabilities, each with a fixed
  `Effect`/derived `Tier`. No grouping/discovery layer above it.
- **Plugin API** (`plugin_api/__init__.py`): a stable, domain-only
  import surface for capability *authors*. Not a discovery mechanism,
  and out of scope to extend here -- no built-in skill in this queue
  needs a third-party authoring path.
- **Router** (`kernel/router.py`, `application/routing/router.py`,
  WP-104): maps free text to one capability id (Stage A deterministic,
  reusing `kernel/intent.py::resolve_intent()`) or, via Stage B
  reasoning fallback, a structurally-validated `RouteResult`. It has no
  "list what's possible in domain X" concept, and it **never executes
  anything itself** -- `authorize_and_route` only ever dispatches to
  the small, fixed `PLAN_STEP_EXECUTORS` table, three hand-wired
  `communications.*` branches, or creates (never runs) a task. This is
  the one execution choke point a Skill layer must sit above, never
  beside.
- **Task planner/executor** (`application/planning/`, `kernel/tasks.py`,
  ADR-0062): plans are a *sequence of capability-id steps*, each
  individually authorized at execution time -- no batch pre-approval.
  A skill is not a plan and must never pre-approve or bundle
  authorization across its member capabilities.
- **Memory** (`kernel/memory.py`): unrelated data-storage capability;
  a skill could *describe* `memory.write`/`memory.retrieve` but memory
  itself has no notion of skills.
- **Event system** (`domain/events.py`, WP-111): a real, minimal
  `TaskCreated`/`TaskStatusChanged` in-process bus. No "skill invoked"
  event exists yet (see WP-177's own separate scope).
- **Ports/adapters**: no `SkillPort` of any kind exists; nothing here
  needs one -- a skill is static, in-tree metadata, not an external
  system.
- **CLI structure** (`cli/main.py`, WP-166's `jarvis do --help`
  epilog): today's only "what can I do" surface is a hand-written help
  epilog plus `docs/protocol/README.md`. WP-174 will give this a real,
  queryable counterpart.
- **Docs/ADR structure**: 63 ADRs, none define a skill concept.
  `docs/OPEN_DECISIONS.md` and `docs/ROADMAP.md` have no open item
  about one either -- this is new, additive scope, not a resolution of
  an existing open question.

**Conclusion**: no existing abstraction covers this. A minimal,
additive Skill layer is justified.

## The abstraction

```
SkillId          -- a validated, single-token identifier (mirrors CapabilityId)
SkillDescriptor  -- id, name, description, domain, capability_ids (non-empty
                     tuple of real CapabilityId), optional instructions,
                     optional discoverability tags
```

Both are pure, frozen, stdlib-only dataclasses in `jarvis.domain.skill`
-- the same ring `CapabilityDescriptor` lives in, for the identical
reason (no I/O, no async, no wall-clock/randomness; described once,
looked up by id).

**What a Skill is not, by construction**:

- Not a second execution system. `SkillDescriptor` carries no `Effect`,
  no `Tier`, and no callable -- it cannot be "run." Every capability id
  it names is invoked exactly as it always was, through
  `AuthorizationOrchestrator`/the existing `authorize_and_*`
  composition functions.
- Not a batch pre-approval mechanism. Grouping `fs.read_file` and
  `fs.list_dir` under a "Filesystem" skill does not grant one on behalf
  of the other; each is still authorized individually, exactly as
  ADR-0062 already requires for plan steps.
- Not a new capability-registration path. `capability_ids` must
  reference capabilities already registered in the real
  `CapabilityRegistry` -- WP-172's registry validates this by reusing
  that registry directly, not by inventing a parallel notion of what
  exists.

## What WP-172/173/174/175 build on top of this, unchanged by this note

- WP-172: `SkillRegistry` (register/get/list/`__contains__`, duplicate
  rejection) mirroring `CapabilityRegistry`'s own shape, plus a
  validation function cross-checking every skill's `capability_ids`
  against a real `CapabilityRegistry`.
- WP-173: `kernel/skills.py::build_default_skill_registry()` (mirrors
  `kernel/capabilities.py::build_default_registry()`) registering the
  first skills for already-stable domains.
- WP-174: CLI discovery commands reading the registry.
- WP-175: a compact, deterministically-filtered projection of skill
  metadata fed to the router's existing Stage-B reasoning call --
  never a second router, never a way to bypass registry validation or
  authorization.
