"""The GTK4 confirmation dialog: the physical-keypress UI (WP-24, Finding 2 closure).

See ``jarvis.ui.confirm.dialog`` for the implementation and the
security rationale behind its event-genuineness check.
"""

from __future__ import annotations

from .dialog import show_confirmation_dialog

__all__ = [
    "show_confirmation_dialog",
]
