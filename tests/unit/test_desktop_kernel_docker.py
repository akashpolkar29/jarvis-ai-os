"""Unit tests for jarvis.kernel.desktop's Docker authorize_and_* composition-root functions.

What's mocked and why: a small stub DockerPort (with call tracking) is
injected in place of a real DockerCliAdapter -- per this run's own
hard-stop rule, no automated test may touch a real Docker daemon, not
even the read-only list_containers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.desktop import (
    authorize_and_build_docker_image,
    authorize_and_list_docker_containers,
    authorize_and_run_docker_container,
    authorize_and_stop_docker_container,
)
from jarvis.ports.docker import DockerCommandFailedError

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1


class _StubDocker:
    """A DockerPort test double that records every call, in order."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        """Start with an empty call log; optionally raise DockerCommandFailedError on any call."""
        self.calls: list[tuple[str, ...]] = []
        self._raise_on_call = raise_on_call

    def _record(self, *args: str) -> None:
        self.calls.append(args)
        if self._raise_on_call:
            msg = "docker command failed"
            raise DockerCommandFailedError(msg)

    def list_containers(self) -> tuple[str, ...]:
        """Record a list_containers() call and return fixed real-shaped output."""
        self._record("list_containers")
        return ("web", "db")

    def run_container(self, image: str) -> str:
        """Record a run_container() call and return a fake container id."""
        self._record("run_container", image)
        return "fakecontainerid"

    def stop_container(self, container: str) -> None:
        """Record a stop_container() call."""
        self._record("stop_container", container)

    def build_image(self, context_dir: Path, tag: str) -> str:
        """Record a build_image() call and return the tag."""
        self._record("build_image", str(context_dir), tag)
        return tag


def test_list_containers_is_always_granted_and_returns_real_output(tmp_path: Path) -> None:
    """docker.list_containers floors ALLOW -- granted unconditionally, output returned."""
    docker = _StubDocker()

    outcome = authorize_and_list_docker_containers(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert outcome.decision.granted is True
    assert outcome.containers == ("web", "db")
    assert docker.calls == [("list_containers",)]


def test_granted_run_container_call_runs_the_image(tmp_path: Path) -> None:
    """A granted call (physical confirmation) runs the given image."""
    docker = _StubDocker()

    decision = authorize_and_run_docker_container(
        "python:3.12-slim",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is True
    assert docker.calls == [("run_container", "python:3.12-slim")]


def test_denied_run_container_call_never_touches_docker(tmp_path: Path) -> None:
    """No physical confirmation: MANUAL_ONLY-tier docker.run_container is denied, untouched."""
    docker = _StubDocker()

    decision = authorize_and_run_docker_container(
        "python:3.12-slim",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is False
    assert docker.calls == []


def test_remote_confirmation_alone_cannot_grant_run_container(tmp_path: Path) -> None:
    """Unlike stop_container's CONFIRM tier, run_container needs physical presence."""
    docker = _StubDocker()

    decision = authorize_and_run_docker_container(
        "python:3.12-slim",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is False
    assert docker.calls == []


def test_granted_stop_container_call_stops_the_container(tmp_path: Path) -> None:
    """A granted call (physical or remote confirmation, CONFIRM tier) stops the container."""
    docker = _StubDocker()

    decision = authorize_and_stop_docker_container(
        "web",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is True
    assert docker.calls == [("stop_container", "web")]


def test_denied_stop_container_call_never_touches_docker(tmp_path: Path) -> None:
    """No confirmation at all: CONFIRM-tier docker.stop_container is denied, untouched."""
    docker = _StubDocker()

    decision = authorize_and_stop_docker_container(
        "web",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is False
    assert docker.calls == []


def test_granted_build_image_call_builds_with_context_and_tag(tmp_path: Path) -> None:
    """A granted call (physical confirmation) builds the given context dir/tag."""
    docker = _StubDocker()
    context_dir = tmp_path / "myproject"

    decision = authorize_and_build_docker_image(
        context_dir,
        "myproject:latest",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is True
    assert docker.calls == [("build_image", str(context_dir), "myproject:latest")]


def test_denied_build_image_call_never_touches_docker(tmp_path: Path) -> None:
    """No physical confirmation: MANUAL_ONLY-tier docker.build_image is denied, untouched."""
    docker = _StubDocker()

    decision = authorize_and_build_docker_image(
        tmp_path / "myproject",
        "myproject:latest",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        docker=docker,
    )

    assert decision.granted is False
    assert docker.calls == []


def test_docker_audit_record_is_saved_even_when_run_container_raises(tmp_path: Path) -> None:
    """A granted decision is persisted even if the subsequent real-world action fails."""
    chain_path = tmp_path / "audit_chain.json"
    docker = _StubDocker(raise_on_call=True)

    with pytest.raises(DockerCommandFailedError):
        authorize_and_run_docker_container(
            "python:3.12-slim",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            docker=docker,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True
