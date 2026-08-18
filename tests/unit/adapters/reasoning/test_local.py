"""Unit tests for jarvis.adapters.reasoning.local.LocalReasoningAdapter.

What's mocked and why: only the actual HTTP call (``call``) is faked --
no real local inference server is required, or reliably available, in
CI. See ``local.py``'s module docstring for why the real ``_post_sync``
has no automated test of its own.
"""

from __future__ import annotations

from jarvis.adapters.reasoning.local import LocalReasoningAdapter, _extract_content
from jarvis.domain.provenance import Trust


async def test_generate_returns_the_called_content() -> None:
    async def fake_call(prompt: str, model: str) -> str:
        assert prompt == "do the task"
        assert model == "local-default"
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
