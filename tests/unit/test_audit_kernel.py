"""Unit tests for jarvis.kernel.audit.authorize_and_view_audit_history (Phase 10)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.kernel.audit import authorize_and_view_audit_history
from jarvis.kernel.files import authorize_and_list_dir
from jarvis.kernel.ping import authorize_ping

if TYPE_CHECKING:
    from pathlib import Path

_THREE_RECORDS = 3


def test_granted_history_view_returns_every_real_record(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert outcome.decision.granted is True
    # Two real pings plus this view's own now-appended record.
    assert len(outcome.records) == _THREE_RECORDS
    assert [r.sequence for r in outcome.records] == [0, 1, 2]


def test_history_view_is_always_granted_regardless_of_confirmation(tmp_path: Path) -> None:
    """audit.history is READ_LOCAL/Tier.ALLOW -- always granted, same as git.status."""
    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
    )

    assert outcome.decision.granted is True
    # Real, honest behavior (see this module's own docstring) -- every
    # capability call is audited with no exceptions, so granting this
    # view already appends its own record to the chain before this
    # function returns, and a first-ever call sees itself.
    assert len(outcome.records) == 1
    assert outcome.records[0].decision.invocation.descriptor.id.value == "audit.history"


def test_limit_returns_only_the_most_recent_records(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        limit=1,
    )

    # The most recent record by the time filtering runs is this view's own
    # just-appended call (sequence 2), not the second ping (sequence 1) --
    # see test_history_view_is_always_granted_regardless_of_confirmation's
    # own comment for why.
    assert len(outcome.records) == 1
    assert outcome.records[0].sequence == 2  # noqa: PLR2004 -- the real sequence number above
    assert outcome.records[0].decision.invocation.descriptor.id.value == "audit.history"


def test_capability_id_filter_returns_only_matching_records(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        capability_id="ping",
    )

    # The real ping plus this view's own record -- both are "ping"? No: this
    # view's own record is "audit.history", so exactly one real "ping" match.
    assert len(outcome.records) == 1
    assert outcome.records[0].decision.invocation.descriptor.id.value == "ping"


def test_capability_id_filter_with_no_matches_returns_empty(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        capability_id="memory.write",
    )

    assert outcome.records == ()


def test_the_view_call_itself_is_durably_appended_to_the_chain(tmp_path: Path) -> None:
    """A real, honest consequence: viewing history is itself a real, audited capability call."""
    chain_path = tmp_path / "audit_chain.json"

    first_outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    assert len(first_outcome.records) == 1

    second_outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )

    assert len(second_outcome.records) == 2  # noqa: PLR2004 -- both real, prior view calls
    assert second_outcome.records[-1].decision.invocation.descriptor.id.value == "audit.history"


def test_skill_filter_returns_only_records_belonging_to_that_skill(tmp_path: Path) -> None:
    """WP-177: --skill filters real audit records via the real, unmodified skill registry."""
    chain_path = tmp_path / "audit_chain.json"
    authorize_ping(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    authorize_and_list_dir(
        tmp_path,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        allowed_root=tmp_path,
    )

    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        skill_id="filesystem",
    )

    # "ping" and "audit.history" (this view's own record) both belong to no
    # skill at all -- only the real fs.list_dir call is grouped under
    # "filesystem" (WP-173).
    assert len(outcome.records) == 1
    assert outcome.records[0].decision.invocation.descriptor.id.value == "fs.list_dir"


def test_skill_filter_combines_with_capability_id_filter(tmp_path: Path) -> None:
    """Both filters apply together (AND), not either-or."""
    chain_path = tmp_path / "audit_chain.json"
    authorize_and_list_dir(
        tmp_path,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        allowed_root=tmp_path,
    )

    matching = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        skill_id="filesystem",
        capability_id="fs.list_dir",
    )
    assert len(matching.records) == 1

    non_matching = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        skill_id="filesystem",
        capability_id="fs.read_file",
    )
    assert non_matching.records == ()


def test_skill_filter_with_an_unregistered_skill_id_returns_empty_not_a_crash(
    tmp_path: Path,
) -> None:
    """An unknown skill id is an honest empty result, mirroring 'jarvis skills show'."""
    chain_path = tmp_path / "audit_chain.json"
    authorize_and_list_dir(
        tmp_path,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        allowed_root=tmp_path,
    )

    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        skill_id="not-a-real-skill",
    )

    assert outcome.records == ()


def test_skill_filter_with_a_malformed_skill_id_returns_empty_not_a_crash(
    tmp_path: Path,
) -> None:
    """A whitespace-containing (invalid SkillId token) skill id is also an honest empty result."""
    outcome = authorize_and_view_audit_history(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        skill_id="not a valid id",
    )

    assert outcome.records == ()
