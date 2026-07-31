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


class AuditRecordTampered(JarvisError):  # noqa: N818 -- reads as a fact, not an "-Error"
    """Raised when an AuditRecord's stored hash doesn't match its own content.

    A data-integrity signal, not a programming error: some record's
    fields (or its stored ``record_hash``) were changed after the fact
    without recomputing the hash to match. It is structurally
    impossible to construct an ``AuditRecord`` this way through its
    normal constructor -- ``__post_init__`` checks this on every
    construction -- so this being raised means a record was corrupted
    out-of-band (a buggy deserializer, or an actual tampering attempt):
    the same category of runtime security-relevant failure that made
    ``TaintViolation`` a ``JarvisError`` subclass, not a plain
    ``ValueError``.
    """


class AuditRecordNotSerializable(JarvisError):  # noqa: N818 -- reads as a fact, not an "-Error"
    """Raised when a Decision's content cannot be deterministically hashed.

    Unlike ``AuditRecordTampered``, this is a programming error: a
    capability passed an argument value that the audit log's
    canonicalization scheme has no stable way to serialize. It gets
    its own ``JarvisError`` subclass, distinct from
    ``AuditRecordTampered``, because the two are actionable in
    completely different ways -- a caller catching this should fix the
    capability's argument types; a caller catching
    ``AuditRecordTampered`` should investigate a security incident.
    Conflating them into one error would hide which kind of problem
    actually occurred.
    """
