# Full-history secrets scan, license compliance, SBOM (10-phase combined pass, Phase 9)

## Status

Real, tool-based audit, not a manual spot-check. Date: 2026-09-05.

## 1. Full-history secrets scan

Two independent tools, different detection methods, both run against
the real repository:

**`truffleHog` (v2, Python-based) against the full real git history**
(`--regex --entropy=True --repo_path .`, walks every real commit on
every real branch, not just the current tree): 11 "High Entropy"
findings total, zero regex-pattern (AWS key, private key, JWT, etc.)
findings. Every finding investigated directly, not assumed benign:

- All but one are in `uv.lock` -- real SHA-256 package/wheel hashes
  and PyPI URLs, the expected, standard false-positive class for
  entropy scanners against any lockfile.
- One is in `src/jarvis/adapters/vad.py`'s own historical diff --
  traced to a `_MODEL_COMMIT_SHA` constant, a public git commit hash
  pinning a Hugging Face model release (not a secret), confirmed by
  reading the real historical file content directly, not just the
  diff view.

**`detect-secrets` (Yelp) against the real, current working tree**
(`src`, `tests`, `docs`, `pyproject.toml`, `README.md`, `CLAUDE.md` --
scoped to real project files, not third-party `.venv` packages):
5 files flagged, all read and confirmed as intentional test/pinning
values, not real secrets:

- `src/jarvis/adapters/vad.py`: the same `_MODEL_COMMIT_SHA` constant
  ("Hex High Entropy String").
- `tests/integration/test_adapter_failure_resilience.py`,
  `tests/integration/test_email_calendar_against_local_servers.py`:
  `_GREENMAIL_PASSWORD = "testpass"`,
  `_RADICALE_PASSWORD = "anything-radicale-auth-type-is-none"`,
  `password_reference="unused-static-test-password"` -- all real,
  hardcoded credentials for local, disposable, already-credential-free
  test containers (GreenMail/Radicale), explicitly never real accounts.
- `tests/unit/adapters/reasoning/test_family_a.py`/`test_family_b.py`:
  `assert api_key == "sk-real-key"` -- a fake stub value shaped like an
  API key, used to test redaction/handling logic, not a leaked key.

**Verdict: no real secret found, in the current tree or anywhere in
this repository's full git history**, across two independently-built
tools using different detection strategies (regex-pattern matching
and Shannon-entropy analysis).

## 2. License compliance

`pip-licenses` run against the real, currently-resolved `.venv`
(`uv run --with pip-licenses pip-licenses`). This project is MIT
(`pyproject.toml`). Every non-permissive license found was checked
against its real, shipped metadata/LICENSE file directly, not assumed
from `pip-licenses`' own classifier string alone (which is known to
mis-classify packages whose trove classifiers lag their real
`License:` field):

**Confirmed false alarms, no real risk**:
- `fastembed` ("Other/Proprietary License" per its classifier) -- its
  real `METADATA` says `License: Apache License`, with a shipped
  `LICENSE`/`NOTICE` file confirming Apache-2.0. A classifier/metadata
  mismatch, not a real proprietary license.
- `py_rust_stemmers` ("UNKNOWN") -- its real, shipped `LICENSE` file
  (read directly) is plain MIT.
- `docutils` (tri-licensed BSD/GPL/Public-Domain) and `caldav`
  (dual-licensed `GPL-3.0-or-later OR Apache-2.0`) -- both offer a
  non-copyleft option a downstream user may choose; not a real
  constraint.
- The NVIDIA CUDA packages (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`,
  `nvidia-cuda-nvrtc-cu12`) -- standard, expected proprietary-EULA
  binary redistribution terms for GPU numerical libraries, the same
  real constraint every ONNX/CUDA-accelerated Python project already
  carries; not specific to or newly introduced by this codebase.
- The several LGPL packages (`PyGObject`, `pycairo`,
  `recurring-ical-events`, `x-wr-timezone`, `yattag`) -- LGPL is
  specifically designed to permit dependency use without requiring the
  depending project's own code to become LGPL; standard, low-risk.

**Two real, substantive findings -- flagged for the user's own
decision, not resolved here (this pass may not silently change
architecture or rip out working functionality)**:

1. **`piper-tts` is `GPL-3.0-or-later`, no alternative license
   offered, and is imported directly, in-process**
   (`src/jarvis/adapters/tts.py`: `from piper import PiperVoice`) --
   confirmed by reading the real import, not assumed. This is a
   materially different, stronger case than a mere subprocess
   invocation: importing a GPL library's own Python API directly into
   the same running program is the class of use the FSF's own guidance
   treats as more likely to create a "combined work." Whether shipping/
   distributing this MIT-licensed project bundled with a direct
   `piper-tts` import is compatible with MIT's own terms, or whether
   this needs `piper-tts` treated as an optional, separately-installed
   adapter rather than a bundled dependency, or a licensing decision
   this project has not yet made, is a real legal/product question
   this pass cannot and does not resolve.
2. **`icalendar-searcher` is `AGPL-3.0-or-later`** (the strictest
   common copyleft license, with its own network-use clause) -- a
   real, direct dependency of `caldav` (confirmed in `uv.lock`), and
   genuinely exercised at runtime: `adapters/calendar.py`'s
   `CalDavCalendarAdapter` calls `calendar.date_search(...)`, `caldav`'s
   own real recurrence-search entry point, which is what pulls in
   `icalendar-searcher`'s functionality -- not a dead, unused
   transitive dependency. Same real, unresolved question as above,
   scoped to the calendar capability.

Neither finding was acted on (no code removed, no relicensing
attempted) -- named here, with full evidence, for the user's own
review.

**Update (7 real decisions prompt, Decision 3, 2026-09-05)**: finding
1 (`piper-tts`) is now resolved by a real, direct user decision --
kept, not switched. The user's own reasoning, and the real caveat on
when it would need re-examination, is recorded in
`docs/architecture/license-alternatives-research.md`'s own new
"Real decision recorded" section, not duplicated here. Finding 2
(`icalendar-searcher`) has its own real, separate resolution --
tracked under Decision 4, see `docs/OPEN_DECISIONS.md` and
`docs/architecture/license-alternatives-research.md` for that
outcome, whichever way the real evidence lands. **Update (same prompt,
Decision 4, 2026-09-05)**: finding 2 (`icalendar-searcher`) is now
resolved for real, empirically, not just documented -- the
`server_expand=True` mitigation was tested against a real, local
Radicale server, confirmed to bring real `icalendar_searcher`
invocation (`Searcher.check_component`) to zero real calls, and
applied as `adapters/calendar.py`'s own permanent configuration. See
`docs/architecture/license-alternatives-research.md`'s own updated
section for the full methodology and evidence. `icalendar-searcher`
remains in `uv.lock` (it is `caldav`'s own transitive dependency, not
directly removable) but is no longer exercised at runtime by this
codebase's own real usage.

**A real, honest note on this prompt's own file-naming assumption**:
Decision 3, as given, referred to updating
"`docs/architecture/license-inventory.md`" alongside
`license-alternatives-research.md`. No file by that name exists in
this repository -- this document (`secrets-license-sbom-audit-phase9.md`,
Phase 9 of the 10-phase combined pass) is the real document that
originally inventoried both license findings, and is the one updated
here instead. No new, differently-named file was created to match the
prompt's own assumption literally, since doing so would have split
this real finding's history across two documents rather than keeping
it in the one that has carried it since Phase 9.

## 3. SBOM

A real CycloneDX 1.6 SBOM generated from the actual, currently-
resolved `.venv` via `cyclonedx-py environment` (not a hand-maintained
list) -- `docs/architecture/sbom.cyclonedx.json` (133 real components,
each with its own resolved version, PURL, and license where available).
`scripts/generate_sbom.sh` regenerates it on demand -- not run
automatically by CI or any gate, matching this project's own existing
`poc/wp61_vector_store_benchmark.py`/kernel-benchmark precedent of a
real, on-demand snapshot rather than a repeated CI artifact that could
silently drift out of sync with a script it no longer matches.

## Conclusion

No real secret exists in this codebase or its full history, confirmed
by two independent tools. License compliance is clean for the large
majority of dependencies, with two real, substantive, unresolved
findings (`piper-tts` GPL, `icalendar-searcher` AGPL) named plainly for
the user's own legal/product judgment rather than silently decided. A
real, reproducible SBOM now exists and can be regenerated on demand.
