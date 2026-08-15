"""UI ring: rendering-only code with a real display and real input devices.

This ring holds the first genuinely privileged-nothing code in the
project: it may draw windows and read GTK4/GLib events, but it knows
nothing about JARVIS itself. Import-linter contract "C5 ui privilege"
enforces this structurally: no module under ``jarvis.ui`` may import
``jarvis.domain``, ``jarvis.ports``, ``jarvis.application``,
``jarvis.adapters``, ``jarvis.kernel``, ``jarvis.ipc``, or
``jarvis.cli``. Every function here is a pure prompt-in/answer-out leaf
that an adapter (``jarvis.adapters.physical_confirmation``) calls into,
never the other way around.

``confirm/`` holds the GTK4 confirmation dialog: the Finding 2 closure
(docs/threat-model/v0.md), the first real UI code in this project.
"""

from __future__ import annotations
