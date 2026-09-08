"""Unit tests for jarvis.kernel.job_application: a real, thin convention on top of memory.

Mirrors ``tests/unit/test_memory_kernel.py``'s own fixture shape --
these fakes are duplicated here rather than imported, matching this
codebase's own established per-test-file convention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from jarvis.application.memory.writer import MEMORY_WRITE_CAPABILITY_ID
from jarvis.domain.capability import Effect, Tier
from jarvis.kernel.job_application import (
    VALID_JOB_APPLICATION_STATUSES,
    JobApplicationListOutcome,
    authorize_and_list_job_applications,
    authorize_and_record_job_application,
)
from jarvis.kernel.memory import MemoryWriteOutcome, authorize_and_remember

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 9, 8, tzinfo=UTC)
_ALL_RECORDS_COUNT = 3


class _FakeEmbeddingPort:
    """Maps every text to the same vector -- similarity ranking is not what these tests check."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeClock:
    def __init__(self, now: datetime = _NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class _SequentialIdPort:
    def __init__(self) -> None:
        self._counter = 0

    def new_id(self) -> str:
        self._counter += 1
        return f"mem:{self._counter}"


def _record(  # noqa: PLR0913 -- one per fake-fixture pass-through
    tmp_path: Path,
    company: str,
    role: str,
    *,
    status: str,
    folder: str | None = None,
    notes: str | None = None,
    id_port: _SequentialIdPort | None = None,
) -> MemoryWriteOutcome:
    return authorize_and_record_job_application(
        company,
        role,
        status=status,
        folder=folder,
        notes=notes,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port or _SequentialIdPort(),
    )


def _list(tmp_path: Path, *, status: str | None = None) -> JobApplicationListOutcome:
    return authorize_and_list_job_applications(
        status=status,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )


def test_record_rejects_an_invalid_status(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="status must be one of"):
        _record(tmp_path, "Acme", "Software Engineer", status="ghosted")


def test_round_trip_record_then_list(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    write_outcome = _record(
        tmp_path,
        "Acme Corp",
        "Software Engineer",
        status="applied",
        folder="/home/user/applications/2026-09/acme",
        notes="Referred by a friend.",
        id_port=id_port,
    )
    assert write_outcome.decision.granted is True

    list_outcome = _list(tmp_path)
    assert list_outcome.decision.granted is True
    assert len(list_outcome.records) == 1
    data = list_outcome.records[0].value.value
    assert data == {
        "kind": "job_application",
        "company": "Acme Corp",
        "role": "Software Engineer",
        "status": "applied",
        "date_applied": _NOW.isoformat(),
        "folder": "/home/user/applications/2026-09/acme",
        "notes": "Referred by a friend.",
    }


def test_list_filters_by_status(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    _record(tmp_path, "Acme Corp", "Software Engineer", status="applied", id_port=id_port)
    _record(tmp_path, "Globex", "Data Scientist", status="interviewing", id_port=id_port)
    _record(tmp_path, "Initech", "Backend Engineer", status="applied", id_port=id_port)

    applied_only = _list(tmp_path, status="applied")
    companies = {
        record.value.value["company"]  # type: ignore[index]
        for record in applied_only.records
    }
    assert companies == {"Acme Corp", "Initech"}

    interviewing_only = _list(tmp_path, status="interviewing")
    assert len(interviewing_only.records) == 1
    assert interviewing_only.records[0].value.value["company"] == "Globex"  # type: ignore[index]

    everything = _list(tmp_path)
    assert len(everything.records) == _ALL_RECORDS_COUNT


def test_record_with_no_folder_stores_none(tmp_path: Path) -> None:
    _record(tmp_path, "Acme Corp", "Software Engineer", status="drafted")

    outcome = _list(tmp_path)
    assert outcome.records[0].value.value["folder"] is None  # type: ignore[index]


def test_list_ignores_ordinary_memories_that_are_not_job_applications(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    authorize_and_remember(
        "prefers tabs over spaces",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    _record(tmp_path, "Acme Corp", "Software Engineer", status="applied", id_port=id_port)

    outcome = _list(tmp_path)
    assert len(outcome.records) == 1
    assert outcome.records[0].value.value["company"] == "Acme Corp"  # type: ignore[index]


def test_record_reuses_memory_write_effect_and_tier_exactly(tmp_path: Path) -> None:
    """A job-application record is Classification.PUBLIC, same as any other memory.write call.

    Reuses authorize_and_remember completely unmodified -- this proves
    it, rather than asserting it: the granted decision's own tier and
    declared effects are checked directly against ADR-0049's ordinary
    (non-SECRET) memory.write outcome, Effect.WRITE_LOCAL/Tier.CONFIRM.
    """
    outcome = _record(tmp_path, "Acme Corp", "Software Engineer", status="applied")

    assert outcome.decision.tier is Tier.CONFIRM
    assert outcome.decision.invocation.descriptor.id == MEMORY_WRITE_CAPABILITY_ID
    assert outcome.decision.invocation.descriptor.effects == Effect.WRITE_LOCAL


def test_valid_statuses_are_exactly_the_documented_five() -> None:
    assert VALID_JOB_APPLICATION_STATUSES == (
        "drafted",
        "applied",
        "interviewing",
        "rejected",
        "offer",
    )
