"""Property-based test for jarvis.application.memory.retrieval_guard.exclude_secret_records.

The required acceptance criterion named by ADR-0050's own amendment: "a
real test proving that a MemoryRecord carrying Classification.SECRET,
if present in the underlying store by any means, is never included in
RetrievalPort.retrieve()'s returned results, and that encountering one
raises the real, distinct exception this ADR now names -- not silently
dropped, not silently returned." Exercised here against arbitrary
combinations of records across every real Classification, not just a
hand-picked example.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.memory.retrieval_guard import exclude_secret_records
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.ports.retrieval import MemoryIntegrityViolationError

_WRITTEN_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _record(index: int, classification: Classification) -> MemoryRecord:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return MemoryRecord(
        identifier=f"mem:{index}",
        value=Tainted("x", provenance),
        written_at=_WRITTEN_AT,
        expires_at=None,
    )


_CLASSIFICATIONS = st.sampled_from(list(Classification))
_RECORD_SETS = st.lists(_CLASSIFICATIONS, min_size=0, max_size=8).map(
    lambda classifications: tuple(
        _record(index, classification) for index, classification in enumerate(classifications)
    )
)


@given(_RECORD_SETS)
def test_a_secret_record_is_never_returned_and_always_raises(
    records: tuple[MemoryRecord, ...],
) -> None:
    """A SECRET record present anywhere in the input always raises, never appears in a result."""
    contains_secret = any(
        record.value.provenance.classification is Classification.SECRET for record in records
    )

    if contains_secret:
        with pytest.raises(MemoryIntegrityViolationError):
            exclude_secret_records(records)
    else:
        result = exclude_secret_records(records)
        assert result == records
        assert all(
            record.value.provenance.classification is not Classification.SECRET for record in result
        )
