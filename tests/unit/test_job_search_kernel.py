"""Unit tests for jarvis.kernel.job_search's build_job_search_url/authorize_and_open_job_search.

A stub `BravePort` (with call tracking) is injected in place of the
real `BraveCliAdapter`, mirroring `test_desktop_kernel.py`'s own
`_StubBrowser` precedent for `authorize_and_open_brave_url` exactly --
these tests must be hermetic and never launch a real browser
subprocess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.kernel.job_search import (
    JobSearchSite,
    authorize_and_open_job_search,
    build_job_search_url,
)
from jarvis.ports.brave import BrowserLaunchFailedError

if TYPE_CHECKING:
    from pathlib import Path


class _StubBrowser:
    """A BravePort test double that records which URLs were opened, in order."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        self.calls: list[str] = []
        self._raise_on_call = raise_on_call

    def open_url(self, url: str) -> None:
        self.calls.append(url)
        if self._raise_on_call:
            msg = "Failed to launch brave-browser: not found"
            raise BrowserLaunchFailedError(msg)


def test_build_job_search_url_for_linkedin_uses_keywords_and_location() -> None:
    """The real, verified LinkedIn format: keywords/location query params."""
    url = build_job_search_url(JobSearchSite.LINKEDIN, "python developer", "remote")

    assert url == "https://www.linkedin.com/jobs/search/?keywords=python+developer&location=remote"


def test_build_job_search_url_for_linkedin_omits_location_when_none() -> None:
    url = build_job_search_url(JobSearchSite.LINKEDIN, "python developer", None)

    assert url == "https://www.linkedin.com/jobs/search/?keywords=python+developer"
    assert "location" not in url


def test_build_job_search_url_for_indeed_uses_q_and_l() -> None:
    """The real, verified Indeed format: q/l query params."""
    url = build_job_search_url(JobSearchSite.INDEED, "data scientist", "New York")

    assert url == "https://www.indeed.com/jobs?q=data+scientist&l=New+York"


def test_build_job_search_url_for_indeed_omits_location_when_empty_string() -> None:
    url = build_job_search_url(JobSearchSite.INDEED, "data scientist", "")

    assert url == "https://www.indeed.com/jobs?q=data+scientist"
    assert "l=" not in url


def test_granted_call_really_opens_the_real_built_url(tmp_path: Path) -> None:
    browser = _StubBrowser()

    decision = authorize_and_open_job_search(
        JobSearchSite.LINKEDIN,
        "python developer",
        "remote",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser=browser,
    )

    assert decision.granted is True
    assert browser.calls == [
        "https://www.linkedin.com/jobs/search/?keywords=python+developer&location=remote"
    ]


def test_denied_call_never_builds_or_opens_a_url(tmp_path: Path) -> None:
    """With no confirmation flags, CONFIRM-tier job_search.open_results is denied, browser untouched."""  # noqa: E501
    browser = _StubBrowser()

    decision = authorize_and_open_job_search(
        JobSearchSite.INDEED,
        "data scientist",
        None,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser=browser,
    )

    assert decision.granted is False
    assert browser.calls == []


def test_remote_confirmation_alone_is_sufficient_to_grant(tmp_path: Path) -> None:
    """CONFIRM tier grants on physical OR remote confirmation -- remote alone is enough."""
    browser = _StubBrowser()

    decision = authorize_and_open_job_search(
        JobSearchSite.LINKEDIN,
        "python developer",
        None,
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        browser=browser,
    )

    assert decision.granted is True
    assert browser.calls == ["https://www.linkedin.com/jobs/search/?keywords=python+developer"]


def test_a_real_browser_launch_failure_propagates(tmp_path: Path) -> None:
    browser = _StubBrowser(raise_on_call=True)

    with pytest.raises(BrowserLaunchFailedError):
        authorize_and_open_job_search(
            JobSearchSite.LINKEDIN,
            "python developer",
            None,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            browser=browser,
        )


def test_a_denied_decision_is_still_durably_saved(tmp_path: Path) -> None:
    """The audit-save guarantee holds even on denial -- mirrors every other composition function."""
    chain_path = tmp_path / "audit_chain.json"
    browser = _StubBrowser()

    authorize_and_open_job_search(
        JobSearchSite.INDEED,
        "data scientist",
        None,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        browser=browser,
    )

    assert chain_path.exists()
