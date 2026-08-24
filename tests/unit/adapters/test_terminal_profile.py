"""Unit tests for jarvis.adapters.terminal_profile.ensure_synthetic_input_profile_exists.

What's faked and why: the real GSettings I/O (``ensure_exists``) and
UUID derivation (``profile_uuid_fn``) are both injected fakes here --
no real dconf/GSettings state is touched by these tests. The real
default implementation (``_ensure_profile_exists_via_gsettings``,
``_real_profile_uuid``) was verified live against this machine's real
GNOME Terminal profile settings instead -- see the module's own
docstring for what that verification found, including genuine
idempotency (running it twice does not duplicate the profile in
``ProfilesList``).
"""

from __future__ import annotations

from jarvis.adapters.terminal_profile import ensure_synthetic_input_profile_exists

_FIXED_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_returns_the_uuid_from_profile_uuid_fn() -> None:
    """The returned UUID is whatever profile_uuid_fn produced, unchanged."""
    result = ensure_synthetic_input_profile_exists(
        profile_uuid_fn=lambda: _FIXED_UUID, ensure_exists=lambda _uuid: None
    )

    assert result == _FIXED_UUID


def test_ensure_exists_is_called_with_the_derived_uuid() -> None:
    """ensure_exists() receives exactly the UUID profile_uuid_fn produced -- the real dispatch."""
    calls: list[str] = []

    ensure_synthetic_input_profile_exists(
        profile_uuid_fn=lambda: _FIXED_UUID, ensure_exists=calls.append
    )

    assert calls == [_FIXED_UUID]


def test_calling_twice_ensures_the_same_uuid_both_times() -> None:
    """Idempotency at the dispatch level: two calls compute and ensure the same UUID."""
    calls: list[str] = []

    first = ensure_synthetic_input_profile_exists(
        profile_uuid_fn=lambda: _FIXED_UUID, ensure_exists=calls.append
    )
    second = ensure_synthetic_input_profile_exists(
        profile_uuid_fn=lambda: _FIXED_UUID, ensure_exists=calls.append
    )

    assert first == second == _FIXED_UUID
    assert calls == [_FIXED_UUID, _FIXED_UUID]


def test_real_profile_uuid_derivation_is_deterministic_across_calls() -> None:
    """The real (non-injected) UUID derivation -- pure, no I/O -- is stable, not random."""
    from jarvis.adapters.terminal_profile import _real_profile_uuid  # noqa: PLC0415

    assert _real_profile_uuid() == _real_profile_uuid()
