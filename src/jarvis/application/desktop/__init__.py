"""Multi-step desktop-control orchestration, beyond a single authorize-then-call-one-port shape.

``jarvis.kernel.desktop`` handles every "simple" M3 capability
(Spotify, Brave, VS Code, the two consumer chat desktop apps) directly:
authorize, then call exactly one port method if granted. No vendor
names appear in this module, per ADR-0021. Terminal's
real flow (WP-52) genuinely needs more than that -- launch a sandboxed
process, find its window, focus it, type into it, best-effort read its
output -- the same reasoning ``jarvis.application.reasoning`` already
established for why multi-step orchestration lives in ``application``,
not inlined into ``kernel``.

This package also carries a real, mechanically-enforced restriction
``kernel.desktop`` cannot: ``kernel.desktop`` must never reference
``DesktopWindowPort.read_visible_text`` at all (ADR-0045,
``tests/meta/test_no_response_scraping.py``), so Terminal's own
legitimate use of it (ADR-0046) has to live somewhere else -- here.
"""

from __future__ import annotations

from .terminal import run_in_sandboxed_terminal

__all__ = [
    "run_in_sandboxed_terminal",
]
