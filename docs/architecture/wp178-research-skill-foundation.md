# Research skill foundation (WP-178)

## Status

Real, implemented (one new, cross-cutting `SkillDescriptor`, purely
declarative). No ADR -- no new `CapabilityId`/`Effect`/`Tier`, no new
execution mechanism, no authorization change.

## What this is, and is not

A `Skill` (WP-171) is discoverability metadata over already-existing,
individually-authorized capabilities -- never a second execution
system. "Research Skill" here means exactly that: a new
`SkillDescriptor`, `research` (`kernel/skills.py::RESEARCH_SKILL_ID`),
grouping eleven already-registered capabilities that, together,
already support a real research workflow, plus a description of that
workflow as free-text `instructions` -- not a new autonomous agent, not
a new orchestration engine, not a bypass of anything.

## The six-step workflow, and what already implements each step

1. **Understand the request** -- no capability needed; this is the
   caller's (human or reasoning fallback's) own job, unchanged.
2. **Identify relevant sources** -- `fs.find`/`fs.search_content`/
   `fs.recent` (an already-known local scope) or `browser.open_page`
   (an already-known URL). **This is where the one real, honest gap
   lives** -- see below.
3. **Gather information** -- `fs.read_file` for local content;
   `browser.inspect_dom`/`browser.screenshot` for an already-open
   page's content. Each is already its own, separately-authorized
   capability call -- gathering from three sources means three
   separate authorizations, never one batch grant.
4. **Synthesize** -- real reasoning over gathered content, via
   `planning.run_plan` (already its own outer-gated, per-step-
   authorized capability, ADR-0062) for a structured, multi-step goal.
   `coding.run_task`/`job_assistance.draft` are equally real synthesis
   paths but are not part of this skill's own `capability_ids`, since
   both are already their own, separately-discoverable skills/
   capabilities -- grouping them here too would blur what "Research"
   actually names, not clarify it.
5. **Return structured findings** -- the caller's own responsibility.
   This skill invents no new output format, no new `PageHandle`-like
   type, nothing to maintain.
6. **Preserve provenance where supported** -- already structural, not
   something this skill adds: content read via `browser.inspect_dom`/
   `browser.screenshot` is real page content that, per this project's
   own established convention (`docs/architecture/prompt-injection-resilience-phase7.md`),
   would be tagged `Trust.UNTRUSTED_EXTERNAL` the moment it enters a
   reasoning call; `memory.retrieve`/`memory.get` (both listed) recall
   whatever provenance a prior `memory.write` already recorded, unchanged.
   Persisting a synthesized finding uses `jarvis memory write`/
   `remember <text>` directly -- `memory.write` is a dynamic-effect
   capability (ADR-0049) and is deliberately not in `capability_ids`,
   the same reasoning the Memory skill's own instructions already give.

## The one real gap, investigated and documented, not built around

**No generic, non-job-specific "search the web for X" capability
exists anywhere in this codebase.** Checked directly:
`browser.open_page` requires an already-known, literal URL -- it has
no query parameter and builds no search URL of its own.
`job_search.open_results`/`job_search.find_careers_page`
(`kernel/job_search.py`) *do* build a real search-engine query URL,
but both are narrowly, deliberately scoped to job search specifically
(LinkedIn/Indeed result pages, or a DuckDuckGo "<company> careers"
query) -- structurally enforced to never read page content at all
(`tests/meta/test_job_search_no_content_reading.py`), the opposite of
what a general research "gather and read" step needs. Neither is
listed in this skill's `capability_ids`: including them would either
misrepresent what they do (they don't return content) or, if their own
no-scraping constraint were loosened here, would violate the "no
uncontrolled web browsing" instruction this work package operates
under.

**Deliberately not closed by building a new capability in this work
package.** A generic web-search capability is a real, plausible future
capability (open a search-engine results page for an arbitrary query,
mirroring `job_search.find_careers_page`'s own already-proven,
ToS-checked DuckDuckGo pattern, `Effect.EXECUTE`/`Tier.CONFIRM`) --
but building one was not asked for here, and this work package's own
instruction is explicit: "if existing web/search capabilities are
insufficient, document the missing capability instead of inventing
unsafe execution." Today's real, practical consequence: a research
request naming a source by name rather than URL (e.g. "look into what
X company does") has no capability to discover that URL on its own --
a caller must already know or be given the URL, or fall back to the
job-search-specific tools where that fits.

## What was deliberately not built

- No autonomous, unrestricted research agent -- every capability this
  skill names is still individually authorized through the same,
  unmodified `AuthorizationOrchestrator`/`AuditChain` choke point.
- No new web browsing mechanism -- `browser.*` is reused completely
  unmodified; no new port, no new scraping capability, no loosening of
  `job_search.*`'s own no-content-reading structural guarantee.
- No new `CapabilityId`/`Effect`/`Tier`.
- No generic web-search capability (see above) -- documented as a real
  gap, not built.

## Testing

`tests/unit/test_skills.py`: the skill registry now registers exactly
7 skills (up from 6); a dedicated test confirms the Research skill's
`capability_ids` is exactly the eleven real capabilities named above,
spanning filesystem/browser/memory/planning, and that it carries real
`instructions`. `build_default_skill_registry()` continuing to
validate cleanly (all capability ids real and registered) is itself
proof this skill names nothing invented.
