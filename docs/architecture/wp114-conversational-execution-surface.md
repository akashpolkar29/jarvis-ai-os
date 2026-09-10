# WP-114: expanding the conversational execution surface (2026-09-10)

## Status

Real, implemented. No new `CapabilityId`/`Effect`/`Tier`, no ADR, no
second router, no direct UI-to-capability execution path -- every
capability this work package exposes already existed, already
classified, already authorized; this work closes the gap between
"already implemented" and "reachable through a normal typed sentence."

Roadmap numbering checked directly first: the highest real `WP-\d+`
reference was 113 (WP-113, task failure-state hardening). WP-114 was
genuinely free -- the `WP-124` reference in `CLAUDE.md` remains a
proposed implementation-order range from an unbuilt UI-architecture
design artifact, not a real, built work package.

## Inspection findings (Step 1), stated precisely

Checked directly, not assumed, before writing any code:

| Capability | Registered, `Tier.ALLOW` | Real CLI command | Deterministic grammar (voice + typed) before this WP | Wired into `authorize_and_route`'s own execution boundary before this WP |
|---|---|---|---|---|
| `fs.find` | yes | `jarvis fs find` | yes (`kernel/intent.py`, "find files") | **no** |
| `fs.search_content` | yes | `jarvis fs search-content` | yes ("search files") | **no** |
| `fs.recent` | yes | `jarvis fs recent` | yes ("recent files") | **no** |
| `communications.list_email` | yes | `jarvis email list` | **no** | **no** |
| `communications.read_email` | yes | `jarvis email read` | **no** | **no** |
| `communications.list_calendar_events` | yes | `jarvis calendar list-events` | **no** | **no** |
| `communications.send_email` | dynamic-effect, not registered | `jarvis send-email` | yes ("send email") | no (never should be) |
| `communications.create_calendar_event` | dynamic-effect, not registered | `jarvis create-calendar-event` | yes ("create event") | no (never should be) |

The real gap, precisely: `fs.find`/`fs.search_content`/`fs.recent`
already had voice/typed grammar (`kernel/intent.py::resolve_intent()`)
but were never added to `kernel.capability_dispatch.PLAN_STEP_EXECUTORS`,
the router's own real execution boundary -- typing "find files *.py"
into `jarvis do`/`jarvis ui` already *recognized* the request but
never *ran* it (`decision=None`, `execution_result=None`, the same
"recognized, not wired" outcome `git.force_push` deliberately gets).
`communications.list_email`/`read_email`/`list_calendar_events` had
no grammar at all -- `kernel/intent.py`'s own docstring already named
why (they need a real, pre-configured `email_port`/`calendar_port`
with no safe default, and `resolve_intent()` is deliberately clockless
too, for calendar's "today"/"tomorrow" resolution). `send_email`/
`create_calendar_event` already have grammar and are correctly,
deliberately never wired for direct execution -- writes stay
`Tier.MANUAL_ONLY` (ADR-0059) and are never auto-executed by a typed
sentence; this work package does not change that in any way.

## The fix, in three parts

### 1. `fs.find`/`fs.search_content`/`fs.recent` -- add to `PLAN_STEP_EXECUTORS`

`kernel/capability_dispatch.py` gained three new adapter functions
(`_execute_find_files`/`_execute_search_content`/`_execute_recent_files`),
following the exact, established shape every existing entry already
uses -- unpack the plan step's generic `arguments` mapping, call the
already-existing `authorize_and_*` function unmodified, wrap its
result in `PlanStepOutcome`. All three have a real, safe default
(`allowed_root=Path.home()`), so no port/config was needed. This also
means `planning.run_plan` (which imports `PLAN_STEP_EXECUTORS`
directly) gains these three as real, usable plan steps too -- a real,
useful side effect of reusing the already-shared table, not a new
mechanism.

### 2. `communications.list_email`/`read_email`/`list_calendar_events` -- new grammar + direct `await` dispatch

**A real, empirically-caught structural constraint, not a style
choice**: `communications.list_email`/`read_email`/`list_calendar_events`'s
own `authorize_and_*` functions (`kernel/communications.py`) are
`async def`, but `PlanStepExecutor` (the type every `PLAN_STEP_EXECUTORS`
entry implements) is a plain, synchronous callable. A first attempt
wrapped the async calls in `asyncio.run()` inside a sync executor --
this raises `RuntimeError: asyncio.run() cannot be called from a
running event loop`, since `authorize_and_route` (the router's own
composition root) is itself `async` and already running inside an
event loop by the time any executor is invoked. Confirmed directly via
a failing test before fixing, not assumed. **The fix**:
`kernel/router.py::authorize_and_route` dispatches these three
capabilities with its own real `await`, in three new branches
alongside the existing `PLAN_STEP_EXECUTORS` branch -- no threading
hack, no second event loop, no change to `PlanStepExecutor`'s own
type or to `application/planning/executor.py` at all.

**New grammar, deliberately NOT added to `kernel.intent.resolve_intent()`**
(the shared grammar both this router and `kernel.voice_loop` call),
for two real, independent, structural reasons:

1. These three capabilities need a real, pre-configured `email_port`/
   `calendar_port` with no safe default. Adding them to the shared,
   pure `resolve_intent()` would make them resolvable via voice too --
   but `kernel.voice_loop._authorize_and_execute`'s own dispatch has
   no branch for these three capability ids, and its own final
   fallback is an *unguarded* dict lookup
   (`_MUSIC_COMMAND_BY_CAPABILITY_ID[resolved.capability_id]`) that
   would raise a real `KeyError` for any newly-resolvable capability id
   it doesn't recognize. This work package's own hard boundary ("do
   not implement voice... do not touch voice runtime") requires
   avoiding that regression, not introducing it.
2. "calendar today"/"tomorrow"/"this week" needs the real, current
   wall-clock time (`ClockPort`) to resolve to a concrete ISO-8601
   range. `resolve_intent()` is a deliberately pure, clockless
   function (see its own module docstring); threading a `ClockPort`
   through it would be an invasive signature change rippling into
   every caller, including `kernel.voice_loop`, which the hard
   boundary also forbids touching.

`kernel/router.py::_resolve_communications_command(text, clock)` is
the new, separate, typed-router-only function this became -- confined
entirely to `kernel.router` (never imported by `kernel.voice_loop`),
so it structurally cannot affect voice in any way, not just by
convention. It is checked **before** `resolve_intent()`, not as a
fallback for `UnrecognizedIntent` -- a real, empirically-caught
collision forced this ordering: `resolve_intent()`'s own pre-existing
single-word `"read <path>"` command happily resolves `"read email
<id>"` to `fs.read_file` with `path="email <id>"`, since it is never
`UnrecognizedIntent`. A fallback-only check would never even run for
that exact phrase. Checking the new grammar first avoids this cleanly;
none of its own trigger phrases collide with any of `resolve_intent()`'s
existing single- or two-word keywords.

Real, supported phrasings:

- **Email list**: `"list emails"` / `"recent emails"` / `"show my
  emails"` / `"show my recent emails"` / `"show recent emails"`
  (exact match, case-insensitive) -- resolves to `communications.list_email`
  with `folder="INBOX"`, `limit=10` (mirrors `jarvis email list`'s own
  CLI defaults exactly).
- **Email read**: `"read email <id>"` -- everything after the fixed
  keyword, verbatim, is the real message id. A real, honest
  limitation, not hidden: this requires a literal message id recited,
  never `"the latest email"`/`"emails from Alice"` -- `EmailPort` has
  no "latest"/"by sender" lookup primitive, and this work package's
  own Step 3 instruction is explicit ("do not invent... do not add a
  fake abstraction"), so those phrasings are genuinely unsupported,
  not silently guessed. `"read email"` alone (no id) is a real,
  recognized-but-incomplete match, terminal `UNKNOWN` -- never
  silently falls through to `resolve_intent()`'s colliding `"read
  <path>"` command.
- **Calendar list**: a small, fixed trigger-phrase table (`"what's on
  my calendar"`, `"whats on my calendar"`, `"show my calendar"`,
  `"what meetings do i have"`, bare `"calendar"`) combined with a
  small, fixed range-suffix table (empty/`"today"`/`"for today"` →
  today, `"tomorrow"`/`"for tomorrow"` → tomorrow, `"this
  week"`/`"for this week"` → this week) -- covers Step 4's three named
  examples exactly (`"what's on my calendar today?"`, `"show my
  calendar for tomorrow"`, `"what meetings do I have this week?"`)
  plus reasonable variants, all deterministic exact/prefix matches,
  never fuzzy substring search. "today"/"tomorrow" are real,
  midnight-to-midnight UTC day ranges; "this week" is Monday 00:00 UTC
  through the following Monday, computed from the real
  `ClockPort.now()` passed into `authorize_and_route`. A trigger
  phrase matching with an unrecognized suffix (e.g. `"calendar next
  monday"`) is real, recognized-but-unsupported, terminal `UNKNOWN` --
  never guessed, never a fabricated date range.

Both the "read email" (no id) and "calendar <unsupported phrase>"
cases mirror `AmbiguousJobSearchSite`'s own, already-established
reasoning exactly for not escalating to Stage B reasoning either: once
a trigger phrase is recognized, Stage A already has a more precise
read on what's missing than a reasoning call would provide.

### 3. `jarvis ui` -- optional, explicit configuration, no credentials committed

`jarvis ui` gained seven new, entirely optional flags:
`--email-imap-host`/`--email-smtp-host`/`--email-username`/
`--email-password-reference` and `--calendar-caldav-url`/
`--calendar-username`/`--calendar-password-reference` -- the exact
same flag *names and semantics* `jarvis email list`/`jarvis calendar
list-events` already use. `--email-password-reference`/
`--calendar-password-reference` are keyring references, resolved via
the existing `SecretPort`/`SecretServiceAdapter` mechanism at
construction time -- no raw secret ever appears in source, tests,
frontend JS, or committed configuration, matching this project's
existing, unmodified secret-handling convention exactly.

All four email flags (or all three calendar flags) must be supplied
together, or the corresponding port stays unconfigured (`None`) --
proven by a real test. Omitting all of them behaves byte-for-byte as
before this work package: `UiServerConfig.email_port`/`calendar_port`
default to `None`, and `kernel.router.authorize_and_route` receives
`None` for both when `_run_ui` doesn't construct them, reaching the
exact same "recognized, not wired" `unwired_capability` response every
other unconfigured/unwired capability already produces -- now with a
more precise message naming *why* ("email isn't configured for this
server -- start `jarvis ui` with the real IMAP connection flags, or
use `jarvis email list` directly") rather than the generic "isn't
wired" text.

## Authorization -- unchanged, verified directly

All six capabilities this work package touches are `Effect.EGRESS_LOCAL`/
`Tier.ALLOW` -- identical to `fs.read_file`/`memory.retrieve`, the two
capabilities the router already executed before this work package. No
existing `Effect`/`Tier` classification changed. `communications.send_email`/
`create_calendar_event` (the two *write* capabilities) remain
completely untouched: still dynamic-effect, never registered in
`build_default_registry()`, never in any executor table this router
consults, still floored at `Tier.MANUAL_ONLY` (ADR-0059) regardless of
how a request reaches them. A real test proves a route naming
`communications.list_calendar_events` (a real, registered capability)
without a configured `calendar_port` is still never executed, the
identical structural property `git.force_push` already proved.

`application/planning/executor.py` (ADR-0062's own per-step
authorization, no batch pre-approval), `Dispatcher`, `EscalationLadder`,
and the authorization kernel itself were not touched by any part of
this work package.

## UI -- automatically benefits, zero frontend changes

`src/jarvis/cli/ui_static/index.html` already renders `"response"`/
`"unwired_capability"`/`"denied"` generically, with no per-capability
branch -- confirmed by inspection before deciding this needed no
change. `POST /api/command` was extended to pass `email_port`/
`calendar_port` through to `authorize_and_route` (both default `None`,
unaffected unless `jarvis ui` was launched with the new flags); the
response shape (`type`/`message`/`capability_id`/`granted`) is
identical to every other route. No new frontend rendering, no
fabricated `success=true` -- every summarizer function (`_summarize_list_email`,
etc., `cli/ui_server.py`) returns `None` for a denied/empty result,
falling through to the real `"Ran <capability_id>."`/`"No messages
found."`/`"No events found."` text the backend actually knows.

## Memory -- untouched

No new memory-write call anywhere in this work package. A typed "show
my recent emails" request still never creates a memory record --
`Conversation`/`Task`/`Memory` remain exactly as separate as WP-108
first established.

## Testing

- **Deterministic routing**: parametrized tests proving every real
  phrasing for `fs.find`/`fs.search_content`/`fs.recent`/email
  list/email read/all three calendar ranges resolves to the correct
  capability id and arguments (`tests/unit/test_router_kernel.py`).
- **Ambiguity**: `"read email"` (no id) and `"calendar next monday"`
  both resolve to real, terminal `UNKNOWN` -- never silently routed.
- **Collision regression**: a dedicated test proves an ordinary
  `"read notes.txt"` still resolves to `fs.read_file`, confirming the
  fix for the real "read email" collision didn't overcorrect.
- **Authorization**: `communications.list_email`'s `Tier.ALLOW` grants
  regardless of `physical_confirmation_available` (mirrors `recall`'s
  own identical property).
- **Unwired capability**: `communications.list_calendar_events`,
  reasoning-sourced, with no configured port, is recognized but never
  executed -- the same structural test shape `git.force_push` already
  established.
- **Real, end-to-end HTTP integration tests** (`tests/unit/test_ui_server.py`):
  a real `POST /api/command` for `"recent files"` reaches the real
  router/real `fs.recent` executor; a real, second server instance
  constructed with a stub `email_port` proves `"list emails"` actually
  executes end to end over real HTTP; two tests prove the precise
  "not configured" messages for email/calendar. None of these mock the
  router itself.
- **CLI flag wiring** (`tests/unit/test_cli_main.py`): omitting the new
  flags leaves both ports `None`; all-four-email-flags constructs a
  real `ImapEmailAdapter`; a partial set (three of four) leaves the
  port unconfigured (all-or-nothing); all-three-calendar-flags
  constructs a real `CalDavCalendarAdapter`.

## External services

No mandatory test depends on a real IMAP/CalDAV server, real Gmail, or
any real external API -- every email/calendar test uses a real,
hermetic, in-process stub port (mirroring `test_communications_kernel.py`'s
own established `_StubEmailPort`/`_StubCalendarPort` pattern). The
project's own existing, separately-isolated local-integration tests
(`tests/integration/test_email_calendar_against_local_servers.py`,
GreenMail/Radicale) are untouched.

## Full suite, coverage

All gates pass: ruff check/format, mypy --strict, lint-imports (C1
layered architecture holds), pytest (1648 passed, only the 1 known
pre-existing GUI-display failure and the 1 known flaky live-Ollama
test), all three mandatory 100%-coverage gates. `kernel/router.py` and
`kernel/capability_dispatch.py` are both at 100% coverage;
`cli/ui_server.py` reached 100% after adding the missing
denied-result summarizer branches.

## Known limitations, stated plainly

- `jarvis do "<text>"` has no `--email-*`/`--calendar-*` flags of its
  own and never constructs either port -- only `jarvis ui` can. A
  `jarvis do "list emails"` invocation is always recognized but always
  reported as unwired/unconfigured, confirmed directly by reading
  `_run_do_subcommand`'s own call to `authorize_and_route` (no
  `email_port`/`calendar_port` argument at all). Adding equivalent
  flags to `do` was considered and left out of this work package's own
  scope -- a one-shot CLI invocation re-authenticating an IMAP/CalDAV
  connection per call is a real, separate design question (credential
  flags on every single `do` invocation vs. `jarvis ui`'s own
  once-per-server-lifetime construction), not decided here.
- No natural-language date parsing beyond the three fixed calendar
  keywords (today/tomorrow/this week) -- "next Monday"/"in 3 days" are
  genuinely unsupported, reported as `UNKNOWN`, not guessed.
- `"read the latest email"`/`"emails from Alice"`/`"emails from
  today"` are not supported -- the backend (`EmailPort`) has no
  latest/sender-filter/date-filter primitive, and Step 3's own
  instruction explicitly forbids inventing one.
- Voice grammar for these six capabilities remains explicitly out of
  scope, per this work package's own hard boundary -- a future voice
  adapter would need its own, separate wiring (a real `email_port`/
  `calendar_port` construction path inside `kernel/voice_loop.py`,
  plus new `_confirmation_prompt`/`_authorize_and_execute` branches),
  not attempted here.
- `communications.list_email`/`read_email` remain unreachable from
  `kernel/voice_loop.py` even indirectly, by design -- confirmed
  structurally, not just by convention, since `_resolve_communications_command`
  is never imported outside `kernel.router`.
