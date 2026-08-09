"""The audit storage port: the seam between an AuditChain and durable storage.

:class:`AuditStoragePort` is the one abstract boundary between "some
real place an audit chain is durably kept" (a JSON file, a future
database) and :class:`~jarvis.domain.audit.AuditChain`. Nothing in
``domain`` or ``application`` reads or writes an audit chain from disk
directly -- only through this port.

Named for the one thing it stores, not "storage" generically: its
signature is bound to ``AuditChain`` specifically, not to arbitrary
data. A future, unrelated persistence need (plugin config, say) would
get its own port, not be folded into this one.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.audit_storage`` for the
concrete adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.audit import AuditChain


@runtime_checkable
class AuditStoragePort(Protocol):
    """A durable store an AuditChain can be saved to and reloaded from."""

    def save(self, chain: AuditChain) -> None:
        """Durably persist every record currently in ``chain``."""
        ...

    def load(self) -> AuditChain:
        """Return the chain last saved, or an empty AuditChain if none was ever saved.

        Reloading does not itself validate the chain's integrity --
        see the implementing adapter's docstring for exactly what is
        and is not checked at load time. Callers that need that
        guarantee should call :meth:`~jarvis.domain.audit.AuditChain.verify`
        on the result themselves.
        """
        ...
