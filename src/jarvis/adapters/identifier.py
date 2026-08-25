"""Adapters implementing jarvis.ports.identifier.IdPort.

:class:`UuidIdAdapter` wraps a real, random UUID4 -- the one call in
this repo ADR-0054 permits, both by
`tests/meta/test_source_invariants.py`'s own allowlist and by the
`# noqa: TID251` on the one line below. No other file in `src/` may
make this call; ruff's own banned-api rule and the AST-based meta-test
both check this independently.
"""

from __future__ import annotations

import uuid


class UuidIdAdapter:
    """Real, random identifiers via UUID4."""

    def new_id(self) -> str:
        """Return a real, fresh, unique identifier."""
        return str(uuid.uuid4())  # noqa: TID251 -- the one call IdPort exists to wrap
