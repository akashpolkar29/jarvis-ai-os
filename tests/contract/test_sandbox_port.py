"""Contract test: adapters must structurally satisfy jarvis.ports.sandbox's SandboxPort."""

from __future__ import annotations

from jarvis.adapters.sandbox import BwrapSandboxAdapter
from jarvis.ports.sandbox import SandboxPort


def test_bwrap_sandbox_adapter_satisfies_sandbox_port() -> None:
    """BwrapSandboxAdapter is structurally a SandboxPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores a callable), so this needs no real bwrap process.
    """
    adapter = BwrapSandboxAdapter()

    assert isinstance(adapter, SandboxPort)


def test_an_object_missing_run_does_not_satisfy_sandbox_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotASandboxSource:
        """Deliberately lacks run()."""

    assert isinstance(NotASandboxSource(), SandboxPort) is False
