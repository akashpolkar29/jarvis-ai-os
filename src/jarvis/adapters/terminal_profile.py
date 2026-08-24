"""The real-time visual indicator: a dedicated, unmistakable gnome-terminal profile.

ADR-0047's visual half of the real-time indicator, load-bearing per
that ADR's own acceptance condition -- see its "The real-time
indicator" section for the full reasoning. This module is small and
deliberately narrow: it manages exactly one GSettings relocatable
profile (``org.gnome.Terminal.Legacy.Profile``, the same schema
GNOME's own Preferences UI writes to), reserved exclusively for
sandboxed terminals that will receive synthetic input, never applied
to or confused with the user's own terminal profiles.

Real, live-verified mechanics, not assumed from the schema alone (the
same "checked live before writing this" discipline as every other real
D-Bus/GSettings adapter in this repo): ``org.gnome.Terminal.ProfilesList``
has a real ``list`` (an array of profile UUID strings) and ``default``
key; each profile's own settings live under the relocatable path
``/org/gnome/terminal/legacy/profiles:/<uuid>/``, reachable via
``Gio.Settings.new_with_path``. Confirmed live: creating a new UUID,
appending it to ``list``, and setting ``visible-name``/
``use-theme-colors``/``background-color`` on the relocatable path
produces a real, persisted profile a second call does not duplicate
(idempotency was verified the same way -- run twice, ``list`` gains
the UUID exactly once) -- and cleanly removed again via ``dconf reset``
on that one path plus removing the UUID from ``list``, confirming this
is genuinely narrow and reversible, the same bar this project applies
to every other real-machine change (ADR-0047's own framing).

This is safe to build and run for real, unlike the RemoteDesktop portal
calls ADR-0047 also needs: creating a GSettings profile triggers no
interactive dialog and touches no other application's state.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    UuidFn = Callable[[], str]

_LIST_SCHEMA = "org.gnome.Terminal.ProfilesList"
_PROFILE_SCHEMA = "org.gnome.Terminal.Legacy.Profile"
_PROFILE_PATH_TEMPLATE = "/org/gnome/terminal/legacy/profiles:/{}/"

_PROFILE_VISIBLE_NAME = "JARVIS (synthetic input active)"
_PROFILE_BACKGROUND_COLOR = "rgb(120,20,20)"
"""A saturated, low-ambiguity dark red -- deliberately distinct from any
color a normal user profile would plausibly choose (ADR-0047), so the
signal reads as "JARVIS is controlling this window" on sight."""

_JARVIS_PROFILE_NAMESPACE = uuid.UUID("f47a1224-1c3e-4a6a-9b1a-6a2c6b6a6a6a")
"""An arbitrary, fixed namespace UUID used only to derive a stable
profile UUID via uuid.uuid5 -- not a secret, not security-relevant,
just a deterministic seed so this module creates exactly one real
profile across repeated runs rather than a fresh one every time."""


def _real_profile_uuid() -> str:
    """Return a stable, deterministic UUID for JARVIS's own synthetic-input terminal profile.

    Deterministic (uuid5, not uuid4) so ``ensure_synthetic_input_profile_exists``
    is naturally idempotent -- it always computes the same profile UUID
    to check for/create, without needing to persist or look up a
    previously-generated one anywhere.

    Not injected via the module's own testability seam -- this is a
    pure, deterministic function of no arguments, only present as its
    own function (rather than an inline constant) so the "how is this
    derived" reasoning above has one place to live.
    """
    return str(uuid.uuid5(_JARVIS_PROFILE_NAMESPACE, "jarvis-synthetic-input-terminal-profile"))


def _ensure_profile_exists_via_gsettings(profile_uuid: str) -> None:
    """Create/refresh the real GSettings profile for ``profile_uuid``. Idempotent.

    The one real, untested-by-design-by-CI piece of this module --
    manually verified live against this machine's real dconf/GSettings
    instead (see the module docstring): running this twice leaves
    ``ProfilesList``'s ``list`` containing ``profile_uuid`` exactly
    once, never duplicated.
    """
    import gi  # noqa: PLC0415 -- lazy, matching every other real-hardware adapter's own convention

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio  # noqa: PLC0415

    list_settings = Gio.Settings.new(_LIST_SCHEMA)
    profiles = list_settings.get_strv("list")
    if profile_uuid not in profiles:
        list_settings.set_strv("list", [*profiles, profile_uuid])

    profile_settings = Gio.Settings.new_with_path(
        _PROFILE_SCHEMA, _PROFILE_PATH_TEMPLATE.format(profile_uuid)
    )
    profile_settings.set_string("visible-name", _PROFILE_VISIBLE_NAME)
    profile_settings.set_boolean("use-theme-colors", False)
    profile_settings.set_string("background-color", _PROFILE_BACKGROUND_COLOR)


def ensure_synthetic_input_profile_exists(
    *,
    profile_uuid_fn: UuidFn | None = None,
    ensure_exists: Callable[[str], None] | None = None,
) -> str:
    """Ensure JARVIS's dedicated synthetic-input terminal profile exists, and return its UUID.

    Idempotent: safe to call before every ``terminal.run`` invocation
    -- the first call creates the real profile, every subsequent call
    is a real, cheap no-op write of the same values (GSettings has no
    meaningfully different "already correct, skip" fast path worth
    adding here).

    Args:
        profile_uuid_fn: Returns the profile UUID to ensure. Defaults
            to the real, deterministic derivation. Overridable for
            tests so they can assert against a known, fixed UUID
            without depending on this module's own derivation logic.
        ensure_exists: Given a profile UUID, creates/refreshes it for
            real. Defaults to the real GSettings implementation.
            Overridable for tests -- no real dconf/GSettings I/O
            happens unless this default is used.

    Returns:
        The profile's UUID, e.g. for a caller to pass as
        ``--profile=<uuid>`` on the sandboxed terminal's launch command.
    """
    real_profile_uuid_fn: UuidFn = profile_uuid_fn or _real_profile_uuid
    real_ensure_exists: Callable[[str], None] = (
        ensure_exists or _ensure_profile_exists_via_gsettings
    )

    profile_uuid = real_profile_uuid_fn()
    real_ensure_exists(profile_uuid)
    return profile_uuid
