"""Plugin API: the stable surface third-party capability plugins build against.

Plugins are how new features enter JARVIS — the kernel itself knows only
about capabilities, never about specific agents or integrations. This
subpackage is the contract a plugin author imports against, and it is
deliberately kept minimal and stable.

Constraints:

* May depend on ``jarvis.domain`` only (import-linter contract
  "C7 plugin_api depends only on domain"). A plugin author must never
  need to reach into ``jarvis.application``, ``jarvis.adapters``,
  ``jarvis.kernel``, ``jarvis.ipc``, or ``jarvis.cli``.
"""
