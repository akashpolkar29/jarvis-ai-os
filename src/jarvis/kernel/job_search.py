"""The composition root for `job_search.open_results` -- assisted browsing, never scraping.

Real, direct decision following `docs/architecture/job-search-scoping-notes.md`'s
own finding: LinkedIn's and Indeed's current Terms of Service both
explicitly prohibit automated scraping/bot access to their job-search
surfaces (corroborated independently by both sites' own `robots.txt`
for the exact paths this would need), and neither offers a realistic
official API path for an individual, non-commercial tool. The real
resolution: JARVIS constructs a real, correct search-results URL and
opens it in the user's own, real, ordinary Brave browser -- a human
does the actual searching, clicking, and reading; JARVIS never reads,
scrapes, or extracts a single byte of listing content. See that
document's own "Resolution" section for the full account.

**A real, deliberate deviation from this work's own originating
prompt, reported here rather than silently made**: the prompt named
`kernel/browser.py`'s `authorize_and_open_page` as the function to
reuse. Investigated directly first, per the prompt's own "investigate
first" instruction: that function's underlying adapter
(`CdpBrowserAutomationAdapter`) launches a **headless** Brave instance
(`adapters/browser_automation.py`'s own `--headless=new` flag) --
genuinely invisible to any human, which would make "for the user to
look at and click through themselves" structurally impossible, not
merely awkward. Confirmed live during this same investigation: a
one-time, real, headless CDP load of a real Indeed search URL was
actively blocked by Indeed's own bot detection ("Request Blocked"),
while the equivalent LinkedIn URL succeeded -- real, concrete evidence
that headless automation is exactly the fingerprint both sites'
real-world defenses (not just their ToS text) are built to catch. The
correct reuse target is instead `kernel/desktop.py`'s
`authorize_and_open_brave_url`'s own underlying mechanism --
`BravePort`/`BraveCliAdapter`, a real, ordinary `brave-browser <url>`
subprocess launch, already live-verified for real in this project's
own M3 "Live desktop-control verification" pass, indistinguishable at
the network level from a human manually typing the URL. This module
calls that same real port directly (not `browser.open_page`), matching
the *effect/tier classification* `authorize_and_open_brave_url` uses
(`Effect.EXECUTE`, per the "investigate first" instruction's own
"reuse that same classification, not invent one" framing) while
authorizing its own, separate `CapabilityId` -- the same
"one CapabilityId, one composition function, one real adapter call"
shape every other capability in this codebase already follows,
`authorize_and_open_brave_url` included; no composition function in
this codebase calls another composition function's own
`authorize_by_id()` path, and this one does not start doing so either.

**Real, structural scope boundary, enforced mechanically, not just by
this docstring**: this module must never call `inspect_dom`,
`capture_screenshot`, or any other content-reading method on any page
-- it only ever builds a URL string and hands it to `BravePort.open_url`.
See `tests/meta/test_job_search_no_content_reading.py` for the real,
mechanical proof, mirroring `test_job_assistance_no_submission.py`'s
own established AST-scan pattern for ADR-0058's identical shape of
guarantee.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.brave import BraveCliAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import JOB_SEARCH_OPEN_RESULTS_CAPABILITY_ID, build_default_registry

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.policy import Decision
    from jarvis.ports.brave import BravePort


class JobSearchSite(Enum):
    """The only two real, supported job-board sites -- no other site is wired."""

    LINKEDIN = "linkedin"
    INDEED = "indeed"


def build_job_search_url(site: JobSearchSite, keywords: str, location: str | None) -> str:
    """Build the real, correct search-results URL for ``site`` -- pure, no I/O.

    Real, current query-parameter formats, verified live (not guessed
    from memory) during this capability's own implementation --
    LinkedIn's ``keywords``/``location`` confirmed via a real, live
    page load returning a real results header; Indeed's ``q``/``l``
    cross-confirmed against Indeed's own public integration
    documentation after a live load was blocked by Indeed's own bot
    detection (see this module's own docstring).

    Args:
        site: Which job board's URL format to use.
        keywords: The real search keywords, URL-encoded exactly as
            given -- not validated or parsed here.
        location: The real, optional location filter. Omitted from the
            URL entirely if ``None`` or empty, rather than sent as an
            empty parameter.

    Returns:
        A real, complete, ready-to-open search-results URL.
    """
    if site is JobSearchSite.LINKEDIN:
        params = {"keywords": keywords}
        if location:
            params["location"] = location
        return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

    params = {"q": keywords}
    if location:
        params["l"] = location
    return f"https://www.indeed.com/jobs?{urlencode(params)}"


def authorize_and_open_job_search(  # noqa: PLR0913 -- one per real, distinct pass-through argument
    site: JobSearchSite,
    keywords: str,
    location: str | None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser: BravePort | None = None,
) -> Decision:
    """Wire up the stack, authorize opening a real job-search results page, and open it if granted.

    Args:
        site: Which job board to search.
        keywords: The real search keywords.
        location: The real, optional location filter.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        browser: The port the built URL is sent to if granted. Defaults
            to a real ``BraveCliAdapter`` -- the same real, ordinary,
            already-live-verified mechanism ``authorize_and_open_brave_url``
            uses, not the headless one (see module docstring).
            Overridable for tests.

    Returns:
        The ``Decision`` for this call -- durably appended to the
        chain regardless of outcome. If granted, ``browser`` has
        already received ``open_url(url)`` by the time this returns
        (barring an exception it raised); if denied, it was never
        touched at all, and no URL was ever built into a real request.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        JOB_SEARCH_OPEN_RESULTS_CAPABILITY_ID,
        Tainted(
            {"site": site.value, "keywords": keywords, "location": location},
            Provenance.user(),
        ),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            url = build_job_search_url(site, keywords, location)
            real_browser = browser if browser is not None else BraveCliAdapter()
            real_browser.open_url(url)
    finally:
        storage.save(chain)

    return decision
