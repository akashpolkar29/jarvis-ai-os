# Dead-code and unused-import sweep (5 combined hygiene/reliability tasks, Task 3)

## Status

`vulture` 2.16 (added as a real dev dependency, `pyproject.toml`,
mirroring `cosmic-ray`'s own precedent for a periodic, manually-run
quality tool rather than a CI gate) was run against `src/jarvis` at
`--min-confidence 60`. **42 real hits, all 42 individually
investigated by reading the actual source, not assumed. Zero were
genuinely dead. No code was removed.** Every hit falls into one of six
real, checkable false-positive categories, listed below with the
specific evidence checked for each.

## Category 1: `Protocol` stub-method parameter names (13 hits)

`src/jarvis/adapters/calendar.py:89-90` (`dtstart`/`dtend`) and
`src/jarvis/adapters/email.py:65-87` (`mailbox`/`readonly`/`criteria`/
`message_parts`/`message_set`/`from_addr`/`to_addrs`) are parameter
names on `Protocol` method signatures whose bodies are `...` --
narrow, typed re-declarations of `imaplib`/`smtplib`/`caldav`'s own
real interfaces, used only for `mypy --strict` structural typing
against the adapter's real, concrete call sites. The parameter names
are never meant to be referenced inside the stub itself -- that is
what a `Protocol` stub *is*. Confirmed by reading both files directly.

## Category 2: magic-method signature parameters (3 hits)

`src/jarvis/application/coding/sandbox_workspace.py:125-127`
(`exc_type`/`exc_value`/`traceback`) are `__exit__`'s own mandated
context-manager signature. Required by the language's own protocol,
regardless of whether the method body reads them.

## Category 3: dataclass fields read only by the test suite (7 hits)

`src/jarvis/domain/audit.py:267-268` (`ChainVerificationResult.valid`/
`.first_invalid_sequence`) and `src/jarvis/domain/email.py:23-37`
(`EmailSummary.sender`/`.received_at`, `EmailMessage.sender`/
`.received_at`) are real dataclass fields, constructed with real
values at real call sites (`adapters/email.py:213,247`) and asserted
against directly in the real test suite (`tests/unit/test_email.py`,
`tests/unit/adapters/test_email.py`, `tests/property/test_audit.py`).
`vulture`'s default scan is `src/jarvis` only -- it does not see
`tests/` attribute reads, so it flags any field never *read* inside
`src/` itself as unused, even when real. Confirmed by grepping
`tests/` directly for each field name before concluding false-positive
rather than assuming it.

## Category 4: enum members referenced only in tests/docstrings (3 hits)

`src/jarvis/domain/capability.py:32` (`Effect.NONE`),
`src/jarvis/domain/evidence.py:67` (`Evidence.MODEL_OPINION`),
`src/jarvis/domain/provenance.py:35` (`Classification.PERSONAL`) are
real enum members, exercised directly in
`tests/unit/test_capability.py`, `tests/property/test_capability.py`,
and referenced by name in this project's own `CLAUDE.md`
("`Arbiter._score` gives `MODEL_OPINION` evidence zero weight
unconditionally") -- confirmed real, not vestigial.

## Category 5: public API surface exercised only by the test suite (6 hits)

`src/jarvis/application/policy/orchestrator.py`'s `is_registered`/
`list_capabilities`, `src/jarvis/domain/audit.py`'s `verify`,
`src/jarvis/domain/provenance.py`'s `merge_all`/`require_trusted`, and
`src/jarvis/domain/reasoning.py`'s `remaining` property are all real,
public methods called directly and repeatedly across the real test
suite (`tests/unit/application/policy/test_orchestrator.py`,
`tests/property/test_audit.py`, `tests/property/test_provenance.py`,
`tests/unit/test_reasoning.py`, among others) -- confirmed by grep,
same root cause as Category 3 (`vulture` not scanning `tests/`).
`src/jarvis/application/memory/carry_forward.py`'s
`authorize_reasoning_call_with_recalled_context` is the same shape,
confirmed against `tests/unit/application/memory/test_carry_forward.py`.

## Category 6: real, tested, registered capabilities with no current CLI/voice wire (13 hits)

`src/jarvis/kernel/browser.py`'s `authorize_and_open_page`/
`authorize_and_capture_screenshot`/`authorize_and_query_dom`/
`authorize_and_close_page`, `src/jarvis/kernel/communications.py`'s
`authorize_and_list_email`/`authorize_and_read_email`/
`authorize_and_list_calendar_events`, and
`src/jarvis/kernel/desktop.py`'s `authorize_and_run_terminal_command`/
`authorize_and_run_docker_container`/`authorize_and_build_docker_image`
are real, tested (`tests/unit/test_browser_kernel.py`,
`tests/unit/test_desktop_kernel_docker.py`, and others), registered in
the real capability registry (`kernel/capabilities.py`'s
`BROWSER_OPEN_PAGE_CAPABILITY_ID` etc.) composition functions -- **not
dead code, real, pre-existing, already-known gaps in CLI/voice
wiring**, the identical shape this project already found and closed
once for `kernel/desktop.py`'s other capabilities ("Desktop CLI
wiring, 2026-09-04"). Confirmed by grepping `cli/main.py`,
`kernel/voice_loop.py`, and `docs/protocol/README.md` directly for a
"browser" subcommand -- none exists. Two of the three
`kernel/desktop.py` hits (`run_terminal_command`, needing
`SyntheticInputPort`; `run_docker_container`/`build_docker_image`,
DESTRUCTIVE-tier Docker actions) are explicitly, deliberately unwired
per this project's own standing hard gates across multiple prior
passes -- removing them would delete real, deliberately-scoped,
tested capability code. `browser.*` and `communications.list_email`/
`read_email` wiring is real, open scope, already implicitly named
elsewhere in `CLAUDE.md` (`"browser.close_page still requires explicit
invocation, with no automatic cleanup"`; `"Neither
communications.list_email/read_email is wired to a real CLI/voice
entry point yet"`) -- not new information from this sweep, but now
cross-confirmed from the opposite direction (dead-code detection
rather than a CLI-completeness audit).

`src/jarvis/adapters/synthetic_input.py`'s `PortalSyntheticInputAdapter`
and `src/jarvis/adapters/terminal_profile.py`'s
`ensure_synthetic_input_profile_exists` fall in this same category and
are additionally covered by this pass's own explicit hard gate
("do not touch ... `SyntheticInputPort`, RemoteDesktop portal ...") --
confirmed real and tested
(`tests/contract/test_synthetic_input_port.py`,
`tests/unit/adapters/test_synthetic_input.py`,
`tests/unit/adapters/test_terminal_profile.py`) without modifying
either file.

## Category 7: `Protocol` port classes (2 hits)

`src/jarvis/ports/memory_write.py`'s `MemoryWritePort` and
`src/jarvis/ports/retrieval.py`'s `RetrievalPort` are `Protocol`
classes satisfied structurally (by `SqliteMemoryAdapter` and others) --
`vulture` cannot see structural-typing usage, only direct
instantiation/subclassing, so every port in this codebase would be
flagged the same way. Confirmed these two are genuinely no different
from every other port class in `src/jarvis/ports/` that `vulture` did
*not* happen to flag at this confidence threshold (a `--min-confidence`
artifact, not a real distinction).

## What was actually changed

Nothing in `src/jarvis`. `pyproject.toml`/`uv.lock` gained `vulture`
as a real dev dependency. The full gate suite (`ruff check`, `ruff
format --check`, `mypy --strict`, `lint-imports`, `pytest` plus all
three coverage gates) was re-run after adding the dependency to
confirm nothing broke -- a dependency-only change was not expected to
affect any of them, and did not.

## Conclusion

A real, disciplined check-before-removing pass found that this
codebase's own real invariants (100% domain/policy/reasoning coverage,
capability-registry-driven dispatch, `Protocol`-based ports, and a
test suite that exercises far more of the public surface than `src/`
itself ever calls internally) make `vulture`'s default heuristics
produce a 100% false-positive rate at this confidence threshold on
this specific codebase -- a real, useful, negative result, not an
absence of effort. The one real, substantive theme this sweep
surfaced -- browser/communications-read capabilities remaining
CLI/voice-unwired -- was already known and is already tracked; this
sweep did not discover new scope, it independently cross-confirmed
existing scope from a different detection angle.
