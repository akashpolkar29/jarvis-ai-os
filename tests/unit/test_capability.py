"""Unit tests for jarvis.domain.capability."""

from __future__ import annotations

import pytest

from jarvis.domain.capability import (
    _EFFECT_TIER_FLOOR,
    CapabilityDescriptor,
    CapabilityId,
    Effect,
    Tier,
    minimum_tier_for,
)

VALID_CAPABILITY_IDS = ["fs.read_file", "shell.execute", "a", "net.http_get", "x.y.z"]
INVALID_CAPABILITY_IDS = [
    "",
    " ",
    "fs read",
    " fs.read",
    "fs.read ",
    "fs\tread",
    "fs\nread",
]

EFFECT_TIER_CASES = [
    (Effect.READ_LOCAL, Tier.ALLOW),
    (Effect.EGRESS_LOCAL, Tier.ALLOW),
    (Effect.WRITE_LOCAL, Tier.CONFIRM),
    (Effect.EXECUTE, Tier.CONFIRM),
    (Effect.EGRESS_SENSITIVE, Tier.CONFIRM),
    (Effect.DESTRUCTIVE, Tier.MANUAL_ONLY),
    (Effect.IRREVERSIBLE, Tier.MANUAL_ONLY),
    (Effect.CREDENTIAL, Tier.MANUAL_ONLY),
    (Effect.EGRESS_SECRET, Tier.DENY),
    (Effect.MEMORY_WRITE, Tier.DENY),
    (Effect.CODE_WRITE, Tier.CONFIRM),
    (Effect.PROTECTED_PATH_WRITE, Tier.DENY),
    (Effect.NONE, Tier.ALLOW),
    (Effect.EGRESS_SECRET | Effect.READ_LOCAL, Tier.DENY),
    (Effect.MEMORY_WRITE | Effect.READ_LOCAL, Tier.DENY),
    (Effect.PROTECTED_PATH_WRITE | Effect.CODE_WRITE, Tier.DENY),
]


@pytest.mark.parametrize("value", VALID_CAPABILITY_IDS)
def test_capability_id_accepts_valid_tokens(value: str) -> None:
    """CapabilityId accepts non-empty, whitespace-free tokens."""
    assert CapabilityId(value).value == value


@pytest.mark.parametrize("value", INVALID_CAPABILITY_IDS)
def test_capability_id_rejects_invalid_tokens(value: str) -> None:
    """CapabilityId rejects empty strings and anything containing whitespace."""
    with pytest.raises(ValueError, match="CapabilityId"):
        CapabilityId(value)


def test_capability_id_str_is_the_underlying_token() -> None:
    """str(CapabilityId(...)) is the plain token, for log fields."""
    assert str(CapabilityId("fs.read_file")) == "fs.read_file"


@pytest.mark.parametrize(("effects", "expected_tier"), EFFECT_TIER_CASES)
def test_minimum_tier_for_boundary_table(effects: Effect, expected_tier: Tier) -> None:
    """minimum_tier_for matches the spec's effect-to-tier boundary table exactly."""
    assert minimum_tier_for(effects) == expected_tier


def test_every_effect_member_has_a_tier_floor_entry() -> None:
    """Every non-NONE Effect member must have an explicit tier-floor entry.

    Guards against a future Effect being added to the enum without a
    corresponding entry in _EFFECT_TIER_FLOOR, which would otherwise
    silently floor that effect at ALLOW instead of failing loudly here.
    """
    non_none_members = [m for m in Effect.__members__.values() if m != Effect.NONE]
    for member in non_none_members:
        assert member in _EFFECT_TIER_FLOOR, f"{member!r} has no tier-floor entry"


def test_capability_descriptor_rejects_empty_description() -> None:
    """CapabilityDescriptor raises ValueError on an empty description."""
    with pytest.raises(ValueError, match="description"):
        CapabilityDescriptor(
            id=CapabilityId("fs.read_file"),
            effects=Effect.READ_LOCAL,
            description="",
        )
