"""Contract test: adapters must structurally satisfy jarvis.ports.file_system.FileSystemPort."""

from __future__ import annotations

from jarvis.adapters.file_system import LocalFileSystemAdapter
from jarvis.ports.file_system import FileSystemPort


def test_local_file_system_adapter_satisfies_file_system_port() -> None:
    """LocalFileSystemAdapter is structurally a FileSystemPort."""
    adapter = LocalFileSystemAdapter()

    assert isinstance(adapter, FileSystemPort)


def test_an_object_missing_read_text_does_not_satisfy_file_system_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAFileSystemSource:
        """Deliberately lacks read_text()/list_dir()/move()/delete()."""

    assert isinstance(NotAFileSystemSource(), FileSystemPort) is False
