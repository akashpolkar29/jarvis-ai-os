"""job_application.record / job_application.list: a structured-content convention on memory.

**Not a new capability, port, or adapter.** Recording an applied job is
a real, thin convention layered directly on top of the already-real,
already-Accepted ``memory.write``/``memory.retrieve`` capabilities
(``kernel/memory.py``) -- exactly as the work package that added this
module required. This closes a real, original charter gap ("store the
data of applied job roles") without growing the codebase's own real
subsystem count.

**Investigation finding, confirmed before writing any of this module**:
``MemoryRecord.value: Tainted[object]``, ``SqliteMemoryAdapter.write()``,
``memory_effect_for()``, and ``MemoryWriteAuthorizer.authorize_write[T]``
already supported arbitrary JSON-serializable structured values --
only ``authorize_and_remember``'s own public ``text: str`` parameter
was narrower than everything downstream of it. That parameter is now
``value: object`` (see ``kernel/memory.py``'s own updated docstring);
this module is the first real caller to pass it a ``dict``.

**The real "distinguishing tag" mechanism**: ``MemoryRecord`` has no
tag/category/key-namespace field of its own, and ``RetrievalPort``'s
only real interface (``retrieve(query, *, limit)``) is a cosine-
similarity-ranked top-K search -- confirmed by reading both
``ports/retrieval.py`` and ``SqliteMemoryAdapter.retrieve()`` directly,
no exact/prefix-match primitive exists anywhere in this codebase
today. Rather than inventing a new ``MemoryRecord`` field (explicitly
ruled out by this work package), every job-application record embeds
a fixed marker key, ``"kind": "job_application"``, directly inside its
own structured value -- the same JSON blob that already gets embedded
for semantic search (``SqliteMemoryAdapter.write()``'s own
``value_json`` fallback for non-``str`` values). ``list`` recalls
broadly (a fixed, generous query/limit designed to surface the whole
job-application slice of the store) and then filters precisely on
that marker key, client-side -- exact, not approximate, *once a
record is returned*, though the recall step it depends on is a real,
honest approximation. **A real, named limitation, not hidden**: if a
store holds more distinct memories than ``_RECALL_LIST_LIMIT``, some
older or less-semantically-similar job-application records could rank
below the cutoff and be missed by ``list`` -- an inherent consequence
of reusing a similarity-ranked retrieval mechanism with no exact
filter, not a bug in this module. A future, dedicated exact-filter
mechanism on ``RetrievalPort`` itself would close this for real; out
of this work package's own explicit scope (no new port/adapter).

**Effect/Tier**: both functions reuse ``authorize_and_remember``/
``authorize_and_recall`` completely unmodified -- there is no separate
classification logic here to state. Every field this module writes
(company, role, status, dates, folder, notes) is direct, typed-by-the-
user input, wrapped by ``authorize_and_remember`` itself as
``Tainted(value, Provenance.user())`` -- ``Classification.PUBLIC``, so
``memory_effect_for()`` (ADR-0049) always resolves ``Effect.WRITE_LOCAL``/
``Tier.CONFIRM`` here, the same as any other ``memory.write`` call.
``list`` reuses ``memory.retrieve``'s own fixed ``Effect.READ_LOCAL``/
``Tier.ALLOW``. Neither a job-application record's own status/folder/
notes fields, nor anything else about this module, can push either
call to a different tier -- job-application records are not a class
of data this project's own privacy model treats as SECRET.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.kernel.memory import MemoryWriteOutcome, authorize_and_recall, authorize_and_remember

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort

_JOB_APPLICATION_KIND = "job_application"
"""The real, fixed marker value stored under each record's own "kind" key."""

VALID_JOB_APPLICATION_STATUSES = ("drafted", "applied", "interviewing", "rejected", "offer")
"""The real, fixed status vocabulary this convention accepts -- matches the work
package's own worked example exactly. Not a domain enum: this is a thin,
kernel-level convention on a plain dict, not a new domain type."""

_LIST_QUERY = "job application company role status date applied folder notes"
"""A fixed query text chosen to score highly against any job-application
record's own embedded JSON (whose keys are these exact words) relative to
ordinary free-text memories that do not contain them."""

_RECALL_LIST_LIMIT = 1000
"""A generous, fixed top-K passed to the underlying memory.retrieve call --
see this module's own docstring for the real, honest limitation this implies."""


def authorize_and_record_job_application(  # noqa: PLR0913 -- one per composition-function pass-through
    company: str,
    role: str,
    *,
    status: str,
    folder: str | None = None,
    notes: str | None = None,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> MemoryWriteOutcome:
    """Record one applied job as a structured memory. Reuses authorize_and_remember unmodified.

    Args:
        company: The real company name.
        role: The real role/job title.
        status: One of ``VALID_JOB_APPLICATION_STATUSES``. Any other
            value raises ``ValueError`` before anything is authorized
            or written.
        folder: The real, local application-folder path from
            ``job_assistance.prepare_application_folder``, if this
            application has one. ``None`` if recorded manually.
        notes: Real, optional free-text notes.
        physical_confirmation_available: Passed straight through to
            ``authorize_and_remember``.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        database_path: Where the real memory store lives. Overridable
            for tests.
        embedding_port: Overridable for tests -- important to
            override, in fact: a granted write with no override
            triggers a real model download on first use.
        clock: Defaults to a real ``SystemClockAdapter``. Also used to
            stamp ``date_applied`` (ADR-0054: no bare ``datetime.now()``
            in this module).
        id_port: Defaults to a real ``UuidIdAdapter``.

    Returns:
        The same ``MemoryWriteOutcome`` ``authorize_and_remember``
        itself returns -- this function adds no new outcome shape.

    Raises:
        ValueError: If ``status`` is not one of
            ``VALID_JOB_APPLICATION_STATUSES``.
    """
    if status not in VALID_JOB_APPLICATION_STATUSES:
        msg = f"status must be one of {VALID_JOB_APPLICATION_STATUSES!r}; got {status!r}."
        raise ValueError(msg)

    resolved_clock = clock or SystemClockAdapter()
    record: dict[str, object] = {
        "kind": _JOB_APPLICATION_KIND,
        "company": company,
        "role": role,
        "status": status,
        "date_applied": resolved_clock.now().isoformat(),
        "folder": folder,
        "notes": notes,
    }
    return authorize_and_remember(
        record,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )


@dataclass(frozen=True)
class JobApplicationListOutcome:
    """The result of one authorize_and_list_job_applications() call.

    Attributes:
        decision: The Decision for the underlying memory.retrieve call
            this reuses -- always granted (``Tier.ALLOW``), matching
            ``MemoryRecallOutcome``'s own "explicit check, not asserted
            away" convention one level up.
        records: The real, matching job-application records, already
            filtered by the "kind" marker (and by ``status``, if
            given). Each is a real, unmodified ``MemoryRecord`` --
            read a record's own structured fields directly from
            ``record.value.value`` (a plain ``dict``).
    """

    decision: Decision
    records: tuple[MemoryRecord, ...]


def authorize_and_list_job_applications(  # noqa: PLR0913 -- one per composition-function pass-through
    *,
    status: str | None = None,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> JobApplicationListOutcome:
    """List recorded job applications, optionally filtered by status. Reuses authorize_and_recall.

    See this module's own docstring for the real, honest approximation
    the underlying broad recall implies, and why: no exact-match
    filter primitive exists on ``RetrievalPort`` today.

    Args:
        status: If given, only return records whose own ``status``
            field matches exactly. ``None`` returns every real
            job-application record this broad recall surfaces.
        physical_confirmation_available: Passed straight through to
            ``authorize_and_recall``.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        database_path: Where the real memory store lives. Overridable
            for tests.
        embedding_port: Overridable for tests.
        clock: Defaults to a real ``SystemClockAdapter``.
        id_port: Defaults to a real ``UuidIdAdapter``. Unused by a
            read, threaded through only for ``authorize_and_recall``'s
            own shared helper.

    Returns:
        A ``JobApplicationListOutcome`` -- see its own docstring.
    """
    recall_outcome = authorize_and_recall(
        _LIST_QUERY,
        limit=_RECALL_LIST_LIMIT,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    matching = tuple(
        record
        for record in recall_outcome.records
        if isinstance(record.value.value, dict)
        and record.value.value.get("kind") == _JOB_APPLICATION_KIND
        and (status is None or record.value.value.get("status") == status)
    )
    return JobApplicationListOutcome(decision=recall_outcome.decision, records=matching)
