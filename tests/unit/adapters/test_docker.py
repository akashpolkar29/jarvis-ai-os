"""Unit tests for jarvis.adapters.docker.DockerCliAdapter.

What's faked and why: the actual docker subprocess call
(``run_docker``) is always injected. A real ``docker`` invocation is
never exercised anywhere in this suite, deliberately -- per this run's
own hard-stop rule, no automated test may create, mutate, or consume
real Docker daemon state, not even the read-only
``list_containers`` (see the adapter module's own docstring). These
tests exercise only this adapter's own dispatch logic: which argv gets
built for each method, and how a failed command becomes
DockerCommandFailedError.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.adapters.docker import DockerCliAdapter
from jarvis.ports.docker import DockerCommandFailedError


def test_list_containers_calls_docker_ps_and_splits_lines() -> None:
    """list_containers() calls `ps -a --format {{.Names}}` and splits real, multi-line output."""
    calls: list[tuple[str, ...]] = []

    def fake_run_docker(argv: tuple[str, ...]) -> str:
        calls.append(argv)
        return "web\ndb\ncache"

    adapter = DockerCliAdapter(run_docker=fake_run_docker)

    result = adapter.list_containers()

    assert calls == [("ps", "-a", "--format", "{{.Names}}")]
    assert result == ("web", "db", "cache")


def test_list_containers_returns_empty_tuple_for_no_containers() -> None:
    """Empty stdout (no containers) becomes an empty tuple, not a tuple with one blank string."""
    adapter = DockerCliAdapter(run_docker=lambda _argv: "")

    assert adapter.list_containers() == ()


def test_run_container_calls_docker_run_dash_d_with_the_image() -> None:
    """run_container(image) calls exactly ("run", "-d", image) and returns its real output."""
    calls: list[tuple[str, ...]] = []

    def fake_run_docker(argv: tuple[str, ...]) -> str:
        calls.append(argv)
        return "abc123containeridfromrealdockerrun"

    adapter = DockerCliAdapter(run_docker=fake_run_docker)

    result = adapter.run_container("python:3.12-slim")

    assert calls == [("run", "-d", "python:3.12-slim")]
    assert result == "abc123containeridfromrealdockerrun"


def test_stop_container_calls_docker_stop_with_the_container() -> None:
    """stop_container(container) calls exactly ("stop", container)."""
    calls: list[tuple[str, ...]] = []

    def fake_run_docker(argv: tuple[str, ...]) -> str:
        calls.append(argv)
        return ""

    adapter = DockerCliAdapter(run_docker=fake_run_docker)

    adapter.stop_container("web")

    assert calls == [("stop", "web")]


def test_build_image_calls_docker_build_with_context_and_tag_and_returns_the_tag() -> None:
    """build_image(context_dir, tag) calls ("build", "-t", tag, str(context_dir)), returns tag."""
    calls: list[tuple[str, ...]] = []

    def fake_run_docker(argv: tuple[str, ...]) -> str:
        calls.append(argv)
        return ""

    adapter = DockerCliAdapter(run_docker=fake_run_docker)
    context_dir = Path("/home/user/myproject")

    result = adapter.build_image(context_dir, "myproject:latest")

    assert calls == [("build", "-t", "myproject:latest", "/home/user/myproject")]
    assert result == "myproject:latest"


def test_a_failed_command_propagates_docker_command_failed_error() -> None:
    """A DockerCommandFailedError raised by run_docker propagates unchanged."""

    def failing_run_docker(_argv: tuple[str, ...]) -> str:
        msg = "docker run -d nonexistent-image failed (exit 125): no such image"
        raise DockerCommandFailedError(msg)

    adapter = DockerCliAdapter(run_docker=failing_run_docker)

    with pytest.raises(DockerCommandFailedError):
        adapter.run_container("nonexistent-image")
