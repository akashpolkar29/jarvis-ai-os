"""Property-based tests for jarvis.domain.provenance."""

from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jarvis.domain.errors import TaintViolation
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

TRUST = st.sampled_from(Trust)
CLASSIFICATION = st.sampled_from(Classification)
SOURCE_TEXT = st.text(alphabet=string.ascii_letters + string.digits, min_size=0, max_size=8)
SOURCES = st.frozensets(SOURCE_TEXT, max_size=5)
PROVENANCE = st.builds(Provenance, trust=TRUST, classification=CLASSIFICATION, sources=SOURCES)
TAINTED_INT = st.builds(Tainted, value=st.integers(), provenance=PROVENANCE)


@given(PROVENANCE, PROVENANCE)
def test_merge_never_lowers_trust(a: Provenance, b: Provenance) -> None:
    """P-01."""
    assert a.merge(b).trust >= max(a.trust, b.trust)


@given(PROVENANCE, PROVENANCE)
def test_merge_never_lowers_classification(a: Provenance, b: Provenance) -> None:
    """P-02."""
    assert a.merge(b).classification >= max(a.classification, b.classification)


@given(PROVENANCE, PROVENANCE)
def test_merge_commutative(a: Provenance, b: Provenance) -> None:
    """P-03."""
    assert a.merge(b) == b.merge(a)


@given(PROVENANCE, PROVENANCE, PROVENANCE)
def test_merge_associative(a: Provenance, b: Provenance, c: Provenance) -> None:
    """P-04."""
    assert a.merge(b).merge(c) == a.merge(b.merge(c))


@given(st.lists(PROVENANCE, min_size=1, max_size=6))
def test_merge_all_matches_manual_fold(items: list[Provenance]) -> None:
    """P-05."""
    manual = items[0]
    for item in items[1:]:
        manual = manual.merge(item)
    assert Provenance.merge_all(items) == manual


@given(TAINTED_INT, st.integers())
def test_map_preserves_provenance(t: Tainted[int], addend: int) -> None:
    """P-06."""
    mapped = t.map(lambda x: x + addend)
    assert mapped.provenance == t.provenance


@given(TAINTED_INT, TAINTED_INT)
def test_combine_merges_provenance(a: Tainted[int], b: Tainted[int]) -> None:
    """P-07."""
    result = a.combine(b, lambda x, y: x + y)
    assert result.provenance == a.provenance.merge(b.provenance)


@given(TAINTED_INT)
def test_require_trusted_raises_iff_tainted(t: Tainted[int]) -> None:
    """P-08."""
    if t.provenance.is_tainted:
        with pytest.raises(TaintViolation):
            t.require_trusted()
    else:
        assert t.require_trusted() == t.value
