"""Domain-level exception hierarchy.

Every exception raised from within ``jarvis.domain`` that a caller might
want to catch deliberately (rather than let propagate as a bug) is a
subclass of :class:`JarvisError`. This gives outer rings a single type
to catch when they want "any domain-level problem" without committing
to a specific failure mode.
"""

from __future__ import annotations


class JarvisError(Exception):
    """Base class for all domain-level errors raised by JARVIS."""


class TaintViolation(JarvisError):  # noqa: N818 -- reads as a violation, not an "-Error"
    """Raised when a tainted value is used as though it were trusted.

    Raised by :meth:`jarvis.domain.provenance.Tainted.require_trusted`
    when the wrapped value's provenance is still ``UNTRUSTED_EXTERNAL``.
    """
