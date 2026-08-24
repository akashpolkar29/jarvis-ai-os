"""Contract test: adapters must structurally satisfy jarvis.ports.vscode's VsCodePort."""

from __future__ import annotations

from jarvis.adapters.vscode import VsCodeCliAdapter
from jarvis.ports.vscode import VsCodePort


def test_vscode_cli_adapter_satisfies_vscode_port() -> None:
    """VsCodeCliAdapter is structurally a VsCodePort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores a callable), so this needs no real editor.
    """
    adapter = VsCodeCliAdapter()

    assert isinstance(adapter, VsCodePort)


def test_an_object_missing_open_file_does_not_satisfy_vscode_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAVsCodeSource:
        """Deliberately lacks open_file()."""

    assert isinstance(NotAVsCodeSource(), VsCodePort) is False
