# Command discovery integration with skills (WP-174)

## Status

Real, implemented. No ADR -- pure, additive CLI discovery over
already-built, static metadata (WP-171/172/173); no new
`CapabilityId`/`Effect`/`Tier`, no authorization change.

## What was built

- `jarvis skills list` -- lists every registered skill's id, domain,
  and short description.
- `jarvis skills show <skill_id>` -- shows one skill's full detail:
  its grouped, real capability ids, each one's real, derived
  authorization `Tier` (`descriptor.required_tier`, read back from the
  unmodified `Effect`/`Tier` machinery, never re-derived or guessed),
  a plain-language gloss of what that tier means for the caller (e.g.
  "requires physical, in-person confirmation -- can never be satisfied
  remotely" for `MANUAL_ONLY`), and the skill's own optional
  instructions/tags.
- `jarvis do --help`'s epilog (WP-166) now closes with a pointer to
  `jarvis skills list`/`jarvis skills show <skill_id>` for a broader,
  structured answer to "what can jarvis do?" than an exact-phrasing
  example list can give.

Both `skills` subcommands mirror `jarvis doctor`'s own, already-
established, deliberate design choice exactly: **not a capability**.
Neither performs any action nor reads anything beyond already-public,
in-source-tree metadata, so neither has an `Effect`, produces an audit
record, or accepts `--chain-path`/confirmation flags -- proven
directly by a dedicated test mirroring `doctor`'s own identical test.

## How this satisfies the work package's own constraints

- **Deterministic commands remain deterministic**: `resolve_intent()`/
  `kernel.router`'s Stage A is completely untouched. `skills list`/
  `skills show` are new, separate, flat CLI subcommands, not new
  router grammar.
- **Reasoning cannot invent capabilities / cannot bypass registry
  validation / cannot bypass authorization**: unaffected, because
  nothing here touches the reasoning fallback at all. This work
  package's own bullets about the reasoning fallback describe
  properties the router (`application/routing/router.py`) already
  holds structurally (a model-named capability id is checked against
  a live `CapabilityRegistry.__contains__` before it can survive
  validation; the router never executes anything itself) -- giving the
  reasoning fallback compact skill-aware *context* is WP-175's own,
  separate, explicit scope, not built here.
- **Invalid/unwired operations are reported, never executed**:
  `skills show` on an unknown or malformed skill id prints a clean
  message and returns exit code 1 -- never a raw traceback, never a
  guess at what the caller meant.

## Testing

`tests/unit/test_cli_main.py`: `skills list` prints all six built-in
skill ids and returns 0; `skills`/`skills show` reject the common
flags and never touch the audit chain (mirroring `doctor`'s own
tests); `skills show filesystem` prints both `fs.read_file` [ALLOW]
and `fs.delete_file` [MANUAL_ONLY] with the correct authorization
gloss; an unknown skill id and a malformed (whitespace-containing) one
both report cleanly with exit code 1; `skills`/`skills show` alone (no
further argument) are rejected by argparse; `jarvis do --help` prints
the new pointer text.
