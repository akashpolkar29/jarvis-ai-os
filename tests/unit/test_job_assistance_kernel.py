"""Unit tests for jarvis.kernel.job_assistance's authorize_and_draft_document composition root.

Fake ReasoningPort(s) (with call tracking), a fake CandidatePresentationPort,
and a fake DraftStoragePort are wired into the real
AuthorizationOrchestrator/DraftWriteAuthorizer/UnverifiableTaskHandler/
ModelRouter chain -- mirroring test_coding_kernel.py's own "only the
true external-I/O edges are faked" discipline. Satisfies
m6b-job-assistance.md's own acceptance criteria 2 and 3.

``test_real_default_providers_reaches_a_locally_running_ollama_server``
is the one real, live exception -- skipif-guarded on a real
reachability probe against ``localhost:11434``, mirroring
``tests/unit/test_coding_kernel.py``'s own identical guard.
Live-verified manually on this development machine 2026-09-04
(``qwen2.5:0.5b``).
"""

from __future__ import annotations

import urllib.request
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.capability import Tier
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.reasoning import ProviderProfile
from jarvis.kernel.job_assistance import (
    ApplicationFolderAlreadyExistsError,
    ApplicationFolderOutsideBaseDirectoryError,
    authorize_and_draft_document,
    authorize_and_prepare_application_folder,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt


def _real_ollama_server_is_reachable() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    except OSError:
        return False
    return True


_PROFILE_A = ProviderProfile(name="local-a", is_local=True)
_PROFILE_B = ProviderProfile(name="local-b", is_local=True)


class _RealConsoleConstructedInATestError(AssertionError):
    """Raised if this module ever constructs a real GtkConsoleAdapter -- see the fixture below."""


@pytest.fixture(autouse=True)
def _forbid_real_console_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real-window regression guard (found and fixed 2026-09-05).

    Four tests in this module called `authorize_and_draft_document`
    with a granted decision and no `console=` override, silently
    falling through to `_console()`'s own real default
    (`GtkConsoleAdapter()`) -- each one opened a real, unclosed GTK4
    window on the real desktop during an ordinary automated test run
    (observed directly: a real window titled with the drafted task's
    own text, e.g. "job_assistance.draft: draft a cover letter",
    stacking up unclosed across repeated runs). Fixed by passing a
    real `_StubConsole()` at every granted call site in this module.

    This autouse fixture is the real, durable regression guard: it
    patches the exact class `_console()` falls back to
    (`jarvis.kernel.job_assistance.GtkConsoleAdapter`) with one that
    raises immediately if ever constructed, for every test in this
    module, whether or not that test remembers to pass `console=`
    itself. A future test that reintroduces this gap fails loudly and
    immediately -- pointing straight at the real cause -- rather than
    silently leaking another real window.
    """

    def _raise_if_constructed(*_args: object, **_kwargs: object) -> None:
        msg = (
            "A real GtkConsoleAdapter was constructed inside a test -- this test is "
            "missing its own console= override (a _StubConsole()), and would open a "
            "real, unclosed GTK4 window on the real desktop. Pass console=_StubConsole() "
            "to the authorize_and_draft_document() call this test makes."
        )
        raise _RealConsoleConstructedInATestError(msg)

    monkeypatch.setattr("jarvis.kernel.job_assistance.GtkConsoleAdapter", _raise_if_constructed)


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


class _StubConsole:
    """A ConsolePort test double that records every real line shown, in order.

    Mirrors tests/unit/test_browser_kernel.py's own _StubConsole
    exactly.
    """

    def __init__(self) -> None:
        self.shown: list[str] = []

    def show_line(self, text: str) -> None:
        self.shown.append(text)


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
        console=_StubConsole(),
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
        console=_StubConsole(),
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
        console=_StubConsole(),
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


async def test_granted_draft_shows_a_real_console_line(tmp_path: Path) -> None:
    """Post-WP-86 Console UI wiring: a granted, successful draft shows a real on-screen line."""
    console = _StubConsole()

    await authorize_and_draft_document(
        "draft a cover letter",
        ((_PROFILE_A, _CountingProvider("local-a", "content")),),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=_FakePresentation(),
        draft_storage=_FakeDraftStorage(tmp_path),
        console=console,
    )

    assert console.shown == ["job_assistance.draft: draft a cover letter"]


async def test_denied_draft_never_shows_a_console_line(tmp_path: Path) -> None:
    """Mirrors authorize_and_open_page's own test_denied_open_page_never_shows_a_console_line."""
    console = _StubConsole()

    await authorize_and_draft_document(
        "draft a cover letter",
        ((_PROFILE_A, _CountingProvider("local-a", "content")),),
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=_FakePresentation(),
        draft_storage=_FakeDraftStorage(tmp_path),
        console=console,
    )

    assert console.shown == []


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, locally running Ollama server on localhost:11434, not assumed in CI.",
)
async def test_real_default_providers_reaches_a_locally_running_ollama_server(
    tmp_path: Path,
) -> None:
    """Omitting providers really reaches the real local model -- not a stub, not a skip."""
    outcome = await authorize_and_draft_document(
        "draft a one-sentence cover letter opener",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=_FakePresentation(),
        draft_storage=_FakeDraftStorage(tmp_path),
        console=_StubConsole(),
    )

    assert outcome.decision.granted is True
    assert outcome.path is not None


async def test_a_granted_draft_missing_its_console_override_is_caught_by_the_real_window_guard(
    tmp_path: Path,
) -> None:
    """Real proof the regression guard above actually fires -- not just present, but working.

    Deliberately reproduces the exact real gap this pass fixed (a
    granted draft call with no `console=` override) and confirms
    `_forbid_real_console_windows` catches it immediately, before any
    real `GtkConsoleAdapter` -- and therefore any real window -- could
    ever be constructed.
    """
    with pytest.raises(_RealConsoleConstructedInATestError):
        await authorize_and_draft_document(
            "draft a cover letter",
            ((_PROFILE_A, _CountingProvider("local-a", "content")),),
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            presentation=_FakePresentation(),
            draft_storage=_FakeDraftStorage(tmp_path),
        )


def _write_real_templates(tmp_path: Path) -> tuple[Path, Path]:
    """Write two real, distinct, minimal .tex template files under tmp_path, return their paths."""
    cv_template = tmp_path / "cv_template.tex"
    cover_letter_template = tmp_path / "cover_letter_template.tex"
    cv_template.write_text("\\documentclass{article}\n\\begin{document}\nCV\n\\end{document}\n")
    cover_letter_template.write_text(
        "\\documentclass{article}\n\\begin{document}\n% \\input{body.tex}\n\\end{document}\n"
    )
    return cv_template, cover_letter_template


async def test_granted_prepare_creates_folders_and_copies_templates_verbatim(
    tmp_path: Path,
) -> None:
    """Real folder/file creation: CV and Cover Letter templates copied byte-for-byte."""
    cv_template, cover_letter_template = _write_real_templates(tmp_path)
    base_dir = tmp_path / "base"
    provider = _CountingProvider("local", "Dear Hiring Manager, real drafted body.")

    outcome = await authorize_and_prepare_application_folder(
        base_dir,
        "September 2026",
        cv_template,
        cover_letter_template,
        "Software Engineer",
        "Acme Corp",
        providers=((_PROFILE_A, provider),),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=_FakePresentation(),
        console=_StubConsole(),
    )

    assert outcome.decision.granted is True
    assert outcome.decision.tier == Tier.CONFIRM
    assert outcome.cv_path == base_dir / "September 2026" / "CV" / "main.tex"
    assert outcome.cv_path is not None
    assert outcome.cv_path.read_text() == cv_template.read_text()
    assert outcome.cover_letter_template_path == (
        base_dir / "September 2026" / "Cover Letter" / "main.tex"
    )
    assert outcome.cover_letter_template_path is not None
    assert outcome.cover_letter_template_path.read_text() == cover_letter_template.read_text()
    assert outcome.draft_decision is not None
    assert outcome.draft_decision.granted is True
    assert outcome.body_path == base_dir / "September 2026" / "Cover Letter" / "body.tex"
    assert outcome.body_path is not None
    assert outcome.body_path.read_text() == "Dear Hiring Manager, real drafted body."


async def test_denied_prepare_never_creates_any_real_folder_or_file(tmp_path: Path) -> None:
    """A denied outer gate (no confirmation) creates nothing at all -- not even a folder."""
    cv_template, cover_letter_template = _write_real_templates(tmp_path)
    base_dir = tmp_path / "base"

    outcome = await authorize_and_prepare_application_folder(
        base_dir,
        "September 2026",
        cv_template,
        cover_letter_template,
        "Software Engineer",
        "Acme Corp",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        presentation=_FakePresentation(),
        console=_StubConsole(),
    )

    assert outcome.decision.granted is False
    assert outcome.cv_path is None
    assert outcome.cover_letter_template_path is None
    assert outcome.draft_decision is None
    assert outcome.body_path is None
    assert not base_dir.exists()


async def test_a_second_call_without_force_raises_and_leaves_the_first_call_untouched(
    tmp_path: Path,
) -> None:
    """Idempotency safety check: a real, existing application folder is never silently touched."""
    cv_template, cover_letter_template = _write_real_templates(tmp_path)
    base_dir = tmp_path / "base"
    chain_path = tmp_path / "audit_chain.json"

    first_outcome = await authorize_and_prepare_application_folder(
        base_dir,
        "September 2026",
        cv_template,
        cover_letter_template,
        "Software Engineer",
        "Acme Corp",
        providers=((_PROFILE_A, _CountingProvider("local", "first real body")),),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        presentation=_FakePresentation(),
        console=_StubConsole(),
    )
    assert first_outcome.body_path is not None
    original_body_content = first_outcome.body_path.read_text()

    with pytest.raises(ApplicationFolderAlreadyExistsError):
        await authorize_and_prepare_application_folder(
            base_dir,
            "September 2026",
            cv_template,
            cover_letter_template,
            "Software Engineer",
            "Acme Corp",
            providers=((_PROFILE_A, _CountingProvider("local", "second real body")),),
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            presentation=_FakePresentation(),
            console=_StubConsole(),
        )

    # The first call's real, already-drafted content survives untouched.
    assert first_outcome.body_path.read_text() == original_body_content


async def test_force_true_overwrites_and_requires_physical_confirmation_specifically(
    tmp_path: Path,
) -> None:
    """force=True floors at Tier.MANUAL_ONLY -- remote confirmation alone must not suffice."""
    cv_template, cover_letter_template = _write_real_templates(tmp_path)
    base_dir = tmp_path / "base"
    chain_path = tmp_path / "audit_chain.json"

    await authorize_and_prepare_application_folder(
        base_dir,
        "September 2026",
        cv_template,
        cover_letter_template,
        "Software Engineer",
        "Acme Corp",
        providers=((_PROFILE_A, _CountingProvider("local", "first real body")),),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        presentation=_FakePresentation(),
        console=_StubConsole(),
    )

    # force=True, but only remote confirmation available -- must be denied.
    remote_only_outcome = await authorize_and_prepare_application_folder(
        base_dir,
        "September 2026",
        cv_template,
        cover_letter_template,
        "Software Engineer",
        "Acme Corp",
        providers=((_PROFILE_A, _CountingProvider("local", "second real body")),),
        force=True,
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=chain_path,
        presentation=_FakePresentation(),
        console=_StubConsole(),
    )
    assert remote_only_outcome.decision.granted is False
    assert remote_only_outcome.decision.tier == Tier.MANUAL_ONLY

    # force=True with real physical confirmation -- granted, real overwrite.
    forced_outcome = await authorize_and_prepare_application_folder(
        base_dir,
        "September 2026",
        cv_template,
        cover_letter_template,
        "Software Engineer",
        "Acme Corp",
        providers=((_PROFILE_A, _CountingProvider("local", "second real body")),),
        force=True,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        presentation=_FakePresentation(),
        console=_StubConsole(),
    )
    assert forced_outcome.decision.granted is True
    assert forced_outcome.decision.tier == Tier.MANUAL_ONLY
    assert forced_outcome.body_path is not None
    assert forced_outcome.body_path.read_text() == "second real body"


async def test_a_missing_cv_template_fails_cleanly_with_no_partial_folder(tmp_path: Path) -> None:
    """A missing/invalid template path fails cleanly -- never leaves a partial folder behind."""
    _cv_template, cover_letter_template = _write_real_templates(tmp_path)
    missing_cv_template = tmp_path / "does-not-exist.tex"
    base_dir = tmp_path / "base"

    with pytest.raises(FileNotFoundError):
        await authorize_and_prepare_application_folder(
            base_dir,
            "September 2026",
            missing_cv_template,
            cover_letter_template,
            "Software Engineer",
            "Acme Corp",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            presentation=_FakePresentation(),
            console=_StubConsole(),
        )

    assert not base_dir.exists()


async def test_month_label_escaping_the_base_dir_is_rejected(tmp_path: Path) -> None:
    """A month_label containing path traversal cannot escape base_dir."""
    cv_template, cover_letter_template = _write_real_templates(tmp_path)
    base_dir = tmp_path / "base"

    with pytest.raises(ApplicationFolderOutsideBaseDirectoryError):
        await authorize_and_prepare_application_folder(
            base_dir,
            "../../etc",
            cv_template,
            cover_letter_template,
            "Software Engineer",
            "Acme Corp",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            presentation=_FakePresentation(),
            console=_StubConsole(),
        )
