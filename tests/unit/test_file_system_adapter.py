"""Unit tests for jarvis.adapters.file_system.LocalFileSystemAdapter.

No mocking here, deliberately: unlike D-Bus (WP-14), real filesystem
I/O against a real temp file is fully hermetic, fast, and safe -- so
these tests exercise the real read_text() against real files.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.file_system import LocalFileSystemAdapter

if TYPE_CHECKING:
    from pathlib import Path


def test_read_text_returns_the_file_content(tmp_path: Path) -> None:
    """read_text() returns exactly what was written to the file."""
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello from a real file", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    assert adapter.read_text(file_path) == "hello from a real file"


def test_read_text_raises_file_not_found_for_a_nonexistent_path(tmp_path: Path) -> None:
    """A nonexistent path raises the standard, unwrapped FileNotFoundError."""
    adapter = LocalFileSystemAdapter()

    with pytest.raises(FileNotFoundError):
        adapter.read_text(tmp_path / "does_not_exist.txt")


def test_read_text_raises_is_a_directory_error_for_a_directory(tmp_path: Path) -> None:
    """A directory path raises the standard, unwrapped IsADirectoryError."""
    adapter = LocalFileSystemAdapter()

    with pytest.raises(IsADirectoryError):
        adapter.read_text(tmp_path)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod-based permission denial is not meaningful on Windows or as root",
)
def test_read_text_raises_permission_error_for_an_unreadable_file(tmp_path: Path) -> None:
    """A file with no read permission raises the standard, unwrapped PermissionError."""
    file_path = tmp_path / "secret.txt"
    file_path.write_text("shh", encoding="utf-8")
    file_path.chmod(0o000)
    adapter = LocalFileSystemAdapter()

    try:
        with pytest.raises(PermissionError):
            adapter.read_text(file_path)
    finally:
        file_path.chmod(0o644)


def test_read_text_raises_unicode_decode_error_for_a_binary_file(tmp_path: Path) -> None:
    """A non-UTF-8 file raises the standard, unwrapped UnicodeDecodeError."""
    file_path = tmp_path / "binary.dat"
    file_path.write_bytes(b"\xff\xfe\x00\x01invalid utf-8 \xc3\x28")
    adapter = LocalFileSystemAdapter()

    with pytest.raises(UnicodeDecodeError):
        adapter.read_text(file_path)


def test_list_dir_returns_every_real_entry_sorted_by_name(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    adapter = LocalFileSystemAdapter()

    entries = adapter.list_dir(tmp_path)

    assert [entry.name for entry in entries] == ["a.txt", "b.txt", "subdir"]
    assert [entry.is_dir for entry in entries] == [False, False, True]


def test_list_dir_returns_empty_tuple_for_an_empty_directory(tmp_path: Path) -> None:
    adapter = LocalFileSystemAdapter()

    assert adapter.list_dir(tmp_path) == ()


def test_list_dir_raises_not_a_directory_error_for_a_file(tmp_path: Path) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    with pytest.raises(NotADirectoryError):
        adapter.list_dir(file_path)


def test_list_dir_raises_file_not_found_for_a_nonexistent_path(tmp_path: Path) -> None:
    adapter = LocalFileSystemAdapter()

    with pytest.raises(FileNotFoundError):
        adapter.list_dir(tmp_path / "does_not_exist")


def test_move_relocates_a_real_file(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("real content", encoding="utf-8")
    destination = tmp_path / "destination.txt"
    adapter = LocalFileSystemAdapter()

    adapter.move(source, destination)

    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "real content"


def test_move_relocates_a_real_directory(tmp_path: Path) -> None:
    source = tmp_path / "source_dir"
    source.mkdir()
    (source / "inner.txt").write_text("inner", encoding="utf-8")
    destination = tmp_path / "destination_dir"
    adapter = LocalFileSystemAdapter()

    adapter.move(source, destination)

    assert not source.exists()
    assert (destination / "inner.txt").read_text(encoding="utf-8") == "inner"


def test_move_raises_file_not_found_for_a_nonexistent_source(tmp_path: Path) -> None:
    adapter = LocalFileSystemAdapter()

    with pytest.raises(FileNotFoundError):
        adapter.move(tmp_path / "does_not_exist.txt", tmp_path / "destination.txt")


def test_delete_removes_a_real_file(tmp_path: Path) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    adapter.delete(file_path)

    assert not file_path.exists()


def test_delete_raises_file_not_found_for_a_nonexistent_path(tmp_path: Path) -> None:
    adapter = LocalFileSystemAdapter()

    with pytest.raises(FileNotFoundError):
        adapter.delete(tmp_path / "does_not_exist.txt")


def test_delete_raises_is_a_directory_error_for_a_directory(tmp_path: Path) -> None:
    """delete() only ever removes a single real file -- see the port's own module docstring."""
    adapter = LocalFileSystemAdapter()

    with pytest.raises(IsADirectoryError):
        adapter.delete(tmp_path)
