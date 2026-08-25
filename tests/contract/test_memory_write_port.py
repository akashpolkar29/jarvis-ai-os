"""Contract test: jarvis.ports.memory_write.MemoryWritePort's own shape.

No real adapter exists yet (WP-61) -- matching M3's own "port exists
and is tested structurally before any real technology is chosen"
ordering, this proves the Protocol itself is well-formed and
satisfiable via a minimal fake, not that any specific real adapter
satisfies it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.ports.memory_write import MemoryWritePort

if TYPE_CHECKING:
    from jarvis.domain.provenance import Tainted


class _FakeMemoryWriteAdapter:
    """A minimal, real fake proving MemoryWritePort is satisfiable."""

    def write(self, value: Tainted[object]) -> str:  # noqa: ARG002
        return "mem:1"

    def pin(self, identifier: str) -> None:
        pass


def test_a_conforming_fake_satisfies_memory_write_port() -> None:
    """A real, minimal implementation is structurally a MemoryWritePort."""
    adapter = _FakeMemoryWriteAdapter()

    assert isinstance(adapter, MemoryWritePort)


def test_an_object_missing_the_two_methods_does_not_satisfy_memory_write_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAMemoryWriteSource:
        """Deliberately lacks write()/pin()."""

    assert isinstance(NotAMemoryWriteSource(), MemoryWritePort) is False
