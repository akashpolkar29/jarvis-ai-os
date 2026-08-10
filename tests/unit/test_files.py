"""Unit tests for jarvis.kernel.files.authorize_and_read_file.

allowed_root is always overridden to tmp_path here -- the real default
(Path.home()) is only used by the CLI in real invocations. A stub
FileSystemPort with call tracking stands in for
LocalFileSystemAdapter so the "denied/rejected never touches the
filesystem" tests can assert zero calls without touching real files
for those specific cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.provenance import Classification, Trust
from jarvis.kernel.files import PathOutsideAllowedScopeError, authorize_and_read_file

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1
_TWO_INVOCATIONS = 2


class _StubFileSystem:
    """A FileSystemPort test double that records every read_text() call."""

    def __init__(self, content: str = "") -> None:
        """Start with an empty call log, returning `content` from every read."""
        self.calls: list[Path] = []
        self._content = content

    def read_text(self, path: Path) -> str:
        """Record the call and return the fixed content."""
        self.calls.append(path)
        return self._content


class _RaisingFileSystem:
    """A FileSystemPort test double whose read_text() always raises."""

    def __init__(self, exc: Exception) -> None:
        """Store the exception every read_text() call raises."""
        self.calls: list[Path] = []
        self._exc = exc

    def read_text(self, path: Path) -> str:
        """Record the call, then raise."""
        self.calls.append(path)
        raise self._exc


def test_in_scope_read_is_granted_and_returns_tainted_content(tmp_path: Path) -> None:
    """A successful read returns the correct content, wrapped with the right provenance."""
    file_path = tmp_path / "note.txt"
    file_path.write_text("real content", encoding="utf-8")
    file_system = _StubFileSystem("real content")

    outcome = authorize_and_read_file(
        file_path,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=file_system,
    )

    assert outcome.decision.granted is True
    assert outcome.content is not None
    assert outcome.content.value == "real content"
    assert outcome.content.provenance.trust == Trust.UNTRUSTED_EXTERNAL
    assert outcome.content.provenance.classification == Classification.SENSITIVE
    assert file_system.calls == [file_path.resolve()]


def test_out_of_scope_path_is_rejected_before_authorization_and_never_touches_the_filesystem(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A path outside allowed_root raises before authorize_by_id ever runs.

    Proves both halves of the design: the rejection happens (not
    silently allowed), and the filesystem is never touched -- the
    stub's call log stays empty, a stronger guarantee than a
    Decision-level denial since nothing about this request was even
    evaluated.
    """
    outside_dir = tmp_path_factory.mktemp("outside")
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("nope", encoding="utf-8")
    file_system = _StubFileSystem()

    with pytest.raises(PathOutsideAllowedScopeError):
        authorize_and_read_file(
            outside_file,
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=file_system,
        )

    assert file_system.calls == []


def test_out_of_scope_rejection_leaves_no_audit_record(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The documented audit-trail gap: a scope rejection never reaches the chain."""
    chain_path = tmp_path / "audit_chain.json"
    outside_dir = tmp_path_factory.mktemp("outside")
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("nope", encoding="utf-8")

    with pytest.raises(PathOutsideAllowedScopeError):
        authorize_and_read_file(
            outside_file,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=chain_path,
            allowed_root=tmp_path,
            file_system=_StubFileSystem(),
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 0


def test_a_symlink_pointing_outside_the_allowed_root_is_rejected(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Symlink resolution is not a bypass: resolve() follows it before the scope check."""
    outside_dir = tmp_path_factory.mktemp("outside")
    outside_target = outside_dir / "real.txt"
    outside_target.write_text("nope", encoding="utf-8")
    symlink_path = tmp_path / "innocent_looking_link.txt"
    symlink_path.symlink_to(outside_target)

    with pytest.raises(PathOutsideAllowedScopeError):
        authorize_and_read_file(
            symlink_path,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=_StubFileSystem(),
        )


def test_nonexistent_in_scope_path_is_granted_then_raises_file_not_found(tmp_path: Path) -> None:
    """An in-scope but nonexistent path is authorized (in-scope-ness doesn't require existence).

    but then fails at the actual read -- matching how a real
    LocalFileSystemAdapter behaves.
    """
    file_system = _RaisingFileSystem(FileNotFoundError("no such file"))

    with pytest.raises(FileNotFoundError):
        authorize_and_read_file(
            tmp_path / "does_not_exist.txt",
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=file_system,
        )

    assert len(file_system.calls) == 1


def test_audit_record_is_saved_even_when_the_granted_read_fails(tmp_path: Path) -> None:
    """A granted decision is persisted even if the read itself then fails.

    The try/finally audit-save guarantee from WP-14, applied here: the
    decision to authorize fs.read_file for this path was granted and
    must not be silently lost just because the file turned out to be
    unreadable.
    """
    chain_path = tmp_path / "audit_chain.json"
    file_system = _RaisingFileSystem(PermissionError("denied"))

    with pytest.raises(PermissionError):
        authorize_and_read_file(
            tmp_path / "unreadable.txt",
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=chain_path,
            allowed_root=tmp_path,
            file_system=file_system,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True


def test_state_persists_across_separate_calls_against_the_same_path(tmp_path: Path) -> None:
    """Two calls against the same chain path grow the chain, mirroring separate CLI runs."""
    chain_path = tmp_path / "audit_chain.json"
    first_file = tmp_path / "a.txt"
    first_file.write_text("a", encoding="utf-8")
    second_file = tmp_path / "b.txt"
    second_file.write_text("b", encoding="utf-8")

    authorize_and_read_file(
        first_file,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        allowed_root=tmp_path,
        file_system=_StubFileSystem("a"),
    )
    authorize_and_read_file(
        second_file,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        allowed_root=tmp_path,
        file_system=_StubFileSystem("b"),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _TWO_INVOCATIONS
    assert chain.verify().valid is True
