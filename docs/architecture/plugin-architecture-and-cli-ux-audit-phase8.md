# Plugin architecture proof + CLI UX consistency audit (10-phase combined pass, Phase 8)

## Status

Real, evidence-based work: one real proof built and tested, one real
audit with one safe fix applied and the rest documented for the
user's own decision. Date: 2026-09-05.

## Part 1: plugin architecture proof

### The real gap found

`jarvis.plugin_api` was, before this pass, a docstring with no real
content -- confirmed by reading the file in full. `docs/plugin-guide/README.md`
already honestly says so ("`jarvis.plugin_api` has no real content yet,
and dynamic plugin loading from disk doesn't exist"), but nothing had
ever tried to build something against it to see whether the claim "new
features are plugins" (CLAUDE.md's own Core Principle) is checkable at
all in its current, real, source-tree-only form.

### What was built

1. **`jarvis.plugin_api` now has real content**: a deliberately narrow
   re-export of `jarvis.domain`'s own capability-authoring vocabulary
   (`CapabilityDescriptor`, `CapabilityId`, `Effect`, `Tier`,
   `CapabilityRegistry`, `Tainted`, `Provenance`, `Classification`,
   `Trust`, `Decision`, `PolicyContext`, `evaluate`, and their
   associated errors) -- everything `docs/plugin-guide/README.md`'s own
   documented steps 1 and 4 require, nothing reasoning-layer-specific
   (`Attempt`/`Candidate`/`Verdict`, audio/transcript/wake-word types
   are left out as not a capability-authoring concern). Still passes
   the C7 import-linter contract (re-exporting only from `domain`).
2. **`docs/plugin-guide/example_plugin.py`**: a real, minimal,
   self-contained example -- `example.word_count`
   (`Effect.READ_LOCAL`/`Tier.ALLOW`), built importing *only* from
   `jarvis.plugin_api` and stdlib.
3. **`tests/meta/test_plugin_api_example.py`**: mechanical proof, not
   a read-and-trust claim --
   - AST-scans the example file's real imports, asserting every one
     resolves to `jarvis.plugin_api` or stdlib -- with its own
     self-test proving the check would actually catch a real
     violation (mirroring `test_speaker_id_isolation.py`'s own
     "prove the predicate fires" discipline).
   - Builds a real, fresh `CapabilityRegistry` + `AuditChain` +
     `AuthorizationOrchestrator`, registers the example's descriptor,
     and authorizes it under every real confirmation-state
     combination, proving `Tier.ALLOW` behaves correctly end to end
     for a plugin-authored descriptor, not just that it compiles.
   - Calls the example's own real handler (`count_words`), proving it
     does something real.

### What this does NOT solve, stated plainly

Wiring a new capability into the real, running
`build_default_registry()` still means editing a file inside this
source tree -- there is still no dynamic, out-of-tree plugin loading.
This phase proves the *description* half of the plugin story is real
and sufficient; the *loading* half remains exactly the honest,
long-standing limitation `docs/plugin-guide/README.md` already named,
not silently solved here.

## Part 2: CLI UX consistency audit

Read `src/jarvis/cli/main.py` (1,143 lines, 32 subcommand parsers) in
full and checked several dimensions directly, not from memory:

**Structurally guaranteed consistent (checked, not assumed)**:
confirmation-flag naming (`--physical-confirmation-available`/
`--remote-confirmation-available`) is added by exactly one shared
function, `_add_common_flags()`, called by all 30 real leaf
subcommands (confirmed by counting: 32 parsers minus the 2 structural
exceptions -- `memory`, a group container with no flags of its own,
and `listen`, which authorizes nothing itself and has its own,
deliberately different `--chain-path`/`--verbose` flags -- leaves
exactly 30, matching 30 real `_add_common_flags()` call sites). Output/
error formatting is a single choke point (`main()`'s own
`decision.granted`-driven GRANTED/DENIED line and `Error: ...` prefix,
via `_dispatch_command`/`_print_outcome`) -- every command that reaches
it gets the identical shape, by construction, not by convention.

**One real, concrete bug found and fixed**: three help strings leaked
internal architecture-decision-record numbers into user-facing
`--help` text -- `memory backup`'s own help said "...to a chosen path
(ADR-0061)."; `send-email --password-reference`/
`create-calendar-event --password-reference` both said "...provisioned
out of band (ADR-0017/ADR-0042), not by this command." A real user
running `--help` has no ADR documents installed and gains nothing from
a reference like this; it is documentation-culture language that
leaked into user-facing text. Fixed by removing the parenthetical
reference from all three, keeping the substantive meaning intact.
Confirmed no test asserts the exact removed text (`grep`-checked
directly) before changing it.

**Two real, structural inconsistencies found, deliberately NOT fixed
here (both would be user-facing, potentially script-breaking
renames)**:

1. **Nested vs. flat subcommand shape**: `memory` is the only
   capability family using a nested subcommand group
   (`jarvis memory write`/`retrieve`/`forget`/`pin`/`backup`/
   `restore`) -- every other family (git, docker, desktop, files) uses
   flat, hyphenated top-level commands (`jarvis git-commit`,
   `jarvis list-docker-containers`, `jarvis move-file`). This is
   historical accretion (memory's nested group predates the later
   flat-command convention established for M3's desktop-control CLI
   wiring), not a deliberate design choice recorded anywhere. Renaming
   either direction would break existing muscle memory/scripts, so
   left as a real, open, named inconsistency for the user's own
   decision rather than silently restructured.
2. **Same-family naming inconsistency**: within `fs.*`, `fs.read_file`'s
   own CLI command is bare `read` (no "file" in the name, an M0-era
   command predating the later `list-dir`/`move-file`/`delete-file`
   naming, all of which include their noun). A user who learns
   `move-file`/`delete-file` would reasonably expect `read-file`, not
   `read`. Same reasoning as above: a rename is a real, user-facing
   breaking change, not made here, only documented.

**One minor, lower-priority stylistic observation, not fixed**: many
newer help strings (M5/M6a/Phase-5 additions) use "real" as a
qualifier ("The real subject line.", "The real target repository.",
"A real, previously-created backup file.") -- a stylistic habit from
this project's own internal documentation culture (emphasizing
"not a stub" to a reviewer) that reads oddly to an end user, who has
no reason to expect a *fake* subject line. Older (M0-M4) commands don't
use this qualifier ("The file to read.", "The text to memorize.").
Not fixed: purely cosmetic, touches dozens of strings for marginal
readability benefit, and does not risk confusion the way the ADR-number
leak did -- named here rather than either silently rewritten at scale
or ignored.

## Real decision recorded (7 real decisions prompt, Decision 5, 2026-09-05)

The user reviewed both real, structural naming inconsistencies above
and chose: **leave both as-is.** Neither `memory`'s nested-subcommand
shape nor `fs.read_file`'s bare `read` command is worth a real,
user-facing, potentially script-breaking rename this deep into the
project's own life. No code changed as a result of this decision --
both items are now closed as "investigated, decided, kept," not left
open pending further input.

## Conclusion

The plugin architecture's "description" half is now real and
mechanically proven, not merely documented as an aspiration; its
"loading" half remains an honest, named limitation, unchanged. The CLI
has one real bug (ADR-number leakage into user help text), now fixed,
and two real, structural naming inconsistencies -- both surfaced for
the user's own decision, and both now resolved: kept as-is, not
renamed (see "Real decision recorded" above).
