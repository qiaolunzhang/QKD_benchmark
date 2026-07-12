"""P1 objective modules.

Objectives are computed by the benchmark from a verified Solution — never
reported by the algorithm (ARCHITECTURE.md §12).  P1's primary objective
is the number of accepted demands; delivered-surplus keys is the standard
tie-breaker (and the quantity the finite-size-aware heuristics optimise).
"""
from __future__ import annotations

from ..core.registry import registry
from ..core.verifier import route_length_km
from ..scenario.qkd_models import get_qkd_model
from .base import ObjectiveModule


@registry.register("objective", "max_accepted_demands")
class MaxAcceptedDemands(ObjectiveModule):
    name = "max_accepted_demands"
    sense = "max"
    requires = frozenset({"solution.routing"})

    def value(self, instance, solution) -> float:
        return float(len({a.request_id for a in solution.assignments}))


@registry.register("objective", "max_surplus_keys")
class MaxSurplusKeys(ObjectiveModule):
    name = "max_surplus_keys"
    sense = "max"
    requires = frozenset({"solution.routing", "demand.volume_kb"})

    def value(self, instance, solution) -> float:
        model = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        surplus = 0.0
        for a in solution.assignments:
            req = instance.request_by_id(a.request_id)
            keys = model.tp_keys_kb(route_length_km(instance, a.route),
                                    a.n_slots, instance.slot_seconds)
            surplus += keys - req.volume_kb
        return round(surplus, 6)
