"""Contract test: adapters must structurally satisfy jarvis.ports.workspace.WorkspacePort."""

from __future__ import annotations

from pathlib import Path

from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.ports.workspace import WorkspacePort


def test_local_workspace_adapter_satisfies_workspace_port() -> None:
    """LocalWorkspaceAdapter is structurally a WorkspacePort.

    Safe to construct with an arbitrary path here: __init__ does zero
    I/O (it only stores the path), so no real directory needs to exist.
    """
    adapter = LocalWorkspaceAdapter(Path("/nonexistent"))

    assert isinstance(adapter, WorkspacePort)


def test_an_object_missing_the_two_methods_does_not_satisfy_workspace_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAWorkspace:
        """Deliberately lacks root()/apply_patch()."""

    assert isinstance(NotAWorkspace(), WorkspacePort) is False
