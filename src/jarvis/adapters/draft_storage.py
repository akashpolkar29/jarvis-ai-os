"""Adapters implementing jarvis.ports.draft_storage.DraftStoragePort.

:class:`LocalDraftStorageAdapter` writes a drafted document's content
to a real, new file under a configured, real base directory --
WP-83's own real implementation of the port WP-82 defined. Unlike the
D-Bus and cloud-provider adapters elsewhere in this ring, this one is
testable for real with no mocking: plain local-filesystem writes are a
reliable CI dependency, the same reasoning
``adapters/workspace.py``'s own module docstring already gives for
``git apply``, one level simpler (no subprocess involved at all here).

**A real, defensive finding made during implementation, not named in
`docs/architecture/m6b-job-assistance.md` itself**: ``filename_hint``
is caller-supplied text (ultimately, a drafting task's own
description), not a validated filename. Passed through unsanitized, it
could contain path separators or ``..`` segments capable of escaping
the configured base directory entirely -- the same class of real risk
``kernel/files.py``'s own ``PathOutsideAllowedScopeError`` scope check
already exists to close for *reads*. This adapter closes the
equivalent gap for this new *write* surface structurally, not by
validating after the fact: :func:`_safe_stem` reduces ``filename_hint``
to alphanumeric/dash/underscore characters only *before* it ever
touches a real path, so a path separator or ``..`` segment cannot
survive into the constructed path at all -- there is no "check it's
still inside the base directory" step afterward because there is
nothing left in the sanitized stem capable of escaping it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]+")
_FALLBACK_STEM = "draft"


def _safe_stem(filename_hint: str) -> str:
    """Reduce ``filename_hint`` to a safe, filesystem-portable stem.

    Every character outside ``[A-Za-z0-9_-]`` (including any path
    separator or ``.``) becomes a single ``-``; leading/trailing
    ``-`` is stripped. A hint that sanitizes to nothing at all (e.g.
    an empty string, or one made entirely of unsafe characters) falls
    back to a fixed, real, non-empty stem rather than producing an
    unusable filename.
    """
    stem = _UNSAFE_CHARACTERS.sub("-", filename_hint).strip("-")
    return stem or _FALLBACK_STEM


class LocalDraftStorageAdapter:
    """A real, local-filesystem-backed ``DraftStoragePort``."""

    def __init__(self, base_dir: Path) -> None:
        """Store the real directory drafts are saved under.

        Args:
            base_dir: Where real draft files are written. Not
                required to exist yet -- created on first real
                :meth:`save` call, not here, matching
                ``LocalWorkspaceAdapter``'s own "``__init__`` does
                zero I/O" precedent (this constructor stays trivially
                constructible with any path, real or not).
        """
        self._base_dir = base_dir

    def save(self, filename_hint: str, content: str) -> Path:
        """Persist ``content`` to a new, real file under ``base_dir``, provenance-safe by construction.

        Never overwrites an existing file: if the sanitized hint's own
        first candidate filename already exists, a real, incrementing
        numeric suffix is added until a genuinely unused path is
        found -- two calls with the same ``filename_hint`` therefore
        always produce two distinct real files.
        """  # noqa: E501
        self._base_dir.mkdir(parents=True, exist_ok=True)
        target = self._unique_path(_safe_stem(filename_hint))
        target.write_text(content, encoding="utf-8")
        return target

    def _unique_path(self, stem: str) -> Path:
        candidate = self._base_dir / f"{stem}.txt"
        counter = 1
        while candidate.exists():
            candidate = self._base_dir / f"{stem}-{counter}.txt"
            counter += 1
        return candidate
