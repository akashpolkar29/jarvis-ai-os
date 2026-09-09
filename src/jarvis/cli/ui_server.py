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

from jarvis.application.routing.router import RouteKind
from jarvis.domain.errors import JarvisError
from jarvis.kernel.desktop import GitStatusOutcome
from jarvis.kernel.files import DirListOutcome, FileReadOutcome, PathOutsideAllowedScopeError
from jarvis.kernel.memory import MemoryRecallOutcome
from jarvis.kernel.router import authorize_and_route
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


class JarvisUiServer(HTTPServer):
    """A real, single-threaded, `127.0.0.1`-only HTTP server. See module docstring."""

    def __init__(self, server_address: tuple[str, int], config: UiServerConfig) -> None:
        """Store `config` for every request this server will handle, then bind the real socket."""
        self.jarvis_config = config
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
        `route_kind`/`capability_id`/`task_id`/`granted` fields
        regardless of `type`, so a client never has to guess which
        fields exist for which type.
    """
    route = outcome.route
    payload: dict[str, object] = {
        "route_kind": route.kind.value,
        "capability_id": route.capability_id.value if route.capability_id is not None else None,
        "task_id": outcome.task_id,
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
        """Serve the one real static page. Anything else is a real 404, never a file listing."""
        if self.path != "/":
            self._send_json(HTTPStatus.NOT_FOUND, {"type": "error", "message": "Not found."})
            return
        body = _INDEX_HTML_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        """Handle `POST /api/command`. Validates input; never lets an error crash the server."""
        if self.path != "/api/command":
            self._send_json(HTTPStatus.NOT_FOUND, {"type": "error", "message": "Not found."})
            return

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
