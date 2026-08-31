"""The composition root for memory.write/memory.retrieve: real, end-to-end memory capabilities.

:func:`authorize_and_remember` and :func:`authorize_and_recall` are the
first point real memory write/retrieve calls exist as actual,
invocable capabilities, not just isolated, tested-in-parts
infrastructure (``domain/memory.py``, ``application/memory/*``,
``adapters/memory.py`` -- WP-57 through WP-62).

**``memory.write`` is deliberately not registered in
``build_default_registry()``** -- exactly the same reason
``jarvis.application.reasoning.router.ModelRouter`` never registers
its own capability there either (see that module's own docstring):
the correct ``Effect`` genuinely varies per real invocation, based on
the value's own classification (ADR-0049), which a statically-
registered ``CapabilityDescriptor`` cannot express.
:func:`authorize_and_remember` routes through
:class:`~jarvis.application.memory.writer.MemoryWriteAuthorizer`
directly, mirroring :func:`~jarvis.kernel.ping.authorize_ping`'s own
composition shape (registry/storage/confirmation/orchestrator wiring)
everywhere except the authorization call itself.

**``memory.retrieve`` is a static, fixed-effect capability**
(``Effect.READ_LOCAL``, ``Tier.ALLOW`` -- ADR-0048's own worked
example: "the bare act of querying" is not the same concern as what a
caller does with a recalled record, ADR-0050's own separate concern)
-- registered in ``build_default_registry()`` and authorized via the
ordinary ``authorize_by_id()`` path, exactly like ``ping``/
``fs.read_file``/``git.status``.

**Real, deliberate scope boundary, matching this project's own M3
precedent**: like ``docker.*``/``git.*``, neither capability is wired
into ``jarvis.cli.main``'s argparse subcommands or
``jarvis.kernel.intent``'s voice grammar for *recall* -- a real,
tested composition function is "invocable" in the same sense Docker/
Git's own kernel functions already are, without every capability
needing a CLI flag or a voice phrase. ``memory.write`` is the one
exception: ADR-0053 explicitly names the ``kernel/voice_loop.py``
dispatch branch a granted memory write needs for its own spoken
confirmation as real, necessary work for this work package -- see
``kernel/voice_loop.py``'s own docstring for that wiring, and
``kernel/intent.py``'s "remember " keyword, added alongside it,
mirroring "read "'s exact existing shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.embedding import FastEmbedAdapter
from jarvis.adapters.identifier import UuidIdAdapter
from jarvis.adapters.memory import SqliteMemoryAdapter
from jarvis.application.memory.writer import MemoryWriteAuthorizer
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import MEMORY_RETRIEVE_CAPABILITY_ID, build_default_registry

if TYPE_CHECKING:
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort

_DEFAULT_MEMORY_DB_PATH = Path("memory.sqlite3")
"""A plain relative-path literal default, matching cli.main's own
_DEFAULT_CHAIN_PATH precedent -- this project does not yet use
platformdirs for real default data paths anywhere, and this work
package does not unilaterally start that (a real, separate decision
if ever made, not bundled into memory-specific composition wiring).
"""


def _memory_adapter(
    database_path: Path | None,
    embedding_port: EmbeddingPort | None,
    clock: ClockPort,
    id_port: IdPort | None,
) -> SqliteMemoryAdapter:
    return SqliteMemoryAdapter(
        str(database_path or _DEFAULT_MEMORY_DB_PATH),
        embedding_port or FastEmbedAdapter(),
        clock,
        id_port or UuidIdAdapter(),
    )


@dataclass(frozen=True)
class MemoryWriteOutcome:
    """The result of one authorize_and_remember() call.

    Attributes:
        decision: The Decision for this write -- durably appended to
            the chain regardless of outcome.
        identifier: The new record's real identifier, if the decision
            was granted. ``None`` if denied.
    """

    decision: Decision
    identifier: str | None


def authorize_and_remember(  # noqa: PLR0913 -- one per composition-function pass-through
    text: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> MemoryWriteOutcome:
    """Wire up the stack, authorize memorizing ``text``, and write it only if granted.

    Args:
        text: The real text to memorize, typed or spoken directly by
            the user -- wrapped as ``Tainted(text, Provenance.user())``,
            matching every other directly-typed/spoken argument in
            this codebase (``ping``'s empty args, a music command,
            ``fs.read_file``'s path). ``memory_effect_for()``
            (ADR-0049) resolves the real ``Effect`` this declares from
            that provenance's own classification -- ``PUBLIC`` here,
            so this call always floors at ``WRITE_LOCAL``/``CONFIRM``,
            never the unconditional ``MEMORY_WRITE``/``DENY`` floor a
            ``SECRET``-classified value would hit. A future caller
            constructing this value from a less-trusted or more
            sensitive source is responsible for giving it the correct
            provenance before calling this function -- this function
            does not, and cannot, second-guess a provenance it did not
            compute (the same trust boundary ADR-0049's own
            Consequences section names).
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        database_path: Where the real memory store lives. Defaults to
            ``_DEFAULT_MEMORY_DB_PATH``. Overridable for tests.
        embedding_port: The real source of embedding vectors. Defaults
            to a real ``FastEmbedAdapter``. Overridable for tests --
            important to override, in fact: a granted write with no
            override triggers a real model download on first use.
        clock: The real source of wall-clock time. Defaults to a real
            ``SystemClockAdapter``.
        id_port: The real source of new record identifiers. Defaults
            to a real ``UuidIdAdapter``.

    Returns:
        A ``MemoryWriteOutcome`` -- see its own docstring.

    Real trigger for ADR-0051's own owed sweep (closed here): every
    granted write first calls ``adapter.sweep_expired()`` before
    persisting the new value -- the simplest real hook this codebase
    already calls on every write, not a new background scheduler this
    milestone never asked for.
    """
    resolved_clock = clock or SystemClockAdapter()
    value: Tainted[object] = Tainted(text, Provenance.user())

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, build_default_registry(), confirmation=confirmation
    )
    authorizer = MemoryWriteAuthorizer(orchestrator)

    decision = authorizer.authorize_write(value, orchestrator.get_current_context())

    identifier: str | None = None
    try:
        if decision.granted:
            adapter = _memory_adapter(database_path, embedding_port, resolved_clock, id_port)
            adapter.sweep_expired()
            identifier = adapter.write(value)
    finally:
        storage.save(chain)

    return MemoryWriteOutcome(decision=decision, identifier=identifier)


@dataclass(frozen=True)
class MemoryRecallOutcome:
    """The result of one authorize_and_recall() call.

    Attributes:
        decision: The Decision for the bare act of querying -- always
            granted (``memory.retrieve`` is ``Tier.ALLOW``), still
            durably appended to the chain, matching ``ping``'s own
            "explicit check, not asserted away" convention.
        records: The recalled records, if granted. Empty if denied
            (never happens today) or if nothing matched.
    """

    decision: Decision
    records: tuple[MemoryRecord, ...]


def authorize_and_recall(  # noqa: PLR0913 -- one per composition-function pass-through
    query: str,
    *,
    limit: int,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> MemoryRecallOutcome:
    """Wire up the stack, authorize the bare act of querying, and recall if granted.

    Real, deliberate scope note (ADR-0050's own): a granted recall
    returns each ``MemoryRecord`` with its own real, unmodified
    ``Provenance`` intact -- this function performs no further
    tier-based gating on the recalled *content*. A future caller that
    feeds a recalled value into a *new* capability invocation (e.g. a
    cloud-bound reasoning call) is responsible for constructing that
    invocation's own ``Tainted`` argument from the record's own
    ``.value.provenance``, not a fresh one -- exactly the carry-forward
    discipline ``tests/meta/test_memory_provenance_carryforward.py``
    mechanically enforces. No such caller exists yet in this
    codebase -- named here as the real, load-bearing contract, not
    demonstrated by a caller this work package does not build.

    Args:
        query: The real search text.
        limit: The maximum number of records to return.
        physical_confirmation_available: As above -- threaded through
            for consistency, though ``memory.retrieve``'s ``ALLOW``
            tier means it does not affect the outcome (same as
            ``ping``, ``fs.read_file``).
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        database_path: Where the real memory store lives. Defaults to
            ``_DEFAULT_MEMORY_DB_PATH``. Overridable for tests.
        embedding_port: Defaults to a real ``FastEmbedAdapter``.
            Overridable for tests.
        clock: Defaults to a real ``SystemClockAdapter``.
        id_port: Defaults to a real ``UuidIdAdapter`` -- unused by a
            read, threaded through only so ``_memory_adapter`` stays
            one shared helper for both composition functions.

    Returns:
        A ``MemoryRecallOutcome`` -- see its own docstring.
    """
    resolved_clock = clock or SystemClockAdapter()

    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        MEMORY_RETRIEVE_CAPABILITY_ID,
        Tainted({"query": query}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    records: tuple[MemoryRecord, ...] = ()
    try:
        # decision.granted is always True here: evaluate() hardcodes
        # granted=True for Tier.ALLOW, which memory.retrieve always is.
        # Kept as an explicit check (not asserted away) matching
        # authorize_and_read_file's own identical convention.
        if decision.granted:
            adapter = _memory_adapter(database_path, embedding_port, resolved_clock, id_port)
            records = adapter.retrieve(query, limit=limit)
    finally:
        storage.save(chain)

    return MemoryRecallOutcome(decision=decision, records=records)
