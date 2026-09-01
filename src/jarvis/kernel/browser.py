"""The composition root for M5's browser-automation capability family.

browser.open_page / browser.screenshot / browser.inspect_dom / browser.close_page.

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

**``browser.close_page`` is a real, registered, authorized capability
-- not a plain, ungated function.** A prior version of this module
reasoned that tearing down a subprocess this process already fully
controls needed no new authorization, treating it as cleanup rather
than a capability, the same "cleanup is not itself a new authorizable
action" shape ``storage.save(chain)`` gets throughout this codebase.
**That reasoning does not hold up against this project's own real
precedent, checked directly rather than assumed**: ``docker.stop_container``
(``kernel/desktop.py``) is exactly this same shape -- tearing down
something a prior capability started -- and it is a real, registered,
``Effect.EXECUTE`` capability, not a bare port call. Nothing in this
codebase treats "stop what you started" as exempt from authorization;
this module's own prior exemption was a real, un-mirrored inconsistency,
not a considered design choice, and is fixed here to match
``docker.stop_container``'s own precedent exactly (same effect, same
tier, same "recoverable/expected cleanup, not destructive" reasoning).

**Still a real, open gap, named plainly**: registering the capability
closes the *authorization* gap, not the *automatic-invocation* gap --
nothing in this codebase yet calls ``browser.close_page`` on its own
after a ``browser.screenshot``/``browser.inspect_dom`` call, or on any
kind of idle timeout. A caller (a future coding-loop consumer, a CLI
command, a voice command) must still invoke it explicitly, the same
way a caller must explicitly invoke ``docker.stop_container`` --
nothing in this codebase auto-stops a Docker container either. This is
a deliberate, consistent choice, not a shortcut: no other
process/resource-lifecycle capability in this repo (``SandboxPort.launch``'s
own returned pid included) has ever had an automatic sweep or
idle-timeout mechanism -- inventing one here, for browser pages
specifically, would be new, unprecedented machinery this milestone's
own narrow scope does not call for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.browser_automation import CdpBrowserAutomationAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.capabilities import (
    BROWSER_CLOSE_PAGE_CAPABILITY_ID,
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


async def authorize_and_close_page(
    handle: PageHandle,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser_automation: BrowserAutomationPort | None = None,
) -> Decision:
    """Wire up the stack, authorize closing ``handle``, and tear it down only if granted.

    Mirrors ``docker.stop_container``'s own real precedent (see module
    docstring): stopping/tearing down something a prior capability
    started is itself a real, registered, authorized capability in
    this codebase, not exempt cleanup. Returns the bare ``Decision``
    directly, matching ``authorize_and_pin``/``authorize_and_forget``'s
    own shape (``kernel/memory.py``) -- a close has no further output
    data worth wrapping in its own outcome type.

    Args:
        handle: A real, still-live page, from a prior granted
            ``authorize_and_open_page`` call.
        physical_confirmation_available: As above.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        browser_automation: Defaults to a real
            ``CdpBrowserAutomationAdapter``. Overridable for tests.

    Returns:
        The real ``Decision`` for this close call, already durably
        appended to the chain at ``chain_path`` by the time this
        returns.
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
        BROWSER_CLOSE_PAGE_CAPABILITY_ID,
        Tainted({"target_id": handle.target_id}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            await _adapter(browser_automation).close(handle)
    finally:
        storage.save(chain)

    return decision
