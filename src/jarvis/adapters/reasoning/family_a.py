"""Adapter implementing jarvis.ports.reasoning.ReasoningPort against cloud provider family A.

:class:`FamilyAReasoningAdapter` calls a chat-completions-shaped REST
API: ``POST <endpoint> {"model": ..., "messages": [{"role": "user",
"content": <prompt>}]}`` with an ``Authorization: Bearer <key>``
header, expecting back ``{"choices": [{"message": {"content": ...}}]}``.
"family A" is this shape, not a specific vendor -- ADR-0021 forbids a
vendor name anywhere importable from ``domain``/``application``/``ports``,
and per WP-32's own scoping, the *class and module name* stay generic
even here in the adapter ring, though the real endpoint URL and header
names below necessarily are vendor-specific (that detail has to live
somewhere, and "adapter implementation internals" is exactly where
ADR-0021 says it belongs).

**A real, stated gap, partially closed, not silently smoothed over**:
WP-28's own standalone PoC script -- meant to validate this shape
against a real provider before adapters were built against it -- was
never written or run (confirmed absent from ``poc/``). During M2
consolidation, ``_ENDPOINT`` was corrected from a deliberate
``.example`` placeholder to the real OpenAI Chat Completions endpoint,
and one real round-trip was attempted through this exact,
unmodified class, with a real credential resolved via
:class:`~jarvis.ports.secret.SecretPort`. The request reached OpenAI
and authenticated successfully -- confirmed by getting back a real
``insufficient_quota`` error (a billing/quota condition checked
*after* auth) rather than a DNS failure or ``invalid_api_key`` --
which is real evidence the request shape (auth header, JSON body,
``model``/``messages`` fields) is correct. **What remains genuinely
unverified**: :func:`_extract_content`'s response-parsing shape
(``choices[0]["message"]["content"]``), since no successful response
was ever returned to parse. Tracked alongside M1's own open item #19
(live end-to-end verification pending), not glossed over as done.

Trust level: this is a genuine third-party cloud service --
``ProviderProfile.is_local`` is ``False`` for this family -- so its
output is tagged ``Trust.UNTRUSTED_EXTERNAL`` via
:meth:`~jarvis.domain.provenance.Provenance.external`, per the
explicit split-by-``is_local`` decision made during WP-32 (flagged as
an open ambiguity in ``ports/reasoning.py``'s docstring, resolved here).
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

    ChatCompletionCall = Callable[[str, str, str], Awaitable[str]]

_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "family-a-default"
_REQUEST_TIMEOUT_SECONDS = 30.0
_AUTHOR = "family_a"

PROFILE = ProviderProfile(name=_AUTHOR, is_local=False)
"""This adapter's registered-once identity -- for application.reasoning.router (WP-36) to
consume, not for this module or any caller to branch on (see
tests/meta/test_source_invariants.py's ``.name`` identity check)."""


def _extract_content(response_body: dict[str, object]) -> str:
    """Return the generated text from a parsed chat-completions-shaped response body.

    Pure and I/O-free -- unit-tested directly with a fake parsed dict,
    no network required. This is exactly where a wrong-shape assumption
    about the real API would hide, so it is kept separate from the
    actual HTTP call on purpose.
    """
    choices = response_body["choices"]
    first_choice = choices[0]  # type: ignore[index]
    message = first_choice["message"]
    return message["content"]  # type: ignore[no-any-return]


def _post_sync(prompt: str, api_key: str, model: str) -> str:
    """Make the real, blocking POST call and return the generated text.

    The one real, untested-by-design piece of this module -- see the
    module docstring for why. A fresh connection is made per call,
    matching every D-Bus adapter's own framing: there is no persistent
    connection to reuse.
    """
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode(
        "utf-8"
    )
    request = urllib.request.Request(
        _ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
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


class FamilyAReasoningAdapter:
    """Generates Candidates via cloud provider family A's chat-completions API."""

    def __init__(
        self,
        secrets: SecretPort,
        api_key_reference: str,
        model: str = _DEFAULT_MODEL,
        call: ChatCompletionCall | None = None,
    ) -> None:
        """Store how to resolve a credential and how to make the real call.

        Args:
            secrets: Resolves ``api_key_reference`` to a real API key
                at the point of use (ADR-0017, ADR-0042) -- never
                stored as a field, never read at construction time.
            api_key_reference: The keyring reference for this
                provider's API key.
            model: Which model to request. Defaults to a generic
                placeholder -- the real model identifier is real,
                provider-specific configuration, not decided here.
            call: Given ``(prompt, api_key, model)``, makes the real
                call and returns the generated text. Defaults to a
                real implementation. Overridable for tests, matching
                every other adapter's constructor-injection pattern in
                this repo -- no I/O happens at construction time either way.
        """
        self._secrets = secrets
        self._api_key_reference = api_key_reference
        self._model = model
        self._call: ChatCompletionCall = call or _call

    async def generate(self, task: str, prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        """Generate a Candidate for ``task`` by calling cloud provider family A.

        See ``jarvis.ports.reasoning.ReasoningPort.generate`` for the
        full contract this implements.
        """
        api_key = self._secrets.get_secret(self._api_key_reference)
        prompt = build_prompt(task, prior_attempts)
        content = await self._call(prompt, api_key, self._model)
        candidate = Candidate(author=_AUTHOR, content=content)
        return Tainted.external(candidate, _AUTHOR, Classification.PUBLIC)
