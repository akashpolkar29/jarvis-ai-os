"""Real end-to-end scenario tests: multiple real capabilities composed together.

Every capability in this codebase has been tested in isolation. None
have been proven to compose correctly in a realistic sequence a real
user would actually run -- this file closes that gap, chaining
genuinely-existing capabilities via real adapters, asserting on real,
observable outcomes at each step, not just "no exception was raised".

Grounded in this project's own charter examples ("continue yesterday's
project"): read a real file, remember something about it, recall it
back later, and use that recalled context for a real follow-on task
against a real, disposable local repository -- exactly the kind of
session a real user would run.

Memory's own embedding step uses a fake, deterministic `EmbeddingPort`
throughout, matching this codebase's own established "only the true
external-I/O edge is faked" convention (`test_coding_kernel.py`'s own
docstring) -- the real vector-similarity model is a separate, already
live-verified concern (`docs/architecture/m4-benchmark-results.md`),
not what these tests exist to prove. `coding.run_task` uses the real,
local Ollama default where reachable, skipped honestly where it is
not (mirroring every other real-Ollama test in this codebase) -- since
a tiny local model's own patch quality is not a fair bar (this
project's own `adapters/reasoning/local.py` docstring says so
directly), these tests assert on real, structural outcomes (the call
completes, a real decision is granted, real context reached the real
prompt) rather than on the model producing a working patch.
"""

from __future__ import annotations

import subprocess
import urllib.request
from typing import TYPE_CHECKING, ClassVar

import pytest

from jarvis.kernel.coding import authorize_and_run_coding_task
from jarvis.kernel.desktop import authorize_and_commit_git, authorize_and_get_git_status
from jarvis.kernel.files import authorize_and_read_file
from jarvis.kernel.memory import authorize_and_recall, authorize_and_remember

if TYPE_CHECKING:
    from pathlib import Path


def _real_ollama_server_is_reachable() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    except OSError:
        return False
    return True


class _FakeEmbeddingPort:
    """Maps known real strings to hand-picked vectors so similarity ordering is fully controlled.

    Mirrors tests/unit/adapters/test_memory.py's own _FakeEmbeddingPort
    exactly -- the same, already-established fake used everywhere else
    in this codebase for memory tests.
    """

    _VECTORS: ClassVar[dict[str, tuple[float, ...]]] = {
        "this project uses a hash-chained audit log for tamper evidence": (1.0, 0.0),
        "audit log tamper evidence question": (0.9, 0.1),
        "unrelated query about spotify playback": (0.0, 1.0),
    }

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._VECTORS.get(text, (0.0, 0.0)) for text in texts)


def _init_real_disposable_git_repo(repo_dir: Path) -> None:
    """A real `git init` + one real commit, so authorize_and_get_git_status has something to see."""
    subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "Test"], check=True)
    (repo_dir / "README.md").write_text("A real, disposable test repository.\n")
    subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "commit", "-q", "-m", "initial commit"], check=True)


async def test_read_a_real_file_remember_it_and_recall_it_back(tmp_path: Path) -> None:
    """fs.read_file -> memory.write -> memory.retrieve, real data flowing through every step.

    Composes three real capabilities: the real file's own real content
    (not a hand-typed string) becomes the text handed to
    authorize_and_remember, and the recalled record's own content is
    asserted to match the real file's content exactly -- proving real
    data actually flows from one capability's real output into the
    next capability's real input, not just that each call succeeds in
    isolation.
    """
    real_file_content = "This project uses a hash-chained audit log for tamper evidence."
    project_file = tmp_path / "project_notes.py"
    project_file.write_text(f'"""{real_file_content}"""\n')
    database_path = tmp_path / "memory.sqlite3"
    chain_path = tmp_path / "audit_chain.json"

    read_outcome = authorize_and_read_file(
        project_file,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        allowed_root=tmp_path,
    )
    assert read_outcome.decision.granted is True
    assert read_outcome.content is not None
    assert real_file_content in read_outcome.content.value

    write_outcome = authorize_and_remember(
        real_file_content,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert write_outcome.decision.granted is True
    assert write_outcome.identifier is not None

    recall_outcome = authorize_and_recall(
        "audit log tamper evidence question",
        limit=1,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert recall_outcome.decision.granted is True
    assert len(recall_outcome.records) == 1
    assert recall_outcome.records[0].value.value == real_file_content


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, local Ollama server on localhost:11434 -- `ollama serve`.",
)
async def test_recalled_memory_context_feeds_a_real_coding_task_then_git_status_and_commit(
    tmp_path: Path,
) -> None:
    """memory.retrieve's real output feeds coding.run_task's real prompt, then git.status/commit.

    A realistic session shape from this project's own charter
    ("continue yesterday's project"): a memory written earlier is
    recalled and its own real text is woven directly into a new
    coding.run_task's own task description -- real data flowing across
    a third capability boundary, not a contrived, hand-typed one.
    coding.run_task's own real outcome (whether the tiny local model
    produces a passing patch) is not asserted on, per this project's
    own documented "not a fair bar for a 0.5B-parameter model" caveat
    -- only that the real call completes and is genuinely granted.
    git.status/git.commit then run against a real, disposable local
    repository (never the real project repository), proving the
    session can conclude with a real, observable git state change.
    """
    database_path = tmp_path / "memory.sqlite3"
    chain_path = tmp_path / "audit_chain.json"
    repo_dir = tmp_path / "target_repo"
    repo_dir.mkdir()
    _init_real_disposable_git_repo(repo_dir)

    authorize_and_remember(
        "this project uses a hash-chained audit log for tamper evidence",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )

    recall_outcome = authorize_and_recall(
        "audit log tamper evidence question",
        limit=1,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert len(recall_outcome.records) == 1
    recalled_context = recall_outcome.records[0].value.value

    # Deliberately short: a longer, context-laden prompt made the real local
    # model's own SELF_REPAIR rung (DETERMINISTIC_FIX has no real
    # implementation, WP-37) take longer than LocalReasoningAdapter's own
    # fixed 120s per-request timeout on this machine -- a real, honest
    # model/hardware constraint, not something this test should paper over
    # by lengthening a timeout that isn't this test's own to change. Proving
    # the recalled context reaches the real prompt does not require a long
    # prompt around it.
    coding_task = f"Context: {recalled_context}. Add a comment to README.md."
    coding_decision, coding_result = await authorize_and_run_coding_task(
        coding_task,
        repo_dir,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        max_climbs=1,
        protected_patterns=("test_*.py", "*_test.py"),
    )
    assert coding_decision.granted is True
    assert coding_result is not None

    status_outcome = authorize_and_get_git_status(
        repo_dir,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    assert status_outcome.decision.granted is True
    assert status_outcome.status is not None

    marker_file = repo_dir / "session_marker.txt"
    marker_file.write_text("A real, independent change proving the session concludes cleanly.\n")
    subprocess.run(["git", "-C", str(repo_dir), "add", "session_marker.txt"], check=True)

    commit_decision = authorize_and_commit_git(
        repo_dir,
        "session: real end-to-end scenario marker",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    assert commit_decision.granted is True

    final_status = authorize_and_get_git_status(
        repo_dir,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
    )
    assert final_status.decision.granted is True
    assert "nothing to commit" in (final_status.status or "").lower()
