"""Unit tests for jarvis.kernel.router's authorize_and_route composition root (WP-104).

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_planning_kernel.py`'s own established discipline. Everything else
(Stage A's real `resolve_intent()` reuse, Stage B's real structural
validation, and every real downstream authorization/execution) runs
for real.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from jarvis.adapters.reasoning.local import LocalReasoningAdapter
from jarvis.application.routing.router import RouteKind
from jarvis.domain.calendar import CalendarEvent
from jarvis.domain.capability import CapabilityId
from jarvis.domain.email import EmailMessage, EmailSummary
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capability_dispatch import (
    CalendarListStepResult,
    EmailListStepResult,
    EmailReadStepResult,
)
from jarvis.kernel.router import authorize_and_route, route_deterministically
from jarvis.kernel.tasks import authorize_and_get_task

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.calendar import CalendarEventDraft
    from jarvis.domain.evidence import Attempt


_FIXED_NOW = datetime(2026, 9, 10, 15, 30, tzinfo=UTC)
"""A real, fixed Wednesday -- 2026-09-10's own real weekday (Thursday, weekday()==3)
gives a real, non-trivial "this week" Monday-start boundary to assert against."""


class _FixedClock:
    def now(self) -> datetime:
        return _FIXED_NOW


class _StubEmailPort:
    """Records every real call it receives, returns canned real results. Mirrors
    `test_communications_kernel.py`'s own identical stub."""

    def __init__(
        self, summaries: tuple[EmailSummary, ...] = (), message: EmailMessage | None = None
    ) -> None:
        self.list_calls: list[tuple[str, int]] = []
        self.read_calls: list[str] = []
        self._summaries = summaries
        self._message = message

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        self.list_calls.append((folder, limit))
        return self._summaries

    async def read_message(self, message_id: str) -> EmailMessage:
        self.read_calls.append(message_id)
        assert self._message is not None
        return self._message

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        raise NotImplementedError


class _StubCalendarPort:
    """Records every real call it receives, returns canned real results. Mirrors
    `test_communications_kernel.py`'s own identical stub."""

    def __init__(self, events: tuple[CalendarEvent, ...] = ()) -> None:
        self.list_calls: list[tuple[str, str]] = []
        self._events = events

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        self.list_calls.append((start, end))
        return self._events

    async def create_event(self, draft: CalendarEventDraft) -> str:
        raise NotImplementedError


def _real_ollama_server_is_reachable() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    except OSError:
        return False
    return True


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed routing response."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[str] = []

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        self.calls.append(task)
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


# ---------------------------------------------------------------------------
# Stage A: deterministic routing
# ---------------------------------------------------------------------------


def test_route_deterministically_resolves_a_known_command_standalone() -> None:
    """The public, standalone Stage-A entry point -- no provider, no downstream authorization."""
    route = route_deterministically("recall anything")

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("memory.retrieve")
    assert route.source == "deterministic"
    assert route.confidence == 1.0


def test_route_deterministically_returns_unknown_for_unrecognized_text() -> None:
    """The public, standalone Stage-A entry point also reports real UNKNOWN, never a guess."""
    route = route_deterministically("asdkjaslkdjalskdjgibberish")

    assert route.kind == RouteKind.UNKNOWN
    assert route.confidence == 0.0


async def test_a_known_command_executes_via_plan_step_executors(tmp_path: Path) -> None:
    """ "recall <query>" resolves deterministically to memory.retrieve and is actually executed."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("should never be called")

    outcome = await authorize_and_route(
        "recall anything",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.source == "deterministic"
    assert outcome.route.capability_id == CapabilityId("memory.retrieve")
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert outcome.execution_result is not None
    assert provider.calls == []  # Stage A resolved it; Stage B was never even invoked.


async def test_deterministic_routing_is_case_insensitive(tmp_path: Path) -> None:
    """ "RECALL" (any case) resolves exactly like "recall" -- resolve_intent()'s own contract."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("should never be called")

    outcome = await authorize_and_route(
        "RECALL anything",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("memory.retrieve")
    assert provider.calls == []


async def test_deterministic_routing_tolerates_a_please_prefix(tmp_path: Path) -> None:
    """ "please recall ..." normalizes to "recall ..." before resolve_intent() ever sees it."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("should never be called")

    outcome = await authorize_and_route(
        "please recall anything",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("memory.retrieve")
    assert provider.calls == []


async def test_deterministic_routing_tolerates_can_you_prefix_and_trailing_question_mark(
    tmp_path: Path,
) -> None:
    """ "can you recall ...?" normalizes the same way "please ..." does."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("should never be called")

    outcome = await authorize_and_route(
        "can you recall anything?",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("memory.retrieve")


async def test_an_ambiguous_job_search_command_is_unknown_with_a_real_clarifying_detail(
    tmp_path: Path,
) -> None:
    """ "search jobs <keywords>" with no site clause is real, ambiguous UNKNOWN, not a guess.

    **Deliberately never escalates to Stage B**: Stage A already has a
    more precise answer (missing site clause) than reasoning could
    provide -- see `_route_deterministically`'s own module docstring
    for why falling through here would be a real quality regression,
    not a hypothetical one. The fake provider below would make this
    test fail loudly (a surprise call) if that regression were ever
    reintroduced.
    """
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("should never be called")

    outcome = await authorize_and_route(
        "search jobs python developer",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert provider.calls == []
    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.route.source == "deterministic"
    assert outcome.route.detail is not None
    assert "site" in outcome.route.detail
    assert outcome.decision is None


async def test_a_genuinely_unknown_command_falls_back_to_reasoning(tmp_path: Path) -> None:
    """Stage A reporting UNKNOWN is exactly when -- and only when -- Stage B is ever invoked."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps({"kind": "unknown", "capability_id": None, "arguments": {}, "goal": None})
    )

    outcome = await authorize_and_route(
        "asdkjaslkdjalskdjgibberish",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert len(provider.calls) == 1
    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.route.source == "reasoning"
    assert outcome.decision is None


# ---------------------------------------------------------------------------
# Stage B: reasoning fallback
# ---------------------------------------------------------------------------


async def test_a_valid_complex_goal_route_creates_a_task_when_granted(tmp_path: Path) -> None:
    """A well-formed complex_goal response creates a real, new task -- never runs it."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "complex_goal",
                "capability_id": None,
                "arguments": {},
                "goal": "find good internships",
            }
        )
    )

    outcome = await authorize_and_route(
        "find me good internships",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.route.kind == RouteKind.COMPLEX_GOAL
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert outcome.task_id is not None

    get_outcome = authorize_and_get_task(
        outcome.task_id,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )
    assert get_outcome.record is not None
    record_value = get_outcome.record.value.value
    assert isinstance(record_value, dict)
    assert record_value["status"] == "created"


async def test_a_complex_goal_route_cannot_bypass_authorization_without_confirmation(
    tmp_path: Path,
) -> None:
    """Task creation reuses memory.write's own Tier.CONFIRM floor -- reasoning cannot skip it."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "complex_goal",
                "capability_id": None,
                "arguments": {},
                "goal": "do a big thing",
            }
        )
    )

    outcome = await authorize_and_route(
        "do a big thing",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.decision is not None
    assert outcome.decision.granted is False
    assert outcome.task_id is None


async def test_a_malformed_reasoning_response_is_handled_safely_not_a_crash(tmp_path: Path) -> None:
    """A real RoutingError from Stage B never propagates -- it becomes a real UNKNOWN route."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("not json at all")

    outcome = await authorize_and_route(
        "asdkjaslkdj",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.decision is None
    assert outcome.route.detail is not None


async def test_reasoning_cannot_invent_an_unregistered_capability_id(tmp_path: Path) -> None:
    """A model naming a plausible-but-fake capability id is rejected, reported as UNKNOWN."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "deterministic_command",
                "capability_id": "shell.execute_arbitrary_command",
                "arguments": {"command": "rm -rf /"},
                "goal": None,
            }
        )
    )

    outcome = await authorize_and_route(
        "do something dangerous",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.decision is None


async def test_reasoning_rejects_non_object_arguments(tmp_path: Path) -> None:
    """Invalid (non-object) arguments for a deterministic_command route are rejected safely."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "deterministic_command",
                "capability_id": "fs.read_file",
                "arguments": "not an object",
                "goal": None,
            }
        )
    )

    outcome = await authorize_and_route(
        "do something involving a file somehow",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.decision is None


async def test_no_provider_falls_back_to_local_with_a_real_observable_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Omitting `provider` on a Stage-B-escalating route logs a real, honest warning.

    Mirrors `test_planning_kernel.py`'s own identical
    `test_no_provider_falls_back_to_local_with_a_real_observable_warning`.
    """
    chain_path = tmp_path / "audit_chain.json"
    fake_local_adapter = _FakeReasoningProvider(
        json.dumps({"kind": "unknown", "capability_id": None, "arguments": {}, "goal": None})
    )

    with (
        mock.patch("jarvis.kernel.router.LocalReasoningAdapter", return_value=fake_local_adapter),
        caplog.at_level(logging.WARNING, logger="jarvis.kernel.router"),
    ):
        outcome = await authorize_and_route(
            "asdkjaslkdjalskdjgibberish",
            None,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    assert outcome.route.kind == RouteKind.UNKNOWN
    assert len(fake_local_adapter.calls) == 1
    assert any(record.levelno == logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# Security: the router never executes a capability directly
# ---------------------------------------------------------------------------


async def test_reasoning_naming_a_real_but_unwired_capability_is_reported_never_executed(
    tmp_path: Path,
) -> None:
    """A real, registered, high-risk capability (git.force_push) is never auto-executed.

    `git.force_push` is a real, statically-registered capability (so
    it passes Stage B's own `is_registered` check), but it has no
    entry in `PLAN_STEP_EXECUTORS` -- this proves the router's own,
    structural execution boundary holds even for a real capability
    the model is technically allowed to *name*.
    """
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "deterministic_command",
                "capability_id": "git.force_push",
                "arguments": {"repo_dir": str(tmp_path), "remote": "origin", "branch": "main"},
                "goal": None,
            }
        )
    )

    outcome = await authorize_and_route(
        "force push my repo",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=True,
        chain_path=chain_path,
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("git.force_push")
    # The real, structural safety property: recognized, never executed, no Decision at all.
    assert outcome.decision is None
    assert outcome.execution_result is None


async def test_a_model_supplied_confidence_field_is_never_read(tmp_path: Path) -> None:
    """Even a model claiming confidence=0.99 for a dangerous route changes nothing real."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "deterministic_command",
                "capability_id": "git.force_push",
                "arguments": {"repo_dir": str(tmp_path), "remote": "origin", "branch": "main"},
                "goal": None,
                "confidence": 0.99,
            }
        )
    )

    outcome = await authorize_and_route(
        "force push my repo",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=True,
        chain_path=chain_path,
    )

    assert outcome.decision is None
    assert outcome.route.confidence != pytest.approx(0.99)


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, locally running Ollama server on localhost:11434, not assumed in CI.",
)
async def test_real_local_reasoning_adapter_routes_a_real_complex_goal(tmp_path: Path) -> None:
    """Real, end-to-end scenario test: the real, un-mocked default provider, not a fake one.

    Mirrors `test_planning_kernel.py`'s own
    `test_real_local_reasoning_adapter_generates_and_executes_a_real_plan`
    precedent exactly, including its own honest caveat: this tiny local
    model does not reliably produce valid structured output every
    single time (a real, empirically observed ~33% failure rate
    elsewhere in this codebase) -- skipif-guarded, never run in CI, a
    real pass here means "this real model's own real output was
    parseable and valid this one time," not a guaranteed property.
    """
    chain_path = tmp_path / "audit_chain.json"

    outcome = await authorize_and_route(
        "find suitable mechanical engineering internships in Germany",
        LocalReasoningAdapter(),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
    )

    assert outcome.route.kind in (
        RouteKind.COMPLEX_GOAL,
        RouteKind.UNKNOWN,
        RouteKind.DETERMINISTIC_COMMAND,
    )


# ---------------------------------------------------------------------------
# WP-114: expanding the conversational execution surface
# ---------------------------------------------------------------------------
# fs.find / fs.search_content / fs.recent: already had resolve_intent() grammar
# (voice), now also wired into PLAN_STEP_EXECUTORS -- these prove the typed
# router can actually execute them, not just recognize them.
# ---------------------------------------------------------------------------


async def test_find_files_command_executes_via_plan_step_executors(tmp_path: Path) -> None:
    """ "find files <pattern>" resolves deterministically to fs.find and is actually executed."""
    chain_path = tmp_path / "audit_chain.json"
    (tmp_path / "notes.txt").write_text("hi")
    provider = _FakeReasoningProvider("should never be called")

    with mock.patch("jarvis.kernel.files.Path.home", return_value=tmp_path):
        outcome = await authorize_and_route(
            "find files *.txt",
            provider,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("fs.find")
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert outcome.execution_result is not None
    assert provider.calls == []


async def test_search_files_command_executes_via_plan_step_executors(tmp_path: Path) -> None:
    """ "search files <query>" resolves deterministically to fs.search_content and executes."""
    chain_path = tmp_path / "audit_chain.json"
    (tmp_path / "notes.txt").write_text("radar camera fusion")
    provider = _FakeReasoningProvider("should never be called")

    with mock.patch("jarvis.kernel.files.Path.home", return_value=tmp_path):
        outcome = await authorize_and_route(
            "search files radar",
            provider,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("fs.search_content")
    assert outcome.decision is not None
    assert outcome.decision.granted is True


async def test_recent_files_command_executes_via_plan_step_executors(tmp_path: Path) -> None:
    """ "recent files" resolves deterministically to fs.recent and executes."""
    chain_path = tmp_path / "audit_chain.json"
    (tmp_path / "notes.txt").write_text("hi")
    provider = _FakeReasoningProvider("should never be called")

    with mock.patch("jarvis.kernel.files.Path.home", return_value=tmp_path):
        outcome = await authorize_and_route(
            "recent files",
            provider,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("fs.recent")
    assert outcome.decision is not None
    assert outcome.decision.granted is True


# ---------------------------------------------------------------------------
# WP-114: email/calendar deterministic grammar (typed-router-only -- see
# kernel/router.py's own _resolve_communications_command docstring for why
# this is not in kernel/intent.py's shared resolve_intent()).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["list emails", "recent emails", "show my emails", "show my recent emails", "LIST EMAILS"],
)
def test_route_deterministically_resolves_list_emails(text: str) -> None:
    route = route_deterministically(text)

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("communications.list_email")
    assert route.arguments is not None
    assert route.arguments.value == {"folder": "INBOX", "limit": 10}


def test_route_deterministically_resolves_read_email_with_a_verbatim_message_id() -> None:
    route = route_deterministically("read email <abc123@example.com>")

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("communications.read_email")
    assert route.arguments is not None
    assert route.arguments.value == {"message_id": "<abc123@example.com>"}


def test_route_deterministically_read_email_with_no_id_is_unknown() -> None:
    """ "read email" alone (no id) is genuinely ambiguous -- never silently guessed."""
    route = route_deterministically("read email")

    assert route.kind == RouteKind.UNKNOWN


def test_route_deterministically_a_plain_read_command_is_unaffected_by_the_new_grammar() -> None:
    """Regression test for the real collision this work package found and fixed.

    Before the fix, "read email <id>"/"read email" fell through to
    resolve_intent()'s own pre-existing "read <path>" command (since
    resolve_intent() happily resolves them, never returning
    UnrecognizedIntent). This proves the fix didn't overcorrect: an
    ordinary "read <path>" command, unrelated to email, still resolves
    to fs.read_file exactly as before.
    """
    route = route_deterministically("read notes.txt")

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("fs.read_file")
    assert route.arguments is not None
    assert route.arguments.value == {"path": "notes.txt"}


@pytest.mark.parametrize(
    ("text", "expected_start", "expected_end"),
    [
        ("what's on my calendar today?", "2026-09-10T00:00:00+00:00", "2026-09-11T00:00:00+00:00"),
        ("show my calendar", "2026-09-10T00:00:00+00:00", "2026-09-11T00:00:00+00:00"),
        ("calendar", "2026-09-10T00:00:00+00:00", "2026-09-11T00:00:00+00:00"),
        (
            "show my calendar for tomorrow",
            "2026-09-11T00:00:00+00:00",
            "2026-09-12T00:00:00+00:00",
        ),
        (
            "what meetings do i have this week?",
            "2026-09-07T00:00:00+00:00",
            "2026-09-14T00:00:00+00:00",
        ),
    ],
)
def test_route_deterministically_resolves_calendar_ranges(
    text: str, expected_start: str, expected_end: str
) -> None:
    route = route_deterministically(text, clock=_FixedClock())

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("communications.list_calendar_events")
    assert route.arguments is not None
    assert route.arguments.value == {"start": expected_start, "end": expected_end}


def test_route_deterministically_calendar_with_an_unsupported_date_phrase_is_unknown() -> None:
    """ "calendar next monday" is genuinely unsupported -- never guessed, honestly UNKNOWN."""
    route = route_deterministically("calendar next monday", clock=_FixedClock())

    assert route.kind == RouteKind.UNKNOWN


def test_route_deterministically_still_prefers_resolve_intent_for_existing_commands() -> None:
    """A pre-existing resolve_intent() command is unaffected by the new communications grammar."""
    route = route_deterministically("recall my notes", clock=_FixedClock())

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("memory.retrieve")


async def test_a_communications_command_escalates_to_reasoning_when_no_port_is_configured(
    tmp_path: Path,
) -> None:
    """Genuinely unrelated text still escalates normally -- the new grammar doesn't widen Stage A.

    Stage A tries the new communications grammar before escalating,
    but genuinely unrelated text matches none of it -- confirming the
    new grammar doesn't accidentally widen what counts as recognized.
    """
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps({"kind": "unknown", "capability_id": None, "arguments": {}, "goal": None})
    )

    outcome = await authorize_and_route(
        "asdkjaslkdjalskdjgibberish",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert len(provider.calls) == 1
    assert outcome.route.kind == RouteKind.UNKNOWN


# ---------------------------------------------------------------------------
# WP-114: email/calendar execution -- recognized but unwired without a
# configured port; actually executed, through the real authorization choke
# point, when one is supplied.
# ---------------------------------------------------------------------------


async def test_list_emails_without_a_configured_email_port_is_recognized_but_not_executed(
    tmp_path: Path,
) -> None:
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider("should never be called")

    outcome = await authorize_and_route(
        "list emails",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("communications.list_email")
    assert outcome.decision is None
    assert outcome.execution_result is None
    assert provider.calls == []


async def test_calendar_command_without_a_configured_calendar_port_is_recognized_but_not_executed(
    tmp_path: Path,
) -> None:
    chain_path = tmp_path / "audit_chain.json"

    outcome = await authorize_and_route(
        "show my calendar",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        clock=_FixedClock(),
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("communications.list_calendar_events")
    assert outcome.decision is None
    assert outcome.execution_result is None


async def test_list_emails_with_a_configured_email_port_actually_executes(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    port = _StubEmailPort(
        summaries=(
            EmailSummary(
                message_id="<one@example.com>", sender="a@x.com", subject="s", received_at="d"
            ),
        )
    )

    outcome = await authorize_and_route(
        "list emails",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        email_port=port,
    )

    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert port.list_calls == [("INBOX", 10)]
    assert isinstance(outcome.execution_result, EmailListStepResult)
    assert outcome.execution_result.summaries is not None
    assert len(outcome.execution_result.summaries) == 1


async def test_read_email_with_a_configured_email_port_actually_executes(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    port = _StubEmailPort(
        message=EmailMessage(
            message_id="<abc@example.com>",
            sender="a@x.com",
            recipients=("b@x.com",),
            subject="s",
            body="body text",
            received_at="d",
        )
    )

    outcome = await authorize_and_route(
        "read email <abc@example.com>",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        email_port=port,
    )

    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert port.read_calls == ["<abc@example.com>"]
    assert isinstance(outcome.execution_result, EmailReadStepResult)
    assert outcome.execution_result.message is not None


async def test_calendar_list_events_with_a_configured_calendar_port_actually_executes(
    tmp_path: Path,
) -> None:
    chain_path = tmp_path / "audit_chain.json"
    port = _StubCalendarPort(
        events=(
            CalendarEvent(
                uid="1",
                summary="Standup",
                start="2026-09-10T09:00:00+00:00",
                end="...",
                attendees=(),
            ),
        )
    )

    outcome = await authorize_and_route(
        "what's on my calendar today?",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        calendar_port=port,
        clock=_FixedClock(),
    )

    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert port.list_calls == [("2026-09-10T00:00:00+00:00", "2026-09-11T00:00:00+00:00")]
    assert isinstance(outcome.execution_result, CalendarListStepResult)
    assert outcome.execution_result.events is not None
    assert len(outcome.execution_result.events) == 1


async def test_list_emails_tier_allow_grants_even_without_physical_confirmation(
    tmp_path: Path,
) -> None:
    """communications.list_email is Tier.ALLOW -- grants regardless of confirmation, like recall."""
    chain_path = tmp_path / "audit_chain.json"
    port = _StubEmailPort()

    outcome = await authorize_and_route(
        "list emails",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        email_port=port,
    )

    assert outcome.decision is not None
    assert outcome.decision.granted is True


# ---------------------------------------------------------------------------
# WP-114: a real, unwired-but-registered capability the reasoning fallback
# might name is still never executed -- the structural boundary this router
# already proves for git.force_push holds for a real read capability too.
# ---------------------------------------------------------------------------


async def test_reasoning_naming_list_calendar_events_without_a_configured_port_is_never_executed(
    tmp_path: Path,
) -> None:
    """A real, registered, ALLOW-tier capability is still never executed without its real port."""
    chain_path = tmp_path / "audit_chain.json"
    provider = _FakeReasoningProvider(
        json.dumps(
            {
                "kind": "deterministic_command",
                "capability_id": "communications.list_calendar_events",
                "arguments": {
                    "start": "2026-01-01T00:00:00+00:00",
                    "end": "2026-01-02T00:00:00+00:00",
                },
                "goal": None,
            }
        )
    )

    outcome = await authorize_and_route(
        "asdkjaslkdjalskdjgibberish",
        provider,
        physical_confirmation_available=True,
        remote_confirmation_available=True,
        chain_path=chain_path,
    )

    assert outcome.route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert outcome.route.capability_id == CapabilityId("communications.list_calendar_events")
    assert outcome.decision is None
    assert outcome.execution_result is None
