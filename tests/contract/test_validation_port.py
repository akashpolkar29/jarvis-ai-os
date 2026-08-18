"""Contract test: adapters must structurally satisfy jarvis.ports.validation.ValidationPort.

Deviates from this directory's usual pattern, on purpose, flagged
here: every other contract test in ``tests/contract/`` instantiates a
*real* adapter and asserts it satisfies its port. No real adapter for
``ValidationPort`` exists yet -- ``adapters/validation/`` is WP-33, not
this work package, which is ports-only. ``_FakeValidator`` below is a
minimal, test-local stand-in satisfying the Protocol's shape, used
only because there is nothing real to import yet. When WP-33 lands,
its contract test should add the same "a real adapter satisfies this
port" test the other seven ports have, alongside (not necessarily
replacing) this one.
"""

from __future__ import annotations

from jarvis.domain.evidence import Candidate, Evidence, EvidenceKind, Verdict
from jarvis.ports.validation import ValidationPort


class _FakeValidator:
    """A minimal stand-in ValidationPort, satisfying the Protocol's shape only."""

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Always report PASSED, ignoring ``candidate`` -- a fake, not a real check."""
        evidence = Evidence(
            kind=EvidenceKind.VALIDATION_RESULT,
            author="fake-validator",
            weight=1.0,
            description=f"Fake validation of {candidate.author}'s candidate.",
        )
        return (Verdict.PASSED, (evidence,))


def test_fake_validator_satisfies_validation_port() -> None:
    """_FakeValidator is structurally a ValidationPort."""
    validator = _FakeValidator()

    assert isinstance(validator, ValidationPort)


def test_an_object_missing_validate_does_not_satisfy_validation_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAValidator:
        """Deliberately lacks validate()."""

    assert isinstance(NotAValidator(), ValidationPort) is False
