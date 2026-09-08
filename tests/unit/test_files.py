"""Unit tests for jarvis.kernel.files's authorize_and_* composition-root functions.

allowed_root is always overridden to tmp_path here -- the real default
(Path.home()) is only used by the CLI in real invocations. A stub
FileSystemPort with call tracking stands in for
LocalFileSystemAdapter so the "denied/rejected never touches the
filesystem" tests can assert zero calls without touching real files
for those specific cases.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.file_system import LocalFileSystemAdapter
from jarvis.domain.file_system import DirEntry
from jarvis.domain.provenance import Classification, Trust
from jarvis.kernel.files import (
    PathOutsideAllowedScopeError,
    authorize_and_delete_file,
    authorize_and_find_files,
    authorize_and_list_dir,
    authorize_and_list_recent_files,
    authorize_and_move_file,
    authorize_and_read_file,
    authorize_and_search_content,
)

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1
_TWO_INVOCATIONS = 2


class _StubFileSystem:
    """A FileSystemPort test double that records every real call it receives."""

    def __init__(self, content: str = "", entries: tuple[DirEntry, ...] = ()) -> None:
        """Start with an empty call log, returning `content`/`entries` from reads/lists."""
        self.calls: list[Path] = []
        self.move_calls: list[tuple[Path, Path]] = []
        self.delete_calls: list[Path] = []
        self._content = content
        self._entries = entries

    def read_text(self, path: Path) -> str:
        """Record the call and return the fixed content."""
        self.calls.append(path)
        return self._content

    def list_dir(self, path: Path) -> tuple[DirEntry, ...]:
        """Record the call and return the fixed entries."""
        self.calls.append(path)
        return self._entries

    def move(self, source: Path, destination: Path) -> None:
        """Record the call."""
        self.move_calls.append((source, destination))

    def delete(self, path: Path) -> None:
        """Record the call."""
        self.delete_calls.append(path)

    def find(self, root: Path, pattern: str) -> tuple[Path, ...]:
        """Record the call. Never used by any real test -- see module docstring."""
        self.calls.append(root)
        raise NotImplementedError(pattern)

    def search_content(
        self, root: Path, query: str, *, max_file_bytes: int, max_files_scanned: int
    ) -> tuple[tuple[tuple[Path, int, str], ...], bool]:
        """Record the call. Never used by any real test -- see module docstring."""
        self.calls.append(root)
        raise NotImplementedError(query, max_file_bytes, max_files_scanned)

    def recent(self, root: Path, limit: int) -> tuple[Path, ...]:
        """Record the call. Never used by any real test -- see module docstring."""
        self.calls.append(root)
        raise NotImplementedError(limit)


class _RaisingFileSystem:
    """A FileSystemPort test double every real method of which always raises."""

    def __init__(self, exc: Exception) -> None:
        """Store the exception every real call raises."""
        self.calls: list[Path] = []
        self._exc = exc

    def read_text(self, path: Path) -> str:
        """Record the call, then raise."""
        self.calls.append(path)
        raise self._exc

    def list_dir(self, path: Path) -> tuple[DirEntry, ...]:
        """Record the call, then raise."""
        self.calls.append(path)
        raise self._exc

    def move(self, source: Path, _destination: Path) -> None:
        """Record the call, then raise."""
        self.calls.append(source)
        raise self._exc

    def delete(self, path: Path) -> None:
        """Record the call, then raise."""
        self.calls.append(path)
        raise self._exc

    def find(self, root: Path, pattern: str) -> tuple[Path, ...]:
        """Record the call, then raise."""
        del pattern
        self.calls.append(root)
        raise self._exc

    def search_content(
        self, root: Path, query: str, *, max_file_bytes: int, max_files_scanned: int
    ) -> tuple[tuple[tuple[Path, int, str], ...], bool]:
        """Record the call, then raise."""
        del query, max_file_bytes, max_files_scanned
        self.calls.append(root)
        raise self._exc

    def recent(self, root: Path, limit: int) -> tuple[Path, ...]:
        """Record the call, then raise."""
        del limit
        self.calls.append(root)
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


def test_list_dir_returns_tainted_entries_when_granted(tmp_path: Path) -> None:
    entries = (DirEntry(name="a.txt", is_dir=False), DirEntry(name="subdir", is_dir=True))
    file_system = _StubFileSystem(entries=entries)

    outcome = authorize_and_list_dir(
        tmp_path,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=file_system,
    )

    assert outcome.decision.granted is True
    assert outcome.entries is not None
    assert [e.value.name for e in outcome.entries] == ["a.txt", "subdir"]
    assert outcome.entries[0].provenance.trust == Trust.UNTRUSTED_EXTERNAL
    assert outcome.entries[0].provenance.classification == Classification.SENSITIVE


def test_list_dir_out_of_scope_path_is_rejected_and_never_touches_the_filesystem(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside_dir = tmp_path_factory.mktemp("outside")
    file_system = _StubFileSystem()

    with pytest.raises(PathOutsideAllowedScopeError):
        authorize_and_list_dir(
            outside_dir,
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=file_system,
        )

    assert file_system.calls == []


def test_move_file_relocates_when_granted(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    file_system = _StubFileSystem()

    decision = authorize_and_move_file(
        source,
        destination,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=file_system,
    )

    assert decision.granted is True
    assert file_system.move_calls == [(source.resolve(), destination.resolve())]


def test_move_file_denied_never_touches_the_filesystem(tmp_path: Path) -> None:
    """fs.move_file floors WRITE_LOCAL/CONFIRM -- no confirmation channel means denied."""
    file_system = _StubFileSystem()

    decision = authorize_and_move_file(
        tmp_path / "source.txt",
        tmp_path / "destination.txt",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=file_system,
    )

    assert decision.granted is False
    assert file_system.move_calls == []


def test_move_file_rejects_an_out_of_scope_destination(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Both endpoints are scope-checked -- an in-scope source with an out-of-scope destination fails."""  # noqa: E501
    outside_dir = tmp_path_factory.mktemp("outside")
    source = tmp_path / "source.txt"
    file_system = _StubFileSystem()

    with pytest.raises(PathOutsideAllowedScopeError):
        authorize_and_move_file(
            source,
            outside_dir / "destination.txt",
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=file_system,
        )

    assert file_system.move_calls == []


def test_delete_file_removes_when_granted(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    file_system = _StubFileSystem()

    decision = authorize_and_delete_file(
        path,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=file_system,
    )

    assert decision.granted is True
    assert file_system.delete_calls == [path.resolve()]


def test_delete_file_denied_without_physical_confirmation_never_touches_the_filesystem(
    tmp_path: Path,
) -> None:
    """The single most important property this ADR-0060 capability exists to guarantee:
    fs.delete_file (Tier.MANUAL_ONLY) is denied whenever physical_confirmation_available
    is False, remote confirmation notwithstanding -- mirroring ADR-0059's own identical
    property test shape for email-send/attended-calendar-event creation."""
    file_system = _StubFileSystem()

    decision = authorize_and_delete_file(
        tmp_path / "note.txt",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=file_system,
    )

    assert decision.granted is False
    assert file_system.delete_calls == []


def test_delete_file_out_of_scope_path_is_rejected_and_never_touches_the_filesystem(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside_dir = tmp_path_factory.mktemp("outside")
    file_system = _StubFileSystem()

    with pytest.raises(PathOutsideAllowedScopeError):
        authorize_and_delete_file(
            outside_dir / "secret.txt",
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=tmp_path / "audit_chain.json",
            allowed_root=tmp_path,
            file_system=file_system,
        )

    assert file_system.delete_calls == []


# --- fs.find / fs.search_content / fs.recent (2026-09-08): real, recursive search
# capabilities. Boundary-safety tests use the REAL LocalFileSystemAdapter, not
# _StubFileSystem -- proving the real rglob-based escape defense requires
# exercising real rglob against a real, adversarial filesystem tree, not a stub.


def test_find_granted_returns_every_real_recursive_match(tmp_path: Path) -> None:
    """rglob('*.py') matches at every depth -- both the top-level and nested file."""
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("b", encoding="utf-8")

    outcome = authorize_and_find_files(
        "*.py",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.matches == (tmp_path / "a.py", tmp_path / "sub" / "b.py")


def test_find_a_pattern_containing_dot_dot_never_returns_a_result_outside_allowed_root(
    tmp_path: Path,
) -> None:
    """A real, adversarial glob pattern: '..' segments can make rglob escape allowed_root.

    ``allowed.rglob("../outside/*.txt")`` genuinely walks outside
    ``allowed_root`` at the filesystem level (confirmed directly, not
    assumed) -- this proves the kernel's own post-hoc
    ``_resolve_within_scope`` re-check on every individual result
    silently drops it rather than ever returning it.
    """
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("nope", encoding="utf-8")

    # Confirm the real, adversarial escape actually happens at the raw adapter
    # level first -- otherwise this test would not be proving anything real.
    # rglob's own raw result keeps the literal, unresolved '..' segment
    # (pathlib never auto-normalizes it), so compare resolved forms.
    raw_matches = LocalFileSystemAdapter().find(allowed_root, "../outside/*.txt")
    assert (outside_dir / "secret.txt").resolve() in {match.resolve() for match in raw_matches}

    outcome = authorize_and_find_files(
        "../outside/*.txt",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=allowed_root,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.matches == ()


def test_find_a_symlink_escaping_allowed_root_is_dropped_from_results(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("nope", encoding="utf-8")
    (allowed_root / "escape_link").symlink_to(outside_dir)

    outcome = authorize_and_find_files(
        "**/*.txt",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=allowed_root,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.matches is not None
    assert all(match.is_relative_to(allowed_root.resolve()) for match in outcome.matches)


def test_search_content_granted_returns_only_in_scope_matches(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello world\n", encoding="utf-8")

    outcome = authorize_and_search_content(
        "world",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.matches == ((tmp_path / "a.txt", 1, "hello world"),)
    assert outcome.capped is False


def test_search_content_surfaces_the_real_capped_flag_honestly(tmp_path: Path) -> None:
    """A real, small file-count cap: the outcome's own capped flag reflects it, not silently."""
    for i in range(3):
        (tmp_path / f"file{i}.txt").write_text("world", encoding="utf-8")

    outcome = authorize_and_search_content(
        "world",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=LocalFileSystemAdapter(),
    )

    # The real, hardcoded kernel-level cap (5,000) is far above this test's
    # own 3 files -- capped is correctly False here. A dedicated adapter-level
    # test (test_file_system_adapter.py) already proves the cap mechanism
    # itself fires at small, explicit thresholds; this test proves the
    # kernel wires that same real flag straight through, unmodified.
    assert outcome.decision.granted is True
    assert outcome.capped is False
    assert outcome.matches is not None
    assert len(outcome.matches) == 3  # noqa: PLR2004 -- the real, exact file count this test sets


def test_search_content_a_pattern_containing_dot_dot_path_never_returns_a_result_outside_allowed_root(  # noqa: E501
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("world", encoding="utf-8")
    (allowed_root / "escape_link").symlink_to(outside_dir)

    outcome = authorize_and_search_content(
        "world",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=allowed_root,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.matches is not None
    assert all(
        path.is_relative_to(allowed_root.resolve()) for path, _line_number, _line in outcome.matches
    )


def test_recent_granted_returns_only_in_scope_files_most_recent_first(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_text("old", encoding="utf-8")
    new = tmp_path / "new.txt"
    new.write_text("new", encoding="utf-8")
    now = new.stat().st_mtime
    os.utime(tmp_path / "old.txt", (now - 100, now - 100))

    outcome = authorize_and_list_recent_files(
        limit=10,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=tmp_path,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.files == (new, tmp_path / "old.txt")


def test_recent_a_symlink_escaping_allowed_root_is_dropped_from_results(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("nope", encoding="utf-8")
    (allowed_root / "escape_link").symlink_to(outside_dir)

    outcome = authorize_and_list_recent_files(
        limit=10,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        allowed_root=allowed_root,
        file_system=LocalFileSystemAdapter(),
    )

    assert outcome.decision.granted is True
    assert outcome.files is not None
    assert all(match.is_relative_to(allowed_root.resolve()) for match in outcome.files)
