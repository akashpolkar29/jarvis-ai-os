# License-safe alternatives research (3 combined tasks, Task 3)

## Status

Real research only. **No dependency was switched, no code was
changed.** This document lays out real, verified options for the
user's own eventual decision -- it is an addendum to
`docs/architecture/secrets-license-sbom-audit-phase9.md` (the 10-phase
combined pass's own Phase 9), which first found these two real
license-compatibility concerns. Date: 2026-09-05.

## 1. `piper-tts` (GPL-3.0-or-later)

### Confirmed real usage pattern

`src/jarvis/adapters/tts.py` does `from piper import PiperVoice`
(a direct, lazy but real, in-process Python import) and calls
`PiperVoice.synthesize()` directly on it -- confirmed by reading the
adapter's own source. This is not a subprocess boundary; `piper-tts`'s
own code runs inside the same Python process, same address space, as
the rest of JARVIS.

### Real legal exposure this specific pattern creates

Quoting GPL-3.0's own real, verbatim text (`piper-tts`'s own installed
`COPYING` file, confirmed by reading it directly):

> A compilation of a covered work with other separate and independent
> works, which are not by their nature extensions of the covered work,
> and which are not combined with it such as to form a larger program,
> in or on a volume of a storage or distribution medium, is called an
> "aggregate" if the compilation and its resulting copyright are not
> used to limit the access or legal rights of the compilation's users
> beyond what the individual works permit. Inclusion of a covered work
> in an aggregate does not cause this License to apply to the other
> parts of the aggregate.

This "aggregate" exception is narrow: it explicitly concerns
"separate and independent works... not combined... such as to form a
larger program" -- text most naturally read as describing works
merely bundled on the same medium (e.g. two unrelated programs shipped
on the same disk), not two programs sharing one process and calling
each other's functions directly at runtime.

The GPL's own text does not itself define exactly where "mere
aggregation" ends and "forming a larger program" begins for the
specific case of same-process library linking -- that line has never
been definitively settled in court, and the FSF's own long-standing,
widely-cited (though not legally binding) position is that dynamically
or statically linking two programs into the same process, such that
they share data structures and call each other's functions directly,
is far more likely to be judged "combining to form a larger program"
than two processes merely communicating over a pipe or socket. Under
that reasoning -- stated here as the real, standard interpretation
this concern rests on, not as a definitive legal conclusion this
document is qualified to give -- `PiperVoice` being imported and
called directly, in-process, is a real, meaningful case for treating
JARVIS's own combination with `piper-tts` as a "covered work" for
GPL purposes if JARVIS is ever conveyed (distributed) to others in
that combined form. That would mean the combination's own source must
be made available under GPL-compatible terms -- a real conflict with
distributing the rest of JARVIS's own code under a bare MIT license
with no such condition attached.

**What this does not mean**: running JARVIS privately, never conveying
it to anyone else, carries no GPL obligation at all (GPL's own
Section 2's "you may make, run and propagate covered works that you do
not convey, without conditions" already covers this). The real
exposure is specifically about ever distributing/conveying JARVIS
bundled with `piper-tts` to someone else.

### Real, verified, actively-maintained alternatives

**`kokoro-onnx`** (PyPI, latest `0.6.1`) -- verified directly, not
assumed:
- Real, MIT-licensed code, confirmed by fetching its own GitHub
  repository's real `LICENSE` file directly
  ([thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)).
- Wraps the real Kokoro-82M neural TTS model via ONNX Runtime --
  matches this project's own already-established "ONNX over
  torch/CUDA" pattern (the same reasoning `adapters/embedding.py`'s
  own docstring already gives for choosing `fastembed` over a
  torch-based embedding model).
- The underlying model weights (`hexgrad/Kokoro-82M` on Hugging Face)
  are themselves released under Apache-2.0 -- both the code and the
  model are permissively licensed, unlike some neural TTS projects
  where the code is permissive but the weights are not.
- Real dependencies (`onnxruntime`, `numpy`, `phonemizer`,
  `espeakng-loader`) -- no `torch` requirement for inference.
- A close sibling package, **`pykokoro`** (Apache-2.0, confirmed
  directly from its own PyPI-hosted license text), wraps the same
  model with a different API surface -- a second, real option if
  `kokoro-onnx`'s specific interface doesn't fit.

**Silero TTS** (`silero`/`silero-tts` on PyPI) -- investigated and
found to carry its own real complication, not a clean alternative:
its own model weights are released under a **non-commercial**
CC-BY-NC license, with only the base `cis-tts` models under MIT (a
real, verified licensing split between code and weights, the opposite
problem from `kokoro-onnx`'s clean situation). It also requires
`torch>=1.12.0` at the code level -- reintroducing exactly the
torch/CUDA dependency risk this project's own M4 embedding-model
decision already chose to avoid. Named here as investigated and
rejected, not silently omitted, given this project already trusts
Silero's own VAD model (`SileroVadAdapter`) -- the trust in the vendor
doesn't carry over to this specific model's own separate, more
restrictive licensing terms.

**Feature-parity note, stated honestly**: neither `kokoro-onnx` nor
`piper-tts` has been evaluated here for real audio-quality parity or
for whether `adapters/tts.py`'s own real `LD_LIBRARY_PATH`/CUDA
workaround logic would even be needed with an ONNX-CPU-only pipeline
(likely not, but not verified) -- a real switch would need its own
implementation pass and live listening comparison, out of this
research-only task's own scope.

## 2. `icalendar-searcher` (AGPL-3.0-or-later)

### Confirmed real usage pattern, more precisely than the prior audit stated

`adapters/calendar.py` calls `calendar.date_search(start, end)`
(both bounds always supplied by this codebase's real call sites).
Reading `caldav`'s own installed source directly
(`.venv/.../caldav/collection.py`) confirms `date_search`'s own
`expand` parameter defaults to `"maybe"`, which resolves to `True`
whenever both `start` and `end` are given -- exactly this codebase's
own real call shape. `date_search`'s own docstring states plainly:
"we're doing client side expansion instead" -- and `caldav/search.py`
(confirmed by `grep`) imports `icalendar_searcher.Searcher` and uses
it specifically for this client-side recurrence expansion. **This
means `icalendar-searcher`'s own AGPL-licensed code is genuinely,
actually executed by this codebase's real, current usage pattern on
every real calendar-listing call that includes a recurring event --
not a merely-theoretical, unexercised transitive dependency.**

### Real legal exposure

AGPL-3.0 is GPL-3.0 plus one added clause (Section 13, confirmed by
reading `icalendar-searcher`'s own installed `LICENSE.md` directly),
quoted verbatim:

> Notwithstanding any other provision of this License, if you modify
> the Program, your modified version must prominently offer all users
> interacting with it remotely through a computer network (if your
> version supports such interaction) an opportunity to receive the
> Corresponding Source of your version...

This specific network-interaction clause is triggered by *modifying*
`icalendar-searcher` itself and then exposing that modified version to
remote users over a network -- JARVIS does neither (it uses
`icalendar-searcher` unmodified, and it is a local, single-user
personal agent, not a multi-user network service). **The narrower,
Section-13-specific AGPL trigger does not appear to apply to this
project's own real usage.** The base GPL-3.0 same-process-linking
concern described above for `piper-tts`, however, applies identically
here in principle -- except one real step removed: JARVIS's own code
never imports `icalendar-searcher` directly; `caldav`'s own internals
do, on JARVIS's behalf, as an implementation detail of a method
JARVIS calls. Whether that one-level-of-indirection changes the real
"combined work" analysis is a genuinely harder question than the
direct-import case, and not one this document is qualified to resolve
either way.

### A real, no-new-dependency mitigation option, found during this research

`caldav`'s own newer `search()` method exposes a real
`server_expand: bool = False` parameter -- setting it `True` asks the
*CalDAV server itself* to perform recurrence expansion via the real
RFC4791 protocol mechanism, rather than `caldav` doing it client-side
through `icalendar-searcher`. If the real, deployed CalDAV server
supports this (the library's own docstring warns real server support
is inconsistent -- "servers often behave differently"), switching from
the deprecated `date_search()` to `search(..., server_expand=True)`
would avoid invoking `icalendar-searcher`'s code at all, with **no
dependency change** -- only a different call into the exact same,
already-present `caldav` library. This is a real, viable option to
investigate further, not applied here (this task is research only,
and confirming real server-side expand support against this project's
own real, deployed CalDAV server has not been done).

### Real, verified alternative libraries

**No actively-maintained, full replacement for `caldav` itself was
found.** It is the dominant, most feature-complete Python CalDAV
client library; `vdirsyncer` (a real, actively-maintained project)
is a synchronization *tool*, not an importable client library, and
solves a different problem (mirroring a calendar to local files, not
programmatic query/create).

**`recurring-ical-events`** (PyPI, real, LGPL-3.0-or-later, confirmed
directly) is already a real, existing dependency of this project
(found in the prior license audit) and performs the same real
category of work (RFC5545 recurrence expansion) as
`icalendar-searcher` -- but under LGPL, a **weak** copyleft that
explicitly permits linking from differently-licensed code without
extending copyleft to the whole combined program, a meaningfully
different, more permissive legal position than AGPL's. It is not a
drop-in replacement for `icalendar-searcher` inside `caldav`'s own
internals (that would require patching or forking `caldav` itself to
use it instead), but it is real, existing, real evidence that a
license-compatible recurrence-expansion library already exists and is
already trusted by this project for other purposes.

**`icalendar`** (PyPI, BSD-licensed, confirmed directly, already a
`caldav` dependency) provides raw RFC5545 parsing with no
recurrence-expansion logic of its own -- the permissively-licensed
foundation a from-scratch, in-house expansion implementation could be
built on, if that were ever the chosen path (a real, larger
engineering undertaking, not evaluated further here).

## Summary table

| Dependency | Real license | Real usage | Verified alternative(s) | Real cost of switching |
| --- | --- | --- | --- | --- |
| `piper-tts` | GPL-3.0-or-later | Direct, in-process import | `kokoro-onnx` (MIT code + Apache-2.0 weights, ONNX-only, real & verified) | Re-implement `adapters/tts.py` against a different API; unverified audio-quality parity |
| `icalendar-searcher` | AGPL-3.0-or-later | Via `caldav`'s own internals, genuinely exercised on every recurring-event query | No full `caldav` replacement found; `server_expand=True` may avoid triggering it at all, with zero dependency change (real server-support unverified) | Either verify server-side expand support, or fork/patch `caldav`'s own internals -- both real, non-trivial paths |

## Real decision recorded: `piper-tts` stays (7 real decisions prompt, Decision 3, 2026-09-05)

The user made a real, direct decision to keep `piper-tts`, on this
reasoning, stated here as the user's own judgment call -- **not a
legal conclusion this project asserts with certainty**: GPL's own
copyleft obligations (the "combined work"/"conveying" analysis in
Section 1 above) are triggered by *distributing* the combined software
to others, and this project, as currently used, is run personally and
privately by its own author/user -- not packaged or distributed as a
binary or installer to third parties. GPL's own Section 2 ("you may
make, run and propagate covered works that you do not convey, without
conditions") already covers exactly this use pattern, as Section 1
above already noted.

**This reasoning is scoped to the current, real distribution model,
not a permanent closure of the question.** It would need genuine
re-examination if that model ever changes -- for example, if this
project is ever packaged as a built binary/installer, published to a
package registry, or otherwise distributed to someone other than its
own current user/author. No such change is planned as of this
decision; if one is ever planned, this document's own Section 1
reasoning (and `kokoro-onnx` as a real, already-verified alternative)
remains available to revisit at that time, not re-researched from
scratch.

No dependency was switched. No code changed as a result of this
decision.

## `icalendar-searcher` (AGPL): real, empirical resolution (7 real decisions prompt, Decision 4, 2026-09-05)

**The `server_expand=True` mitigation was tested empirically against
the real, local Radicale test server, and confirmed real -- it has
now been applied as the permanent configuration.**

### Methodology, more precise than a single yes/no answer

A real, live-instrumented `unittest.mock.patch.object` wrapping
`icalendar_searcher.Searcher.check_component` (the actual method that
performs substantive recurrence-filtering/expansion logic --
confirmed by reading `caldav/search.py`'s own `_filter_search_results`
directly, not assumed) counted real invocations while a real
`CalDavCalendarAdapter.list_events()` call ran against a real,
5-occurrence weekly recurring event seeded directly on the real,
local Radicale server. A positive control (the same real server, same
real event, `calendar.search(..., expand=True)` -- functionally
equivalent to the deprecated `date_search()`'s own default behavior)
confirmed the instrumentation itself would have caught a real
invocation, ruling out "it just happened not to fire" as an
explanation for a negative result.

**Real result**: with `server_expand=True` and `expand` left at its
own real default (`False`), `check_component` was called **zero
times** -- proven, not assumed. The positive control confirmed at
least one real call under the old shape. A deeper check (a real,
diffed `coverage.py` trace of the entire `icalendar_searcher` package,
comparing "import + object construction only" against "a full search
call") found that `server_expand=True` alone executes exactly two
lines of `icalendar_searcher` code beyond ordinary class/module
definition -- both inside `Searcher.sort()`'s own generic, non-
calendar-specific `else: return components.copy()` fallback branch
(no sort keys were configured) -- not any real filtering, expansion,
or date-comparison logic.

**A real, precise, non-obvious finding, not in `caldav`'s own
migration docstring**: `date_search()`'s own deprecation notice
suggests migrating to `calendar.search(start=start, end=end,
event=True, expand=True)` -- this combination alone, even with
`server_expand=True` added, was empirically measured to still invoke
`check_component` once. The combination that actually avoids it
requires `expand` to be left at its own real default (`False`); adding
`expand=True` back in (matching the literal docstring example) partly
defeats the mitigation. This distinction would not have been caught
by reading documentation alone -- it required the real, empirical test
this decision asked for.

**Applied**: `src/jarvis/adapters/calendar.py`'s `_list_events_sync`
now calls `calendar.search(start=..., end=..., event=True,
server_expand=True)` instead of the deprecated `calendar.date_search(start,
end)`. A real regression test
(`tests/integration/test_icalendar_searcher_server_expand.py`, gated
behind the same real, local Radicale reachability skip this project's
other CalDAV integration tests already use) proves both the negative
result (zero `check_component` calls under the new, real call shape)
and the positive control (at least one call under the old shape),
against a real server, every time it runs. Unit tests
(`tests/unit/adapters/test_calendar.py`) updated to match the new
`search()`-based Protocol; a dedicated new test guards against a
future edit silently dropping `server_expand=True` or reintroducing
`expand=True`.

**This resolves finding 2 from `docs/architecture/secrets-license-sbom-audit-phase9.md`**:
`icalendar-searcher`'s own AGPL-licensed substantive logic is no
longer genuinely, actually invoked by this codebase's real, current
calendar-listing call path -- a real, empirically-verified change, not
a documentation-only decision like `piper-tts`'s own Decision 3. The
dependency itself remains in `uv.lock` (removing it outright would
require `caldav`'s own internals to drop the import, out of this
project's control) but is no longer exercised at runtime by this
codebase's own real usage.

## Conclusion

`piper-tts`'s real license question is now resolved by a real, direct
user decision (above): kept, on a real, stated distribution-model
reasoning, not a switch to `kokoro-onnx`. `icalendar-searcher`'s own
real outcome is tracked separately under Decision 4. This document's
own original research (both dependencies' real usage patterns, the
quoted license text, and both verified alternative libraries) remains
accurate and is preserved unedited above as the real evidence base
either decision was made from.
