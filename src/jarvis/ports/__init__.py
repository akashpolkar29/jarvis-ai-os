"""Ports ring: the abstract boundaries the domain and application depend on.

A port is a ``typing.Protocol`` describing a capability the outside world
must provide (a clock, an id generator, a reasoning provider, storage,
audio capture, and so on) without naming which concrete implementation
supplies it. Concrete implementations live in ``jarvis.adapters``.

Constraints:

* No vendor names (no "openai", "anthropic", "chatgpt", "claude", "gpt").
  A port describes a role, never a specific integration.
* May depend on ``jarvis.domain`` only.
"""
