# WP-108: UI foundation + local application boundary (2026-09-09)

## Status

Real, implemented design -- not a proposal. Built and merged the same
day it was requested. No ADR was written for this work package: it
introduces no new `CapabilityId`, no new `Effect`/`Tier`, and no new
authorization path -- every real action the UI can ever cause is
already-existing, already-classified, already-Accepted machinery
(`kernel.router.authorize_and_route`, WP-104). Per this project's own
"do not create unnecessary ADRs merely to document implementation
details" convention, a design doc is the right artifact here, not an
ADR.

No prior committed doc described "WP-108" as anything else -- the only
prior WP-104-through-WP-124 numbering scheme was a design-only,
un-committed Artifact from an earlier read-only pass (`CLAUDE.md`'s own
"Documentation-consistency audit read-only pass, 2026-09-09" paragraph
names this directly), so there was nothing in the repository itself to
reconcile.

## Architecture: the UI is a client, never a second execution system

```
Browser (index.html, vanilla JS)
    |  POST /api/command  {"text": "..."}
    v
jarvis.cli.ui_server (a real, local HTTP boundary)
    |  authorize_and_route(text, ...)   <-- completely unmodified, WP-104
    v
jarvis.kernel.router
    |  Stage A: kernel.intent.resolve_intent() (unmodified, unduplicated)
    |  Stage B: application.routing.router.generate_route() (reasoning fallback)
    v
The existing, unmodified authorization/capability system
```

The server module (`src/jarvis/cli/ui_server.py`) adds exactly one new
thing: translating one already-existing kernel call
(`kernel.router.authorize_and_route`) into an HTTP request/response
shape a browser can use. It does not parse commands itself, does not
maintain its own capability list, and does not invoke any
`authorize_and_*` function other than the one `authorize_and_route`
already calls internally. Confirmed directly by reading the module: it
imports `authorize_and_route` and nothing else from `kernel` capable of
performing a real action.

## Where this lives, and a real, investigated documentation finding

Before writing any code, the repository was inspected for an existing
service boundary. `jarvis.ipc`'s own docstring claims it "may depend on
... `jarvis.kernel`" and is meant for "clients -- the CLI, a future
voice frontend, a future GUI -- to reach a running kernel instance."
That reads like exactly the right home for this work.

It is not, and the reason is concrete, not a judgment call: the real,
enforced `C1 layered architecture` import-linter contract
(`pyproject.toml`) orders layers as

```
jarvis.cli, jarvis.kernel, jarvis.ipc, jarvis.adapters,
jarvis.application, jarvis.ports, jarvis.domain, jarvis.ui
```

Import-linter's `layers` contract only permits an earlier layer to
import a later one. `kernel` sits *before* `ipc` in that list, so `ipc`
structurally cannot import `kernel` -- the exact opposite of what its
own docstring claims. Checked directly, not assumed: `git log --
src/jarvis/ipc/` shows the package has never had any real content
beyond that docstring, so this was never exercised or caught. This is
a real, stale, aspirational piece of documentation for a package that
has done nothing yet -- flagged here plainly, not silently routed
around, and not fixed in this work package either (whether to widen C1
or correct the docstring is a real, separate architectural decision
this work package's own scope does not include).

`jarvis.cli` is layer 1 -- it already may import `jarvis.kernel`
freely, and it is already the one layer permitted to construct real,
concrete adapters and run a continuous foreground process
(`_run_listen`'s own `Gtk4PhysicalConfirmationAdapter` construction,
`run_voice_loop`'s own serve-until-interrupted shape). `jarvis.cli.ui_server`
mirrors that exact, already-established precedent. `lint-imports` was
run after implementation and confirms all six contracts, including C1,
still hold.

## Local-only, by construction

The server always binds `127.0.0.1`. There is no `--host`/bind-address
flag anywhere in `ui_server.py` or its CLI wiring (`jarvis ui`), on
purpose, so this cannot be misconfigured into listening on a
LAN-reachable or public interface -- a real test
(`test_ui_has_no_host_flag`) proves passing `--host` fails argument
parsing.

## Single-threaded by design -- a real, deliberate safety choice

`http.server.HTTPServer` is used, not `ThreadingHTTPServer`. Every real
`authorize_and_*` composition function in this codebase (including
`authorize_and_route`) does its own `chain_path` load-append-save per
call -- correct for the CLI's "one process, one request" shape, but
two *concurrent* requests inside one long-running server process
racing to load-append-save the same audit-chain file would reproduce
the already-documented, still-open cross-process race
(`docs/OPEN_DECISIONS.md` item 5), except now reachable from a single
local process instead of requiring two separate ones. Serializing all
request handling removes that new exposure entirely, at the honest
cost of not serving two requests at once -- an acceptable trade for a
genuinely single-user, local chat interface where the human types one
message at a time regardless.

## Authorization: what the UI can and cannot cause

Nothing new. `authorize_and_route`'s own real, structural execution
boundary (WP-104) is unchanged and untouched:

- A `DETERMINISTIC_COMMAND` route only actually runs if its capability
  id is one of the four entries already wired in
  `kernel.capability_dispatch.PLAN_STEP_EXECUTORS`
  (`fs.read_file`/`fs.list_dir`/`git.status`/`memory.retrieve`, all
  `Tier.ALLOW`). A real, registered-but-unwired capability (e.g. a
  reasoning-sourced route naming `git.force_push`) is reported back to
  the browser as `"unwired_capability"`, never executed -- proven by a
  real test (`test_real_server_reports_a_recognized_but_unwired_capability`,
  `test_build_response_payload_for_a_recognized_but_unwired_capability`).
- A `COMPLEX_GOAL` route creates, never runs, a new task via WP-107's
  own `authorize_and_create_task` (`Effect.WRITE_LOCAL`/`Tier.CONFIRM`,
  `memory.write`'s own classification, unchanged).
- `RouteKind.UNKNOWN` causes no authorization attempt at all.

`UiServerConfig.physical_confirmation_available`/
`remote_confirmation_available` are applied **uniformly to every
request for the server's whole lifetime**, set once at `jarvis ui`
launch time -- not per-request, and not inferred from "this request
came from localhost." This was a real, deliberate choice, not a
default reached for convenience: both flags default to `False`,
identical to every other subcommand, so a task-creating `COMPLEX_GOAL`
route only succeeds if the operator explicitly launches
`jarvis ui --physical-confirmation-available` -- the same explicit,
human-supplied opt-in every other subcommand already requires. Nothing
about "the request arrived over HTTP to 127.0.0.1" is treated as
equivalent to a real physical-confirmation signal; that would have been
a real, silent reinterpretation of ADR-0013's own physical-presence
guarantee, which this work package does not make.

Job-application submission (ADR-0058) is untouched -- there is no
submission capability for any route to ever reach, wired or not.

## Response shape

```json
{
  "type": "response" | "task_created" | "denied" | "not_routed" | "unwired_capability" | "error",
  "message": "...",
  "route_kind": "deterministic_command" | "complex_goal" | "unknown" | null,
  "capability_id": "memory.retrieve" | null,
  "task_id": "..." | null,
  "granted": true | false | null
}
```

`granted` is `null` exactly when `outcome.decision is None` (nothing
was authorized at all) -- never fabricated as `true`/`false` for a
request that never reached the authorization choke point.

## Conversation, task, and memory stay separate

Each `POST /api/command` is a single, stateless call into
`authorize_and_route` -- the server persists no conversation history
anywhere. The browser's own JS keeps the visible message list in
memory only (`ui_static/index.html`), lost on refresh. No UI message is
ever auto-written to memory; no conversation history lives inside
`TaskStore`.

## Error handling

Every request is validated before it reaches `authorize_and_route`:
missing/empty `text`, non-JSON body, non-object body, and an 8 KB body
cap all fail with a clean `400` and a `{"type": "error", ...}` body,
never a stack trace. A real, narrow exception tuple
(`_HANDLED_ROUTING_ERRORS` -- covering exactly what the router's own
reachable capability surface can raise: path-scope errors, git
failures, memory-store errors, `OSError`/`sqlite3.Error`/etc.) is
caught and reported as a clean `400`; any other, truly unexpected
exception is caught by a final backstop and reported as a generic
`500`, logged server-side via `logging.exception`, never echoed to the
browser. A real test
(`test_post_command_never_leaks_a_traceback_on_an_unexpected_error`)
proves the raw exception message never reaches the client.

## Voice: a placeholder only, nothing implemented

The mic button in `index.html` is disabled (`title="Voice input coming
soon"`). No microphone capture, wake-word detection, or audio streaming
code was added or touched -- `kernel/voice_loop.py`,
`adapters/wake_word.py`, and every wake-word/microphone test are
untouched (confirmed by `git diff --name-only`). The intended future
shape is:

```
Typed input --\
                +--> normalized text --> the same authorize_and_route
Voice input  --/
```

Voice would become a second real input adapter feeding the same
router, not a second router.

## Startup / developer experience

```sh
jarvis ui                                   # serves on http://127.0.0.1:8765
jarvis ui --port 9000                       # a different local port
jarvis ui --physical-confirmation-available # allow COMPLEX_GOAL routes to create tasks
```

Open the printed URL in a browser. Ctrl+C stops the server cleanly
(`"\nStopped."`, exit code 0) -- no separate frontend build step, no
`npm`, no dev server: `index.html` is one static, self-contained file
served directly by the same process.

## Testing

`tests/unit/test_ui_server.py` (27 tests): request validation (missing
body, empty/missing `text`, malformed JSON, non-object body, oversized
body, a malformed `Content-Length` header via a raw socket), error
handling (a listed exception becomes a clean `400`; an unlisted one
becomes a clean, non-leaking `500`), the pure `build_response_payload`/
`_summarize_execution_result` formatting logic for all four real
`PLAN_STEP_EXECUTORS` result shapes, and -- the real integration
requirement -- two tests that start a real server and issue real HTTP
requests through the entirely unmocked `authorize_and_route`/
`resolve_intent` path (`recall anything` -> a real, granted
`memory.retrieve`; `ping` -> a real, recognized-but-unwired report),
proving the HTTP boundary genuinely uses the existing router rather
than a mock standing in for it. `tests/unit/test_cli_main.py` gained 5
more tests for `jarvis ui`'s own argument wiring, default port,
Ctrl+C handling, and the absence of a `--host` flag. 100% branch
coverage on `ui_server.py`; the full existing suite passes except the
one, already-known, unrelated GUI-display failure.
