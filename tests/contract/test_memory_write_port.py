"""Contract test: jarvis.ports.memory_write.MemoryWritePort's own shape.

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
from jarvis.ports.memory_write import MemoryWritePort

if TYPE_CHECKING:
    from jarvis.domain.provenance import Tainted

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeMemoryWriteAdapter:
    """A minimal, real fake proving MemoryWritePort is satisfiable."""

    def write(self, value: Tainted[object]) -> str:  # noqa: ARG002
        return "mem:1"

    def pin(self, identifier: str) -> None:
        pass

    def sweep_expired(self) -> int:
        return 0

    def forget(self, identifier: str) -> None:
        pass


class _FakeEmbeddingPort:
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((0.0,) for _ in texts)


class _FakeClock:
    def now(self) -> datetime:
        return _NOW


class _FakeIdPort:
    def new_id(self) -> str:
        return "mem:1"


def test_a_conforming_fake_satisfies_memory_write_port() -> None:
    """A real, minimal implementation is structurally a MemoryWritePort."""
    adapter = _FakeMemoryWriteAdapter()

    assert isinstance(adapter, MemoryWritePort)


def test_sqlite_memory_adapter_satisfies_memory_write_port() -> None:
    """The real WP-61 adapter is structurally a MemoryWritePort."""
    adapter = SqliteMemoryAdapter(":memory:", _FakeEmbeddingPort(), _FakeClock(), _FakeIdPort())

    assert isinstance(adapter, MemoryWritePort)


def test_an_object_missing_the_required_methods_does_not_satisfy_memory_write_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAMemoryWriteSource:
        """Deliberately lacks write()/pin()/sweep_expired()/forget()."""

    assert isinstance(NotAMemoryWriteSource(), MemoryWritePort) is False
