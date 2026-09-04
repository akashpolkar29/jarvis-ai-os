"""Domain values for real local filesystem entries.

:class:`DirEntry` is the one real value `fs.list_dir` returns per
entry -- plain, stdlib-only, matching `PageHandle`'s own "explicit,
typed fields, not one opaque blob" precedent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DirEntry:
    """One real entry inside a listed directory.

    Attributes:
        name: The entry's own real filename (no path components).
        is_dir: Whether the entry is itself a real directory.
    """

    name: str
    is_dir: bool
