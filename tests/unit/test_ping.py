"""Unit tests for jarvis.kernel.ping.authorize_ping."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.ping import authorize_ping

if TYPE_CHECKING:
    from pathlib import Path

_TWO_INVOCATIONS = 2


def test_ping_is_granted(tmp_path: Path) -> None:
    """The hardcoded "ping" capability (READ_LOCAL, Tier.ALLOW) is always granted."""
    decision = authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
    )

    assert decision.granted is True


def test_ping_is_granted_regardless_of_confirmation_flags(tmp_path: Path) -> None:
    """ALLOW-tier grants unconditionally -- the flags are wired through but don't change this."""
    decision = authorize_ping(
        physical_confirmation_available=True,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
    )

    assert decision.granted is True


def test_a_single_call_appends_one_verifiable_record(tmp_path: Path) -> None:
    """One authorize_ping() call persists exactly one record that verifies."""
    chain_path = tmp_path / "audit_chain.json"

    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1
    assert chain.verify().valid is True


def test_state_persists_across_separate_calls_against_the_same_path(tmp_path: Path) -> None:
    """Two authorize_ping() calls against the same path grow the chain, proving persistence.

    Mirrors what two separate CLI invocations against the same
    --chain-path would produce: the second call's load() sees the
    first call's save().
    """
    chain_path = tmp_path / "audit_chain.json"

    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    authorize_ping(
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _TWO_INVOCATIONS
    assert chain.verify().valid is True
