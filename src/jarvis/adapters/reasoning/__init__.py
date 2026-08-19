"""Adapters implementing jarvis.ports.reasoning.ReasoningPort.

Three real-provider adapters, matching ``docs/architecture/m2-reasoning-layer.md``
section 7's recovered package layout exactly (``adapters/reasoning/ -
family_a, family_b, local``): ``FamilyAReasoningAdapter`` and
``FamilyBReasoningAdapter`` each call a real cloud provider family's
REST API (two structurally different shapes -- see each module's own
docstring), and ``LocalReasoningAdapter`` calls a real local, on-device
model server. Generic family names throughout, per ADR-0021 -- see
``family_a.py``'s module docstring for why real vendor identifiers
still never appear even here in the adapter ring for this specific
pair.

``CassetteRecorder``/``CassettePlayer`` (WP-38) are a fourth pair,
deliberately different in kind: not a fourth real provider, but the
record/replay harness (deliverable #10) that wraps any one of the
three above for regression testing -- see ``cassette.py``'s own
docstring.

This is a genuine per-adapter subpackage (C4 "adapter independence" is
configured in ``pyproject.toml`` starting WP-32 -- see
``tests/meta/test_gate_integrity.py``'s ``CONTRACT_SCHEDULE``): none of
the modules below import from each other.
"""

from __future__ import annotations

from .cassette import (
    CassetteExhaustedError,
    CassetteMismatchError,
    CassettePlayer,
    CassetteRecorder,
)
from .family_a import FamilyAReasoningAdapter
from .family_b import FamilyBReasoningAdapter
from .local import LocalReasoningAdapter

__all__ = [
    "CassetteExhaustedError",
    "CassetteMismatchError",
    "CassettePlayer",
    "CassetteRecorder",
    "FamilyAReasoningAdapter",
    "FamilyBReasoningAdapter",
    "LocalReasoningAdapter",
]
