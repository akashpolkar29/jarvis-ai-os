"""Unit tests for jarvis.adapters.reasoning.local.LocalReasoningAdapter.

What's mocked and why: only the actual HTTP call (``call``) is faked --
no real local inference server is required, or reliably available, in
CI. See ``local.py``'s module docstring for why the real ``_post_sync``
has no automated test of its own.

``test_real_generate_against_a_locally_running_ollama_server`` is the
one real, live exception -- skipif-guarded on a real reachability
probe against ``localhost:11434`` (no credential to gate on, unlike
IMAP/SMTP's own env-var-gated precedent, since a local Ollama server
needs none), mirroring ``test_real_cdp_flow_against_a_local_page``'s
own real-infrastructure discipline. Honestly skipped in CI (no Ollama
server there); live-verified manually on this development machine
2026-09-04 (`qwen2.5:0.5b`, pulled for real, no account/auth).
"""

from __future__ import annotations

import urllib.request

import pytest

from jarvis.adapters.reasoning.local import LocalReasoningAdapter, _extract_content
from jarvis.domain.provenance import Trust


def _real_ollama_server_is_reachable() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    except OSError:
        return False
    return True


async def test_generate_returns_the_called_content() -> None:
    async def fake_call(prompt: str, model: str) -> str:
        assert prompt == "do the task"
        assert model == "qwen2.5:0.5b"
        return "generated answer"

    adapter = LocalReasoningAdapter(call=fake_call)

    tainted = await adapter.generate("do the task", ())

    assert tainted.value.content == "generated answer"
    assert tainted.value.author == "local"


async def test_generate_tags_the_candidate_system_trust() -> None:
    """A local, on-device model (is_local=True) gets Trust.SYSTEM, per the WP-32 decision."""

    async def fake_call(_prompt: str, _model: str) -> str:
        return "answer"

    adapter = LocalReasoningAdapter(call=fake_call)

    tainted = await adapter.generate("task", ())

    assert tainted.provenance.trust == Trust.SYSTEM


async def test_generate_uses_a_non_default_model_when_given_one() -> None:
    seen_models: list[str] = []

    async def fake_call(_prompt: str, model: str) -> str:
        seen_models.append(model)
        return "answer"

    adapter = LocalReasoningAdapter(model="llama-large", call=fake_call)

    await adapter.generate("task", ())

    assert seen_models == ["llama-large"]


def test_extract_content_reads_the_response_field() -> None:
    body = {"response": "the real answer", "done": True}

    assert _extract_content(body) == "the real answer"


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, locally running Ollama server on localhost:11434, not assumed in CI.",
)
async def test_real_generate_against_a_locally_running_ollama_server() -> None:
    """The real, unmocked HTTP call, against a real server, produces a real result."""
    adapter = LocalReasoningAdapter()

    tainted = await adapter.generate("Say hello in exactly three words.", ())

    assert isinstance(tainted.value.content, str)
    assert len(tainted.value.content) > 0
    assert tainted.value.author == "local"
