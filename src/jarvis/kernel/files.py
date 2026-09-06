"""The composition root for fs.*: read/list/move/delete real, scope-bounded local files.

**Updated 2026-09-04 (ADR-0060, Proposed)**: :func:`authorize_and_list_dir`,
:func:`authorize_and_move_file`, and :func:`authorize_and_delete_file`
join :func:`authorize_and_read_file` -- the real file-management gap a
charter-completeness re-check found. All four reuse the identical
:func:`_resolve_within_scope` boundary (`allowed_root`, default
``Path.home()``) -- an allowlist, not a denylist of sensitive
subpaths, matching this module's own already-established
"allowlist-over-denylist" posture. `fs.move_file` checks *both*
`source` and `destination` against that same boundary before anything
else happens. See ADR-0060's own Context/Decision for the real,
considered reasoning on why no *additional* protected-path check
(mirroring ADR-0056's `resolve_protected_patterns`) was added for
`fs.move_file`/`fs.delete_file` -- in short: that mechanism's own real
purpose (protecting a coding agent's *target repository* from its own
writes) does not transfer to general file management, and
`fs.delete_file`'s own `Tier.MANUAL_ONLY` floor already gives every
real deletion a live, physical human checkpoint ADR-0056's own
scenario specifically lacks.

:func:`authorize_and_read_file` follows the same composition-root
shape as :func:`~jarvis.kernel.music.authorize_and_run_music_command`:
build the registry (via
:func:`~jarvis.kernel.capabilities.build_default_registry`)/storage/
confirmation/orchestrator pieces, authorize, act only if granted, save
unconditionally via ``try``/``finally``.

Effect and tier: ``fs.read_file`` is registered with
``Effect.EGRESS_LOCAL``, not ``Effect.READ_LOCAL``. Both currently
floor at ``Tier.ALLOW`` in ``_EFFECT_TIER_FLOOR``, so this choice does
not change enforcement today -- it is a semantic one. ``READ_LOCAL``
fits an action that observes local state without exposing content
(e.g. an existence check); this capability's entire purpose is to
extract a file's content out to the user's terminal, which is an
egress even though it never leaves the machine. None of the taxonomy's
CONFIRM-or-higher effects (``WRITE_LOCAL``, ``EXECUTE``,
``EGRESS_SENSITIVE``, ``EGRESS_SECRET``) honestly describe this --
nothing is mutated, no code runs, nothing leaves the machine -- and
ADR-0004 closes the taxonomy to ad hoc extension. So the real
protection here is not the tier: it's the scope check below, which no
confirmation flag can override. One consequence worth stating plainly:
because this lands at ``ALLOW``, there is no "denied for lack of
confirmation" path for an in-scope read, the same as ``ping``.

Scope check: a path is only ever read if
``path.expanduser().resolve()`` falls within ``allowed_root``
(default: the real ``Path.home()``), checked via ``is_relative_to``.
``resolve()`` fully follows symlinks to their real target, so a
symlink inside the allowed root pointing outside it is caught by this
same check -- no separate symlink-specific logic needed. This is a
single coarse boundary, not a denylist of sensitive subpaths
(``.ssh/``, ``.aws/``, etc.) -- consistent with this project's
allowlist-over-denylist posture (ADR-0007's spirit), and a denylist
would create a false sense of completeness. Narrower, sensitivity-aware
scoping is legitimate future work, not built speculatively here.

The scope check runs *before* ``authorize_by_id()`` is ever called --
see :class:`PathOutsideAllowedScopeError` for why, and for the audit
gap this creates.

Provenance: the path argument is ``Provenance.user()`` (typed directly
at the CLI, same as every other capability so far). The file's
*content*, once read, is wrapped as
``Tainted(content, Provenance.external(source=str(resolved_path),
classification=Classification.SENSITIVE))`` -- JARVIS cannot know
whether an arbitrary file under the allowed root is mundane or
originated from an untrusted source before being saved to disk (a
downloaded README, an email attachment), so it is not assumed benign.
``SENSITIVE`` rather than ``SECRET``: ``SECRET`` is this project's term
specifically for credentials/API keys/passwords (unconditional DENY to
any cloud provider); defaulting every file read to that would make the
content unusable by any future consumer for no good reason.  This
tainting has no effect on *this* invocation's own tier -- tier
escalation only reads the *argument's* provenance, computed before the
call executes, never the result's. Nothing downstream consumes this
content yet in this WP; the point is that a future capability that
does inherits correct provenance automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.file_system import LocalFileSystemAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.capabilities import (
    DELETE_FILE_CAPABILITY_ID,
    LIST_DIR_CAPABILITY_ID,
    MOVE_FILE_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from jarvis.domain.file_system import DirEntry
    from jarvis.domain.policy import Decision
    from jarvis.ports.file_system import FileSystemPort


class PathOutsideAllowedScopeError(Exception):
    """Raised when a requested path resolves outside the allowed root.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: this is
    a kernel-level operational rejection, not a domain-raised
    exception, the same reasoning WP-14's port-level exceptions used.
    Raised *before* any :class:`~jarvis.domain.capability.CapabilityInvocation`
    is constructed -- deliberately, per this module's own docstring --
    because the existing taint-escalation formula (exactly one tier
    step per taint) cannot express an unconditional, unconfirmable
    DENY from an ALLOW-floor capability without either raising
    ``fs.read_file``'s base tier to MANUAL_ONLY (disproportionate for
    ordinary in-scope reads) or modifying ``evaluate()``'s escalation
    formula itself (a real change to the frozen WP-04 policy engine,
    requiring its own sign-off, not something to fold into this WP).

    LIMITATION, STATED PLAINLY: because this rejection happens before
    any ``CapabilityInvocation`` is constructed, out-of-scope access
    attempts are NOT recorded in the audit chain -- unlike a granted or
    normally-denied decision, there is no forensic record of who tried
    to read what outside the allowed root. Closing this gap requires
    either extending ``evaluate()``'s escalation formula (a frozen
    WP-04 change) or a separate, out-of-band security-event log,
    neither of which exists yet. This is a real, open gap, not a
    documentation nicety -- flagged explicitly for a future work
    package to close, not forgotten here.
    """


@dataclass(frozen=True)
class FileReadOutcome:
    """The result of one authorize_and_read_file() call.

    Attributes:
        decision: The Decision for this read -- durably appended to
            the chain regardless of outcome (unless the request never
            reached authorization at all; see
            :class:`PathOutsideAllowedScopeError`).
        content: The file's content, tagged with its provenance, if
            the decision was granted and the read succeeded. ``None``
            if denied. A granted-but-failed read (nonexistent path,
            permission denied, etc.) raises rather than returning --
            see the module docstring's failure-mode handling.
    """

    decision: Decision
    content: Tainted[str] | None


def _resolve_within_scope(path: Path, allowed_root: Path) -> Path:
    """Resolve ``path`` and confirm it falls within ``allowed_root``.

    Raises:
        PathOutsideAllowedScopeError: If the resolved path does not.
    """
    resolved = path.expanduser().resolve()
    resolved_root = allowed_root.expanduser().resolve()
    if not resolved.is_relative_to(resolved_root):
        msg = f"{resolved} is outside the allowed root {resolved_root}."
        raise PathOutsideAllowedScopeError(msg)
    return resolved


def authorize_and_read_file(  # noqa: PLR0913 -- one more than music's 5, for allowed_root/file_system
    path: Path,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    allowed_root: Path | None = None,
    file_system: FileSystemPort | None = None,
) -> FileReadOutcome:
    """Wire up the stack, authorize a read of ``path``, and read it only if granted.

    Args:
        path: The file to read. Resolved and scope-checked before
            anything else happens -- see the module docstring.
        physical_confirmation_available: As in
            ``authorize_and_run_music_command`` -- threaded through
            for consistency, though ``fs.read_file``'s ALLOW tier
            means it does not affect the outcome.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        allowed_root: The scope boundary. Defaults to the real
            ``Path.home()``. Overridable for tests, exactly as
            ``AuthorizationOrchestrator``'s confirmation port is (WP-11).
        file_system: The port the file is read through if granted.
            Defaults to a real ``LocalFileSystemAdapter``. Overridable
            for tests.

    Returns:
        A ``FileReadOutcome`` -- see its own docstring.

    Raises:
        PathOutsideAllowedScopeError: If ``path`` resolves outside
            ``allowed_root``. Raised before authorization runs; see
            its own docstring for the audit-trail gap this creates.
        FileNotFoundError: If a granted read's path does not exist.
        IsADirectoryError: If a granted read's path is a directory.
        PermissionError: If a granted read's path cannot be read.
        UnicodeDecodeError: If a granted read's path is not valid UTF-8.
    """
    resolved_path = _resolve_within_scope(path, allowed_root or Path.home())

    registry = build_default_registry()

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, registry, confirmation=confirmation, clock=SystemClockAdapter()
    )

    decision = orchestrator.authorize_by_id(
        READ_FILE_CAPABILITY_ID,
        Tainted({"path": str(resolved_path)}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    content: Tainted[str] | None = None
    try:
        # decision.granted is always True here: evaluate() hardcodes
        # granted=True for Tier.ALLOW, which fs.read_file always is.
        # Kept as an explicit check (not asserted away) for structural
        # consistency with authorize_and_run_music_command and in case
        # a future change raises this capability's tier.
        if decision.granted:
            reader = file_system if file_system is not None else LocalFileSystemAdapter()
            raw_content = reader.read_text(resolved_path)
            content = Tainted(
                raw_content,
                Provenance.external(
                    source=str(resolved_path),
                    classification=Classification.SENSITIVE,
                ),
            )
    finally:
        storage.save(chain)

    return FileReadOutcome(decision=decision, content=content)


@dataclass(frozen=True)
class DirListOutcome:
    """The result of one authorize_and_list_dir() call.

    Attributes:
        decision: The Decision for this listing -- durably appended to
            the chain regardless of outcome (unless the request never
            reached authorization at all; see
            :class:`PathOutsideAllowedScopeError`).
        entries: Every real entry directly inside the listed
            directory, tagged with its own provenance, if the decision
            was granted. ``None`` if denied.
    """

    decision: Decision
    entries: tuple[Tainted[DirEntry], ...] | None


def authorize_and_list_dir(  # noqa: PLR0913 -- one more than music's 5, for allowed_root/file_system
    path: Path,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    allowed_root: Path | None = None,
    file_system: FileSystemPort | None = None,
) -> DirListOutcome:
    """Wire up the stack, authorize listing ``path``, and list it only if granted.

    Mirrors :func:`authorize_and_read_file` exactly -- see its own
    docstring for the shared scope-check/argument/return shape.

    Args:
        path: The directory to list. Resolved and scope-checked before
            anything else happens.
        physical_confirmation_available: As above -- threaded through
            for consistency, though ``fs.list_dir``'s ALLOW tier means
            it does not affect the outcome.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        allowed_root: The scope boundary. Defaults to the real
            ``Path.home()``. Overridable for tests.
        file_system: The port the directory is listed through if
            granted. Defaults to a real ``LocalFileSystemAdapter``.
            Overridable for tests.

    Returns:
        A ``DirListOutcome`` -- see its own docstring.

    Raises:
        PathOutsideAllowedScopeError: If ``path`` resolves outside
            ``allowed_root``. Raised before authorization runs.
        FileNotFoundError: If a granted listing's path does not exist.
        NotADirectoryError: If a granted listing's path is not a directory.
        PermissionError: If a granted listing's path cannot be listed.
    """
    resolved_path = _resolve_within_scope(path, allowed_root or Path.home())

    registry = build_default_registry()

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, registry, confirmation=confirmation, clock=SystemClockAdapter()
    )

    decision = orchestrator.authorize_by_id(
        LIST_DIR_CAPABILITY_ID,
        Tainted({"path": str(resolved_path)}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    entries: tuple[Tainted[DirEntry], ...] | None = None
    try:
        if decision.granted:
            lister = file_system if file_system is not None else LocalFileSystemAdapter()
            raw_entries = lister.list_dir(resolved_path)
            entries = tuple(
                Tainted(
                    entry,
                    Provenance.external(
                        source=str(resolved_path / entry.name),
                        classification=Classification.SENSITIVE,
                    ),
                )
                for entry in raw_entries
            )
    finally:
        storage.save(chain)

    return DirListOutcome(decision=decision, entries=entries)


def authorize_and_move_file(  # noqa: PLR0913 -- one per composition-function pass-through
    source: Path,
    destination: Path,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    allowed_root: Path | None = None,
    file_system: FileSystemPort | None = None,
) -> Decision:
    """Wire up the stack, authorize moving ``source`` to ``destination``, and move only if granted.

    Args:
        source: The real file or directory to move. Resolved and
            scope-checked before anything else happens.
        destination: Where to move it to. Resolved and scope-checked
            the identical way -- a real move must stay entirely within
            ``allowed_root`` at both ends, not just at the source.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        allowed_root: The scope boundary. Defaults to the real
            ``Path.home()``. Overridable for tests.
        file_system: The port the move is performed through if
            granted. Defaults to a real ``LocalFileSystemAdapter``.
            Overridable for tests.

    Returns:
        The real ``Decision`` -- already durably appended to the
        injected ``AuditChain`` by the time this returns. The real
        move happens only if ``granted``.

    Raises:
        PathOutsideAllowedScopeError: If ``source`` or ``destination``
            resolves outside ``allowed_root``. Raised before
            authorization runs, for either path.
        FileNotFoundError: If a granted move's source does not exist.
        PermissionError: If a granted move cannot access either path.
        OSError: For other real, underlying filesystem failures.
    """
    resolved_root = allowed_root or Path.home()
    resolved_source = _resolve_within_scope(source, resolved_root)
    resolved_destination = _resolve_within_scope(destination, resolved_root)

    registry = build_default_registry()

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, registry, confirmation=confirmation, clock=SystemClockAdapter()
    )

    decision = orchestrator.authorize_by_id(
        MOVE_FILE_CAPABILITY_ID,
        Tainted(
            {"source": str(resolved_source), "destination": str(resolved_destination)},
            Provenance.user(),
        ),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            mover = file_system if file_system is not None else LocalFileSystemAdapter()
            mover.move(resolved_source, resolved_destination)
    finally:
        storage.save(chain)

    return decision


def authorize_and_delete_file(  # noqa: PLR0913 -- one more than music's 5, for allowed_root/file_system
    path: Path,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    allowed_root: Path | None = None,
    file_system: FileSystemPort | None = None,
) -> Decision:
    """Wire up the stack, authorize permanently deleting ``path``, and delete only if granted.

    ``fs.delete_file`` floors at ``Tier.MANUAL_ONLY`` (ADR-0060) --
    never satisfiable by remote confirmation alone, mirroring
    ``git.force_push``/``memory.forget``.

    Args:
        path: The real file to delete. Resolved and scope-checked
            before anything else happens. Files only -- see
            ``ports/file_system.py``'s own module docstring for why
            recursive directory deletion is out of scope.
        physical_confirmation_available: Whether a human is physically
            present -- the only channel that can grant this call.
        remote_confirmation_available: Threaded through for
            consistency; never sufficient alone for this capability.
        chain_path: Where the audit chain is persisted.
        allowed_root: The scope boundary. Defaults to the real
            ``Path.home()``. Overridable for tests.
        file_system: The port the deletion is performed through if
            granted. Defaults to a real ``LocalFileSystemAdapter``.
            Overridable for tests.

    Returns:
        The real ``Decision`` -- already durably appended to the
        injected ``AuditChain`` by the time this returns. The real,
        permanent deletion happens only if ``granted``.

    Raises:
        PathOutsideAllowedScopeError: If ``path`` resolves outside
            ``allowed_root``. Raised before authorization runs.
        FileNotFoundError: If a granted deletion's path does not exist.
        IsADirectoryError: If a granted deletion's path is a directory.
        PermissionError: If a granted deletion's path cannot be deleted.
    """
    resolved_path = _resolve_within_scope(path, allowed_root or Path.home())

    registry = build_default_registry()

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, registry, confirmation=confirmation, clock=SystemClockAdapter()
    )

    decision = orchestrator.authorize_by_id(
        DELETE_FILE_CAPABILITY_ID,
        Tainted({"path": str(resolved_path)}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            deleter = file_system if file_system is not None else LocalFileSystemAdapter()
            deleter.delete(resolved_path)
    finally:
        storage.save(chain)

    return decision
