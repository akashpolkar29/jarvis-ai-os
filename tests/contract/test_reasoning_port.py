"""Contract test: adapters must structurally satisfy jarvis.ports.reasoning.ReasoningPort.

Deviates from this directory's usual pattern, on purpose, flagged
here: every other contract test in ``tests/contract/`` instantiates a
*real* adapter (``FasterWhisperAdapter``, ``PiperTtsAdapter``, etc.)
and asserts it satisfies its port. No real adapter for ``ReasoningPort``
exists yet -- ``adapters/reasoning/`` is WP-32, not this work package,
which is ports-only. ``_FakeReasoningProvider`` below is a minimal,
test-local stand-in satisfying the Protocol's shape, used only because
there is nothing real to import yet. When WP-32 lands, its contract
test should add the same "a real adapter satisfies this port" test the
other seven ports have, alongside (not necessarily replacing) this one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
