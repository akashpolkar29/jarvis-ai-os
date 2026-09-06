"""Unit tests for jarvis.kernel.capability_dispatch.

Each real adapter is tested by mocking the specific `authorize_and_*`
function it wraps -- these underlying functions already have their
own full, dedicated test suites elsewhere (`tests/unit/test_files.py`,
`tests/unit/test_memory_kernel.py`, etc.); what's real and new here is
only whether this module's own adapter correctly unpacks a generic
`arguments` mapping into that function's own specific, typed call.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import (
    GIT_STATUS_CAPABILITY_ID,
    LIST_DIR_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
)
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS


def _granted_decision() -> Decision:
    invocation = CapabilityInvocation(
        CapabilityDescriptor(
            id=CapabilityId("test.cap"), effects=Effect.READ_LOCAL, description="x"
        ),
        Tainted({}, Provenance.user()),
    )
    return Decision(
        tier=Tier.ALLOW, granted=True, reasons=DecisionReason.BASE_TIER, invocation=invocation
    )


def test_read_file_executor_calls_authorize_and_read_file_with_unpacked_arguments() -> None:
    """The fs.read_file adapter unpacks 'path' and threads confirmation/chain_path through."""
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_read_file") as fake:
        fake.return_value = mock.Mock(decision=_granted_decision())
        executor = PLAN_STEP_EXECUTORS[READ_FILE_CAPABILITY_ID]

        outcome = executor({"path": "/tmp/a.txt"}, True, False, Path("/tmp/chain.json"))

        fake.assert_called_once_with(
            Path("/tmp/a.txt"),
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=Path("/tmp/chain.json"),
        )
        assert outcome.decision.granted is True


def test_list_dir_executor_calls_authorize_and_list_dir_with_unpacked_arguments() -> None:
    """The fs.list_dir adapter unpacks 'path' and threads confirmation/chain_path through."""
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_list_dir") as fake:
        fake.return_value = mock.Mock(decision=_granted_decision())
        executor = PLAN_STEP_EXECUTORS[LIST_DIR_CAPABILITY_ID]

        executor({"path": "/tmp/dir"}, False, True, Path("/tmp/chain.json"))

        fake.assert_called_once_with(
            Path("/tmp/dir"),
            physical_confirmation_available=False,
            remote_confirmation_available=True,
            chain_path=Path("/tmp/chain.json"),
        )


def test_git_status_executor_calls_authorize_and_get_git_status_with_unpacked_arguments() -> None:
    """The git.status adapter unpacks 'repo_dir' and threads confirmation/chain_path through."""
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_get_git_status") as fake:
        fake.return_value = mock.Mock(decision=_granted_decision())
        executor = PLAN_STEP_EXECUTORS[GIT_STATUS_CAPABILITY_ID]

        executor({"repo_dir": "/tmp/repo"}, True, True, Path("/tmp/chain.json"))

        fake.assert_called_once_with(
            Path("/tmp/repo"),
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=Path("/tmp/chain.json"),
        )


def test_memory_recall_executor_uses_a_default_limit_of_five_when_not_supplied() -> None:
    """The memory.retrieve adapter defaults 'limit' to 5 when the plan step omits it."""
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake:
        fake.return_value = mock.Mock(decision=_granted_decision())
        executor = PLAN_STEP_EXECUTORS[MEMORY_RETRIEVE_CAPABILITY_ID]

        executor({"query": "notes"}, False, False, Path("/tmp/chain.json"))

        fake.assert_called_once_with(
            "notes",
            limit=5,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=Path("/tmp/chain.json"),
        )


def test_memory_recall_executor_honors_an_explicit_limit() -> None:
    """The memory.retrieve adapter passes an explicit real 'limit' through unchanged."""
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake:
        fake.return_value = mock.Mock(decision=_granted_decision())
        executor = PLAN_STEP_EXECUTORS[MEMORY_RETRIEVE_CAPABILITY_ID]

        executor({"query": "notes", "limit": 2}, False, False, Path("/tmp/chain.json"))

        fake.assert_called_once_with(
            "notes",
            limit=2,
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=Path("/tmp/chain.json"),
        )
