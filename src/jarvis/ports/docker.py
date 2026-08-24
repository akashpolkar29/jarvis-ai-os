"""The Docker port: the seam between an authorized command and the real Docker CLI.

:class:`DockerPort` is the one abstract boundary between "some real,
locally installed Docker daemon" and the four typed container/image
capabilities M3 registers (``docker.list_containers``,
``docker.run_container``, ``docker.stop_container``,
``docker.build_image``). Every method maps to exactly one, non-shell-
interpolated ``docker`` CLI invocation -- never a free-text command
string -- matching the subprocess-with-a-fixed-argv pattern
``WorkspacePort``'s real ``git apply`` call (ADR-0043) and every M2
validator adapter already use.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.docker`` for the concrete
CLI-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


class DockerCommandFailedError(Exception):
    """Raised when a real ``docker`` CLI invocation exits non-zero.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter-level, real-world operational condition (the daemon isn't
    running, the image doesn't exist, the build failed), not a
    domain-level security/policy concern -- matching
    :class:`~jarvis.ports.workspace.PatchApplicationFailedError`'s own
    reasoning.
    """


@runtime_checkable
class DockerPort(Protocol):
    """A real, locally installed Docker daemon, reachable via fixed, typed CLI invocations."""

    def list_containers(self) -> tuple[str, ...]:
        """Return the names of every container (running or stopped), read-only.

        Raises:
            DockerCommandFailedError: If the underlying ``docker ps``
                call fails.
        """
        ...

    def run_container(self, image: str) -> str:
        """Run a new detached container from ``image`` and return its real container id.

        Args:
            image: The image reference to run (e.g. ``"python:3.12-slim"``).

        Raises:
            DockerCommandFailedError: If the underlying ``docker run``
                call fails.
        """
        ...

    def stop_container(self, container: str) -> None:
        """Stop the running container named or identified by ``container``.

        Args:
            container: The container's name or id.

        Raises:
            DockerCommandFailedError: If the underlying ``docker stop``
                call fails.
        """
        ...

    def build_image(self, context_dir: Path, tag: str) -> str:
        """Build an image from the Dockerfile in ``context_dir``, tagged ``tag``.

        Args:
            context_dir: The real build context directory -- must
                contain a ``Dockerfile``, the same requirement
                ``docker build`` itself has.
            tag: The tag to apply to the built image.

        Returns:
            ``tag``, unchanged -- the same identifier a caller can use
            to reference the image afterward (``docker build`` itself
            prints build log output, not a separate identifier worth
            parsing out here).

        Raises:
            DockerCommandFailedError: If the underlying ``docker build``
                call fails.
        """
        ...
