"""Minimal, non-LSP file-context injection for `coding.run_task` (M7 code-context design).

:func:`inject_referenced_file_context` is
`docs/architecture/m7-code-context-design.md`'s own real, recommended
mechanism, built: given a task's own text and a target repository,
find real, existing files the task text names literally (a real path
or filename substring, resolved and checked against the repository's
own real boundary), read a real, bounded amount of their content, and
fold it into the task text `build_prompt` already assembles --
no new port, no new third-party dependency, matching the design
doc's own reasoning for why this is preferred over full LSP
integration.

**A real, honest scope narrowing, not silently decided**: the design
doc's own file-selection heuristic also names "files a prior failed
attempt's own validation evidence references" as a second, retry-time
source. This implementation covers only the task-text-naming half --
the first, simpler heuristic. Retry-time evidence-based file selection
is real, deferred future work, not attempted here (see this function's
own docstring for exactly what it does and does not do).

**A real, load-bearing taint decision, made here**: injected file
content is tagged `Trust.UNTRUSTED_EXTERNAL` (via `Provenance.external`),
never assumed to carry the same trust as the caller-typed task text --
a target repository can contain code the user did not personally
write. Classification is *not* independently assessed per file (this
codebase has no generic "does this file contain secret-shaped content"
mechanism, and building one was already considered and rejected
elsewhere, ADR-0060's own reasoning against content-based scanning) --
the merged result's classification is the *task's own*, unchanged,
a real, conservative default: an already-`SENSITIVE`/`SECRET`
classified task stays that way; a `PUBLIC` task does not get
downgraded by file content this mechanism cannot itself assess.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from jarvis.domain.provenance import Provenance, Tainted

if TYPE_CHECKING:
    from pathlib import Path

_MAX_TOTAL_CONTEXT_CHARS = 8000
"""A real, explicit, bounded budget across every included file combined
-- an unbounded inclusion of an entire large repository is a real,
separate problem this mechanism does not attempt to solve (see this
module's own docstring)."""

_FILENAME_LIKE_TOKEN = re.compile(r"[\w./\\-]+\.[A-Za-z0-9]+")
"""Matches a real, plausible filename/relative-path token inside free
text -- e.g. `foo.py`, `src/jarvis/adapters/calendar.py` -- not a full
path grammar, a real, simple heuristic matching this mechanism's own
"minimal, non-LSP" scope."""


def _find_referenced_files(task_text: str, target_repo: Path) -> tuple[Path, ...]:
    """Find real, existing files under `target_repo` whose path is named literally in `task_text`.

    A candidate token is resolved relative to `target_repo` and kept
    only if it resolves to a real, existing file *inside*
    `target_repo`'s own real boundary -- a token that would escape it
    (e.g. via `../`) is silently skipped, not treated as an error: this
    is a best-effort text scan, not a security boundary of its own (the
    real repository-escape protections already live in
    `patch_paths.py`/`CodeWriteAuthorizer`, for real writes -- this
    function only ever reads).
    """
    resolved_root = target_repo.resolve()
    found: list[Path] = []
    seen: set[Path] = set()
    for match in _FILENAME_LIKE_TOKEN.finditer(task_text):
        candidate = (target_repo / match.group(0)).resolve()
        if candidate in seen:
            continue
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            continue
        if candidate.is_file():
            seen.add(candidate)
            found.append(candidate)
    return tuple(found)


def _read_bounded(paths: tuple[Path, ...], max_chars: int) -> tuple[tuple[Path, str], ...]:
    """Read every real file in `paths`, in order, until `max_chars` (combined) is exhausted.

    A file that cannot be read as UTF-8 text, or that no longer exists
    by the time this reads it, is silently skipped -- this is a
    best-effort context-enrichment mechanism, not a required input;
    the task still proceeds with whatever real content was
    successfully read, including none at all.
    """
    results: list[tuple[Path, str]] = []
    remaining = max_chars
    for path in paths:
        if remaining <= 0:
            break
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        truncated = content[:remaining]
        results.append((path, truncated))
        remaining -= len(truncated)
    return tuple(results)


def inject_referenced_file_context(task: Tainted[str], target_repo: Path) -> Tainted[str]:
    """Fold real, bounded content of files `task` names literally into its own text.

    Args:
        task: The real coding task's own text and provenance.
        target_repo: The real target repository files are resolved
            against and read from.

    Returns:
        `task` unchanged if no real, in-scope file was found or none
        could be read. Otherwise a new `Tainted[str]` whose text
        appends each found file's own real, bounded content, and whose
        provenance is `task.provenance` merged with a real
        `Trust.UNTRUSTED_EXTERNAL`-tagged `Provenance.external(...)` --
        `Provenance.merge`'s own fail-closed rule means trust becomes
        `UNTRUSTED_EXTERNAL` regardless of `task`'s own prior trust
        level; classification is `task`'s own, unchanged (see this
        module's own docstring for why per-file classification is not
        attempted).
    """
    referenced = _find_referenced_files(task.value, target_repo)
    files = _read_bounded(referenced, _MAX_TOTAL_CONTEXT_CHARS)
    if not files:
        return task

    resolved_root = target_repo.resolve()
    lines = [task.value, "", "Referenced file contents:"]
    for path, content in files:
        lines.append(f"\n--- {path.relative_to(resolved_root)} ---")
        lines.append(content)
    new_text = "\n".join(lines)

    file_provenance = Provenance.external(
        f"coding_task_referenced_files:{target_repo}", task.provenance.classification
    )
    return Tainted(new_text, task.provenance.merge(file_provenance))
