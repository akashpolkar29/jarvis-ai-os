"""The composition root for fs.read_file: reading a real, scope-bounded local file.

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
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.file_system import LocalFileSystemAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.capabilities import READ_FILE_CAPABILITY_ID, build_default_registry

if TYPE_CHECKING:
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
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

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
