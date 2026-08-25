"""Adapters implementing jarvis.ports.docker.DockerPort.

:class:`DockerCliAdapter` runs real ``docker`` CLI subprocess calls,
one fixed, non-shell-interpolated invocation per method -- the same
pattern ``adapters/workspace.py``'s real ``git apply`` call already
established. No ``SandboxPort`` wrapping (ADR-0044): a ``docker`` CLI
invocation is already a bounded, typed subprocess call, not free text,
so the containment ``SandboxPort`` exists for is not a gap here the
way Terminal's genuinely open-ended text injection is.

Not exercised for real during WP-45's own unattended implementation
pass, deliberately, per that run's own hard-stop rule:
``docker.run_container``/``stop_container``/``build_image`` can
create, mutate, or consume real host resources via a real Docker
daemon -- exactly the class of action that run's rules said not to
execute automatically, and this remains true today -- these three
stay deliberately unexercised, tested only via an injected fake, real
verification deliberately deferred to a session with the user present
to supervise it directly (matching M2's own ``local``/``family_a``
live-verification deferral pattern), not silently assumed covered by
unit tests alone.

**`docker.list_containers` (read-only) has since been live-verified
for real**, in a later, explicitly-scoped M3 live-verification pass:
``authorize_and_list_docker_containers()``, called for real against
this machine's real, active Docker daemon, returned ``granted=True``,
``Tier.ALLOW``, and real container names -- see
``docs/threat-model/v0.md``'s "Milestone 3 additions" section
("Docker: real, read-only call verified"). Automated tests still
exercise this adapter's own dispatch logic only via an injected fake,
matching the read/write distinction this module already draws --
``list_containers``'s real correctness is now proven live, not merely
asserted; the three DESTRUCTIVE-tier methods' is not, correctly.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from jarvis.ports.docker import DockerCommandFailedError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    RunDockerFn = Callable[[tuple[str, ...]], str]


def _run_docker(argv: tuple[str, ...]) -> str:
    """Run a real ``docker`` subprocess call and return its stdout, stripped.

    The one real, untested-by-design-by-CI piece of this module --
    requires a real, running Docker daemon (see the module docstring
    for which real calls have and haven't exercised it for real).

    Raises:
        DockerCommandFailedError: If the command exits non-zero.
    """
    # "docker" resolved via PATH deliberately, matching adapters/workspace.py's identical
    # "git" precedent; argv beyond it is a fixed subcommand plus typed arguments, never
    # caller-supplied shell text.
    result = subprocess.run(  # noqa: S603
        ("docker", *argv),  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"docker {' '.join(argv)} failed (exit {result.returncode}): {result.stderr}"
        raise DockerCommandFailedError(msg)
    return result.stdout.strip()


class DockerCliAdapter:
    """Runs real, typed ``docker`` CLI subprocess calls -- no shell interpolation, ever."""

    def __init__(self, run_docker: RunDockerFn | None = None) -> None:
        """Store the function used to actually run a docker subcommand. No I/O at construction.

        Args:
            run_docker: Given a docker subcommand argv (without the
                leading ``"docker"``), runs it and returns stdout.
                Defaults to a real subprocess call. Overridable for
                tests (see the module docstring for which real calls
                have and haven't exercised the real default).
        """
        self._run_docker: RunDockerFn = run_docker or _run_docker

    def list_containers(self) -> tuple[str, ...]:
        """List every container's name via a real ``docker ps -a`` call."""
        output = self._run_docker(("ps", "-a", "--format", "{{.Names}}"))
        return tuple(output.splitlines()) if output else ()

    def run_container(self, image: str) -> str:
        """Run a new detached container from ``image`` via a real ``docker run -d`` call."""
        return self._run_docker(("run", "-d", image))

    def stop_container(self, container: str) -> None:
        """Stop ``container`` via a real ``docker stop`` call."""
        self._run_docker(("stop", container))

    def build_image(self, context_dir: Path, tag: str) -> str:
        """Build an image from ``context_dir``, tagged ``tag``, via a real ``docker build`` call."""
        self._run_docker(("build", "-t", tag, str(context_dir)))
        return tag
