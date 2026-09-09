"""WP-104: the typed freeform command router's reasoning-fallback (Stage B) logic.

:func:`~jarvis.application.routing.router.generate_route` asks a real
`ReasoningPort` provider (no new port) to propose a structured
:class:`~jarvis.application.routing.router.RouteResult` for text that
`jarvis.kernel.router`'s own deterministic Stage A could not
confidently resolve, then validates the response structurally --
malformed JSON, an unrecognized `kind`, or an unregistered capability
id all raise :class:`~jarvis.application.routing.router.RoutingError`.

`jarvis.kernel.router`'s own `authorize_and_route` is the real
composition root wiring Stage A and Stage B together into the
invocable `jarvis do "<text>"` entry point. Mirrors
`jarvis.application.planning`'s own package-docstring shape.
"""

from __future__ import annotations

from .router import RouteKind, RouteResult, RoutingError, generate_route

__all__ = [
    "RouteKind",
    "RouteResult",
    "RoutingError",
    "generate_route",
]
