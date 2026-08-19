"""Contract test: adapters must structurally satisfy jarvis.ports.reasoning.ReasoningPort.

WP-32 added the three real adapters (``FamilyAReasoningAdapter``,
``FamilyBReasoningAdapter``, ``LocalReasoningAdapter``) this file's own
WP-31 docstring said should land here "alongside (not necessarily
replacing)" the fake-based tests below -- both now coexist:
``_FakeReasoningProvider`` stays because a hand-written minimal stand-in
is still useful as the simplest possible conformance check, matching
no other single reason to remove it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.reasoning import (
    CassettePlayer,
    CassetteRecorder,
    FamilyAReasoningAdapter,
    FamilyBReasoningAdapter,
    LocalReasoningAdapter,
)
from jarvis.adapters.secret import SecretServiceAdapter
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.ports.reasoning import ReasoningPort

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt


class _FakeReasoningProvider:
    """A minimal stand-in ReasoningPort, satisfying the Protocol's shape only."""

    async def generate(
        self,
        task: str,
        prior_attempts: tuple[Attempt, ...],  # noqa: ARG002 -- fake ignores context
    ) -> Tainted[Candidate]:
        """Return a fixed Candidate, ignoring ``prior_attempts`` -- a fake, not a model."""
        return Tainted(Candidate(author="fake-provider", content=task), Provenance.system())


def test_fake_reasoning_provider_satisfies_reasoning_port() -> None:
    """_FakeReasoningProvider is structurally a ReasoningPort."""
    provider = _FakeReasoningProvider()

    assert isinstance(provider, ReasoningPort)


def test_an_object_missing_generate_does_not_satisfy_reasoning_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAReasoningProvider:
        """Deliberately lacks generate()."""

    assert isinstance(NotAReasoningProvider(), ReasoningPort) is False


def test_family_a_reasoning_adapter_satisfies_reasoning_port() -> None:
    """FamilyAReasoningAdapter is structurally a ReasoningPort.

    Safe to construct here: __init__ does zero I/O (it only stores its
    secret reference and call function), so no real keyring or network
    connection is required.
    """
    adapter = FamilyAReasoningAdapter(SecretServiceAdapter(), "family-a-api-key")

    assert isinstance(adapter, ReasoningPort)


def test_family_b_reasoning_adapter_satisfies_reasoning_port() -> None:
    """FamilyBReasoningAdapter is structurally a ReasoningPort."""
    adapter = FamilyBReasoningAdapter(SecretServiceAdapter(), "family-b-api-key")

    assert isinstance(adapter, ReasoningPort)


def test_local_reasoning_adapter_satisfies_reasoning_port() -> None:
    """LocalReasoningAdapter is structurally a ReasoningPort."""
    adapter = LocalReasoningAdapter()

    assert isinstance(adapter, ReasoningPort)


def test_cassette_recorder_satisfies_reasoning_port() -> None:
    """CassetteRecorder is structurally a ReasoningPort.

    Safe to construct here: __init__ does zero I/O (it only stores the
    wrapped provider reference), so no real adapter behavior is needed.
    """
    recorder = CassetteRecorder(LocalReasoningAdapter())

    assert isinstance(recorder, ReasoningPort)


def test_cassette_player_satisfies_reasoning_port() -> None:
    """CassettePlayer is structurally a ReasoningPort."""
    player = CassettePlayer([])

    assert isinstance(player, ReasoningPort)
