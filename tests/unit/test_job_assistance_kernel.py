"""Unit tests for jarvis.kernel.job_assistance's authorize_and_draft_document composition root.

Fake ReasoningPort(s) (with call tracking), a fake CandidatePresentationPort,
and a fake DraftStoragePort are wired into the real
AuthorizationOrchestrator/DraftWriteAuthorizer/UnverifiableTaskHandler/
ModelRouter chain -- mirroring test_coding_kernel.py's own "only the
true external-I/O edges are faked" discipline. Satisfies
m6b-job-assistance.md's own acceptance criteria 2 and 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.reasoning import ProviderProfile
from jarvis.kernel.job_assistance import authorize_and_draft_document

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt

_PROFILE_A = ProviderProfile(name="local-a", is_local=True)
_PROFILE_B = ProviderProfile(name="local-b", is_local=True)


class _CountingProvider:
    """A minimal, test-local ReasoningPort that records every real call it receives."""

    def __init__(self, author: str, content: str) -> None:
        self._author = author
        self._content = content
        self.call_count = 0

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        self.call_count += 1
        candidate = Candidate(author=self._author, content=self._content)
        return Tainted(candidate, Provenance.system())


class _FakePresentation:
    """Records every candidate set it was shown, always selects the first."""

    def __init__(self) -> None:
        self.shown: tuple[Candidate, ...] | None = None

    async def present_and_select(self, candidates: tuple[Candidate, ...]) -> Candidate:
        self.shown = candidates
        return candidates[0]


class _FakeDraftStorage:
    """Records every save() call it receives, returns a fixed fake path."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self.calls: list[tuple[str, str]] = []

    def save(self, filename_hint: str, content: str) -> Path:
        self.calls.append((filename_hint, content))
        return self._tmp_path / f"{filename_hint}.txt"


async def test_granted_draft_invokes_every_provider_and_saves_the_selected_candidate(
    tmp_path: Path,
) -> None:
    provider_a = _CountingProvider("local-a", "Dear hiring manager, from A")
    provider_b = _CountingProvider("local-b", "Dear hiring manager, from B")
    presentation = _FakePresentation()
    storage = _FakeDraftStorage(tmp_path)

    outcome = await authorize_and_draft_document(
        "draft a cover letter",
        ((_PROFILE_A, provider_a), (_PROFILE_B, provider_b)),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=presentation,
        draft_storage=storage,
    )

    assert outcome.decision.granted is True
    assert provider_a.call_count == 1
    assert provider_b.call_count == 1
    assert presentation.shown is not None
    assert len(presentation.shown) == 2  # noqa: PLR2004 -- the real count of providers wired in
    assert len(storage.calls) == 1
    saved_author, saved_content = storage.calls[0]
    assert saved_content in ("Dear hiring manager, from A", "Dear hiring manager, from B")
    assert saved_author in ("local-a", "local-b")
    assert outcome.path == tmp_path / f"{saved_author}.txt"


async def test_denied_draft_never_invokes_any_provider_or_storage(tmp_path: Path) -> None:
    provider = _CountingProvider("local-a", "content")
    presentation = _FakePresentation()
    storage = _FakeDraftStorage(tmp_path)

    outcome = await authorize_and_draft_document(
        "draft a cover letter",
        ((_PROFILE_A, provider),),
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=presentation,
        draft_storage=storage,
    )

    assert outcome.decision.granted is False
    assert outcome.path is None
    assert provider.call_count == 0
    assert presentation.shown is None
    assert storage.calls == []


async def test_remote_confirmation_alone_is_sufficient_to_grant(tmp_path: Path) -> None:
    """job_assistance.draft floats at WRITE_LOCAL/CONFIRM for non-SECRET input -- either channel suffices."""  # noqa: E501
    provider = _CountingProvider("local-a", "content")
    storage = _FakeDraftStorage(tmp_path)

    outcome = await authorize_and_draft_document(
        "draft a cover letter",
        ((_PROFILE_A, provider),),
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        presentation=_FakePresentation(),
        draft_storage=storage,
    )

    assert outcome.decision.granted is True
    assert provider.call_count == 1


async def test_a_single_granted_draft_appends_a_verifiable_audit_record(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"

    await authorize_and_draft_document(
        "draft a cover letter",
        ((_PROFILE_A, _CountingProvider("local-a", "content")),),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        presentation=_FakePresentation(),
        draft_storage=_FakeDraftStorage(tmp_path),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    # >= 1, not == 1: the outer job_assistance.draft decision and the
    # inner ModelRouter.authorize_provider_call decision (inside
    # UnverifiableTaskHandler.handle()) share one orchestrator, so both
    # land in the same chain -- mirroring kernel/coding.py's own
    # "every real decision this one call makes lands in the same,
    # single, tamper-evident record" shape.
    assert len(chain) >= 1
    assert chain.verify().valid is True
    assert chain[0].decision.granted is True
