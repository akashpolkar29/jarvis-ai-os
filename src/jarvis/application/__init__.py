"""Application ring: use cases orchestrating domain objects through ports.

This ring contains the actual behavior of JARVIS: given a request, it
constructs domain objects, calls out to ports (never to concrete
adapters), and produces a result. The policy engine that evaluates a
capability's declared effects against the active tier lives in
``jarvis.application.policy``.

Constraints:

* No vendor names (ADR-0021).
* May depend on ``jarvis.domain`` and ``jarvis.ports`` only; never
  imports a concrete adapter directly.
"""
