"""Adapter implementing jarvis.ports.reasoning.ReasoningPort against cloud provider family B.

:class:`FamilyBReasoningAdapter` calls a messages-shaped REST API:
``POST <endpoint> {"model": ..., "max_tokens": ..., "messages": [{"role":
"user", "content": <prompt>}]}`` with an ``x-api-key: <key>`` header
(not ``Authorization: Bearer``, the header shape family A uses --
deliberately kept different here so this adapter cannot be collapsed
into family A's by accident; two genuinely different request/auth
shapes is also the whole point of cross-vendor heterogeneity,
m2-reasoning-layer.md section 3), expecting back ``{"content": [{"type":
"text", "text": ...}]}``. "family B" is this shape, not a specific
vendor -- see ``family_a.py``'s module docstring for the full ADR-0021
reasoning, which applies identically here.

**Same real, stated gap as family_a.py**: this adapter's exact
request/response shape has not been verified against a real endpoint
-- no WP-28 PoC was ever run, and verifying live would require handling
a real credential this session should not touch. Real, structurally-
complete code; live correctness unverified, tracked the same way as
family_a.py and M1's open item #19.

Trust level: a genuine third-party cloud service
(``ProviderProfile.is_local`` is ``False``), tagged
``Trust.UNTRUSTED_EXTERNAL`` for the same reason as ``family_a.py`` --
see that module's docstring.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import TYPE_CHECKING

from jarvis.adapters.reasoning._prompt import build_prompt
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Classification, Tainted
from jarvis.domain.reasoning import ProviderProfile

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from jarvis.domain.evidence import Attempt
    from jarvis.ports.secret import SecretPort

    MessagesCall = Callable[[str, str, str], Awaitable[str]]

_ENDPOINT = "https://api.family-b.example/v1/messages"
_DEFAULT_MODEL = "family-b-default"
_MAX_TOKENS = 4096
_API_VERSION = "2023-06-01"
_REQUEST_TIMEOUT_SECONDS = 30.0
_AUTHOR = "family_b"

PROFILE = ProviderProfile(name=_AUTHOR, is_local=False)
"""This adapter's registered-once identity -- for application.reasoning.router (WP-36) to
consume, not for this module or any caller to branch on (see
tests/meta/test_source_invariants.py's ``.name`` identity check)."""


def _extract_content(response_body: dict[str, object]) -> str:
    """Return the generated text from a parsed messages-shaped response body.

    Pure and I/O-free -- unit-tested directly with a fake parsed dict,
    no network required, matching ``family_a.py``'s ``_extract_content``.
    """
    content_blocks = response_body["content"]
    first_block = content_blocks[0]  # type: ignore[index]
    return first_block["text"]  # type: ignore[no-any-return]


def _post_sync(prompt: str, api_key: str, model: str) -> str:
    """Make the real, blocking POST call and return the generated text.

    The one real, untested-by-design piece of this module -- see the
    module docstring for why.
    """
    body = json.dumps(
        {
            "model": model,
            "max_tokens": _MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _ENDPOINT,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
        response_body = json.loads(response.read())
    return _extract_content(response_body)


async def _call(prompt: str, api_key: str, model: str) -> str:
    """Run the real, blocking call off the event loop thread."""
    return await asyncio.to_thread(_post_sync, prompt, api_key, model)


class FamilyBReasoningAdapter:
    """Generates Candidates via cloud provider family B's messages API."""

    def __init__(
        self,
        secrets: SecretPort,
        api_key_reference: str,
        model: str = _DEFAULT_MODEL,
        call: MessagesCall | None = None,
    ) -> None:
        """Store how to resolve a credential and how to make the real call.

        Args:
            secrets: Resolves ``api_key_reference`` to a real API key
                at the point of use (ADR-0017, ADR-0042) -- never
                stored as a field, never read at construction time.
            api_key_reference: The keyring reference for this
                provider's API key.
            model: Which model to request. Defaults to a generic
                placeholder, matching ``family_a.py``.
            call: Given ``(prompt, api_key, model)``, makes the real
                call and returns the generated text. Defaults to a
                real implementation. Overridable for tests, matching
                every other adapter's constructor-injection pattern in
                this repo.
        """
        self._secrets = secrets
        self._api_key_reference = api_key_reference
        self._model = model
        self._call: MessagesCall = call or _call

    async def generate(self, task: str, prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        """Generate a Candidate for ``task`` by calling cloud provider family B.

        See ``jarvis.ports.reasoning.ReasoningPort.generate`` for the
        full contract this implements.
        """
        api_key = self._secrets.get_secret(self._api_key_reference)
        prompt = build_prompt(task, prior_attempts)
        content = await self._call(prompt, api_key, self._model)
        candidate = Candidate(author=_AUTHOR, content=content)
        return Tainted.external(candidate, _AUTHOR, Classification.PUBLIC)
