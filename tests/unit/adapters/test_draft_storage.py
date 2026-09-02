"""Unit tests for jarvis.adapters.draft_storage.LocalDraftStorageAdapter.

Unlike the D-Bus and network adapters elsewhere in this ring, nothing
here is mocked: plain local-filesystem writes are a reliable CI
dependency, so every test runs a real write against a real temporary
directory -- see this adapter's own module docstring for why.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.draft_storage import LocalDraftStorageAdapter

if TYPE_CHECKING:
    from pathlib import Path


def test_save_writes_the_real_content_to_a_new_file(tmp_path: Path) -> None:
    adapter = LocalDraftStorageAdapter(tmp_path)

    path = adapter.save("cover-letter", "Dear hiring manager,")

    assert path.read_text(encoding="utf-8") == "Dear hiring manager,"


def test_save_returns_a_real_path_inside_base_dir(tmp_path: Path) -> None:
    adapter = LocalDraftStorageAdapter(tmp_path)

    path = adapter.save("cover-letter", "content")

    assert path.parent == tmp_path
    assert path.exists()


def test_save_creates_base_dir_if_it_does_not_exist_yet(tmp_path: Path) -> None:
    base_dir = tmp_path / "drafts" / "nested"
    adapter = LocalDraftStorageAdapter(base_dir)

    path = adapter.save("cover-letter", "content")

    assert base_dir.is_dir()
    assert path.exists()


def test_save_never_overwrites_an_existing_file_with_the_same_hint(tmp_path: Path) -> None:
    adapter = LocalDraftStorageAdapter(tmp_path)

    first = adapter.save("cover-letter", "first draft")
    second = adapter.save("cover-letter", "second draft")

    assert first != second
    assert first.read_text(encoding="utf-8") == "first draft"
    assert second.read_text(encoding="utf-8") == "second draft"


def test_save_a_third_time_with_the_same_hint_still_never_overwrites(tmp_path: Path) -> None:
    """The uniqueness counter keeps incrementing, not just a one-time fallback."""
    adapter = LocalDraftStorageAdapter(tmp_path)

    first = adapter.save("cover-letter", "1")
    second = adapter.save("cover-letter", "2")
    third = adapter.save("cover-letter", "3")

    assert len({first, second, third}) == 3  # noqa: PLR2004 -- the real count of distinct saves
    assert [p.read_text(encoding="utf-8") for p in (first, second, third)] == ["1", "2", "3"]


def test_save_sanitizes_a_path_traversal_attempt_in_the_filename_hint(tmp_path: Path) -> None:
    """A filename_hint containing '../' segments can never escape base_dir."""
    adapter = LocalDraftStorageAdapter(tmp_path)
    outside_marker = tmp_path.parent / "escaped.txt"

    path = adapter.save("../../../../tmp/escaped", "content")

    assert path.parent == tmp_path
    assert not outside_marker.exists()


def test_save_sanitizes_a_hint_containing_a_path_separator(tmp_path: Path) -> None:
    """A filename_hint containing a literal '/' never creates a subdirectory or escapes base_dir."""
    adapter = LocalDraftStorageAdapter(tmp_path)

    path = adapter.save("some/nested/path", "content")

    assert path.parent == tmp_path
    assert path.exists()


def test_save_falls_back_to_a_real_default_stem_for_an_all_unsafe_hint(tmp_path: Path) -> None:
    adapter = LocalDraftStorageAdapter(tmp_path)

    path = adapter.save("////", "content")

    assert path.parent == tmp_path
    assert path.stem == "draft"
    assert path.read_text(encoding="utf-8") == "content"


def test_save_falls_back_to_a_real_default_stem_for_an_empty_hint(tmp_path: Path) -> None:
    adapter = LocalDraftStorageAdapter(tmp_path)

    path = adapter.save("", "content")

    assert path.stem == "draft"
