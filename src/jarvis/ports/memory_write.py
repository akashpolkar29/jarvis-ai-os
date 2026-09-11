"""The memory write port: persisting a real, provenance-tagged value to memory.

:class:`MemoryWritePort` is one of ADR-0048's two new M4 ports --
writing to memory and reading from it are kept structurally separate,
since they have different authorization stories (ADR-0049 for write,
ADR-0050 for read).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.memory`` for the
concrete adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.provenance import Tainted


class MemoryRecordNotFoundError(Exception):
    """Raised when ``pin()`` is given an identifier no real record matches.

    Defined on the port, not the adapter, matching
    :class:`~jarvis.ports.secret.SecretNotFoundError`'s own reasoning --
    a caller should not need to know which concrete adapter is behind
    the port to catch this. Deliberately not a silent no-op: a
    caller acting on a stale or mistyped identifier and believing a
    pin succeeded when nothing was pinned is exactly the class of bug
    this project has already been burned by once (an AppArmor denial
    silently swallowed as success, ``adapters/media_player.py``'s own
    docstring records the fix) -- not repeated here for a second,
    different mechanism.
    """


@runtime_checkable
class MemoryWritePort(Protocol):
    """A real, persistent store a provenance-tagged value can be written to."""

    def write(self, value: Tainted[object]) -> str:
        """Persist ``value`` to memory, provenance intact.

        No authorization happens inside this method -- matching every
        other port in this repo (``SecretPort``, ``MediaPlayerPort``,
        ``DesktopWindowPort``), this is a pure mechanism. A
        SECRET-classified value is never denied *by this call*: the
        composition root resolves ``memory_effect_for`` (ADR-0049) and
        checks ``AuthorizationOrchestrator``'s real ``Decision``
        *before* ever calling ``write()`` at all -- a denied write
        simply never reaches this method, the same "port method only
        runs after a granted Decision" shape every
        ``kernel/*.py`` composition function already follows.

        Real, necessary correction found during implementation, not
        present in ADR-0048's original code sketch: this method
        returns the new record's real, stable identifier rather than
        ``None`` -- without it, ``pin()`` below would have no way to
        reference the record it was just asked to write, making the
        accepted design uncallable in practice. A small, mechanical
        fix, not a change to this ADR's own reasoning.

        Returns:
            The new ``MemoryRecord``'s real, stable identifier.
        """
        ...

    def pin(self, identifier: str) -> None:
        """Mark the record at ``identifier`` as pinned -- never expires (ADR-0051).

        Sets the record's ``expires_at`` to ``None`` rather than
        extending it by a fixed window, matching ADR-0051's own
        "anything you want kept longer" framing. A no-op if the record
        is already pinned.

        Raises:
            MemoryRecordNotFoundError: If ``identifier`` does not
                match a real, currently-stored record.
        """
        ...

    def sweep_expired(self) -> int:
        """Permanently delete every expired, unpinned record from the real store.

        ADR-0051 names this real sweep as separate, owed work beyond
        ``RetrievalPort.retrieve()``'s own query-time exclusion (WP-60):
        an expired record excluded from queries but never actually
        deleted still occupies real disk space forever. This method is
        that missing deletion -- a pinned record (``expires_at is
        None``) is never eligible, matching
        :meth:`~jarvis.domain.memory.MemoryRecord.is_expired`'s own
        rule exactly.

        Returns:
            The number of records actually deleted. ``0`` if nothing
            was expired -- not an error.
        """
        ...

    def update_value(self, identifier: str, value: Tainted[object]) -> None:
        """Replace the value at ``identifier`` in place -- an update, not a new record (WP-107).

        The one real gap ``write()``/``pin()``/``forget()`` left open:
        every existing write path only ever inserts a new row (a fresh
        identifier) or acts on an identifier's own metadata
        (``expires_at``, deletion) -- nothing could mutate a record's
        own stored *value* without discarding its identity. A real
        ``Task``'s own status needs exactly this: the same task id,
        repeatedly updated in place, not a new record per status
        transition. ``identifier`` itself, ``written_at``, and
        ``expires_at`` are all left untouched -- only the value (and
        its own re-derived text/embedding) changes.

        No authorization happens inside this method, matching
        :meth:`write`'s own identical contract -- a composition root
        resolves the real ``Effect``/``Decision`` before ever calling
        this.

        Args:
            identifier: The real, existing record's identifier to update.
            value: The real, new value to persist at that identifier,
                with its own real provenance -- never re-using the
                original record's stale provenance automatically; a
                caller updating a task's status supplies a fresh,
                correctly-classified value each time.

        Raises:
            MemoryRecordNotFoundError: If ``identifier`` does not
                match a real, currently-stored record.
        """
        ...

    def compare_and_update_value(
        self, identifier: str, expected_value: object, value: Tainted[object]
    ) -> bool:
        """Atomically replace ``identifier``'s value iff current == ``expected_value`` (WP-120).

        The real, process-safe compare-and-swap primitive
        :meth:`update_value` deliberately does not provide -- that
        method is a blind, unconditional overwrite, which is exactly
        right for a caller that already knows it is the sole writer
        (most of this codebase), but is unsafe for a caller that needs
        to detect "did I win a race against another writer," such as
        two independent processes both trying to claim the same
        persisted task for execution.

        A real, total operation -- never raises to signal a lost race:
        returns ``False``, not an exception, if ``identifier`` does
        not match a real, currently-stored record, *or* if it does but
        its current value does not equal ``expected_value`` (another
        writer already changed it since the caller last read it). Only
        a genuine I/O failure of the underlying store raises.

        No authorization happens inside this method, matching
        :meth:`update_value`'s own identical contract.

        Args:
            identifier: The real, existing record's identifier to
                conditionally update.
            expected_value: The value the caller believes is currently
                stored at ``identifier`` -- typically whatever the
                caller itself read moments earlier. Compared by value
                equality (``==``), not identity, and not against the
                record's own provenance (this primitive conditions
                only on the stored *value*).
            value: The real, new value to persist at ``identifier`` if
                the comparison succeeds, with its own real provenance
                -- as :meth:`update_value`.

        Returns:
            ``True`` if the comparison matched and the swap was
            performed; ``False`` if it did not (lost the race, or
            ``identifier`` does not exist) -- the store is left
            completely unchanged in that case.
        """
        ...

    def forget(self, identifier: str) -> None:
        """Permanently delete the record at ``identifier`` from the real store.

        A real deletion, not marking-for-expiry: once this returns,
        the record is gone and unreachable by any later
        ``RetrievalPort.retrieve()`` call, the same bar
        :meth:`sweep_expired` holds itself to. Deletes a pinned record
        too -- pinning protects against *automatic* TTL expiry
        (ADR-0051), not against an explicit, directly-targeted forget.

        Raises:
            MemoryRecordNotFoundError: If ``identifier`` does not
                match a real, currently-stored record.
        """
        ...

    def backup(self, destination_path: str) -> None:
        """Write a real, complete, live-safe copy of the store to ``destination_path``.

        Uses SQLite's own online-backup mechanism (ADR-0061), not a
        raw file copy -- safe to call while the store is open and in
        use, producing a consistent snapshot rather than risking a
        torn, mid-write copy.

        Args:
            destination_path: Where the copy is written. Overwritten
                if it already exists, matching :meth:`restore`'s own
                "replace, not merge" shape in the other direction.
        """
        ...

    def restore(self, source_path: str) -> None:
        """Replace this store's entire real content with ``source_path``'s.

        Not a merge: whatever the live store holds that ``source_path``
        does not is gone once this returns -- the same "no built-in
        undo" finality :meth:`forget` already has, at the scale of the
        whole store (ADR-0061).

        Args:
            source_path: A real, previously-created backup file (see
                :meth:`backup`).

        Raises:
            FileNotFoundError: If ``source_path`` does not exist.
        """
        ...

    def wipe(self) -> int:
        """Permanently delete every real record currently in the store.

        The real, single-command "wipe everything" mechanism (Phase
        10, 10-phase combined pass) -- ``backup()`` already covers the
        real "export my data first" half of this story (a real,
        complete, portable copy); this method is the other half,
        rather than requiring a caller to restore from an empty file
        to achieve the same real effect. No undo -- the same "no
        built-in recovery" finality :meth:`restore` already has, at
        the scale of the whole store.

        Returns:
            The number of records actually deleted. ``0`` if the store
            was already empty -- not an error.
        """
        ...
