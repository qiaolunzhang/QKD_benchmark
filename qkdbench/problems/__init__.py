"""Composable problem definitions (decisions + constraints + objectives).

Importing this package registers all bundled decision, constraint,
objective and preset modules.
"""
from .base import (ConstraintModule, DecisionModule, ObjectiveModule,
                   Problem, get_problem, list_problems)
from . import presets  # noqa: F401  (registers everything)

__all__ = [
    "Problem", "DecisionModule", "ConstraintModule", "ObjectiveModule",
    "get_problem", "list_problems",
]
