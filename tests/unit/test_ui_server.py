"""Unit/integration tests for jarvis.cli.ui_server (WP-108).

Most tests monkeypatch ``jarvis.cli.ui_server.authorize_and_route``
directly (mirroring ``test_cli_main.py``'s own established pattern for
``do``), keeping them fast, deterministic, and independent of a real
local Ollama server. One real, unmocked integration test
(:func:`test_real_server_routes_a_deterministic_command_through_the_real_router`)
proves the HTTP boundary genuinely uses the real, existing
``authorize_and_route`` -- using only deterministic input, so it never
needs a real reasoning provider and is never skip-gated.
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from jarvis.application.planning.planner import PlanningError
from jarvis.application.routing.router import RouteKind, RouteResult
from jarvis.cli.ui_server import (
    UiServerConfig,
    _summarize_execution_result,
    build_response_payload,
    create_server,
    run_ui_server,
)
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.events import TaskCreated, TaskStatusChanged
from jarvis.domain.file_system import DirEntry
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.desktop import GitStatusOutcome
from jarvis.kernel.files import DirListOutcome, FileReadOutcome, PathOutsideAllowedScopeError
from jarvis.kernel.memory import MemoryRecallOutcome
from jarvis.kernel.router import RouteOutcome
from jarvis.kernel.tasks import TaskGetOutcome, TaskRunOutcome, authorize_and_create_task

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from jarvis.cli.ui_server import JarvisUiServer

_OVERSIZED_TEXT_LENGTH = 20000


def _make_decision(*, granted: bool, tier: Tier = Tier.CONFIRM) -> Decision:
    descriptor = CapabilityDescriptor(
        id=CapabilityId("test.capability"), effects=Effect.WRITE_LOCAL, description="Test."
    )
    invocation = CapabilityInvocation(descriptor, Tainted({}, Provenance.user()))
    return Decision(
        tier=tier, granted=granted, reasons=DecisionReason.BASE_TIER, invocation=invocation
    )


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[tuple[str, JarvisUiServer]]:
    """A real, running JarvisUiServer on an ephemeral 127.0.0.1 port. Shut down after the test."""
    config = UiServerConfig(
        chain_path=tmp_path / "audit_chain.json",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        database_path=tmp_path / "memory.sqlite3",
    )
    server = create_server(0, config)
    port = server.server_address[1]
    thread = threading.Thread(target=run_ui_server, args=(server,), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", server
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _post(
    base_url: str, body: bytes | None, *, content_type: str | None = "application/json"
) -> tuple[int, dict[str, object]]:
    headers = {"Content-Type": content_type} if content_type else {}
    req = urllib.request.Request(
        f"{base_url}/api/command", data=body, method="POST", headers=headers
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# Real, unmocked integration test -- proves the HTTP boundary uses the real router.
# ---------------------------------------------------------------------------


def test_real_server_routes_a_deterministic_command_through_the_real_router(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    """A real HTTP request reaches the real, unmocked authorize_and_route/resolve_intent path."""
    base_url, _server = running_server

    status, data = _post(base_url, json.dumps({"text": "recall anything"}).encode())

    assert status == HTTPStatus.OK
    assert data["route_kind"] == "deterministic_command"
    assert data["capability_id"] == "memory.retrieve"
    assert data["type"] == "response"
    assert data["granted"] is True


def test_real_server_reports_a_recognized_but_unwired_capability(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    """A real, deterministically-resolved-but-unwired command (ping) is reported, not executed."""
    base_url, _server = running_server

    status, data = _post(base_url, json.dumps({"text": "ping"}).encode())

    assert status == HTTPStatus.OK
    assert data["type"] == "unwired_capability"
    assert data["capability_id"] == "ping"
    assert data["granted"] is None


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


def test_get_root_serves_the_real_static_page(running_server: tuple[str, JarvisUiServer]) -> None:
    base_url, _server = running_server

    resp = urllib.request.urlopen(f"{base_url}/", timeout=5)

    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Type"] == "text/html; charset=utf-8"
    body = resp.read().decode("utf-8")
    assert "JARVIS" in body


def test_get_unknown_path_returns_404(running_server: tuple[str, JarvisUiServer]) -> None:
    base_url, _server = running_server

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{base_url}/nonexistent", timeout=5)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_post_to_an_unknown_path_returns_404(running_server: tuple[str, JarvisUiServer]) -> None:
    base_url, _server = running_server
    req = urllib.request.Request(f"{base_url}/nonexistent", data=b"{}", method="POST")

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# POST /api/command -- request validation
# ---------------------------------------------------------------------------


def test_post_command_missing_body_returns_400(running_server: tuple[str, JarvisUiServer]) -> None:
    base_url, _server = running_server

    status, data = _post(base_url, None, content_type=None)

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"


def test_post_command_empty_text_returns_400(running_server: tuple[str, JarvisUiServer]) -> None:
    base_url, _server = running_server

    status, data = _post(base_url, json.dumps({"text": "   "}).encode())

    assert status == HTTPStatus.BAD_REQUEST
    assert "text" in str(data["message"])


def test_post_command_missing_text_field_returns_400(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    status, data = _post(base_url, json.dumps({"not_text": "x"}).encode())

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"


def test_post_command_non_object_body_returns_400(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    status, data = _post(base_url, json.dumps(["not", "an", "object"]).encode())

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"


def test_post_command_malformed_json_returns_400(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    status, data = _post(base_url, b"not json at all")

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"


def test_post_command_oversized_body_returns_400(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server
    huge_text = "a" * _OVERSIZED_TEXT_LENGTH

    status, data = _post(base_url, json.dumps({"text": huge_text}).encode())

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"


# ---------------------------------------------------------------------------
# POST /api/command -- error handling for a real, raised exception
# ---------------------------------------------------------------------------


def test_post_command_never_leaks_a_traceback_on_an_unexpected_error(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    """An unexpected, non-listed exception is a clean 500, never a raw traceback."""
    base_url, _server = running_server

    with mock.patch(
        "jarvis.cli.ui_server.authorize_and_route", side_effect=RuntimeError("boom, unexpected")
    ):
        status, data = _post(base_url, json.dumps({"text": "recall anything"}).encode())

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert data["type"] == "error"
    assert "boom" not in str(data["message"])
    assert "Traceback" not in str(data["message"])


def test_post_command_reports_a_handled_kernel_error_cleanly(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    """A real, listed exception (e.g. PathOutsideAllowedScopeError) becomes a clean 400."""
    base_url, _server = running_server

    with mock.patch(
        "jarvis.cli.ui_server.authorize_and_route",
        side_effect=PathOutsideAllowedScopeError("out of scope"),
    ):
        status, data = _post(base_url, json.dumps({"text": "read /etc/hostname"}).encode())

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"
    assert "out of scope" in str(data["message"])


def test_post_command_full_round_trip_for_a_task_created_response(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    """A real HTTP round trip through a granted COMPLEX_GOAL route reports task_created."""
    base_url, _server = running_server
    route = RouteResult(
        kind=RouteKind.COMPLEX_GOAL,
        original_input="find good internships",
        confidence=0.5,
        source="reasoning",
        goal="find good internships",
    )
    outcome = RouteOutcome(
        route=route,
        decision=_make_decision(granted=True),
        execution_result=None,
        task_id="mem:123",
    )

    async def fake_authorize_and_route(*_args: object, **_kwargs: object) -> RouteOutcome:
        return outcome

    with mock.patch("jarvis.cli.ui_server.authorize_and_route", fake_authorize_and_route):
        status, data = _post(base_url, json.dumps({"text": "find good internships"}).encode())

    assert status == HTTPStatus.OK
    assert data["type"] == "task_created"
    assert data["task_id"] == "mem:123"
    assert data["task_status"] == "created"


# ---------------------------------------------------------------------------
# WP-111: GET /api/tasks/<task_id> -- real task-status recovery
# ---------------------------------------------------------------------------


def test_get_task_status_returns_404_for_an_unknown_task_id(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{base_url}/api/tasks/no-such-task", timeout=5)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_get_task_status_returns_404_for_an_empty_task_id(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{base_url}/api/tasks/", timeout=5)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_get_task_status_recovers_a_real_task_created_outside_this_http_request(
    running_server: tuple[str, JarvisUiServer], tmp_path: Path
) -> None:
    """A real task created via a direct kernel call is correctly recovered by a real GET.

    Proves Step 12's own "browser reconnects" requirement directly: the
    server never saw this task get created (no `/api/command` call was
    ever made for it) -- `GET /api/tasks/<id>` still reports its real,
    current, authoritative status, because it re-reads the real,
    shared task store directly, never relying on any event the server
    itself happened to observe.
    """
    base_url, _server = running_server
    create_outcome = authorize_and_create_task(
        "a real, independently-created task",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
    )
    assert create_outcome.task_id is not None

    resp = urllib.request.urlopen(f"{base_url}/api/tasks/{create_outcome.task_id}", timeout=5)
    data = json.loads(resp.read())

    assert resp.status == HTTPStatus.OK
    assert data["task_id"] == create_outcome.task_id
    assert data["goal"] == "a real, independently-created task"
    assert data["status"] == "created"
    assert data["reason"] is None


def test_get_task_status_reports_a_clean_500_for_a_malformed_stored_record(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    """A defensive branch: a task record whose value isn't a dict is reported, not crashed on."""
    base_url, _server = running_server
    malformed_record = MemoryRecord(
        identifier="mem:weird",
        value=Tainted("not a dict", Provenance.user()),
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=None,
    )
    fake_outcome = TaskGetOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW), record=malformed_record
    )

    with (
        mock.patch("jarvis.cli.ui_server.authorize_and_get_task", return_value=fake_outcome),
        pytest.raises(urllib.error.HTTPError) as exc_info,
    ):
        urllib.request.urlopen(f"{base_url}/api/tasks/mem:weird", timeout=5)

    assert exc_info.value.code == HTTPStatus.INTERNAL_SERVER_ERROR
    data = json.loads(exc_info.value.read())
    assert data["type"] == "error"


# ---------------------------------------------------------------------------
# WP-112: POST /api/tasks/<task_id>/run -- runs an already-created task
# ---------------------------------------------------------------------------


def _post_run(base_url: str, task_id: str) -> tuple[int, dict[str, object]]:
    req = urllib.request.Request(f"{base_url}/api/tasks/{task_id}/run", data=b"", method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_post_run_task_returns_404_for_an_unknown_task_id(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    status, data = _post_run(base_url, "no-such-task")

    assert status == HTTPStatus.NOT_FOUND
    assert data["type"] == "error"


def test_post_run_task_returns_404_for_an_empty_task_id(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server

    status, data = _post_run(base_url, "")

    assert status == HTTPStatus.NOT_FOUND
    assert data["type"] == "error"


def test_post_run_task_real_round_trip_looks_up_the_real_goal_and_runs_it(
    running_server: tuple[str, JarvisUiServer], tmp_path: Path
) -> None:
    """A real task, created independently, is looked up and run -- authorize_and_run_task mocked.

    Mocking `authorize_and_run_task` keeps this test hermetic
    (independent of a real local Ollama server), but `authorize_and_get_task`
    is completely real -- proving the endpoint's own real goal lookup
    against a real, independently-created task record.
    """
    base_url, _server = running_server
    create_outcome = authorize_and_create_task(
        "a real, independently-created task",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
    )
    assert create_outcome.task_id is not None

    received: list[tuple[str, str]] = []

    async def fake_authorize_and_run_task(
        task_id: str, goal: str, *_args: object, **_kwargs: object
    ) -> TaskRunOutcome:
        received.append((task_id, goal))
        return TaskRunOutcome(
            decision=_make_decision(granted=True), status="completed", reason=None
        )

    with mock.patch("jarvis.cli.ui_server.authorize_and_run_task", fake_authorize_and_run_task):
        status, data = _post_run(base_url, create_outcome.task_id)

    assert status == HTTPStatus.OK
    assert data["task_id"] == create_outcome.task_id
    assert data["granted"] is True
    assert data["status"] == "completed"
    assert received == [(create_outcome.task_id, "a real, independently-created task")]


def test_post_run_task_reports_a_handled_planning_error_cleanly(
    running_server: tuple[str, JarvisUiServer], tmp_path: Path
) -> None:
    base_url, _server = running_server
    create_outcome = authorize_and_create_task(
        "an impossible goal",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
    )
    assert create_outcome.task_id is not None

    async def failing_authorize_and_run_task(*_args: object, **_kwargs: object) -> TaskRunOutcome:
        raise PlanningError("the provider's response was not valid JSON")

    with mock.patch("jarvis.cli.ui_server.authorize_and_run_task", failing_authorize_and_run_task):
        status, data = _post_run(base_url, create_outcome.task_id)

    assert status == HTTPStatus.BAD_REQUEST
    assert data["type"] == "error"
    assert "not valid JSON" in str(data["message"])


def test_post_run_task_never_leaks_a_traceback_on_an_unexpected_error(
    running_server: tuple[str, JarvisUiServer], tmp_path: Path
) -> None:
    base_url, _server = running_server
    create_outcome = authorize_and_create_task(
        "a goal",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
    )
    assert create_outcome.task_id is not None

    async def failing_authorize_and_run_task(*_args: object, **_kwargs: object) -> TaskRunOutcome:
        raise RuntimeError("boom, unexpected")

    with mock.patch("jarvis.cli.ui_server.authorize_and_run_task", failing_authorize_and_run_task):
        status, data = _post_run(base_url, create_outcome.task_id)

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert data["type"] == "error"
    assert "boom" not in str(data["message"])


def test_post_run_task_reports_a_clean_500_for_a_malformed_stored_record(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    base_url, _server = running_server
    malformed_record = MemoryRecord(
        identifier="mem:weird",
        value=Tainted("not a dict", Provenance.user()),
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=None,
    )
    fake_outcome = TaskGetOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW), record=malformed_record
    )

    with mock.patch("jarvis.cli.ui_server.authorize_and_get_task", return_value=fake_outcome):
        status, data = _post_run(base_url, "mem:weird")

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert data["type"] == "error"


# ---------------------------------------------------------------------------
# WP-111: JarvisUiServer owns one real, shared EventBus with real subscribers
# ---------------------------------------------------------------------------


def test_server_event_bus_has_a_real_subscriber_for_task_created(
    running_server: tuple[str, JarvisUiServer], caplog: pytest.LogCaptureFixture
) -> None:
    """Proves the wiring is real: publishing directly to the server's own bus is observed."""
    _base_url, server = running_server
    event = TaskCreated(
        event_id="evt:1", task_id="mem:1", goal="test goal", status="created", timestamp="t1"
    )

    with caplog.at_level("INFO", logger="jarvis.cli.ui_server"):
        server.event_bus.publish(event)

    assert any("TaskCreated" in record.getMessage() for record in caplog.records)


def test_server_event_bus_has_a_real_subscriber_for_task_status_changed(
    running_server: tuple[str, JarvisUiServer], caplog: pytest.LogCaptureFixture
) -> None:
    _base_url, server = running_server
    event = TaskStatusChanged(
        event_id="evt:2",
        task_id="mem:1",
        goal="test goal",
        previous_status="created",
        new_status="running",
        reason=None,
        timestamp="t2",
    )

    with caplog.at_level("INFO", logger="jarvis.cli.ui_server"):
        server.event_bus.publish(event)

    assert any("TaskStatusChanged" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# build_response_payload -- pure, hand-constructed RouteOutcome tests
# ---------------------------------------------------------------------------


def test_build_response_payload_for_unknown_route() -> None:
    route = RouteResult(
        kind=RouteKind.UNKNOWN,
        original_input="asdf",
        confidence=0.0,
        source="deterministic",
        detail="No known deterministic command matched this request.",
    )
    outcome = RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)

    payload = build_response_payload(outcome)

    assert payload["type"] == "not_routed"
    assert payload["message"] == "No known deterministic command matched this request."
    assert payload["granted"] is None


def test_build_response_payload_for_a_denied_task_creation() -> None:
    route = RouteResult(
        kind=RouteKind.COMPLEX_GOAL,
        original_input="do a big thing",
        confidence=0.5,
        source="reasoning",
        goal="do a big thing",
    )
    outcome = RouteOutcome(
        route=route, decision=_make_decision(granted=False), execution_result=None, task_id=None
    )

    payload = build_response_payload(outcome)

    assert payload["type"] == "denied"
    assert payload["granted"] is False


def test_build_response_payload_for_a_granted_task_creation() -> None:
    route = RouteResult(
        kind=RouteKind.COMPLEX_GOAL,
        original_input="find good internships",
        confidence=0.5,
        source="reasoning",
        goal="find good internships",
    )
    outcome = RouteOutcome(
        route=route,
        decision=_make_decision(granted=True),
        execution_result=None,
        task_id="mem:123",
    )

    payload = build_response_payload(outcome)

    assert payload["type"] == "task_created"
    assert payload["task_id"] == "mem:123"
    assert payload["task_status"] == "created"
    assert "find good internships" in str(payload["message"])


def test_build_response_payload_task_status_is_none_for_non_task_routes() -> None:
    route = RouteResult(
        kind=RouteKind.UNKNOWN,
        original_input="asdf",
        confidence=0.0,
        source="deterministic",
        detail="No known deterministic command matched this request.",
    )
    outcome = RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)

    payload = build_response_payload(outcome)

    assert payload["task_status"] is None


def test_build_response_payload_for_a_recognized_but_unwired_capability() -> None:
    route = RouteResult(
        kind=RouteKind.DETERMINISTIC_COMMAND,
        original_input="force push my repo",
        confidence=0.5,
        source="reasoning",
        capability_id=CapabilityId("git.force_push"),
        arguments=Tainted({}, Provenance.user()),
    )
    outcome = RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)

    payload = build_response_payload(outcome)

    assert payload["type"] == "unwired_capability"
    assert payload["capability_id"] == "git.force_push"
    assert payload["granted"] is None


# ---------------------------------------------------------------------------
# _summarize_execution_result -- one real branch per PLAN_STEP_EXECUTORS entry
# ---------------------------------------------------------------------------


def _make_memory_record(value: object) -> MemoryRecord:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MemoryRecord(
        identifier="mem:1", value=Tainted(value, Provenance.user()), written_at=now, expires_at=None
    )


def test_summarize_execution_result_for_memory_recall_with_records() -> None:
    result = MemoryRecallOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW),
        records=(_make_memory_record("hello"), _make_memory_record({"kind": "task"})),
    )

    summary = _summarize_execution_result("memory.retrieve", result)

    assert "hello" in summary
    assert "task" in summary


def test_summarize_execution_result_for_memory_recall_with_no_records() -> None:
    result = MemoryRecallOutcome(decision=_make_decision(granted=True, tier=Tier.ALLOW), records=())

    summary = _summarize_execution_result("memory.retrieve", result)

    assert summary == "No matching memories found."


def test_summarize_execution_result_for_a_short_file_read() -> None:
    result = FileReadOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW),
        content=Tainted("short content", Provenance.user()),
    )

    summary = _summarize_execution_result("fs.read_file", result)

    assert summary == "short content"


def test_summarize_execution_result_truncates_a_long_file_read() -> None:
    long_text = "a" * 5000
    result = FileReadOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW),
        content=Tainted(long_text, Provenance.user()),
    )

    summary = _summarize_execution_result("fs.read_file", result)

    assert summary.endswith("... (truncated)")
    assert len(summary) < len(long_text)


def test_summarize_execution_result_for_a_denied_file_read_falls_back() -> None:
    result = FileReadOutcome(decision=_make_decision(granted=False, tier=Tier.ALLOW), content=None)

    summary = _summarize_execution_result("fs.read_file", result)

    assert summary == "Ran fs.read_file."


def test_summarize_execution_result_for_a_non_empty_dir_list() -> None:
    result = DirListOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW),
        entries=(
            Tainted(DirEntry(name="a.txt", is_dir=False), Provenance.user()),
            Tainted(DirEntry(name="sub", is_dir=True), Provenance.user()),
        ),
    )

    summary = _summarize_execution_result("fs.list_dir", result)

    assert "a.txt" in summary
    assert "sub/" in summary


def test_summarize_execution_result_for_a_denied_dir_list_falls_back() -> None:
    result = DirListOutcome(decision=_make_decision(granted=False, tier=Tier.ALLOW), entries=None)

    summary = _summarize_execution_result("fs.list_dir", result)

    assert summary == "Ran fs.list_dir."


def test_summarize_execution_result_for_an_empty_dir_list() -> None:
    result = DirListOutcome(decision=_make_decision(granted=True, tier=Tier.ALLOW), entries=())

    summary = _summarize_execution_result("fs.list_dir", result)

    assert summary == "(empty directory)"


def test_summarize_execution_result_for_git_status() -> None:
    result = GitStatusOutcome(
        decision=_make_decision(granted=True, tier=Tier.ALLOW), status="On branch main\n"
    )

    summary = _summarize_execution_result("git.status", result)

    assert summary == "On branch main\n"


def test_summarize_execution_result_falls_back_for_an_unrecognized_result_shape() -> None:
    summary = _summarize_execution_result("some.capability", object())

    assert summary == "Ran some.capability."


# ---------------------------------------------------------------------------
# A malformed Content-Length header -- needs a raw socket, urllib can't send one.
# ---------------------------------------------------------------------------


def test_post_command_with_a_malformed_content_length_header_returns_400(
    running_server: tuple[str, JarvisUiServer],
) -> None:
    _base_url, server = running_server
    port = server.server_address[1]

    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        request = (
            "POST /api/command HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Length: not-a-number\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("utf-8"))
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk

    status_line = response.split(b"\r\n", 1)[0].decode("utf-8")
    assert " 400 " in status_line
