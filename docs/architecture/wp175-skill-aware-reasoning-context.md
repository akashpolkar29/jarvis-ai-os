# Skill-aware reasoning context for the router's Stage-B fallback (WP-175)

## Status

Real, implemented. No ADR -- purely advisory prompt content, no
authorization change, no new `CapabilityId`/`Effect`/`Tier`.

## A real premise correction, checked before writing any code

The work package's own framing ("instead of blindly receiving the
entire system description") does not match this codebase's real,
pre-existing behavior -- checked directly, not assumed. Neither
`application/routing/router.py::generate_route` (Stage B of the typed
router, WP-104) nor `application/planning/planner.py::generate_plan`
(the planner, ADR-0062) ever sent *any* real capability/skill list to
a model before this work package. Both prompts carried a single fixed,
generic example (`"fs.read_file"`) and nothing else describing what
actually exists -- the model had to guess blind, with `is_registered`
as the only real backstop. There was no "entire system description" to
trim down; the real gap was the opposite one (zero context), which is
what this work package actually closes for the router's Stage B
specifically (the planner is unchanged -- out of this work package's
own scope).

## What was built

- `application/routing/router.py::_select_relevant_skills(text, skills, limit=5)`
  -- deterministic, plain, case-insensitive substring matching against
  each skill's own id/domain/name/tags. No embeddings, no reasoning
  call, no randomness; skills are sorted by id first so the result
  never depends on the caller's own iteration order. Returns an empty
  tuple (never a fallback to the full list) when nothing matches,
  keeping the added context genuinely optional and genuinely compact.
- `_format_skill_context` -- renders only `id`/`domain`/`description`/
  `capability_ids` for the matched subset. A skill's own free-text
  `instructions` field is deliberately never included, proven by a
  dedicated test.
- `generate_route(text, provider, is_registered, skills=())` -- a new,
  optional fourth parameter. Every existing caller/test that never
  passes it gets the exact byte-for-byte prompt shape as before
  (proven by `test_generate_route_with_no_matching_skills_sends_the_original_prompt_shape`
  and `test_build_routing_prompt_without_skills_matches_the_original_prompt_shape`).
- `kernel/router.py::authorize_and_route` -- when Stage A escalates to
  Stage B, builds `build_default_skill_registry(registry)` (the same,
  already-built `registry` it already had) and passes it straight
  through. No new registry construction beyond what already existed.

## Why this is still safe -- unchanged, not merely asserted

- **Registry validation remains mandatory and unconditional**:
  `is_registered` (the real `CapabilityRegistry.__contains__`) still
  runs on whatever `capability_id` the model actually returns, whether
  or not it matches anything in the supplied skill context. Proven
  directly: `test_generate_route_still_rejects_unregistered_capability_with_skill_context`
  shows a model naming an unregistered capability is rejected exactly
  as before, even with matching skill context present.
- **No secret/credential exposure**: skill descriptors are static,
  built-in, in-source-tree metadata (WP-173) -- no live mailbox
  content, no calendar data, no credentials of any kind ever pass
  through this path, because none of that data is a skill's own field
  in the first place.
- **Strict structured output is unchanged**: the JSON schema the
  prompt asks for is untouched; `_parse_route`'s own validation is
  untouched.
- **The router is not redesigned**: `kernel/router.py`'s own execution
  boundary (`PLAN_STEP_EXECUTORS`, the three hand-wired
  `communications.*` branches, task creation) is completely
  unmodified. This work package only changes what text Stage B's
  prompt contains.
- **Purely advisory, never load-bearing**: a model that ignores the
  hint, or invents a capability id anyway, is caught by the exact same
  validation path that already existed -- this change can only make a
  correct answer more likely, never make an incorrect one succeed.

## Testing

`tests/unit/application/routing/test_router.py`: `_select_relevant_skills`
matches on domain/tag substrings, returns empty (no fallback) when
nothing matches, is deterministic regardless of input order, and
respects its limit; `_build_routing_prompt` is byte-shape-unchanged
with no skills, includes compact context with matching skills, and
never leaks a skill's own `instructions`; `generate_route` end-to-end
tests prove the real prompt text does/doesn't include skill context as
expected, and that unregistered-capability rejection is unaffected.
`tests/unit/test_router_kernel.py::test_stage_b_prompt_genuinely_includes_relevant_built_in_skill_context`
proves the real wiring end to end through `authorize_and_route` itself,
not just the isolated `generate_route` unit tests.
