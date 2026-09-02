"""Contract test: jarvis.ports.draft_storage.DraftStoragePort's own shape.

A minimal fake proves the Protocol itself is well-formed and
satisfiable independent of any specific adapter (WP-82, mirroring
test_memory_write_port.py's own "port exists and is tested
structurally before any real technology is chosen" ordering).
LocalDraftStorageAdapter (WP-83) is the real, now-existing adapter,
checked below too -- safe to construct with an arbitrary path, since
__init__ does zero I/O (mirrors LocalWorkspaceAdapter's own precedent,
test_workspace_port.py).
"""

from __future__ import annotations

from pathlib import Path

from jarvis.adapters.draft_storage import LocalDraftStorageAdapter
from jarvis.ports.draft_storage import DraftStoragePort


class _FakeDraftStorageAdapter:
    """A minimal, real fake proving DraftStoragePort is satisfiable."""

    def save(self, filename_hint: str, content: str) -> Path:
        del content
        return Path(f"/tmp/{filename_hint}.txt")  # a fake path, never a real write


def test_a_conforming_fake_satisfies_draft_storage_port() -> None:
    """A real, minimal implementation is structurally a DraftStoragePort."""
    adapter = _FakeDraftStorageAdapter()

    assert isinstance(adapter, DraftStoragePort)


def test_local_draft_storage_adapter_satisfies_draft_storage_port() -> None:
    """LocalDraftStorageAdapter is structurally a DraftStoragePort."""
    adapter = LocalDraftStorageAdapter(Path("/nonexistent"))

    assert isinstance(adapter, DraftStoragePort)


def test_an_object_missing_save_does_not_satisfy_draft_storage_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotADraftStore:
        """Deliberately lacks save()."""

    assert isinstance(NotADraftStore(), DraftStoragePort) is False
