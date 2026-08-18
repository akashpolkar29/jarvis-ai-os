"""The reasoning port: the seam between a task description and a proposed Candidate.

:class:`ReasoningPort` is the one abstract boundary between "some real
reasoning provider" (a cloud model family, a local model) and the rest
of the system. Nothing outside an adapter implementing this port knows
or cares which provider actually produced a :class:`~jarvis.domain.evidence.Candidate`
-- ADR-0021 forbids a vendor name anywhere in this file, same as
``domain``/``application``.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.reasoning`` (WP-32, not
yet built) for the concrete provider-backed adapters that satisfy this
port.

**A real, stated gap, not silently resolved**: ``docs/architecture/m2-reasoning-layer.md``
section 5's deliverable #1 names "ReasoningPort + ProviderProfile +
adapters... + shared contract test suite" but never specifies a method
signature anywhere in the recovered material -- there was nothing to
check this shape against beyond that one line. The signature below is
a new decision, made here, not extracted from the recovered doc:

* :class:`~jarvis.domain.reasoning.ProviderProfile` is deliberately
  **not** a parameter of :meth:`ReasoningPort.generate`. Every other
  real port in this repo binds one concrete backend per adapter
  *class* (``FasterWhisperAdapter``, ``PiperTtsAdapter``,
  ``OpenWakeWordAdapter`` each take no "which model" argument -- the
  backend is fixed at construction, not per call). Following that
  precedent, "which provider" is a fact about *which adapter instance*
  a caller chose to call, decided by the application-layer router
  (``application.reasoning.router``, WP-36) -- not something this port
  needs to accept as an argument. ``ProviderProfile`` is real,
  registered-once metadata the router uses to make that choice; it
  does not need to appear inside this Protocol to be useful. A
  ``profile`` property on the Protocol itself was considered and
  rejected: no existing port in this repo declares a data attribute on
  its Protocol (every one is method-only), and inventing that pattern
  here would be exactly the kind of new-pattern-for-no-reason this
  work package was told not to do.
* The return type wraps :class:`~jarvis.domain.evidence.Candidate` in
  :class:`~jarvis.domain.provenance.Tainted`, mirroring
  :class:`~jarvis.ports.stt.SttPort`'s ``Tainted[Transcript]``: content
  a real inference process produced is new information entering the
  trust model at this exact boundary, the same reasoning that makes
  ``SttPort.transcribe()``'s output tainted rather than its input.
  **What ``Trust`` level a real adapter should assign is not decided
  here** -- unlike a spoken command (``Provenance.user()``, per the M1
  architecture doc), it is genuinely unclear whether a cloud provider's
  output should be ``Trust.SYSTEM`` (it's JARVIS's own reasoning
  subsystem talking) or ``Trust.UNTRUSTED_EXTERNAL`` (it's an external
  system whose output could reflect adversarial input, e.g. prompt
  injection reflected back). This is real, undecided design work for
  WP-32's real adapters, not resolved by this Protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt, Candidate
    from jarvis.domain.provenance import Tainted


@runtime_checkable
class ReasoningPort(Protocol):
    """A reasoning provider that generates a Candidate for a task."""

    async def generate(self, task: str, prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        """Generate a Candidate for ``task``, informed by ``prior_attempts``.

        Args:
            task: A plain-text description of what to produce. Not
                ``Tainted`` -- by the time this port is called, any
                Classification-based egress gating (ADR-0014/ADR-0015/
                ADR-0038) has already happened upstream, at the
                ``CapabilityInvocation``/policy-evaluate layer (ADR-0039),
                the same way ``SttPort.transcribe()``'s ``Segment``
                input and ``VadPort.segment()``'s ``AudioChunk`` input
                are plain, not ``Tainted`` -- taint is about content
                already in the system needing tracking, not something
                every port call re-derives.
            prior_attempts: Every previous attempt at this task, in
                order, or an empty tuple for a first attempt. This is
                the self-repair feedback mechanism (ADR-0022): a
                non-empty ``prior_attempts`` is how an implementation
                learns what was already tried and why it failed --
                each element already carries its own
                :class:`~jarvis.domain.evidence.Candidate` and
                :class:`~jarvis.domain.evidence.Verdict`.

        Returns:
            A newly generated ``Candidate``, tagged with its real
            provenance. See this module's docstring for why the exact
            ``Trust`` level is left to the implementation, not fixed
            here.
        """
        ...
