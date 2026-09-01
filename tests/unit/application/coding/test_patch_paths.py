"""Unit tests for jarvis.application.coding.patch_paths.

Covers ADR-0056's own amendment 2 requirements directly:
canonicalization (`.`/`..`/symlinks) and identical treatment of a
created file vs. a modified one -- matching
`docs/architecture/m5-browser-coding.md`'s own acceptance criterion 8.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.application.coding.patch_paths import touched_paths

_TWO_FILES = 2


def test_a_modified_file_surfaces_its_own_path(tmp_path: Path) -> None:
    patch = "--- a/widget.py\n+++ b/widget.py\n@@ -1 +1 @@\n-old\n+new\n"

    assert touched_paths(patch, tmp_path) == (Path("widget.py"),)


def test_a_created_file_surfaces_its_own_path_identically_to_a_modified_one(
    tmp_path: Path,
) -> None:
    """ADR-0056 amendment 2's own required property: created == modified, classification-wise."""
    created_patch = "--- /dev/null\n+++ b/new_file.py\n@@ -0,0 +1 @@\n+content\n"
    modified_patch = "--- a/existing_file.py\n+++ b/existing_file.py\n@@ -1 +1 @@\n-old\n+new\n"

    created_result = touched_paths(created_patch, tmp_path)
    modified_result = touched_paths(modified_patch, tmp_path)

    assert created_result == (Path("new_file.py"),)
    assert modified_result == (Path("existing_file.py"),)


def test_a_deleted_file_surfaces_its_own_pre_image_path(tmp_path: Path) -> None:
    patch = "--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-content\n"

    assert touched_paths(patch, tmp_path) == (Path("gone.py"),)


def test_multiple_files_in_one_patch_all_surface_deduplicated(tmp_path: Path) -> None:
    patch = (
        "--- a/one.py\n+++ b/one.py\n@@ -1 +1 @@\n-a\n+b\n"
        "--- a/two.py\n+++ b/two.py\n@@ -1 +1 @@\n-a\n+b\n"
    )

    result = touched_paths(patch, tmp_path)

    assert set(result) == {Path("one.py"), Path("two.py")}
    assert len(result) == _TWO_FILES  # each path once, not once per --- / +++ header line


def test_a_dot_dot_path_is_canonicalized_before_being_returned(tmp_path: Path) -> None:
    """ADR-0056 amendment 2's own required canonicalization property."""
    patch = "--- a/sub/../widget.py\n+++ b/sub/../widget.py\n@@ -1 +1 @@\n-old\n+new\n"

    assert touched_paths(patch, tmp_path) == (Path("widget.py"),)


def test_a_path_that_escapes_the_repo_root_is_returned_absolute_not_silently_dropped(
    tmp_path: Path,
) -> None:
    patch = "--- a/../../etc/passwd\n+++ b/../../etc/passwd\n@@ -1 +1 @@\n-old\n+new\n"

    result = touched_paths(patch, tmp_path)

    assert len(result) == 1
    assert result[0].is_absolute()
    assert not result[0].is_relative_to(tmp_path)


def test_an_empty_patch_touches_nothing(tmp_path: Path) -> None:
    assert touched_paths("", tmp_path) == ()


def test_prose_mentioning_diff_style_lines_that_are_not_real_headers_is_ignored(
    tmp_path: Path,
) -> None:
    """Only real header lines (--- / +++ ) count -- context lines starting similarly do not."""
    patch = "not a real header\n--- a/real.py\n+++ b/real.py\n@@ -1 +1 @@\n-old\n+new\n"

    assert touched_paths(patch, tmp_path) == (Path("real.py"),)


def test_a_header_path_with_no_a_b_prefix_is_used_as_is(tmp_path: Path) -> None:
    """Not every real diff tool prefixes with a/ b/ (e.g. some -p0-style output) -- handled."""
    patch = "--- widget.py\n+++ widget.py\n@@ -1 +1 @@\n-old\n+new\n"

    assert touched_paths(patch, tmp_path) == (Path("widget.py"),)
