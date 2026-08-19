"""Unit tests for jarvis.application.reasoning.unverifiable.UnverifiableTaskHandler.

Uses a real ModelRouter/AuthorizationOrchestrator -- only the
ReasoningPort adapters and the CandidatePresentationPort are faked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.router import ModelRouter
from jarvis.application.reasoning.unverifiable import (
    NoProviderAuthorizedError,
    UnverifiableTaskHandler,
)
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt

_FULL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True, remote_confirmation_available=True
)
_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False, remote_confirmation_available=False
)

_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_FAMILY_A_PROFILE = ProviderProfile(name="family_a", is_local=False)
_FAMILY_B_PROFILE = ProviderProfile(name="family_b", is_local=False)


class _FakeReasoningProvider:
    def __init__(self, author: str) -> None:
        self._author = author
        self.calls = 0

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        self.calls += 1
        candidate = Candidate(author=self._author, content=f"{self._author}: {task}")
        return Tainted(candidate, Provenance.system())


class _FakePresentation:
    def __init__(self, pick_index: int) -> None:
        self._pick_index = pick_index
        self.presented: tuple[Candidate, ...] | None = None

    async def present_and_select(self, candidates: tuple[Candidate, ...]) -> Candidate:
        self.presented = candidates
        return candidates[self._pick_index]


def _router() -> ModelRouter:
    return ModelRouter(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))


def _task() -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted("draft a poem", provenance)


async def test_every_authorized_provider_is_asked_exactly_once() -> None:
    """Criterion #8: no escalation -- each provider is tried once, never retried."""
    local = _FakeReasoningProvider("local")
    family_a = _FakeReasoningProvider("family_a")
    providers = ((_LOCAL_PROFILE, local), (_FAMILY_A_PROFILE, family_a))
    presentation = _FakePresentation(pick_index=0)
    handler = UnverifiableTaskHandler(providers, _router(), presentation)

    await handler.handle(_task(), _FULL_CONFIRMATION)

    assert local.calls == 1
    assert family_a.calls == 1


async def test_all_authorized_candidates_are_presented_to_the_human() -> None:
    local = _FakeReasoningProvider("local")
    family_a = _FakeReasoningProvider("family_a")
    providers = ((_LOCAL_PROFILE, local), (_FAMILY_A_PROFILE, family_a))
    presentation = _FakePresentation(pick_index=0)
    handler = UnverifiableTaskHandler(providers, _router(), presentation)

    await handler.handle(_task(), _FULL_CONFIRMATION)

    assert presentation.presented is not None
    assert {c.author for c in presentation.presented} == {"local", "family_a"}


async def test_the_human_selected_candidate_is_returned() -> None:
    local = _FakeReasoningProvider("local")
    family_a = _FakeReasoningProvider("family_a")
    providers = ((_LOCAL_PROFILE, local), (_FAMILY_A_PROFILE, family_a))
    presentation = _FakePresentation(pick_index=1)
    handler = UnverifiableTaskHandler(providers, _router(), presentation)

    result = await handler.handle(_task(), _FULL_CONFIRMATION)

    assert presentation.presented is not None
    assert result is presentation.presented[1]


async def test_an_unauthorized_provider_is_never_asked_and_never_presented() -> None:
    local = _FakeReasoningProvider("local")
    family_a = _FakeReasoningProvider("family_a")
    providers = ((_LOCAL_PROFILE, local), (_FAMILY_A_PROFILE, family_a))
    presentation = _FakePresentation(pick_index=0)
    handler = UnverifiableTaskHandler(providers, _router(), presentation)

    # No confirmation: the cloud provider (family_a) is denied by policy (ADR-0015),
    # the local provider is still always allowed.
    await handler.handle(_task(), _NO_CONFIRMATION)

    assert local.calls == 1
    assert family_a.calls == 0
    assert presentation.presented is not None
    assert {c.author for c in presentation.presented} == {"local"}


async def test_raises_when_every_provider_is_unauthorized() -> None:
    family_a = _FakeReasoningProvider("family_a")
    family_b = _FakeReasoningProvider("family_b")
    providers = ((_FAMILY_A_PROFILE, family_a), (_FAMILY_B_PROFILE, family_b))
    presentation = _FakePresentation(pick_index=0)
    handler = UnverifiableTaskHandler(providers, _router(), presentation)

    with pytest.raises(NoProviderAuthorizedError):
        await handler.handle(_task(), _NO_CONFIRMATION)

    assert presentation.presented is None
