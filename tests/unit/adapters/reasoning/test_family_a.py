"""Unit tests for jarvis.adapters.reasoning.family_a.FamilyAReasoningAdapter.

What's mocked and why: only the actual HTTP call (``call``) is faked --
no real network access or credential is required, or reliably
available, in CI. See ``family_a.py``'s module docstring for why the
real ``_post_sync`` has no automated test of its own.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.reasoning.family_a import FamilyAReasoningAdapter, _extract_content
from jarvis.domain.provenance import Trust


class _FakeSecretPort:
    """A minimal stand-in SecretPort returning a fixed value for any reference."""

    def __init__(self, value: str) -> None:
        self._value = value
        self.requested_references: list[str] = []

    def get_secret(self, reference: str) -> str:
        self.requested_references.append(reference)
        return self._value

    def set_secret(self, reference: str, value: str) -> None:
        """Not used by this reasoning adapter -- present only to satisfy SecretPort."""
        raise NotImplementedError


async def test_generate_resolves_the_credential_and_returns_the_called_content() -> None:
    secrets = _FakeSecretPort("sk-real-key")

    async def fake_call(prompt: str, api_key: str, model: str) -> str:
        assert prompt == "do the task"
        assert api_key == "sk-real-key"
        assert model == "family-a-default"
        return "generated answer"

    adapter = FamilyAReasoningAdapter(secrets, "family-a-key-ref", call=fake_call)

    tainted = await adapter.generate("do the task", ())

    assert tainted.value.content == "generated answer"
    assert tainted.value.author == "family_a"
    assert secrets.requested_references == ["family-a-key-ref"]


async def test_generate_tags_the_candidate_untrusted_external() -> None:
    """A cloud provider (is_local=False) gets Trust.UNTRUSTED_EXTERNAL, per the WP-32 decision."""
    secrets = _FakeSecretPort("sk-real-key")

    async def fake_call(_prompt: str, _api_key: str, _model: str) -> str:
        return "answer"

    adapter = FamilyAReasoningAdapter(secrets, "family-a-key-ref", call=fake_call)

    tainted = await adapter.generate("task", ())

    assert tainted.provenance.trust == Trust.UNTRUSTED_EXTERNAL


async def test_generate_uses_a_non_default_model_when_given_one() -> None:
    secrets = _FakeSecretPort("sk-real-key")
    seen_models: list[str] = []

    async def fake_call(_prompt: str, _api_key: str, model: str) -> str:
        seen_models.append(model)
        return "answer"

    adapter = FamilyAReasoningAdapter(
        secrets, "family-a-key-ref", model="family-a-large", call=fake_call
    )

    await adapter.generate("task", ())

    assert seen_models == ["family-a-large"]


def test_extract_content_reads_the_first_choice_message_content() -> None:
    body: dict[str, object] = {"choices": [{"message": {"content": "the real answer"}}]}

    assert _extract_content(body) == "the real answer"


def test_extract_content_raises_on_an_empty_choices_list() -> None:
    with pytest.raises(IndexError):
        _extract_content({"choices": []})
