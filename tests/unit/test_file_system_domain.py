"""Unit tests for jarvis.domain.file_system.DirEntry."""

from __future__ import annotations

from jarvis.domain.file_system import DirEntry


def test_dir_entry_holds_the_real_name_and_is_dir_flag() -> None:
    entry = DirEntry(name="note.txt", is_dir=False)

    assert entry.name == "note.txt"
    assert entry.is_dir is False


def test_dir_entry_for_a_real_directory() -> None:
    entry = DirEntry(name="subdir", is_dir=True)

    assert entry.is_dir is True
