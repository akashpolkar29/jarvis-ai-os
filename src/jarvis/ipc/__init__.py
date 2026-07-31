"""IPC ring: transport for talking to a running kernel from another process.

This subpackage defines and implements the wire protocol (see
``docs/protocol/``) used by clients — the CLI, a future voice frontend,
a future GUI — to reach a running kernel instance without linking
against it directly.

Constraints:

* May depend on ``jarvis.domain``, ``jarvis.ports``,
  ``jarvis.application``, ``jarvis.adapters``, and ``jarvis.kernel``.
* Never imports ``jarvis.cli`` (the CLI depends on ipc, not the reverse).
"""
