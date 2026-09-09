# WP-110: UI conversation + typed input end-to-end (2026-09-09)

## Status

Real, implemented, frontend-only change on top of WP-108's already-real
`jarvis ui`. No ADR: no new `CapabilityId`/`Effect`/`Tier`, and the one
backend change (a `task_status` field) is additive, not a redesign of
the existing API contract.

## A real naming collision, found before writing any code, not silently overwritten

The originating prompt calls this work "WP-109." A real, already-merged
WP-109 exists in this repository's own git history
(`6fdd3b2`/`e6aef97`, "unify stuck/failed task-status terminology,"
2026-09-09) -- a different, already-shipped work package, unrelated to
the UI. This is labeled **WP-110** instead: the next real, sequential,
available number (confirmed by scanning every `WP-\d+` reference across
`CLAUDE.md`/`docs/ROADMAP.md`/`docs/OPEN_DECISIONS.md` -- the highest
real number in use before this work was 109). This mirrors this
project's own established precedent for exactly this situation (the
`v0.3.0`-requested-but-already-`v0.7.0`-used renumbering, and the
`v0.7.1`-requested-but-`v0.9.0`-used renumbering) -- real git state
wins over a prompt's own requested label, stated plainly, not silently
substituted.

## What WP-108 already provided, confirmed by direct inspection before writing anything

`src/jarvis/cli/ui_static/index.html` already had: a message list with
distinct user/jarvis/error bubble styling, an input row (text input +
Send button + a disabled mic button), Enter-to-send, a `fetch` call to
the real `/api/command` endpoint, and `.finally()`-based cleanup that
already re-enabled the Send button and cleared a status line
regardless of success or failure. `src/jarvis/cli/ui_server.py`
already returned a stable, complete JSON contract (`type`/`message`/
`route_kind`/`capability_id`/`task_id`/`granted`) covering every real
route outcome (`response`/`task_created`/`denied`/`not_routed`/
`unwired_capability`/`error`).

## Real gaps found and fixed -- nothing rebuilt that already worked

1. **A real message-ordering hazard** (the one genuinely load-bearing
   bug): the old `send()` only disabled the Send *button*, not the
   text input, and the `keydown` handler called `send()` directly with
   no re-entry check at all. Pressing Enter twice quickly (or typing a
   second message and hitting Enter before the first response
   arrived) could fire two concurrent `fetch` calls whose responses
   could resolve out of order, visually reordering the conversation --
   exactly the failure mode the originating prompt named explicitly.
   Fixed with a real `isSending` guard checked at the top of `send()`,
   plus disabling `textInput` (not just the button) for the duration
   of the request.
2. **No distinct rendering per real response `type`.** The old code
   only distinguished `"error"` from everything else -- a granted
   task creation, an authorization denial, an unwired-but-recognized
   capability, and a genuine "I don't know" all rendered as the same
   generic bubble. Added `renderResponse()`, mapping each real `type`
   the backend can return to distinct, clearly-labeled rendering:
   `task_created` gets a "Task created" heading with `Task ID:`/
   `Status:` lines; `denied` gets an "Authorization required" heading;
   `response`/`not_routed`/`unwired_capability` render as plain text
   (already clear on their own).
3. **No visible "processing" state inside the conversation itself** --
   only a separate status line below the input row. Replaced with a
   real, removable "Thinking..." bubble inserted immediately after the
   user's own message and removed the moment the real response (or a
   real failure) arrives -- matching the originating prompt's own
   example flow (`You: ... / JARVIS: Thinking...`) and keeping the
   removed status-line element from becoming dead markup.
4. **One small, additive backend change**: `build_response_payload`
   (`ui_server.py`) gained a `task_status` field, always present
   (`null` except for `task_created`). For `task_created` it is always
   the literal string `"created"` -- a real, always-true fact, not
   invented: `authorize_and_create_task` (WP-107) never produces any
   other status for a brand-new task, so this needed no extra real
   I/O (no follow-up `authorize_and_get_task` call) to state correctly.
   Every other existing field is unchanged; no existing consumer of
   the API breaks.

## What was already correct and needed no fix

Empty/whitespace-only input was already rejected (`text.trim()`
before doing anything). Failure recovery already worked: `.finally()`
already unconditionally re-enabled the Send button and refocused the
input on any outcome, including a network failure or a malformed
response -- the old code was never at real risk of a permanently-stuck
loading state. The error message shown on a real network failure was
strengthened to read "I couldn't process that request. Please try
again." (previously a more technical "Could not reach the JARVIS
backend"), matching the originating prompt's own example wording, but
this was a wording change, not a behavioral fix.

## One router only -- unchanged

No new router, no `ui_router.py`/`frontend_router.py`/
`browser_intent.py` of any kind was created. The frontend still only
ever calls `POST /api/command`; the backend still only ever calls the
exact same, unmodified `kernel.router.authorize_and_route` (WP-104).
The browser never decides what a request means -- it only renders
whatever the real router/authorization system already decided.

## Conversation, Task, and Memory remain separate

No conversation persistence was added anywhere, client or server side.
The browser's own in-memory message list is exactly as ephemeral as
it was in WP-108 -- lost on refresh, never written to `TaskStore`,
never auto-written to memory. `build_response_payload`'s new
`task_status` field is a real fact *about* a task, not a mechanism for
storing conversation state.

## Security and authorization -- unchanged

Still `127.0.0.1`-only, no `--host` flag exists. Still single-threaded
(`http.server.HTTPServer`). `UiServerConfig.physical_confirmation_available`/
`remote_confirmation_available` are still applied uniformly for the
server's whole lifetime, set once at `jarvis ui` launch -- this work
package did not add any new confirmation mechanism, any localhost-as-
physical-confirmation inference, or any new way for the browser to
name a capability id directly. ADR-0058 (no automated job-application
submission) and ADR-0062 (per-step authorization, no batch
pre-approval) are both untouched -- neither `kernel/router.py` nor
`application/planning/` were modified at all in this work package.

## What was deliberately not built (per explicit scope)

No `EventBus`, WebSocket, or Server-Sent Events; no real task-progress
polling (a task's own status can change after creation, but nothing
in this work package queries it again -- WP-110's own successor,
"event/task progress," owns that); no persistent conversation
database; no voice/microphone code of any kind (the mic button is
still the same disabled placeholder WP-108 already shipped).

## Testing

**Backend** (`tests/unit/test_ui_server.py`): two new tests for the
`task_status` field (`"created"` on a granted task-creation route,
`null` everywhere else) plus a new, real HTTP round-trip test
(`test_post_command_full_round_trip_for_a_task_created_response`)
proving the server's own JSON response genuinely carries `task_status`
end to end. All of WP-108's own existing real, unmocked integration
tests are unchanged and still pass.

**Frontend**: this repository has no JS test framework, no `npm`, and
no existing browser-automation testing dependency capable of
simulating keystrokes/clicks (`ports/browser_automation.py`'s own real
`BrowserAutomationPort` only supports `open_page`/`screenshot`/
`query_dom`/`close` -- reading a page, not driving one). Rather than
adding a new, disproportionate testing dependency for one static HTML
file, or fabricating a claim of "tested" that wouldn't be real, the
actual, shipped `<script>` content was executed unmodified inside a
minimal, hand-rolled DOM stub (a few dozen lines: `getElementById`,
`createElement`, `appendChild`, `remove`, `addEventListener`) with
Node's real, built-in `fetch` calling the real, running `jarvis ui`
server -- a genuine execution of the production code against a real
backend, not a reimplementation. 16 real checks, all passing: the
re-entry guard (a second Enter while a request is in flight adds no
second message), the pending bubble appearing then being removed,
both the Send button and the text input disabling and re-enabling
correctly, whitespace-only input being rejected, a real network
failure (a connection to a closed port) recovering cleanly with the
input usable again, and a retry after that failure succeeding. This
verification is real and was actually run, but -- stated plainly, not
glossed over -- it is not part of the committed, repeatable gate suite
(matching this project's own established precedent for GUI-adjacent
code with no real automated coverage, e.g. `ui/confirm/dialog.py`'s
own "needs a real display, proven by manual verification" note); a
real, standing gap, not a hidden one.
