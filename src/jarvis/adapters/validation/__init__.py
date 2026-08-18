"""Adapters implementing jarvis.ports.validation.ValidationPort.

Five adapters, matching ``docs/architecture/m2-reasoning-layer.md``
section 7's recovered package layout (``adapters/validation/ - build,
pytest, static, runtime, user_script``): ``BuildValidator``,
``PytestValidator`` (see that module's own docstring for its filename
deviation), ``StaticAnalysisValidator``, ``RuntimeCheckValidator``, and
``UserScriptValidator``. Each applies a Candidate's content as a patch
to a real :class:`~jarvis.ports.workspace.WorkspacePort` (ADR-0043),
then runs a real command and judges the result by its exit code --
``jarvis.adapters.validation._command`` factors out the logic all five
share.

This is a genuine per-adapter subpackage, like
``jarvis.adapters.reasoning`` (WP-32): the five modules below must not
import from each other.
"""

from __future__ import annotations

from .build import BuildValidator
from .pytest_validator import PytestValidator
from .runtime import RuntimeCheckValidator
from .static import StaticAnalysisValidator
from .user_script import UserScriptValidator

__all__ = [
    "BuildValidator",
    "PytestValidator",
    "RuntimeCheckValidator",
    "StaticAnalysisValidator",
    "UserScriptValidator",
]
