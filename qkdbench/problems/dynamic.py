"""Dynamic admission + key-pool problem (P2) modules.

P2 asks an online controller which arriving demands to admit and onto
which route, subject to each link's key-pool generation rate.  Its single
feasibility module replays the recorded admissions through the shared
simulator (:mod:`qkdbench.scenario.simulator`) — the same model the online
algorithm ran against — so the verifier and the algorithm never disagree.
Objectives (acceptance ratio, blocking, served rate) are computed by the
benchmark from the verified admissions.
"""
from __future__ import annotations

from typing import List

from ..core.registry import registry
from ..scenario.simulator import replay_violations
from .base import ConstraintModule, DecisionModule, ObjectiveModule, Problem


# ----------------------------------------------------------- decisions
@registry.register("decision", "admission_control")
class AdmissionControl(DecisionModule):
    name = "admission_control"
    solution_component = "admissions"
    requires = frozenset({"demand.arrival_t", "demand.rate_kbps"})
    provides = frozenset({"dynamic"})


@registry.register("decision", "online_routing")
class OnlineRouting(DecisionModule):
    name = "online_routing"
    solution_component = "admissions"
    requires = frozenset({"demand.src", "demand.dst"})


# ---------------------------------------------------------- constraints
@registry.register("constraint", "keypool_capacity")
class KeyPoolCapacity(ConstraintModule):
    """Every admission stays within its links' key-pool generation rates
    (replayed independently of the algorithm)."""
    name = "keypool_capacity"
    requires = frozenset({"solution.admissions", "demand.rate_kbps"})

    def check(self, instance, solution) -> List[str]:
        return replay_violations(instance, solution)


# ----------------------------------------------------------- objectives
@registry.register("objective", "acceptance_ratio")
class AcceptanceRatio(ObjectiveModule):
    name = "acceptance_ratio"
    sense = "max"
    requires = frozenset({"solution.admissions"})

    def value(self, instance, solution) -> float:
        n = len(instance.demands)
        return round(len(solution.admitted_ids) / n, 6) if n else 0.0


@registry.register("objective", "blocking_probability")
class BlockingProbability(ObjectiveModule):
    name = "blocking_probability"
    sense = "min"
    requires = frozenset({"solution.admissions"})

    def value(self, instance, solution) -> float:
        n = len(instance.demands)
        return round(1.0 - len(solution.admitted_ids) / n, 6) if n else 0.0


@registry.register("objective", "served_rate_kbps")
class ServedRateKbps(ObjectiveModule):
    name = "served_rate_kbps"
    sense = "max"
    requires = frozenset({"solution.admissions", "demand.rate_kbps"})

    def value(self, instance, solution) -> float:
        by_id = {d.id: d for d in instance.demands}
        return round(sum(by_id[i].rate_kbps or 0.0
                         for i in solution.admitted_ids), 3)


P2_DECISIONS = ["admission_control", "online_routing"]
P2_CONSTRAINTS = ["keypool_capacity"]
P2_OBJECTIVES = ["acceptance_ratio", "blocking_probability", "served_rate_kbps"]


@registry.register("problem", "dynamic_admission_keypool")
def dynamic_admission_keypool(**params) -> Problem:
    """Dynamic request admission + key-pool management (P2)."""
    build = lambda kind, names: [registry.get(kind, n)() for n in names]
    return Problem(
        name="dynamic_admission_keypool",
        decisions=build("decision", P2_DECISIONS),
        constraints=build("constraint", P2_CONSTRAINTS),
        objectives=build("objective", P2_OBJECTIVES),
        params=params,
    )
