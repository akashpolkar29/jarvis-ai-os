"""Contract test: jarvis.ports.retrieval.RetrievalPort's own shape.

A minimal fake proves the Protocol itself is well-formed and
satisfiable independent of any specific adapter (M3's own "port exists
and is tested structurally before any real technology is chosen"
ordering). ``SqliteMemoryAdapter`` (WP-61) is the real adapter, checked
separately below -- safe to construct with an in-memory database and
fake dependencies, since its own ``__init__`` only opens a local
SQLite connection, no network or model I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from jarvis.adapters.memory import SqliteMemoryAdapter
from jarvis.ports.retrieval import RetrievalPort

if TYPE_CHECKING:
    from jarvis.domain.memory import MemoryRecord

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeRetrievalAdapter:
    """A minimal, real fake proving RetrievalPort is satisfiable."""

    def retrieve(self, query: str, *, limit: int) -> tuple[MemoryRecord, ...]:  # noqa: ARG002
        return ()


class _FakeEmbeddingPort:
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((0.0,) for _ in texts)


class _FakeClock:
    def now(self) -> datetime:
        return _NOW


class _FakeIdPort:
    def new_id(self) -> str:
        return "mem:1"


def test_a_conforming_fake_satisfies_retrieval_port() -> None:
    """A real, minimal implementation is structurally a RetrievalPort."""
    adapter = _FakeRetrievalAdapter()

    assert isinstance(adapter, RetrievalPort)


def test_sqlite_memory_adapter_satisfies_retrieval_port() -> None:
    """The real WP-61 adapter is structurally a RetrievalPort."""
    adapter = SqliteMemoryAdapter(":memory:", _FakeEmbeddingPort(), _FakeClock(), _FakeIdPort())

    assert isinstance(adapter, RetrievalPort)


def test_an_object_missing_retrieve_does_not_satisfy_retrieval_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotARetrievalSource:
        """Deliberately lacks retrieve()."""

    assert isinstance(NotARetrievalSource(), RetrievalPort) is False
