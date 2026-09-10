"""WP-108: a real, minimal, local-only HTTP boundary for the JARVIS UI foundation.

**Where this lives, and why, a real, investigated decision, not a
default**: `jarvis.ipc`'s own docstring claims it "may depend on
... `jarvis.kernel`" -- but the real, enforced `C1 layered architecture`
contract (`pyproject.toml`'s `[tool.importlinter]`) orders layers
`cli, kernel, ipc, adapters, application, ports, domain, ui`, meaning
`ipc` sits *below* `kernel` and structurally cannot import it (only
earlier layers may import later ones). That docstring is stale,
aspirational text for a package that has never had any real content --
confirmed directly, not assumed, by checking `git log -- src/jarvis/ipc/`
and this contract's own real behavior. Fixing that inconsistency is a
real, separate, deliberate decision (whether to widen C1 or correct the
docstring) this work package's own scope does not include -- flagged
plainly, not silently routed around. This module lives in `jarvis.cli`
instead, which already may import `jarvis.kernel` freely and is already
the one layer permitted to construct real, concrete adapters and run a
continuous foreground process (`_run_listen`'s own
`Gtk4PhysicalConfirmationAdapter` construction, `run_voice_loop`'s own
`serve`-until-interrupted shape) -- this module mirrors that exact,
established precedent, not a new pattern.

**The UI is a client of the existing application layer, never a second
execution system.** Every real request this server handles is routed
through `jarvis.kernel.router.authorize_and_route` (WP-104) completely
unmodified -- the same deterministic-then-reasoning-fallback routing,
the same structural "never execute a capability outside the
already-wired, small `PLAN_STEP_EXECUTORS` table" boundary, the same
task-creation-never-run behavior. This module adds no new
`CapabilityId`, no new `Effect`/`Tier`, no new authorization path --
it only translates one real, existing kernel call into an HTTP
request/response shape a browser can use.

**Single-threaded by design, a real, deliberate safety choice, not an
oversight**: `http.server.HTTPServer` (not `ThreadingHTTPServer`) is
used on purpose. `authorize_and_route` (like every other real
`authorize_and_*` composition function in this codebase) does its own
`chain_path` load-append-save per call -- safe for the CLI's own
"one process, one request" shape, but two *concurrent* requests inside
one long-running server process racing to load-append-save the exact
same audit-chain file would reproduce the identical, already-documented,
still-open cross-process race (`docs/OPEN_DECISIONS.md` item 5) --
except now reachable from a single local process instead of requiring
two. Serializing all request handling removes that new exposure
entirely, at the honest cost of not serving two requests at once -- an
acceptable trade for a genuinely single-user, local chat interface
where the human types one message at a time regardless.

**Local-only, by construction, not by convention**: the server always
binds `127.0.0.1` -- there is no `--host`/bind-address flag anywhere in
this module or its CLI wiring, on purpose, so this cannot be
misconfigured into listening on a LAN-reachable or public interface.

**Conversation history is not persisted anywhere server-side.** Each
`POST /api/command` is a single, stateless, independent call into
`authorize_and_route` -- the browser's own JS keeps the visible message
list in memory only (see `ui_static/index.html`). This keeps
`Conversation`/`Task`/`Memory` genuinely separate, per this work
package's own explicit instruction: no UI message is ever
auto-written to memory, and no conversation history lives inside
`TaskStore`.

**WP-111 (2026-09-10): real task lifecycle events + status recovery.**
`JarvisUiServer` now owns one real, shared `jarvis.domain.events.EventBus`
for its entire lifetime, passed into every `authorize_and_route` call
so a `COMPLEX_GOAL` route's own real `TaskCreated` event (WP-111) is
genuinely published in-process. Two minimal, real subscribers are
attached at construction time, logging every real event -- the one,
deliberately small "future adapters" consumer this pass actually
builds, proving the wiring is real rather than just plumbing nothing
ever uses.

**Why this is not SSE, and not a live push mechanism at all**: this
server is deliberately single-threaded (see above) -- an SSE
connection that stays open indefinitely would block the one real
thread from handling any other request for as long as it stayed open,
directly contradicting the single-threaded design this module already
committed to. `GET /api/tasks/<task_id>` instead does one real,
authoritative read of the real, persistent task store
(`kernel.tasks.authorize_and_get_task`) per call -- the frontend polls
this at a short interval while a task is outstanding. This also
solves browser-reconnection cleanly, for free: a refreshed or
reconnected browser has nothing but this same real, authoritative
query to ask again, and gets the same real answer back, regardless of
whether it missed any events while disconnected -- the real
`TaskStore` is authoritative, `EventBus` is not, and is not made to
pretend to be.

**A real, stated limitation, not hidden**: today, nothing in
`kernel.router.authorize_and_route`'s own real call graph ever runs an
already-created task (a `COMPLEX_GOAL` route creates, never runs, by
WP-104's own explicit, unchanged design) -- so a task created through
this UI can only ever be observed reaching `"created"` via this
server's own, single, long-running process. If a task is later run via
a separate `jarvis task run <id> <goal>` invocation (a different
process), that process's own real `TaskStatusChanged` events publish
into *that* process's own, separate, short-lived `EventBus` instance,
never this server's -- this server's own `EventBus` was never told
about it. `GET /api/tasks/<task_id>` still correctly reflects that
real, cross-process change, because it re-reads the real, shared,
persistent task store directly, not this server's own in-process
event history.

**WP-112 (2026-09-10): a real, explicit way to run an already-created
task from the UI.** `POST /api/tasks/<task_id>/run` reuses
`kernel.tasks.authorize_and_run_task` completely unmodified -- the
exact same function `jarvis task run` already calls, the exact same
outer `memory.update`-based "running" transition gate, the exact same
unmodified `planning.run_plan` outer gate plus real, individual,
per-step authorization (ADR-0062). No new authorization concept, no
new confirmation semantics: this endpoint reads
`UiServerConfig.physical_confirmation_available`/
`remote_confirmation_available` exactly like `POST /api/command`
already does. **Never automatic**: creating a task (a `COMPLEX_GOAL`
route) still only ever creates it -- running it is a real, separate,
explicitly-triggered HTTP request the browser only sends when the
user clicks a real "Run" control, mirroring `jarvis task create`/
`jarvis task run`'s own already-established two-verb separation
(WP-107) exactly. The real, current goal is looked up server-side via
`authorize_and_get_task` before running -- the browser never supplies
its own copy of the goal text, so it cannot smuggle a different goal
into a real plan run than the one the task was actually created for.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.application.planning.executor import PlanValidationError
from jarvis.application.planning.planner import PlanningError
from jarvis.application.routing.router import RouteKind
from jarvis.domain.errors import JarvisError
from jarvis.domain.events import EventBus, TaskCreated, TaskStatusChanged
from jarvis.kernel.desktop import GitStatusOutcome
from jarvis.kernel.files import DirListOutcome, FileReadOutcome, PathOutsideAllowedScopeError
from jarvis.kernel.memory import MemoryRecallOutcome
from jarvis.kernel.router import authorize_and_route
from jarvis.kernel.tasks import authorize_and_get_task, authorize_and_run_task
from jarvis.ports.git import GitCommandFailedError
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.retrieval import MemoryIntegrityViolationError

if TYPE_CHECKING:
    from jarvis.adapters.memory import UnsupportedMemoryValueError
    from jarvis.kernel.router import RouteOutcome
else:
    from jarvis.adapters.memory import UnsupportedMemoryValueError

_logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "ui_static"
_INDEX_HTML_PATH = _STATIC_DIR / "index.html"

_TASK_STATUS_PATH_PREFIX = "/api/tasks/"
"""GET <this>+<task_id> -- a real, authoritative task-store read (WP-111). See
module docstring's own "why this is not SSE" section."""

_TASK_RUN_PATH_SUFFIX = "/run"
"""POST <_TASK_STATUS_PATH_PREFIX>+<task_id>+<this> -- runs an already-created
task (WP-112). See module docstring's own WP-112 section."""

_MAX_REQUEST_BODY_BYTES = 8192
"""A defensive cap on POST /api/command's own body size -- one short, typed request,
never a large upload; rejects anything absurd before it is even parsed."""

_RESULT_TEXT_TRUNCATE_CHARS = 4000
"""Caps how much of a real file's own content -- fs.read_file's real result -- is
echoed back in one chat response, so one huge file cannot flood the browser."""

_MAX_MEMORY_RECORDS_SHOWN = 5
"""Caps how many recalled memory records one chat response shows, mirroring
this codebase's own established "cap, report honestly, never silently truncate
without saying so" convention (see fs.search_content's own capped flag)."""

# The real, narrow exception surface `authorize_and_route` can actually raise, given
# the router's own real, structural execution boundary (WP-104): only the four
# fs.read_file/fs.list_dir/git.status/memory.retrieve PLAN_STEP_EXECUTORS entries, or
# memory.write for task creation, ever run real, external-I/O-touching code. This is
# deliberately narrower than main()'s own broad exception tuple, which additionally
# handles capabilities (email, calendar, browser, docker, desktop-app control, coding,
# job assistance) the router cannot reach at all -- listing those here would be a real,
# misleading claim of a failure mode this module can never actually hit.
_HANDLED_ROUTING_ERRORS = (
    JarvisError,
    PathOutsideAllowedScopeError,
    GitCommandFailedError,
    MemoryRecordNotFoundError,
    UnsupportedMemoryValueError,
    MemoryIntegrityViolationError,
    OSError,
    UnicodeDecodeError,
    KeyError,
    ValueError,
    sqlite3.Error,
)

# POST /api/tasks/<task_id>/run (WP-112) reaches authorize_and_run_task, which --
# unlike anything authorize_and_route itself can ever trigger -- genuinely runs a
# real plan, so a real PlanningError/PlanValidationError is a real, reachable
# failure mode here that _HANDLED_ROUTING_ERRORS's own narrower surface never
# needed to cover. Everything else this tuple already covers (memory-store/OS-level
# errors) applies equally, since both paths write through the same real store.
_HANDLED_TASK_RUN_ERRORS = (*_HANDLED_ROUTING_ERRORS, PlanningError, PlanValidationError)


@dataclass(frozen=True)
class UiServerConfig:
    """Real, fixed-for-the-server's-lifetime configuration for every request it handles.

    Attributes:
        chain_path: Where every real request's own audit record lands
            -- identical meaning to every other subcommand's
            `--chain-path` flag.
        physical_confirmation_available: Applied uniformly to every
            request this server handles for as long as it runs --
            **not** per-request, and **not** inferred from "this is a
            local request" (see module docstring's own reasoning:
            reusing the exact, existing, explicit flag semantics
            rather than inventing an implicit confirmation signal).
            Defaults to `False` everywhere this is constructed unless
            the operator explicitly launches `jarvis ui` with
            `--physical-confirmation-available` -- the same explicit,
            human-supplied opt-in every other subcommand already
            requires, never automatic.
        remote_confirmation_available: As above.
        database_path: Where the real memory store lives. `None`
            reaches the same real, existing default every other
            memory-touching subcommand already uses.
    """

    chain_path: Path
    physical_confirmation_available: bool
    remote_confirmation_available: bool
    database_path: Path | None = None


def _log_task_created(event: TaskCreated) -> None:
    """The one, minimal, real "future adapters" consumer this pass actually builds."""
    _logger.info("task event: TaskCreated task_id=%s status=%s", event.task_id, event.status)


def _log_task_status_changed(event: TaskStatusChanged) -> None:
    _logger.info(
        "task event: TaskStatusChanged task_id=%s %s -> %s",
        event.task_id,
        event.previous_status,
        event.new_status,
    )


class JarvisUiServer(HTTPServer):
    """A real, single-threaded, `127.0.0.1`-only HTTP server. See module docstring."""

    def __init__(self, server_address: tuple[str, int], config: UiServerConfig) -> None:
        """Store `config`, build one real, shared EventBus, then bind the real socket."""
        self.jarvis_config = config
        self.event_bus = EventBus()
        self.event_bus.subscribe(TaskCreated, _log_task_created)
        self.event_bus.subscribe(TaskStatusChanged, _log_task_status_changed)
        super().__init__(server_address, _JarvisUiRequestHandler)


def _summarize_memory_recall(result: MemoryRecallOutcome) -> str:
    """Render a real `memory.retrieve` result as chat text."""
    if not result.records:
        return "No matching memories found."
    shown = result.records[:_MAX_MEMORY_RECORDS_SHOWN]
    return "\n".join(f"- {record.value.value!r}" for record in shown)


def _summarize_file_read(result: FileReadOutcome) -> str | None:
    """Render a real `fs.read_file` result as chat text, truncated. `None` if no content."""
    if result.content is None:
        return None
    text = result.content.value
    if len(text) > _RESULT_TEXT_TRUNCATE_CHARS:
        return text[:_RESULT_TEXT_TRUNCATE_CHARS] + "\n... (truncated)"
    return text


def _summarize_dir_list(result: DirListOutcome) -> str | None:
    """Render a real `fs.list_dir` result as chat text. `None` if there were no entries."""
    if result.entries is None:
        return None
    if not result.entries:
        return "(empty directory)"
    return "\n".join(
        f"{tainted.value.name}{'/' if tainted.value.is_dir else ''}" for tainted in result.entries
    )


def _summarize_execution_result(capability_id: str, result: object) -> str:
    """Render one of the four real, wired PLAN_STEP_EXECUTORS results as chat text.

    A real, closed, exhaustive set -- `PLAN_STEP_EXECUTORS` (WP-104,
    `kernel/capability_dispatch.py`) has exactly four entries today,
    so this function's own four `isinstance` branches are a complete
    match, not a partial one that silently drops a fifth real shape.
    The fallback line only fires if that table itself grows without
    this function being updated alongside it -- a real, honest gap,
    not hidden.
    """
    if isinstance(result, MemoryRecallOutcome):
        return _summarize_memory_recall(result)
    if isinstance(result, FileReadOutcome):
        summary = _summarize_file_read(result)
        if summary is not None:
            return summary
    if isinstance(result, DirListOutcome):
        summary = _summarize_dir_list(result)
        if summary is not None:
            return summary
    if isinstance(result, GitStatusOutcome) and result.status is not None:
        return result.status
    return f"Ran {capability_id}."


def build_response_payload(outcome: RouteOutcome) -> dict[str, object]:
    """Translate one real `RouteOutcome` (WP-104) into this API's own real JSON shape.

    A pure function, deliberately -- directly unit-testable against a
    hand-built `RouteOutcome`, with no real HTTP/socket involved.

    Returns:
        A JSON-serializable dict with `type` (`"not_routed"` |
        `"unwired_capability"` | `"denied"` | `"task_created"` |
        `"response"`), a human-readable `message`, and the same real
        `route_kind`/`capability_id`/`task_id`/`task_status`/`granted`
        fields regardless of `type`, so a client never has to guess
        which fields exist for which type.
    """
    route = outcome.route
    payload: dict[str, object] = {
        "route_kind": route.kind.value,
        "capability_id": route.capability_id.value if route.capability_id is not None else None,
        "task_id": outcome.task_id,
        "task_status": None,
        "granted": outcome.decision.granted if outcome.decision is not None else None,
    }

    if outcome.decision is None:
        if route.kind == RouteKind.DETERMINISTIC_COMMAND:
            # A real, distinct case from genuine UNKNOWN -- see
            # kernel/router.py's own module docstring: the request was
            # confidently, correctly recognized, it just names a real
            # capability with no entry in PLAN_STEP_EXECUTORS yet.
            # Mirrors _print_do_outcome's own identical distinction in
            # cli/main.py -- reporting "I couldn't determine this"
            # here would be a real, honest-sounding lie.
            payload["type"] = "unwired_capability"
            payload["message"] = (
                f"I recognized this as {payload['capability_id']}, but it isn't wired for "
                "direct execution through this UI yet -- use its own dedicated command instead."
            )
            return payload
        payload["type"] = "not_routed"
        payload["message"] = route.detail or "I couldn't confidently determine what you meant."
        return payload

    if not outcome.decision.granted:
        payload["type"] = "denied"
        payload["message"] = f"That wasn't authorized (tier={outcome.decision.tier.name})."
        return payload

    if route.kind == RouteKind.COMPLEX_GOAL:
        payload["type"] = "task_created"
        payload["message"] = f"Created a task for: {route.goal}"
        # A real, always-true fact, not invented: authorize_and_create_task (WP-107)
        # always writes a brand-new task's status as "created" -- never anything
        # else -- so this is safe to state directly, with no extra real I/O (a
        # follow-up authorize_and_get_task call) needed to confirm it.
        payload["task_status"] = "created"
        return payload

    payload["type"] = "response"
    capability_id_text = route.capability_id.value if route.capability_id is not None else "?"
    payload["message"] = _summarize_execution_result(capability_id_text, outcome.execution_result)
    return payload


class _JarvisUiRequestHandler(BaseHTTPRequestHandler):
    """Exactly two real routes: `GET /` (the static page) and `POST /api/command`."""

    server: JarvisUiServer  # narrows the inherited, generically-typed `server` attribute

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 -- stdlib's own name
        """Route stdlib's default stderr access logging through this module's own logger."""
        _logger.debug("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:
        """Serve the one real static page, or a real task-status lookup. Anything else is a 404."""
        if self.path == "/":
            body = _INDEX_HTML_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith(_TASK_STATUS_PATH_PREFIX):
            task_id = self.path[len(_TASK_STATUS_PATH_PREFIX) :]
            self._handle_get_task_status(task_id)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"type": "error", "message": "Not found."})

    def _handle_get_task_status(self, task_id: str) -> None:
        """Handle `GET /api/tasks/<task_id>` -- a real, authoritative task-store read.

        No `EventBus` involvement at all: this always re-reads
        `kernel.tasks.authorize_and_get_task` directly, so a
        reconnected or refreshed browser gets the real, current answer
        regardless of any event it may have missed while disconnected
        (see module docstring's own "why this is not SSE" section).
        """
        if not task_id:
            self._send_json(HTTPStatus.NOT_FOUND, {"type": "error", "message": "Not found."})
            return
        config = self.server.jarvis_config
        get_outcome = authorize_and_get_task(
            task_id,
            physical_confirmation_available=config.physical_confirmation_available,
            remote_confirmation_available=config.remote_confirmation_available,
            chain_path=config.chain_path,
            database_path=config.database_path,
        )
        record = get_outcome.record
        if record is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"type": "error", "message": "No task found for this identifier."},
            )
            return
        data = record.value.value
        if not isinstance(data, dict):
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"type": "error", "message": "This task's own stored record is malformed."},
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "task_id": task_id,
                "goal": data.get("goal"),
                "status": data.get("status"),
                "reason": data.get("reason"),
            },
        )

    def do_POST(self) -> None:
        """Handle `POST /api/command` or `POST /api/tasks/<id>/run`. Never crashes the server."""
        if self.path == "/api/command":
            self._handle_post_command()
            return
        if self.path.startswith(_TASK_STATUS_PATH_PREFIX) and self.path.endswith(
            _TASK_RUN_PATH_SUFFIX
        ):
            task_id = self.path[len(_TASK_STATUS_PATH_PREFIX) : -len(_TASK_RUN_PATH_SUFFIX)]
            self._handle_run_task(task_id)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"type": "error", "message": "Not found."})

    def _handle_post_command(self) -> None:
        """Handle `POST /api/command`. Validates input; never lets an error crash the server."""
        text = self._read_and_validate_text()
        if text is None:
            return  # _read_and_validate_text already sent the real error response.

        config = self.server.jarvis_config
        try:
            outcome = asyncio.run(
                authorize_and_route(
                    text,
                    physical_confirmation_available=config.physical_confirmation_available,
                    remote_confirmation_available=config.remote_confirmation_available,
                    chain_path=config.chain_path,
                    database_path=config.database_path,
                    event_bus=self.server.event_bus,
                )
            )
        except _HANDLED_ROUTING_ERRORS as exc:
            _logger.warning("ui_server: command failed: %s", exc)
            self._send_json(HTTPStatus.BAD_REQUEST, {"type": "error", "message": str(exc)})
            return
        except Exception:
            # A real, final backstop -- never let one bad request take the whole server
            # down, and never leak a raw traceback to the browser (Step 8's own
            # explicit requirement).
            _logger.exception("ui_server: unexpected internal error handling a command")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"type": "error", "message": "An unexpected internal error occurred."},
            )
            return

        self._send_json(HTTPStatus.OK, build_response_payload(outcome))

    def _handle_run_task(self, task_id: str) -> None:
        """Handle `POST /api/tasks/<task_id>/run` (WP-112) -- reuses authorize_and_run_task unmodified.

        The real, current goal is looked up server-side first (never
        supplied by the browser) so a caller cannot run a real plan
        for a goal different from the one this task was actually
        created for. See module docstring's own WP-112 section.
        """  # noqa: E501
        if not task_id:
            self._send_json(HTTPStatus.NOT_FOUND, {"type": "error", "message": "Not found."})
            return

        config = self.server.jarvis_config
        get_outcome = authorize_and_get_task(
            task_id,
            physical_confirmation_available=config.physical_confirmation_available,
            remote_confirmation_available=config.remote_confirmation_available,
            chain_path=config.chain_path,
            database_path=config.database_path,
        )
        record = get_outcome.record
        if record is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"type": "error", "message": "No task found for this identifier."},
            )
            return
        data = record.value.value
        goal = data.get("goal") if isinstance(data, dict) else None
        if not isinstance(goal, str):
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"type": "error", "message": "This task's own stored record is malformed."},
            )
            return

        try:
            run_outcome = asyncio.run(
                authorize_and_run_task(
                    task_id,
                    goal,
                    physical_confirmation_available=config.physical_confirmation_available,
                    remote_confirmation_available=config.remote_confirmation_available,
                    chain_path=config.chain_path,
                    database_path=config.database_path,
                    event_bus=self.server.event_bus,
                )
            )
        except _HANDLED_TASK_RUN_ERRORS as exc:
            _logger.warning("ui_server: running task %s failed: %s", task_id, exc)
            self._send_json(HTTPStatus.BAD_REQUEST, {"type": "error", "message": str(exc)})
            return
        except Exception:
            _logger.exception("ui_server: unexpected internal error running task %s", task_id)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"type": "error", "message": "An unexpected internal error occurred."},
            )
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "task_id": task_id,
                "granted": run_outcome.decision.granted,
                "status": run_outcome.status,
                "reason": run_outcome.reason,
            },
        )

    def _read_and_validate_text(self) -> str | None:
        """Read and validate the real request body. Sends its own error response and returns None on failure."""  # noqa: E501
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = -1
        if length <= 0 or length > _MAX_REQUEST_BODY_BYTES:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"type": "error", "message": "Request body missing, empty, or too large."},
            )
            return None

        raw_body = self.rfile.read(length)
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"type": "error", "message": "Malformed JSON body."}
            )
            return None

        if not isinstance(parsed, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"type": "error", "message": "Expected a JSON object body."}
            )
            return None
        raw_text = parsed.get("text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"type": "error", "message": "Expected a non-empty 'text' field."},
            )
            return None
        return raw_text.strip()

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def create_server(port: int, config: UiServerConfig) -> JarvisUiServer:
    """Build a real, bound, not-yet-serving `JarvisUiServer` on `127.0.0.1:<port>`.

    Split from actually serving (see `run_ui_server`) so a test can
    bind a real, ephemeral port (`port=0`), read back the real,
    assigned port, and drive real HTTP requests against it without
    ever calling `serve_forever()`'s own blocking loop.
    """
    return JarvisUiServer(("127.0.0.1", port), config)


def run_ui_server(server: JarvisUiServer) -> None:
    """Serve `server` in the foreground until interrupted. Always closes the socket on exit."""
    try:
        server.serve_forever()
    finally:
        server.server_close()
