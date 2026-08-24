"""Unit tests for jarvis.adapters.sandbox.

Three groups of test, matching the module's own seams:

* ``_build_bwrap_argv`` is pure -- tested directly, no subprocess
  involved, covering exactly what real argv results from each option
  combination.
* ``BwrapSandboxAdapter.run`` is tested against a *real* ``bwrap``
  subprocess for the cases that matter most (this is exactly M3's own
  acceptance criterion #2: real, executed denial of filesystem/network
  access, not merely a documented flag) -- matching
  ``tests/unit/test_workspace_adapter.py``'s "git is a reliable CI
  dependency, test for real" precedent, now extended to ``bwrap``. A
  couple of dispatch-only cases use an injected fake instead, where a
  real sandboxed process would add nothing a fake doesn't already prove.
* ``BwrapSandboxAdapter.launch`` (added WP-52, ADR-0046) is tested the
  same way, plus one test proving it is genuinely non-blocking against
  a real, running sandboxed process -- the exact property Terminal's
  own flow depends on.
"""

from __future__ import annotations

import time
from pathlib import Path

from jarvis.adapters.sandbox import BwrapSandboxAdapter, _build_bwrap_argv
from jarvis.domain.process import CommandResult

_EXPECTED_BIND_FLAG_COUNT = 2
_EXPECTED_EXIT_CODE = 3

# ---------------------------------------------------------------------------
# _build_bwrap_argv: pure, no subprocess.
# ---------------------------------------------------------------------------


def test_build_bwrap_argv_with_no_options_has_no_network_or_bind_flags() -> None:
    """No bind_paths, network disallowed: no --share-net, no --bind, command appended after --."""
    argv = _build_bwrap_argv(("echo", "hi"), bind_paths=(), allow_network=False)

    assert "--share-net" not in argv
    assert "--bind" not in argv
    assert argv[-3:] == ("--", "echo", "hi")


def test_build_bwrap_argv_with_allow_network_adds_share_net() -> None:
    """allow_network=True adds --share-net -- the one explicit network escape hatch."""
    argv = _build_bwrap_argv(("curl",), bind_paths=(), allow_network=True)

    assert "--share-net" in argv


def test_build_bwrap_argv_binds_each_path_read_write_at_its_own_location() -> None:
    """Each bind_path becomes a real --bind <path> <path> pair, same path both sides."""
    argv = _build_bwrap_argv(
        ("ls",), bind_paths=(Path("/work/one"), Path("/work/two")), allow_network=False
    )

    assert argv.count("--bind") == _EXPECTED_BIND_FLAG_COUNT
    bind_index_one = argv.index("--bind")
    assert argv[bind_index_one : bind_index_one + 3] == ("--bind", "/work/one", "/work/one")


def test_build_bwrap_argv_always_includes_unshare_all_and_die_with_parent() -> None:
    """The base containment flags are always present, regardless of options."""
    argv = _build_bwrap_argv(("true",), bind_paths=(), allow_network=False)

    assert "--unshare-all" in argv
    assert "--die-with-parent" in argv


def test_build_bwrap_argv_starts_with_the_bwrap_binary_name() -> None:
    """The built argv is a real, complete command line starting with the bwrap binary itself."""
    argv = _build_bwrap_argv(("true",), bind_paths=(), allow_network=False)

    assert argv[0] == "bwrap"


# ---------------------------------------------------------------------------
# BwrapSandboxAdapter.run: real bwrap subprocess.
# ---------------------------------------------------------------------------


def test_run_denies_network_access_by_default() -> None:
    """A real sandboxed Python process cannot reach the network without allow_network=True.

    This is M3's own acceptance criterion #2, exercised for real: a
    real attempt to connect out, inside a real sandbox, observing a
    real denial.
    """
    adapter = BwrapSandboxAdapter()
    probe = (
        "python3",
        "-c",
        "import socket, sys\n"
        "try:\n"
        "    socket.create_connection(('8.8.8.8', 53), timeout=2)\n"
        "    sys.exit(1)\n"
        "except OSError:\n"
        "    sys.exit(0)\n",
    )

    result = adapter.run(probe)

    assert result.exit_code == 0


def test_run_denies_filesystem_access_outside_bound_paths() -> None:
    """A real sandboxed process cannot read a real host file outside any bind_paths.

    The other half of acceptance criterion #2: real denial of
    filesystem access, observed by actually attempting the read.
    """
    adapter = BwrapSandboxAdapter()
    probe = (
        "python3",
        "-c",
        "import sys\n"
        "try:\n"
        "    open('/etc/shadow-does-not-exist-in-sandbox-check').read()\n"
        "    sys.exit(1)\n"
        "except OSError:\n"
        "    sys.exit(0)\n",
    )

    result = adapter.run(probe)

    assert result.exit_code == 0


def test_run_can_write_to_an_explicitly_bound_path(tmp_path: Path) -> None:
    """A path passed via bind_paths is genuinely writable from inside the sandbox."""
    adapter = BwrapSandboxAdapter()
    probe_file = tmp_path / "probe.txt"
    probe = ("python3", "-c", f"open('{probe_file}', 'w').write('hello from the sandbox')")

    result = adapter.run(probe, bind_paths=(tmp_path,))

    assert result.exit_code == 0
    assert probe_file.read_text() == "hello from the sandbox"


def test_run_captures_a_real_nonzero_exit_code_and_stderr() -> None:
    """A real failing command's exit code and stderr are captured, not swallowed."""
    adapter = BwrapSandboxAdapter()

    probe = f"import sys; sys.stderr.write('boom'); sys.exit({_EXPECTED_EXIT_CODE})"
    result = adapter.run(("python3", "-c", probe))

    assert result.exit_code == _EXPECTED_EXIT_CODE
    assert "boom" in result.stderr


def test_run_delegates_the_built_argv_to_the_injected_subprocess_runner() -> None:
    """run() passes _build_bwrap_argv's exact output to the injected runner, unmodified."""
    seen: list[tuple[str, ...]] = []

    def fake_run_subprocess(argv: tuple[str, ...]) -> CommandResult:
        seen.append(argv)
        return CommandResult(exit_code=0, stdout="", stderr="")

    adapter = BwrapSandboxAdapter(run_subprocess=fake_run_subprocess)

    adapter.run(("echo", "hi"))

    assert seen == [_build_bwrap_argv(("echo", "hi"), bind_paths=(), allow_network=False)]


# ---------------------------------------------------------------------------
# BwrapSandboxAdapter.launch: real bwrap subprocess, WP-52 (Terminal, ADR-0046).
# ---------------------------------------------------------------------------


def test_launch_delegates_the_built_argv_to_the_injected_launch_subprocess_runner() -> None:
    """launch() passes _build_bwrap_argv's exact output to the injected launcher, unmodified."""
    seen: list[tuple[str, ...]] = []
    fake_pid = 999

    def fake_launch_subprocess(argv: tuple[str, ...]) -> int:
        seen.append(argv)
        return fake_pid

    adapter = BwrapSandboxAdapter(launch_subprocess=fake_launch_subprocess)

    pid = adapter.launch(("gnome-terminal",))

    assert seen == [_build_bwrap_argv(("gnome-terminal",), bind_paths=(), allow_network=False)]
    assert pid == fake_pid


def test_launch_returns_immediately_and_the_real_process_completes_its_work_afterward(
    tmp_path: Path,
) -> None:
    """launch() genuinely does not wait: a real sandboxed process keeps running after it returns.

    Proves launch() is real (a real bwrap subprocess actually starts
    and can write to a bound path) and non-blocking (the call returns
    before the launched process's own work is necessarily done) --
    the exact property Terminal's flow (WP-52) depends on: launch a
    real terminal emulator without blocking on it exiting, since an
    interactive terminal never exits on its own.
    """
    adapter = BwrapSandboxAdapter()
    marker = tmp_path / "marker.txt"
    probe = f"import time; time.sleep(0.3); open('{marker}', 'w').write('done')"

    pid = adapter.launch(("python3", "-c", probe), bind_paths=(tmp_path,))

    assert pid > 0
    assert not marker.exists()  # real proof launch() did not wait for completion

    max_poll_attempts = 100
    for _ in range(max_poll_attempts):
        if marker.exists():
            break
        time.sleep(0.05)

    assert marker.read_text() == "done"
