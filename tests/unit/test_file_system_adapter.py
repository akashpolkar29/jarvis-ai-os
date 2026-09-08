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


def test_find_matches_recursively_by_glob_pattern(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("b", encoding="utf-8")
    (tmp_path / "sub" / "c.txt").write_text("c", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    matches = adapter.find(tmp_path, "*.py")

    assert matches == (tmp_path / "a.py", tmp_path / "sub" / "b.py")


def test_find_returns_empty_tuple_for_no_matches(tmp_path: Path) -> None:
    adapter = LocalFileSystemAdapter()

    assert adapter.find(tmp_path, "*.py") == ()


def test_search_content_finds_matching_lines_recursively(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello world\nsecond line\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("no match here\n", encoding="utf-8")
    (tmp_path / "sub" / "c.txt").write_text("another world entry\n", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    matches, capped = adapter.search_content(
        tmp_path, "world", max_file_bytes=1_000_000, max_files_scanned=1_000
    )

    assert set(matches) == {
        (tmp_path / "a.txt", 1, "hello world"),
        (tmp_path / "sub" / "c.txt", 1, "another world entry"),
    }
    assert capped is False


def test_search_content_skips_files_larger_than_the_byte_cap(tmp_path: Path) -> None:
    (tmp_path / "small.txt").write_text("world", encoding="utf-8")
    (tmp_path / "big.txt").write_text("world " + "x" * 100, encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    matches, capped = adapter.search_content(
        tmp_path, "world", max_file_bytes=10, max_files_scanned=1_000
    )

    assert [path for path, _, _ in matches] == [tmp_path / "small.txt"]
    assert capped is False


def test_search_content_stops_after_the_file_count_cap_and_reports_capped(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"file{i}.txt").write_text("world", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    matches, capped = adapter.search_content(
        tmp_path, "world", max_file_bytes=1_000_000, max_files_scanned=2
    )

    assert len(matches) == 2  # noqa: PLR2004 -- the real, exact cap this test sets
    assert capped is True


def test_search_content_does_not_report_capped_when_the_tree_exactly_fits(tmp_path: Path) -> None:
    """capped is False when the whole tree was covered, even at exactly the cap's own count."""
    for i in range(3):
        (tmp_path / f"file{i}.txt").write_text("world", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    matches, capped = adapter.search_content(
        tmp_path, "world", max_file_bytes=1_000_000, max_files_scanned=3
    )

    assert len(matches) == 3  # noqa: PLR2004 -- the real, exact file count this test sets
    assert capped is False


def test_search_content_skips_a_binary_file_without_crashing(tmp_path: Path) -> None:
    (tmp_path / "binary.dat").write_bytes(b"\xff\xfe\x00\x01invalid utf-8 \xc3\x28")
    (tmp_path / "text.txt").write_text("world", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    matches, capped = adapter.search_content(
        tmp_path, "world", max_file_bytes=1_000_000, max_files_scanned=1_000
    )

    assert [path for path, _, _ in matches] == [tmp_path / "text.txt"]
    assert capped is False


def test_recent_sorts_by_real_modification_time_most_recent_first(tmp_path: Path) -> None:
    old = tmp_path / "old.txt"
    old.write_text("old", encoding="utf-8")
    middle = tmp_path / "middle.txt"
    middle.write_text("middle", encoding="utf-8")
    new = tmp_path / "new.txt"
    new.write_text("new", encoding="utf-8")

    now = old.stat().st_mtime
    os.utime(old, (now - 20, now - 20))
    os.utime(middle, (now - 10, now - 10))
    os.utime(new, (now, now))
    adapter = LocalFileSystemAdapter()

    files = adapter.recent(tmp_path, 10)

    assert files == (new, middle, old)


def test_recent_respects_the_limit(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"file{i}.txt").write_text("x", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    files = adapter.recent(tmp_path, 2)

    assert len(files) == 2  # noqa: PLR2004 -- the real, exact limit this test sets


def test_recent_excludes_directories(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    adapter = LocalFileSystemAdapter()

    files = adapter.recent(tmp_path, 10)

    assert files == (tmp_path / "file.txt",)
