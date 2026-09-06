"""Unit tests for jarvis.application.coding.context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.coding.context import inject_referenced_file_context
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

if TYPE_CHECKING:
    from pathlib import Path


def test_returns_task_unchanged_when_no_file_is_referenced(tmp_path: Path) -> None:
    """A task naming no real file at all is returned exactly as given."""
    task = Tainted("fix the bug in the parser", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert result is task


def test_returns_task_unchanged_when_the_named_file_does_not_exist(tmp_path: Path) -> None:
    """A task naming a filename-shaped token that isn't a real file is returned unchanged."""
    task = Tainted("fix the bug in nonexistent.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert result is task


def test_injects_real_content_of_a_referenced_file(tmp_path: Path) -> None:
    """A real, existing file named in the task text has its own real content folded in."""
    (tmp_path / "foo.py").write_text("def bar():\n    return 1\n")
    task = Tainted("fix the bug in foo.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert "foo.py" in result.value
    assert "def bar():" in result.value
    assert "fix the bug in foo.py" in result.value


def test_injected_content_is_tagged_untrusted_external(tmp_path: Path) -> None:
    """Injected file content always downgrades trust to UNTRUSTED_EXTERNAL, merge's own fail-closed rule."""  # noqa: E501
    (tmp_path / "a.py").write_text("real content")
    task = Tainted("look at a.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert result.provenance.trust == Trust.UNTRUSTED_EXTERNAL


def test_classification_is_preserved_from_the_original_task(tmp_path: Path) -> None:
    """Classification is not independently assessed per file -- it stays the task's own."""
    (tmp_path / "a.py").write_text("real content")
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.SENSITIVE, sources=frozenset()
    )
    task = Tainted("look at a.py", provenance)

    result = inject_referenced_file_context(task, tmp_path)

    assert result.provenance.classification == Classification.SENSITIVE


def test_a_path_traversal_token_escaping_the_repo_is_silently_skipped(tmp_path: Path) -> None:
    """A '../'-style token that would escape the repo's own real boundary is never read."""
    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("should never be read")
    repo = tmp_path / "repo"
    repo.mkdir()
    task = Tainted("check ../outside_secret.txt", Provenance.user())

    result = inject_referenced_file_context(task, repo)

    assert result is task


def test_multiple_referenced_files_are_all_included(tmp_path: Path) -> None:
    """Every real, distinct file named in the task text is included, not just the first."""
    (tmp_path / "a.py").write_text("content a")
    (tmp_path / "b.py").write_text("content b")
    task = Tainted("compare a.py and b.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert "content a" in result.value
    assert "content b" in result.value


def test_total_included_content_is_bounded(tmp_path: Path) -> None:
    """Combined included content across all files never exceeds the real, stated budget."""
    huge_content = "x" * 20000
    (tmp_path / "big.py").write_text(huge_content)
    task = Tainted("look at big.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    max_reasonable_length = len(task.value) + 8000 + 200
    assert len(result.value) < max_reasonable_length


def test_the_same_file_referenced_twice_in_the_task_text_is_included_only_once(
    tmp_path: Path,
) -> None:
    """A file named more than once in the task text is deduplicated, not read/included twice."""
    (tmp_path / "a.py").write_text("content a")
    task = Tainted("look at a.py, then re-check a.py again", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert result.value.count("content a") == 1


def test_a_second_file_is_skipped_once_the_real_budget_is_already_exhausted(
    tmp_path: Path,
) -> None:
    """The second of two referenced files is never even read once the combined budget hits zero."""
    (tmp_path / "big.py").write_text("x" * 8000)
    (tmp_path / "small.py").write_text("distinctive marker content")
    task = Tainted("look at big.py and small.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert "distinctive marker content" not in result.value


def test_a_file_that_is_not_valid_utf8_is_silently_skipped(tmp_path: Path) -> None:
    """A real, existing file with invalid UTF-8 content is skipped, not a hard error."""
    binary_path = tmp_path / "binary.py"
    binary_path.write_bytes(b"\xff\xfe\x00\x01invalid utf-8")
    task = Tainted("look at binary.py", Provenance.user())

    result = inject_referenced_file_context(task, tmp_path)

    assert result is task
