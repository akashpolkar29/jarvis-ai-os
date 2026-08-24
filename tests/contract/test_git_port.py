"""Contract test: adapters must structurally satisfy jarvis.ports.git's GitPort."""

from __future__ import annotations

from jarvis.adapters.git import GitCliAdapter
from jarvis.ports.git import GitPort


def test_git_cli_adapter_satisfies_git_port() -> None:
    """GitCliAdapter is structurally a GitPort.

    Safe to construct with no arguments here: __init__ does zero I/O,
    so this needs no real git repository.
    """
    adapter = GitCliAdapter()

    assert isinstance(adapter, GitPort)


def test_an_object_missing_the_five_methods_does_not_satisfy_git_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAGitSource:
        """Deliberately lacks status()/create_branch()/commit()/push()/force_push()."""

    assert isinstance(NotAGitSource(), GitPort) is False
