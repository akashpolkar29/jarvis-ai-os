"""Adapters implementing jarvis.ports.docker.DockerPort.

:class:`DockerCliAdapter` runs real ``docker`` CLI subprocess calls,
one fixed, non-shell-interpolated invocation per method -- the same
pattern ``adapters/workspace.py``'s real ``git apply`` call already
established. No ``SandboxPort`` wrapping (ADR-0044): a ``docker`` CLI
invocation is already a bounded, typed subprocess call, not free text,
so the containment ``SandboxPort`` exists for is not a gap here the
way Terminal's genuinely open-ended text injection is.

**Never exercised for real during this pass, deliberately, per this
run's own hard-stop rule**: ``docker.run_container``/
``stop_container``/``build_image`` can create, mutate, or consume real
host resources via a real Docker daemon -- exactly the class of action
this run's rules say not to execute automatically. Even
``docker.list_containers`` (read-only) is tested only via an injected
fake here, for consistency, and because this run has no way to
distinguish "safe to run for real" from "not" without a human
confirming the target Docker daemon/environment is actually a
disposable one. Live verification against a real Docker daemon is
deferred to when the user is present to supervise it directly
(matching M2's own ``local``/``family_a`` live-verification deferral
pattern) -- a real, tracked gap, not silently assumed covered by these
unit tests.
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

    The one real, untested-by-design piece of this module -- requires
    a real, running Docker daemon this pass never invokes (see the
    module docstring).

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
                tests -- this run never exercises the real default
                (see the module docstring).
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
