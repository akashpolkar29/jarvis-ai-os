"""The real memory-store adapter: SQLite persistence, brute-force cosine similarity search.

:class:`SqliteMemoryAdapter` is the real adapter chosen for both
``MemoryWritePort`` (ADR-0048) and ``RetrievalPort`` (ADR-0048) --
one class, one backing SQLite file, since both ports share the same
real storage concern. Brute-force numpy cosine similarity, not an ANN
index, is the real search mechanism -- a benchmark-backed decision,
not a preference; see ``docs/architecture/m4-benchmark-results.md``
and ``poc/wp61_vector_store_benchmark.py`` for the real numbers this
came from.

Applies both required retrieval-time guarantees before ever ranking
anything: ``exclude_secret_records`` (ADR-0050's amendment) and
``exclude_expired_records`` (ADR-0051) -- the same adapter-independent
functions WP-59/WP-60 already built and tested against fakes, called
here for real for the first time.

Real, deliberate scope limit, narrowed by the overnight Track 5 pass
(2026-09-02), not fully removed: this adapter persists any
JSON-serializable value -- ``str``, ``int``, ``float``, ``bool``,
``None``, ``list``, ``dict`` -- and rejects anything else
(:class:`UnsupportedMemoryValueError`). This is a safety-neutral,
mechanical extension, not a new classification/effect decision:
``jarvis.application.memory.classification.memory_effect_for`` already
resolved the correct ``Effect`` purely from
``value.provenance.classification``, never from ``type(value.value)``,
and ``MemoryWriteAuthorizer.authorize_write`` was already generic over
``T`` -- neither needed to change. The one real, mechanical problem
this pass actually solves is that the chosen embedding pipeline
(``EmbeddingPort``) only ever accepts text: a non-``str`` value is
embedded via its own ``json.dumps`` representation instead of the
value itself (a real, stated precision loss for semantic search over
structured data, not a safety concern -- classification/effect
enforcement never depends on embedding quality). ``value_json`` is a
new, migrated-in column (``ALTER TABLE ... ADD COLUMN``, applied in
``__init__`` if missing) holding each new record's real
``json.dumps`` value; a pre-migration row (``value_json IS NULL``)
still reads back exactly as before, via the unchanged ``text`` column
-- real backward compatibility, not a schema break. A real, stated
limitation of using ``json``, not silently hidden: round-tripping a
``tuple`` returns a ``list`` (JSON has no tuple type), and NaN/
Infinity floats serialize via Python's own non-standard
``allow_nan=True`` default -- neither is a safety concern, both are
plain data-fidelity notes for a caller storing either.

**WP-120 (2026-09-11): a real, process-safe compare-and-swap primitive.**
``update_value`` is a blind, unconditional overwrite -- correct for
every existing caller, which already knows it is the sole writer. It
is unsafe for a new real need: two genuinely independent processes
(e.g. two `jarvis task worker` instances, or a worker racing a direct
`jarvis task run`) both trying to claim the same persisted task for
execution. ``compare_and_update_value`` closes that gap using SQLite's
own file-level locking (`BEGIN IMMEDIATE`, empirically verified across
real, separate OS processes, not merely assumed from documentation --
see its own docstring and the new process-safety test) rather than a
new dependency or a SQLite JSON1/`json_extract` predicate. See
``jarvis.kernel.worker``'s own module docstring for the real caller
this exists for.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from jarvis.application.memory.retention import compute_write_timestamps, exclude_expired_records
from jarvis.application.memory.retrieval_guard import exclude_secret_records
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.ports.memory_write import MemoryRecordNotFoundError

if TYPE_CHECKING:
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_records (
    identifier TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    embedding TEXT NOT NULL,
    trust INTEGER NOT NULL,
    classification INTEGER NOT NULL,
    sources TEXT NOT NULL,
    written_at TEXT NOT NULL,
    expires_at TEXT
)
"""

_ADD_VALUE_JSON_COLUMN = "ALTER TABLE memory_records ADD COLUMN value_json TEXT"


def _ensure_value_json_column(connection: sqlite3.Connection) -> None:
    """Migrate an existing ``memory_records`` table to add ``value_json`` if missing.

    A real, minimal migration, not a schema break: ``CREATE TABLE IF
    NOT EXISTS`` alone never adds a column to an already-existing
    table, so a database created before this pass would otherwise
    never gain ``value_json`` at all. Checked via ``PRAGMA
    table_info`` rather than a try/except around ``ALTER TABLE`` --
    deterministic, not exception-driven control flow.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(memory_records)")}
    if "value_json" not in columns:
        connection.execute(_ADD_VALUE_JSON_COLUMN)
        connection.commit()


class UnsupportedMemoryValueError(Exception):
    """Raised when a value passed to :meth:`SqliteMemoryAdapter.write` is not JSON-serializable.

    A real, deliberate scope limit (see module docstring), not a
    generic validation error -- this adapter's own real embedding
    pipeline (``EmbeddingPort``) only ever accepts text, so any value
    stored here must have some real text representation derivable
    from it.
    """


def _decode_stored_value(value_json: str | None, text: str) -> object:
    """Decode one row's real stored value, mirroring `_row_to_record_and_embedding`'s inline logic.

    A ``NULL`` ``value_json`` is a real, pre-migration row written
    before that column existed -- ``text`` alone was, and still is,
    that row's own real, complete value. Never re-derived from
    ``json.loads(text)``, which would incorrectly wrap it in an extra
    layer of quoting. Extracted as its own function (WP-120) so
    :meth:`SqliteMemoryAdapter.compare_and_update_value` can decode a
    freshly-read row the exact same way
    :meth:`SqliteMemoryAdapter._row_to_record_and_embedding` already
    does, rather than a second, separately-maintained copy of this
    same real rule.
    """
    return json.loads(value_json) if value_json is not None else text


def _cosine_similarity(a: tuple[float, ...], b: list[float]) -> float:
    vector_a = np.array(a, dtype=np.float64)
    vector_b = np.array(b, dtype=np.float64)
    denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(vector_a, vector_b) / denominator)


class SqliteMemoryAdapter:
    """A real ``MemoryWritePort``/``RetrievalPort`` backed by one SQLite file.

    ``__init__`` opens the real SQLite connection and ensures the
    schema exists -- real, but local, file-only I/O, no daemon or
    network involved, matching this project's own established
    ``JsonFileAuditStorageAdapter`` precedent for plain-file
    persistence.
    """

    def __init__(
        self,
        database_path: str,
        embedding_port: EmbeddingPort,
        clock: ClockPort,
        id_port: IdPort,
    ) -> None:
        """Open (creating if needed) the real SQLite store at ``database_path``.

        Args:
            database_path: A real filesystem path, or ``":memory:"``
                for an ephemeral store (tests use this).
            embedding_port: The real source of embedding vectors for
                both writes and queries.
            clock: The real source of wall-clock time for
                ``written_at``/``expires_at`` (ADR-0051, ADR-0054).
            id_port: The real source of new record identifiers
                (ADR-0054).
        """
        self._embedding_port = embedding_port
        self._clock = clock
        self._id_port = id_port
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(_CREATE_TABLE)
        self._connection.commit()
        _ensure_value_json_column(self._connection)

    def write(self, value: Tainted[object]) -> str:
        """Persist ``value`` to the real store, provenance intact.

        Raises:
            UnsupportedMemoryValueError: If ``value.value`` is not
                JSON-serializable (see module docstring).
        """
        try:
            value_json = json.dumps(value.value)
        except TypeError as exc:
            msg = (
                "SqliteMemoryAdapter only persists JSON-serializable memories "
                "(str, int, float, bool, None, list, dict); "
                f"got {type(value.value).__name__}."
            )
            raise UnsupportedMemoryValueError(msg) from exc
        text = value.value if isinstance(value.value, str) else value_json
        (embedding,) = self._embedding_port.embed((text,))
        written_at, expires_at = compute_write_timestamps(self._clock)
        identifier = self._id_port.new_id()
        self._connection.execute(
            "INSERT INTO memory_records "
            "(identifier, text, value_json, embedding, trust, classification, sources, "
            "written_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identifier,
                text,
                value_json,
                json.dumps(embedding),
                int(value.provenance.trust),
                int(value.provenance.classification),
                json.dumps(sorted(value.provenance.sources)),
                written_at.isoformat(),
                expires_at.isoformat(),
            ),
        )
        self._connection.commit()
        return identifier

    def update_value(self, identifier: str, value: Tainted[object]) -> None:
        """Replace the value at ``identifier`` in place, re-deriving text/embedding (WP-107).

        Mirrors :meth:`pin`'s own "UPDATE ... WHERE identifier = ?,
        check rowcount" shape exactly, but updates the value columns
        (``text``/``value_json``/``embedding``/``trust``/
        ``classification``/``sources``) rather than ``expires_at`` --
        ``written_at``/``expires_at`` themselves are left untouched,
        matching this method's own real contract (an update, not a
        fresh write with a new retention window).

        Raises:
            UnsupportedMemoryValueError: If ``value.value`` is not
                JSON-serializable (see module docstring).
            MemoryRecordNotFoundError: If ``identifier`` matches no
                real, currently-stored record.
        """
        try:
            value_json = json.dumps(value.value)
        except TypeError as exc:
            msg = (
                "SqliteMemoryAdapter only persists JSON-serializable memories "
                "(str, int, float, bool, None, list, dict); "
                f"got {type(value.value).__name__}."
            )
            raise UnsupportedMemoryValueError(msg) from exc
        text = value.value if isinstance(value.value, str) else value_json
        (embedding,) = self._embedding_port.embed((text,))
        cursor = self._connection.execute(
            "UPDATE memory_records SET text = ?, value_json = ?, embedding = ?, trust = ?, "
            "classification = ?, sources = ? WHERE identifier = ?",
            (
                text,
                value_json,
                json.dumps(embedding),
                int(value.provenance.trust),
                int(value.provenance.classification),
                json.dumps(sorted(value.provenance.sources)),
                identifier,
            ),
        )
        self._connection.commit()
        if cursor.rowcount == 0:
            msg = f"No memory record found with identifier {identifier!r}."
            raise MemoryRecordNotFoundError(msg)

    def compare_and_update_value(
        self, identifier: str, expected_value: object, value: Tainted[object]
    ) -> bool:
        """Atomically swap `identifier`'s value iff current == `expected_value` (WP-120).

        **The real process-safety mechanism**: `BEGIN IMMEDIATE`
        acquires SQLite's own write lock immediately, before reading
        anything -- empirically verified (not merely assumed from
        documentation) to block a second, truly independent
        `sqlite3.connect()` to the same file from starting its own
        write transaction until this one commits or rolls back,
        across real, separate OS processes (see
        `tests/unit/test_memory_adapter_process_safety.py`). The
        current row is then re-read *inside* that lock, decoded with
        the exact same rule `get_by_identifier` uses
        (`_decode_stored_value`), and compared by value equality
        against `expected_value` -- if another writer changed it since
        the caller last read it, this comparison correctly sees that
        writer's own, newer value, not a stale snapshot. No SQLite
        JSON1/`json_extract` dependency: the comparison is plain
        Python equality on the decoded value, not a SQL-level
        predicate, so this works on any SQLite build.

        The embedding for the *new* value is computed before the lock
        is acquired -- it depends only on `value` itself, never on
        what is currently stored, so there is no reason to hold the
        write lock any longer than the compare-and-write itself needs.

        Returns:
            `True` if the comparison matched and the swap was
            performed (a real commit landed). `False` if `identifier`
            does not exist, or its current value does not equal
            `expected_value` -- the store is left completely unchanged
            in that case; this is a normal, expected outcome for a
            caller racing another writer, never an error.

        Raises:
            UnsupportedMemoryValueError: If `value.value` is not
                JSON-serializable (checked before the lock is ever
                acquired).
        """
        try:
            value_json = json.dumps(value.value)
        except TypeError as exc:
            msg = (
                "SqliteMemoryAdapter only persists JSON-serializable memories "
                "(str, int, float, bool, None, list, dict); "
                f"got {type(value.value).__name__}."
            )
            raise UnsupportedMemoryValueError(msg) from exc
        text = value.value if isinstance(value.value, str) else value_json
        (embedding,) = self._embedding_port.embed((text,))
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT value_json, text FROM memory_records WHERE identifier = ?", (identifier,)
            ).fetchone()
            if row is None or _decode_stored_value(row[0], row[1]) != expected_value:
                self._connection.rollback()
                return False
            self._connection.execute(
                "UPDATE memory_records SET text = ?, value_json = ?, embedding = ?, trust = ?, "
                "classification = ?, sources = ? WHERE identifier = ?",
                (
                    text,
                    value_json,
                    json.dumps(embedding),
                    int(value.provenance.trust),
                    int(value.provenance.classification),
                    json.dumps(sorted(value.provenance.sources)),
                    identifier,
                ),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        else:
            return True

    def pin(self, identifier: str) -> None:
        """Set the record at ``identifier``'s ``expires_at`` to ``NULL`` (never expires).

        Raises:
            MemoryRecordNotFoundError: If ``identifier`` matches no
                real, currently-stored record.
        """
        cursor = self._connection.execute(
            "UPDATE memory_records SET expires_at = NULL WHERE identifier = ?",
            (identifier,),
        )
        self._connection.commit()
        if cursor.rowcount == 0:
            msg = f"No memory record found with identifier {identifier!r}."
            raise MemoryRecordNotFoundError(msg)

    def sweep_expired(self) -> int:
        """Permanently delete every expired, unpinned row from the real SQLite file.

        ADR-0051's own real sweep, owed beyond ``exclude_expired_records``'s
        query-time-only exclusion: a ``NULL`` ``expires_at`` (pinned) is
        never eligible.

        Returns:
            The number of rows actually deleted.
        """
        now = self._clock.now().isoformat()
        cursor = self._connection.execute(
            "DELETE FROM memory_records WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        self._connection.commit()
        return cursor.rowcount

    def forget(self, identifier: str) -> None:
        """Permanently delete the row at ``identifier`` from the real SQLite file.

        Raises:
            MemoryRecordNotFoundError: If ``identifier`` matches no
                real, currently-stored record.
        """
        cursor = self._connection.execute(
            "DELETE FROM memory_records WHERE identifier = ?",
            (identifier,),
        )
        self._connection.commit()
        if cursor.rowcount == 0:
            msg = f"No memory record found with identifier {identifier!r}."
            raise MemoryRecordNotFoundError(msg)

    def backup(self, destination_path: str) -> None:
        """Write a real, live-safe copy of this store to ``destination_path`` (ADR-0061).

        Uses ``sqlite3.Connection.backup()`` -- SQLite's own real
        online-backup mechanism -- rather than a raw file copy, so a
        concurrent write to the live connection cannot produce a torn
        snapshot.
        """
        destination_connection = sqlite3.connect(destination_path)
        try:
            self._connection.backup(destination_connection)
        finally:
            destination_connection.close()

    def restore(self, source_path: str) -> None:
        """Replace this store's entire real content with ``source_path``'s (ADR-0061).

        Copies ``source_path``'s content into this adapter's own,
        already-open connection via ``sqlite3.Connection.backup()``,
        in the reverse direction from :meth:`backup` -- an in-place
        replacement, not a reopen, so this adapter instance stays
        valid for any caller already holding a reference to it.

        Raises:
            FileNotFoundError: If ``source_path`` does not exist.
        """
        if not Path(source_path).exists():
            msg = f"No backup file found at {source_path!r}."
            raise FileNotFoundError(msg)
        source_connection = sqlite3.connect(source_path)
        try:
            source_connection.backup(self._connection)
        finally:
            source_connection.close()

    def wipe(self) -> int:
        """Permanently delete every real row currently in the store (Phase 10).

        Returns:
            The number of rows actually deleted. ``0`` if the store
            was already empty.
        """
        cursor = self._connection.execute("DELETE FROM memory_records")
        self._connection.commit()
        return cursor.rowcount

    def retrieve(self, query: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        """Return up to ``limit`` real records ranked by cosine similarity to ``query``.

        Applies ``exclude_secret_records`` and ``exclude_expired_records``
        before ever ranking anything -- both required, adapter-
        independent guarantees this milestone's own ADRs name.
        """
        rows = self._connection.execute(
            "SELECT identifier, text, value_json, embedding, trust, classification, sources, "
            "written_at, expires_at FROM memory_records"
        ).fetchall()
        parsed = [self._row_to_record_and_embedding(row) for row in rows]
        embeddings_by_id = {record.identifier: embedding for record, embedding in parsed}

        records = tuple(record for record, _ in parsed)
        records = exclude_secret_records(records)
        records = exclude_expired_records(records, self._clock.now())
        if not records:
            return ()

        (query_vector,) = self._embedding_port.embed((query,))
        ranked = sorted(
            records,
            key=lambda record: (
                -_cosine_similarity(query_vector, embeddings_by_id[record.identifier])
            ),
        )
        return tuple(ranked[:limit])

    def get_by_identifier(self, identifier: str) -> MemoryRecord | None:
        """Return the one real record at ``identifier``, or ``None`` if not found (WP-107).

        A direct ``SELECT ... WHERE identifier = ?`` -- no ranking, no
        embedding call, no full-table scan, the real, O(1)-by-key
        counterpart to :meth:`retrieve`'s similarity search. Applies
        the same two real guarantees :meth:`retrieve` applies, via the
        same adapter-independent functions.

        Raises:
            MemoryIntegrityViolationError: If the record at
                ``identifier`` is ``Classification.SECRET``.
        """
        row = self._connection.execute(
            "SELECT identifier, text, value_json, embedding, trust, classification, sources, "
            "written_at, expires_at FROM memory_records WHERE identifier = ?",
            (identifier,),
        ).fetchone()
        if row is None:
            return None
        record, _embedding = self._row_to_record_and_embedding(row)
        (record,) = exclude_secret_records((record,))
        records = exclude_expired_records((record,), self._clock.now())
        return records[0] if records else None

    @staticmethod
    def _row_to_record_and_embedding(
        row: tuple[str, str, str | None, str, int, int, str, str, str | None],
    ) -> tuple[MemoryRecord, list[float]]:
        (
            identifier,
            text,
            value_json,
            embedding_json,
            trust,
            classification,
            sources_json,
            written_at,
            expires_at,
        ) = row
        value = _decode_stored_value(value_json, text)
        provenance = Provenance(
            trust=Trust(trust),
            classification=Classification(classification),
            sources=frozenset(json.loads(sources_json)),
        )
        record = MemoryRecord(
            identifier=identifier,
            value=Tainted(value, provenance),
            written_at=datetime.fromisoformat(written_at),
            expires_at=datetime.fromisoformat(expires_at) if expires_at is not None else None,
        )
        return record, json.loads(embedding_json)
