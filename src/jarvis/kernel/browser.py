"""The composition root for M5's browser-automation capability family.

browser.open_page / browser.screenshot / browser.inspect_dom.

Mirrors ``jarvis.kernel.desktop``'s ``authorize_and_open_brave_url``
pattern exactly: registry/storage/confirmation/orchestrator wiring,
``orchestrator.authorize_by_id()`` always first, the real side effect
only ever inside ``if decision.granted:``, ``storage.save(chain)`` in
a ``finally`` block so a granted decision is never lost even if the
subsequent real action raises.

**Only WP-67 through WP-69 of ``m5-browser-coding.md``'s own sketch --
the browser-automation track only.** No coding-loop wrapper, no
``Effect.CODE_WRITE``/``Effect.PROTECTED_PATH_WRITE``, no code from
ADR-0055/ADR-0056 exists anywhere in this module or this codebase --
both ADRs remain **Proposed**, not Accepted, per this pass's own
explicit, narrower scope. See ``m5-browser-coding.md``'s own header
for why even *this* module's design doc basis is more provisional than
M3/M4's own kernel modules were.

**Static, fixed-effect capabilities, not a dynamic classification
function** -- unlike ``memory.write``/(the not-yet-built)
``coding.write``, none of these three capabilities' correct ``Effect``
varies per invocation with the argument's own content classification;
each is registered once in ``build_default_registry()`` with a fixed
effect (``kernel/capabilities.py``), the same shape
``desktop.brave_open_url``/``fs.read_file`` already use.

**Real content extracted from a browser page is tainted
``Trust.UNTRUSTED_EXTERNAL``/``Classification.SENSITIVE``**, mirroring
``kernel/files.py``'s own ``authorize_and_read_file`` exactly: a
screenshot or a DOM fragment pulled from an arbitrary, real web page is
exactly the same class of "JARVIS cannot know whether this content is
mundane or originated from an untrusted, possibly-adversarial source"
content ``fs.read_file``'s own docstring already reasons about for an
arbitrary local file -- not assumed benign here either. This taint has
no bearing on the *current* invocation's own tier (tier escalation
only reads the *argument's* provenance, computed before the call), only
on what a *future* capability consuming this content inherits.

**``browser.open_page`` returns a real, reconnectable ``PageHandle``,
not tainted itself** -- it is an opaque reference, the same
"not content, not tainted" treatment ``WindowHandle`` already gets from
``kernel/desktop.py``.

**No ``browser.close`` capability is registered.** Tearing down a real
browser process this module itself launched is real, necessary cleanup
-- but it acts only on state this process already fully controls (its
own already-granted, already-launched subprocess), the same
"cleanup is not itself a new authorizable action" reasoning
``storage.save(chain)`` already gets throughout this codebase.
:func:`close_browser_page` exists as a plain, ungated function for
exactly this reason -- a real, necessary caller-facing capability this
work package's own scope still leaves genuinely open: nothing in this
codebase yet calls it automatically after a real
``browser.screenshot``/``browser.inspect_dom`` call, so every real
``browser.open_page`` call today leaks one real browser subprocess and
temporary profile directory until something -- a future work package,
a manual call -- closes it. Named here plainly, not silently smoothed
over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.browser_automation import CdpBrowserAutomationAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.capabilities import (
    BROWSER_INSPECT_DOM_CAPABILITY_ID,
    BROWSER_OPEN_PAGE_CAPABILITY_ID,
    BROWSER_SCREENSHOT_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.browser import PageHandle
    from jarvis.domain.policy import Decision
    from jarvis.ports.browser_automation import BrowserAutomationPort


def _adapter(browser_automation: BrowserAutomationPort | None) -> BrowserAutomationPort:
    return browser_automation or CdpBrowserAutomationAdapter()


async def authorize_and_open_page(
    url: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser_automation: BrowserAutomationPort | None = None,
) -> tuple[Decision, PageHandle | None]:
    """Wire up the stack, authorize opening ``url``, and open a real page only if granted.

    Args:
        url: The URL to navigate a new, dedicated browser page to,
            passed straight through to ``browser_automation.open_page``
            if granted.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        browser_automation: The port ``url`` is sent to if granted.
            Defaults to a real ``CdpBrowserAutomationAdapter``.
            Overridable for tests.

    Returns:
        ``(decision, handle)`` -- ``handle`` is the real, reconnectable
        ``PageHandle`` if granted, ``None`` if denied. Not tainted (see
        module docstring).
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
        BROWSER_OPEN_PAGE_CAPABILITY_ID,
        Tainted({"url": url}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    handle: PageHandle | None = None
    try:
        if decision.granted:
            handle = await _adapter(browser_automation).open_page(url)
    finally:
        storage.save(chain)

    return decision, handle


async def authorize_and_capture_screenshot(
    handle: PageHandle,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser_automation: BrowserAutomationPort | None = None,
) -> tuple[Decision, Tainted[bytes] | None]:
    """Wire up the stack, authorize a screenshot of ``handle``, and capture it only if granted.

    Args:
        handle: A real, still-live page, from a prior granted
            ``authorize_and_open_page`` call.
        physical_confirmation_available: As above.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        browser_automation: Defaults to a real
            ``CdpBrowserAutomationAdapter``. Overridable for tests.

    Returns:
        ``(decision, screenshot)`` -- ``screenshot`` is the real PNG
        bytes, tagged ``Provenance.external(source=handle.target_id,
        classification=Classification.SENSITIVE)`` (see module
        docstring), if granted; ``None`` if denied.
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
        BROWSER_SCREENSHOT_CAPABILITY_ID,
        Tainted({"target_id": handle.target_id}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    screenshot: Tainted[bytes] | None = None
    try:
        if decision.granted:
            raw = await _adapter(browser_automation).capture_screenshot(handle)
            screenshot = Tainted(
                raw,
                Provenance.external(
                    source=handle.target_id, classification=Classification.SENSITIVE
                ),
            )
    finally:
        storage.save(chain)

    return decision, screenshot


async def authorize_and_query_dom(  # noqa: PLR0913 -- one per composition-function pass-through
    handle: PageHandle,
    selector: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser_automation: BrowserAutomationPort | None = None,
) -> tuple[Decision, Tainted[str] | None]:
    """Wire up the stack, authorize a DOM query of ``handle``, and run it only if granted.

    Args:
        handle: A real, still-live page, from a prior granted
            ``authorize_and_open_page`` call.
        selector: A real CSS selector, passed straight through to
            ``browser_automation.query_dom`` if granted.
        physical_confirmation_available: As above.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        browser_automation: Defaults to a real
            ``CdpBrowserAutomationAdapter``. Overridable for tests.

    Returns:
        ``(decision, html)`` -- ``html`` is the matched element's real
        outer HTML, tagged the same way as
        :func:`authorize_and_capture_screenshot`'s own screenshot, if
        granted and a real match was found. ``None`` if denied, or if
        granted but no element matched ``selector`` (a real, expected
        outcome -- not distinguished from "denied" by this return
        shape alone; callers needing to distinguish them read
        ``decision.granted`` directly).
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
        BROWSER_INSPECT_DOM_CAPABILITY_ID,
        Tainted({"target_id": handle.target_id, "selector": selector}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    html: Tainted[str] | None = None
    try:
        if decision.granted:
            raw = await _adapter(browser_automation).query_dom(handle, selector)
            if raw is not None:
                html = Tainted(
                    raw,
                    Provenance.external(
                        source=handle.target_id, classification=Classification.SENSITIVE
                    ),
                )
    finally:
        storage.save(chain)

    return decision, html


async def close_browser_page(
    handle: PageHandle, browser_automation: BrowserAutomationPort | None = None
) -> None:
    """Tear down ``handle``'s real browser subprocess and temporary profile. Not authorized.

    See the module docstring's own "No browser.close capability"
    section for why this is a plain function, not a registered
    capability -- and for the real, still-open gap that nothing in
    this codebase calls this automatically yet.
    """
    await _adapter(browser_automation).close(handle)
