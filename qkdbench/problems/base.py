"""Composable problem definition (ARCHITECTURE.md §6).

A :class:`Problem` is *composed* from three kinds of pluggable module —
decisions, constraints and objectives — rather than being a leaf of a
deep class hierarchy.  This is what lets one problem (say static routing)
run unchanged across topologies and QKD models, and lets a new problem be
built by picking a different set of modules.

Crucially, constraint modules exist to **verify** a solution and to feed
metrics — they do *not* auto-generate a MILP.  Each constraint is a plain
predicate over ``(instance, solution)`` returning human-readable
violation strings; exact solvers still write their own formulation, but
their output is judged by these same modules (ARCHITECTURE.md §6, §12).

Modules declare:

* ``requires`` — instance/solution fields they read, for a dependency
  closure check at compose time;
* ``provides`` / ``conflicts`` — tags used to detect incompatible
  combinations (e.g. ``single_path`` vs ``multipath``).
"""
from __future__ import annotations

from typing import List, Set

from ..core.errors import ConfigError
from ..core.instance import Instance
from ..core.registry import registry
from ..core.solution import Solution


class _Module:
    name: str = None
    requires: Set[str] = frozenset()
    provides: Set[str] = frozenset()
    conflicts: Set[str] = frozenset()


class DecisionModule(_Module):
    """A decision the problem asks an algorithm to make.

    ``solution_component`` names the Solution field the decision populates
    (e.g. ``"routing"``); the compose step checks constraints/objectives
    only reference decisions that are present.
    """
    solution_component: str = None


class ConstraintModule(_Module):
    """A feasibility rule checked against a Solution."""

    def check(self, instance: Instance, solution: Solution) -> List[str]:
        raise NotImplementedError


class ObjectiveModule(_Module):
    """A scalar the benchmark computes from a Solution (never the algo)."""
    sense: str = "max"          # "max" or "min"

    def value(self, instance: Instance, solution: Solution) -> float:
        raise NotImplementedError


class Problem:
    """A composed optimization problem.

    Attributes:
        name: preset/problem identifier.
        decisions / constraints / objectives: module instances.
        params: problem-level parameters (not algorithm hyper-parameters).
    """

    def __init__(self, name, decisions, constraints, objectives,
                 params=None):
        self.name = name
        self.decisions = list(decisions)
        self.constraints = list(constraints)
        self.objectives = list(objectives)
        self.params = dict(params or {})
        self._validate()

    # ---------------------------------------------------------- validation
    def _validate(self):
        tags = set()
        for m in self.decisions + self.constraints + self.objectives:
            clash = tags & set(m.conflicts)
            if clash:
                raise ConfigError(
                    f"problem {self.name!r}: module {m.name!r} conflicts "
                    f"with already-included tag(s) {sorted(clash)}")
            tags |= set(m.provides)
        # dependency closure: every 'solution.*' requirement must be
        # provided by some decision's solution_component.
        provided = {f"solution.{d.solution_component}"
                    for d in self.decisions if d.solution_component}
        for m in self.constraints + self.objectives:
            for req in m.requires:
                if req.startswith("solution.") and req not in provided:
                    raise ConfigError(
                        f"problem {self.name!r}: {m.name!r} requires "
                        f"{req!r}, but no decision provides it")

    # ------------------------------------------------------------- verify
    def verify(self, instance: Instance, solution: Solution):
        """Run every constraint module; return a :class:`Verdict`."""
        from ..core.verifier import Verdict
        violations: List[str] = []
        for c in self.constraints:
            violations.extend(c.check(instance, solution))
        return Verdict(ok=not violations, violations=violations)

    def evaluate_objectives(self, instance, solution) -> dict:
        return {o.name: o.value(instance, solution) for o in self.objectives}


def get_problem(name: str, **params) -> Problem:
    """Instantiate a registered problem preset by name."""
    from . import presets  # noqa: F401  (ensures presets are registered)
    factory = registry.get("problem", name)
    return factory(**params)


def list_problems():
    from . import presets  # noqa: F401
    return registry.names("problem")
