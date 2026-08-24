"""Contract test: adapters must structurally satisfy jarvis.ports.docker's DockerPort."""

from __future__ import annotations

from jarvis.adapters.docker import DockerCliAdapter
from jarvis.ports.docker import DockerPort


def test_docker_cli_adapter_satisfies_docker_port() -> None:
    """DockerCliAdapter is structurally a DockerPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores a callable), so this needs no real Docker daemon.
    """
    adapter = DockerCliAdapter()

    assert isinstance(adapter, DockerPort)


def test_an_object_missing_the_four_methods_does_not_satisfy_docker_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotADockerSource:
        """Deliberately lacks list_containers()/run_container()/stop_container()/build_image()."""

    assert isinstance(NotADockerSource(), DockerPort) is False
