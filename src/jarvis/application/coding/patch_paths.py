"""ADR-0056's amendment 2: which real paths a patch touches, canonicalized.

:func:`touched_paths` is the "whatever parses 'which paths does this
patch touch' from a real diff" piece
`docs/architecture/m5-browser-coding.md`'s own acceptance criterion 8
requires: it canonicalizes each path (resolving ``.``/``..`` and any
existing symlinked parent directories) before a caller checks it
against ``protected_patterns``, and it classifies a file being
*created* identically to one being *modified* -- both a patch's
pre-image (``--- ``) and post-image (``+++ ``) path are parsed, so a
newly-created file (``--- /dev/null``, ``+++ b/new_file.py``) surfaces
its real post-image path exactly the same way a modified file's does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_NULL_PATH = "/dev/null"
_DIFF_HEADER_PREFIXES = ("--- ", "+++ ")
_AB_PREFIX_LENGTH = 2  # "a/" or "b/"


def _strip_ab_prefix(raw: str) -> str:
    if raw.startswith(("a/", "b/")):
        return raw[_AB_PREFIX_LENGTH:]
    return raw


def _raw_header_paths(patch: str) -> list[str]:
    """Extract every real, raw pre-/post-image path named in `patch`'s own headers."""
    raw_paths: list[str] = []
    for line in patch.splitlines():
        if not line.startswith(_DIFF_HEADER_PREFIXES):
            continue
        # A real unified diff may append a trailing tab + timestamp; only the
        # path itself matters here.
        raw = line[4:].strip().split("\t", 1)[0]
        if raw == _NULL_PATH:
            continue
        raw_paths.append(_strip_ab_prefix(raw))
    return raw_paths


def touched_paths(patch: str, repo_root: Path) -> tuple[Path, ...]:
    """Return every real, canonicalized, repo-relative path `patch` touches.

    Args:
        patch: Real unified-diff text, the same shape
            :class:`~jarvis.domain.evidence.Candidate.content` takes
            for any candidate judged against a real workspace
            (ADR-0043) -- parsed the same way
            :class:`~jarvis.adapters.workspace.LocalWorkspaceAdapter`'s
            own real ``git apply`` expects it.
        repo_root: The real repository root every raw path is resolved
            against.

    Returns:
        A real, de-duplicated tuple of paths, each canonicalized
        (``.``/``..`` resolved, any existing symlinked parent
        directories resolved) and made relative to `repo_root` again --
        **except** a raw path that canonicalizes to somewhere outside
        `repo_root` entirely (a real ``../``-escape or symlink-escape
        attempt), which is returned *absolute* instead, deliberately:
        never silently dropped, never silently treated as though it
        were safely inside the repository. Callers must reject any
        absolute result outright rather than pattern-matching it --
        ``fnmatch``-based patterns like ``tests/*`` have no notion of
        "outside the repository" at all and would simply never match an
        absolute escaping path, which would otherwise fall through to
        an ordinary, granted write.
    """
    resolved_root = repo_root.resolve()
    canonical: list[Path] = []
    seen: set[Path] = set()
    for raw in _raw_header_paths(patch):
        resolved = (repo_root / raw).resolve()
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError:
            relative = resolved
        if relative not in seen:
            seen.add(relative)
            canonical.append(relative)
    return tuple(canonical)
