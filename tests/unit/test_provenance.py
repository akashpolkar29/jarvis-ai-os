"""Unit tests for jarvis.domain.provenance."""

from __future__ import annotations

import pytest

from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

VALUE = 42


def test_provenance_user_factory() -> None:
    """Provenance.user() produces USER_DIRECT/PUBLIC/no sources."""
    p = Provenance.user()
    assert p.trust == Trust.USER_DIRECT
    assert p.classification == Classification.PUBLIC
    assert p.sources == frozenset()


def test_provenance_system_factory() -> None:
    """Provenance.system() produces SYSTEM/PUBLIC/no sources."""
    p = Provenance.system()
    assert p.trust == Trust.SYSTEM
    assert p.classification == Classification.PUBLIC
    assert p.sources == frozenset()


def test_provenance_external_factory() -> None:
    """Provenance.external() tags UNTRUSTED_EXTERNAL with the given source."""
    p = Provenance.external("plugin:weather", Classification.SENSITIVE)
    assert p.trust == Trust.UNTRUSTED_EXTERNAL
    assert p.classification == Classification.SENSITIVE
    assert p.sources == frozenset({"plugin:weather"})


def test_provenance_is_tainted() -> None:
    """is_tainted is True only for UNTRUSTED_EXTERNAL provenance."""
    assert Provenance.external("x", Classification.PUBLIC).is_tainted is True
    assert Provenance.user().is_tainted is False
    assert Provenance.system().is_tainted is False


def test_provenance_merge_all_empty_raises() -> None:
    """merge_all() on an empty iterable raises ValueError, not a default."""
    with pytest.raises(ValueError, match="at least one Provenance"):
        Provenance.merge_all([])


def test_tainted_user_factory() -> None:
    """Tainted.user() wraps a value with Provenance.user()."""
    t = Tainted.user(VALUE)
    assert t.value == VALUE
    assert t.provenance == Provenance.user()


def test_tainted_system_factory() -> None:
    """Tainted.system() wraps a value with Provenance.system()."""
    t = Tainted.system(VALUE)
    assert t.value == VALUE
    assert t.provenance == Provenance.system()


def test_tainted_external_factory() -> None:
    """Tainted.external() wraps a value with Provenance.external()."""
    t = Tainted.external(VALUE, "plugin:weather", Classification.SECRET)
    assert t.value == VALUE
    assert t.provenance == Provenance.external("plugin:weather", Classification.SECRET)
