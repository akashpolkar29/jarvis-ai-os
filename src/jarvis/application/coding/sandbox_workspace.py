"""WP-73: a real, disposable, SandboxPort-backed workspace copy for dispatch.

ADR-0055's own "Amendment 2026-09-01" confirmed, against the real code,
that ``Dispatcher.run()`` (``application/reasoning/dispatcher.py``)
calls ``WorkspacePort.apply_patch`` internally -- once per candidate,
at every rung, unconditionally -- with no call site a wrapper could
ever intercept before that write happens. The only way to keep a real
target repository untouched during a ``Dispatcher.run()`` call is for
that call to never see the real repository at all.

:func:`make_disposable_workspace` is the real fix: given a real target
repository path, it produces a fresh, disposable filesystem copy --
made via a real, contained ``SandboxPort.run()`` call (ADR-0044, M3,
reused completely unmodified) -- and returns a :class:`DisposableWorkspace`
wrapping whatever real ``WorkspacePort`` its caller's own
``workspace_factory`` builds against that copy (in practice, an
ordinary, unmodified
:class:`~jarvis.adapters.workspace.LocalWorkspaceAdapter`) -- injected,
not constructed here, since this is application-layer code and depends
only on ports, never a concrete adapter (see :func:`make_disposable_workspace`'s
own docstring). Whatever constructs a ``Dispatcher.run()`` call (the
future WP-71 coding-loop wrapper) hands this copy's own ``WorkspacePort``
to whichever ``ValidationPort`` it builds -- never the real target
repository's own ``WorkspacePort``.

**What this closes, precisely, and what it does not:**

Closes: the real target repository is never referenced by anything
``Dispatcher.run()`` touches, so its own internal, unconditional
``apply_patch`` calls -- however many, for however many candidates, at
however many rungs -- can only ever modify the disposable copy. This is
proven directly, not inferred, by
``tests/unit/application/coding/test_sandbox_workspace.py``'s own
``test_dispatcher_run_against_a_disposable_workspace_leaves_the_real_repository_untouched``.

Does **not** close: (1) the real, pre-existing gap ADR-0055's own
amendment already named and left open -- multiple candidates tried at
one rung (the real ``SECOND_PROVIDER`` default tries two providers) are
each applied to the *same* workspace in sequence, with no revert
between them, a ``WorkspacePort``/``ValidationPort`` lifecycle question
ADR-0043 already deferred and this module does not resolve, only
contains (the accumulation now happens in a disposable copy, never the
real repository). (2) Sandboxing the candidate's own real *execution* --
the ``git apply`` and ``pytest`` subprocesses ``LocalWorkspaceAdapter``/
``PytestValidator`` run once handed this copy are plain, unsandboxed
subprocesses, exactly as before; only the one-time copy operation
itself runs inside ``bwrap``. Routing ``git apply``/the validator's own
command through ``SandboxPort`` too would mean modifying
``LocalWorkspaceAdapter`` or ``PytestValidator``/``adapters/validation/
_command.py`` -- existing ``ValidationPort``/``WorkspacePort``
implementations ADR-0055's own Decision requires stay unmodified. Real,
separate follow-up if ``docs/threat-model/v0.md``'s "candidate
execution is not sandboxed" gap needs closing for the execution step
itself, not invented speculatively here.

**No real caller yet, deliberately** -- WP-71 (the coding-loop wrapper
that will actually construct a ``Dispatcher.run()`` call against this)
is explicitly out of this work package's own scope.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from jarvis.ports.sandbox import SandboxPort
    from jarvis.ports.workspace import WorkspacePort

    WorkspaceFactory = Callable[[Path], WorkspacePort]

_COPY_DIR_PREFIX = "jarvis-coding-sandbox-"


class DisposableWorkspaceCopyFailedError(Exception):
    """Raised when the real, sandboxed copy of a target repository does not succeed."""


class DisposableWorkspace:
    """A real, disposable filesystem copy of a target repo, plus its own real cleanup.

    A context manager, mirroring ``tempfile.TemporaryDirectory``'s own
    stdlib idiom -- appropriate here because removing a disposable
    filesystem copy is implementation-internal resource management, not
    a policy-relevant capability action (unlike, e.g., closing a real
    running browser page, which this project's own precedent -- see
    ``kernel/browser.py``'s ``authorize_and_close_page`` -- correctly
    gates behind real authorization: that precedent applies to tearing
    down a resource a *capability* started, not to an ordinary temp
    directory this module creates and owns for its own internal use).
    """

    def __init__(self, workspace: WorkspacePort, root: Path) -> None:
        """Store the real, already-copied workspace and the disposable root that backs it.

        Args:
            workspace: A real ``WorkspacePort`` (``LocalWorkspaceAdapter``,
                unmodified) already pointed at ``root``.
            root: The real, disposable directory ``workspace`` operates
                on -- removed by :meth:`close`.
        """
        self.workspace = workspace
        self._root = root

    def close(self) -> None:
        """Remove the real, disposable directory this workspace copy occupies.

        Safe to call more than once -- a directory already removed is
        not an error, matching ``shutil.rmtree``'s own ``ignore_errors``
        semantics for exactly that one case.
        """
        shutil.rmtree(self._root, ignore_errors=True)

    def __enter__(self) -> DisposableWorkspace:
        """Return self, for `with make_disposable_workspace(...) as disposable:` usage."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Call :meth:`close` unconditionally on exit, including when the body raised."""
        self.close()


def make_disposable_workspace(
    sandbox: SandboxPort, target_root: Path, workspace_factory: WorkspaceFactory
) -> DisposableWorkspace:
    """Return a real, disposable, SandboxPort-made copy of `target_root` as a WorkspacePort.

    The copy itself runs inside a real, contained ``bwrap`` sandbox
    (``sandbox.run(("cp", "-r", ...), bind_paths=(target_root,
    disposable_root))``) -- real ``SandboxPort`` reuse, unmodified, not
    a new sandboxing mechanism. `target_root` is bound read-write (this
    port's own bind semantics; ``cp`` itself never writes to it) purely
    so the sandboxed ``cp`` process can read it -- nothing under
    ``target_root`` is ever modified by this function.

    Args:
        sandbox: The real ``SandboxPort`` used to run the copy.
        target_root: The real target repository to copy. Never itself
            modified, and never returned -- the whole point of this
            function is that nothing downstream ever sees this path.
        workspace_factory: Builds the real ``WorkspacePort`` this
            function returns, given the fresh disposable copy's root.
            Injected rather than constructed here -- this is
            application-layer code, which depends on ports, never on a
            concrete adapter (``LocalWorkspaceAdapter`` included); the
            real choice of adapter belongs to this function's own
            caller (a composition root), the same "ports here,
            adapters wired in by the caller" shape every other real
            use case in this repo already follows.

    Returns:
        A :class:`DisposableWorkspace` wrapping the ``WorkspacePort``
        `workspace_factory` returns, pointed at the fresh copy.
        Caller-owned: call :meth:`DisposableWorkspace.close` (or use it
        as a context manager) when done.

    Raises:
        DisposableWorkspaceCopyFailedError: If the real, sandboxed
            ``cp`` does not exit cleanly.
    """
    disposable_root = Path(tempfile.mkdtemp(prefix=_COPY_DIR_PREFIX))
    result = sandbox.run(
        ("cp", "-r", f"{target_root}/.", str(disposable_root)),
        bind_paths=(target_root, disposable_root),
    )
    if result.exit_code != 0:
        shutil.rmtree(disposable_root, ignore_errors=True)
        msg = (
            f"Could not create a disposable sandboxed copy of {target_root} "
            f"(cp exited {result.exit_code}): {result.stderr}"
        )
        raise DisposableWorkspaceCopyFailedError(msg)
    workspace = workspace_factory(disposable_root)
    return DisposableWorkspace(workspace, disposable_root)
