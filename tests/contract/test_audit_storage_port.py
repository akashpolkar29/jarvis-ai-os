"""Contract test: adapters must structurally satisfy jarvis.ports.audit_storage.AuditStoragePort."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.ports.audit_storage import AuditStoragePort

if TYPE_CHECKING:
    from pathlib import Path


def test_json_file_audit_storage_adapter_satisfies_audit_storage_port(tmp_path: Path) -> None:
    """JsonFileAuditStorageAdapter is structurally an AuditStoragePort."""
    adapter = JsonFileAuditStorageAdapter(tmp_path / "audit.json")

    assert isinstance(adapter, AuditStoragePort)


def test_an_object_missing_save_and_load_does_not_satisfy_audit_storage_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAnAuditStorageSource:
        """Deliberately lacks save() and load()."""

    assert isinstance(NotAnAuditStorageSource(), AuditStoragePort) is False
