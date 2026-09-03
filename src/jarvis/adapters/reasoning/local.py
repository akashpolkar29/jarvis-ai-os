"""Adapter implementing jarvis.ports.reasoning.ReasoningPort against a local on-device model.

:class:`LocalReasoningAdapter` calls a real local inference server's
REST API (Ollama's ``/api/generate`` shape: ``POST <endpoint> {"model":
..., "prompt": ..., "stream": false}``, expecting back ``{"response":
...}``) on ``localhost`` -- never a cloud host, matching
``ProviderProfile.is_local=True``'s "no egress effect at all" framing.
No :class:`~jarvis.ports.secret.SecretPort` dependency: a local server
on the loopback interface needs no credential, unlike ``family_a.py``/
``family_b.py``.

**Live-verified for real, 2026-09-04** -- closing the gap this
docstring used to name: a real Ollama server was started
(``ollama serve``) and a real, small model pulled
(``qwen2.5:0.5b``, 397MB, no account/auth needed -- an anonymous,
public registry pull, not a cloud-provider credential) on this
machine. `LocalReasoningAdapter(model="qwen2.5:0.5b").generate(...)`
was called directly against the real, running server and returned a
real generated response -- not mocked, not skipped. `_DEFAULT_MODEL`
below now names this real, working model rather than the placeholder
`"local-default"` string it previously held (which was never a real,
resolvable Ollama tag). **Real, honest quality trade-off, stated
plainly**: `qwen2.5:0.5b` is a genuinely small model (0.5B parameters)
chosen for its small download and fast response, not for output
quality -- a caller relying on this default should expect materially
weaker generations than any real cloud provider would give. A future
deployment wanting better local quality overrides `model=` with a
larger real Ollama tag; nothing here prevents that.

Trust level: never leaves the machine (``ProviderProfile.is_local`` is
``True``), tagged ``Trust.SYSTEM`` via
:meth:`~jarvis.domain.provenance.Provenance.system`, per the explicit
split-by-``is_local`` decision made during WP-32 -- see
``family_a.py``'s docstring for the full reasoning and the two other
options considered.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import TYPE_CHECKING

from jarvis.adapters.reasoning._prompt import build_prompt
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Tainted
from jarvis.domain.reasoning import ProviderProfile

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from jarvis.domain.evidence import Attempt

    GenerateCall = Callable[[str, str], Awaitable[str]]

_ENDPOINT = "http://localhost:11434/api/generate"
_DEFAULT_MODEL = "qwen2.5:0.5b"
_REQUEST_TIMEOUT_SECONDS = 120.0
_AUTHOR = "local"

PROFILE = ProviderProfile(name=_AUTHOR, is_local=True)
"""This adapter's registered-once identity -- for application.reasoning.router (WP-36) to
consume, not for this module or any caller to branch on (see
tests/meta/test_source_invariants.py's ``.name`` identity check)."""


def _extract_content(response_body: dict[str, object]) -> str:
    """Return the generated text from a parsed local-generate-shaped response body.

    Pure and I/O-free -- unit-tested directly with a fake parsed dict,
    no network required, matching ``family_a.py``'s ``_extract_content``.
    """
    return response_body["response"]  # type: ignore[return-value]


def _post_sync(prompt: str, model: str) -> str:
    """Make the real, blocking POST call and return the generated text.

    The one real, untested-by-design piece of this module -- see the
    module docstring for why. Longer default timeout than the cloud
    adapters: local inference on CPU/consumer GPU hardware is
    plausibly slower than a cloud provider's own infrastructure.
    """
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        _ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
        response_body = json.loads(response.read())
    return _extract_content(response_body)


async def _call(prompt: str, model: str) -> str:
    """Run the real, blocking call off the event loop thread."""
    return await asyncio.to_thread(_post_sync, prompt, model)


class LocalReasoningAdapter:
    """Generates Candidates via a local, on-device model server."""

    def __init__(self, model: str = _DEFAULT_MODEL, call: GenerateCall | None = None) -> None:
        """Store which model to request and how to make the real call.

        Args:
            model: Which real Ollama model tag to request. Defaults to
                `_DEFAULT_MODEL` (`"qwen2.5:0.5b"`, live-verified
                2026-09-04) -- a small, fast, real, working model, not
                a guarantee of good output quality. A deployment
                wanting better local quality overrides this with its
                own real, pulled model tag.
            call: Given ``(prompt, model)``, makes the real call and
                returns the generated text. Defaults to a real
                implementation. Overridable for tests, matching every
                other adapter's constructor-injection pattern in this
                repo.
        """
        self._model = model
        self._call: GenerateCall = call or _call

    async def generate(self, task: str, prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        """Generate a Candidate for ``task`` by calling the local model server.

        See ``jarvis.ports.reasoning.ReasoningPort.generate`` for the
        full contract this implements.
        """
        prompt = build_prompt(task, prior_attempts)
        content = await self._call(prompt, self._model)
        candidate = Candidate(author=_AUTHOR, content=content)
        return Tainted.system(candidate)
