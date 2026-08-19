"""Adapters implementing jarvis.ports.outcome.OutcomeSinkPort.

:class:`JsonLinesOutcomeSinkAdapter` appends one JSON object per line
to a real file -- the simplest real persistence that still lets a
future analysis tool stream the file without loading it whole, unlike
:class:`~jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter`'s
whole-file rewrite-on-every-save (a deliberately different tradeoff:
that adapter needs the whole chain in memory to verify hash-chain
integrity on load; this one never reads its own output back at all,
so there is nothing to gain from a single-document shape and real cost
to paying for it -- every :meth:`record` call would otherwise mean
reading, appending to, and rewriting a growing file).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class JsonLinesOutcomeSinkAdapter:
    """Appends one JSON-serialized entry per line to a real file."""

    def __init__(self, path: Path) -> None:
        """Store the real file every entry is appended to.

        Args:
            path: Where entries are appended. Not required to exist
                yet -- the first :meth:`record` call creates it.
        """
        self._path = path

    def record(self, entry: Mapping[str, object]) -> None:
        """Append ``entry`` as one JSON line to the real file."""
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry))
            handle.write("\n")
