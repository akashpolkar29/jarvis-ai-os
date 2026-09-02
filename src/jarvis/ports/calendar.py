"""The calendar port: the seam between a real CalDAV calendar and this codebase.

**Real, deliberate scope limit for this pass, not the port's own
permanent shape** -- mirrors ``ports/email.py``'s own identical
reasoning: only ``list_events`` has a real, working implementation.
``create_event`` exists on this Protocol because ``CalendarPort`` is
conceptually one port for "calendar," but every real adapter's own
``create_event`` method raises ``NotImplementedError`` -- creating an
event (even attendee-less) requires the same
``application/communications/classification.py::egress_effect_for``
decision ``EmailPort.send_message`` does (ADR-0057, still `Proposed`,
not `Accepted`). **A real, deliberately conservative scoping choice
this pass makes, not something the design doc itself required**:
`m6a-communications.md` classifies an attendee-less `create_event` as
ordinary `Effect.WRITE_LOCAL`/`Tier.CONFIRM`, not gated by ADR-0057 at
all -- it could, in principle, be implemented today. This pass
implements neither case, attendee-less or not, so there is exactly one
clean, unambiguous boundary ("everything past reading needs ADR-0057")
rather than a partially-implemented write path that would need its own
separate, later review of exactly which half was actually built.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.calendar`` for the
concrete CalDAV-backed adapter that satisfies this port's read half.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.calendar import CalendarEvent, CalendarEventDraft


@runtime_checkable
class CalendarPort(Protocol):
    """A real CalDAV calendar this codebase can list, and (once ADR-0057 is Accepted) write to."""

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        """Return every real event starting within ``[start, end]`` (both ISO-8601).

        No authorization happens inside this method -- matching every
        other port in this repo, this is a pure mechanism. Real
        `Tier.ALLOW` authorization happens at the composition-root
        layer (`kernel/communications.py`), before this is ever
        called.
        """
        ...

    async def create_event(self, draft: CalendarEventDraft) -> str:
        """Not implemented by any real adapter in this codebase -- see this module's own docstring.

        Every real adapter's own implementation raises
        ``NotImplementedError`` unconditionally, before any real CalDAV
        write is ever attempted -- including for an attendee-less
        draft, a deliberate scoping choice this pass makes (see module
        docstring).

        Raises:
            NotImplementedError: Always, until ADR-0057 is reviewed
                and Accepted and a real work package implements this
                for real.
        """
        ...
