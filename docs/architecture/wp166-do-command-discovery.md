# jarvis command discovery: jarvis do --help examples (WP-166, 2026-09-12)

## Status

Real, implemented. No ADR, no new router, no LLM involved — pure CLI
help-text addition.

## What was investigated

Whether a user could discover what `jarvis do "<text>"` actually
recognizes without reading source code or `docs/protocol/README.md`.
**Confirmed live, not assumed**: `jarvis do --help` showed only the
generic argparse usage/flags, zero indication of any recognized
command shape. A genuinely unrecognized request already reports back
a clear `route: unknown`/`detail: ...` line (checked, not a gap) — the
real, concrete gap was purely at the `--help` level, before a user
ever types a request.

## What was built

`jarvis do --help` now includes a real epilog listing nine concrete,
already-working example requests (`"recall ..."`, `"remember ..."`,
`"read ..."`, `"find files ..."`, `"search files ..."`, `"recent
files"`, `"task status <id>"`, `"list tasks"`, `"list scheduled
tasks"`), each live-verified to actually route and execute as shown,
plus one sentence explaining the fallback-then-report-back behavior
for anything else. Points at `docs/protocol/README.md` for the full,
current list rather than duplicating it (avoiding a second place that
can drift).

## What was deliberately not built

- No second router, no new grammar, no behavior change to
  `resolve_intent()`/`authorize_and_route` — pure, additive help text.
- No LLM-backed "explain this command" feature.
- No change to how an ambiguous/unrecognized request is handled — it
  still only ever reports back, never executes speculatively.

## Testing

One new test confirms the real epilog text appears in `jarvis do
--help`'s own output and contains no internal ADR/WP reference,
alongside the existing mechanical leak-detection meta-test (already
passing, unmodified).
