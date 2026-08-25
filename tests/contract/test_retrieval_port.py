"""Contract test: jarvis.ports.retrieval.RetrievalPort's own shape.

No real adapter exists yet (WP-61) -- matching M3's own "port exists
and is tested structurally before any real technology is chosen"
ordering, this proves the Protocol itself is well-formed and
satisfiable via a minimal fake, not that any specific real adapter
satisfies it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.ports.retrieval import RetrievalPort

if TYPE_CHECKING:
    from jarvis.domain.memory import MemoryRecord


class _FakeRetrievalAdapter:
    """A minimal, real fake proving RetrievalPort is satisfiable."""

    def retrieve(self, query: str, *, limit: int) -> tuple[MemoryRecord, ...]:  # noqa: ARG002
        return ()


def test_a_conforming_fake_satisfies_retrieval_port() -> None:
    """A real, minimal implementation is structurally a RetrievalPort."""
    adapter = _FakeRetrievalAdapter()

    assert isinstance(adapter, RetrievalPort)


def test_an_object_missing_retrieve_does_not_satisfy_retrieval_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotARetrievalSource:
        """Deliberately lacks retrieve()."""

    assert isinstance(NotARetrievalSource(), RetrievalPort) is False
