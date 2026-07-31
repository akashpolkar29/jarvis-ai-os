"""CLI ring: the command-line entry point.

The outermost ring. It parses arguments and talks to a running kernel
over ``jarvis.ipc``, or boots the kernel directly for local/dev use. It
holds no business logic of its own.

Constraints:

* May depend on every other ring.
* Contains no domain logic — a command handler translates arguments into
  a call against ``jarvis.kernel`` / ``jarvis.ipc`` and formats the
  result; it does not decide policy or interpret capabilities itself.
"""
