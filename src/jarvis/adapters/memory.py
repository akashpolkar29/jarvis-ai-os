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

Real, deliberate scope limit, not a silent gap: this adapter only
persists ``str``-valued memories (:class:`UnsupportedMemoryValueError`
otherwise) -- matching every real example this milestone's own design
documents use ("prefers tabs," a memorized preference or fact), and
the one thing the chosen embedding pipeline can actually embed. A
future milestone needing structured, non-string memorized values would
need real serialization work this ADR/work package does not do.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
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


class UnsupportedMemoryValueError(Exception):
    """Raised when a value passed to :meth:`SqliteMemoryAdapter.write` is not a ``str``.

    A real, deliberate scope limit (see module docstring), not a
    generic validation error -- this adapter's own real embedding
    pipeline (``EmbeddingPort``) only ever accepts text.
    """


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

    def write(self, value: Tainted[object]) -> str:
        """Persist ``value`` to the real store, provenance intact.

        Raises:
            UnsupportedMemoryValueError: If ``value.value`` is not a
                ``str`` (see module docstring).
        """
        if not isinstance(value.value, str):
            msg = (
                "SqliteMemoryAdapter only persists str-valued memories; "
                f"got {type(value.value).__name__}."
            )
            raise UnsupportedMemoryValueError(msg)
        text = value.value
        (embedding,) = self._embedding_port.embed((text,))
        written_at, expires_at = compute_write_timestamps(self._clock)
        identifier = self._id_port.new_id()
        self._connection.execute(
            "INSERT INTO memory_records "
            "(identifier, text, embedding, trust, classification, sources, written_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identifier,
                text,
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

    def retrieve(self, query: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        """Return up to ``limit`` real records ranked by cosine similarity to ``query``.

        Applies ``exclude_secret_records`` and ``exclude_expired_records``
        before ever ranking anything -- both required, adapter-
        independent guarantees this milestone's own ADRs name.
        """
        rows = self._connection.execute(
            "SELECT identifier, text, embedding, trust, classification, sources, "
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

    @staticmethod
    def _row_to_record_and_embedding(
        row: tuple[str, str, str, int, int, str, str, str | None],
    ) -> tuple[MemoryRecord, list[float]]:
        (
            identifier,
            text,
            embedding_json,
            trust,
            classification,
            sources_json,
            written_at,
            expires_at,
        ) = row
        provenance = Provenance(
            trust=Trust(trust),
            classification=Classification(classification),
            sources=frozenset(json.loads(sources_json)),
        )
        record = MemoryRecord(
            identifier=identifier,
            value=Tainted(text, provenance),
            written_at=datetime.fromisoformat(written_at),
            expires_at=datetime.fromisoformat(expires_at) if expires_at is not None else None,
        )
        return record, json.loads(embedding_json)
