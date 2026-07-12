"""Key-efficiency-aware shortest-path greedy (``key_aware_sp``).

``greedy_sp`` ranks a demand's candidate paths purely by physical length.
But under finite-size key rates a slightly longer path can occasionally
need *fewer* TP slots to cover a demand (its length lands in a more
favourable reach bucket), and a shorter TP frees scarce
(link, wavelength, slot) resources for later demands.  ``key_aware_sp``
keeps the same earliest-deadline demand order as the baseline but ranks
each demand's paths by the number of TP slots they need first, and
physical length only as a tie-breaker — spending the fewest resources per
served demand.
"""
from __future__ import annotations

from ..core.algorithm import Algorithm, register_algorithm
from ..core.solution import Solution
from ..scenario.qkd_models import get_qkd_model
from ._common import (ResourceLedger, greedy_construct, max_feasible_slots,
                      min_slots_for)


@register_algorithm
class KeyAwareShortestPath(Algorithm):
    """EDF order with key-efficiency path ranking (``key_aware_sp``)."""

    name = "key_aware_sp"

    def solve(self, instance) -> Solution:
        k_paths = self.params.get("k_paths", 3)
        model = get_qkd_model(instance.rate_table, **instance.qkd_model_params)
        max_slots = max_feasible_slots(instance, model)
        slot_s = instance.slot_seconds

        def slots_needed(req, length):
            n = min_slots_for(model, length, req.volume_kb, max_slots, slot_s)
            return n if n is not None else max_slots + 1

        def rank_paths(req, cands):
            return sorted(cands, key=lambda c: (slots_needed(req, c[1]), c[1]))

        def order_key(req):
            return (req.deadline_slot, -req.volume_kb)   # EDF, as baseline

        assignments = greedy_construct(instance, model, order_key,
                                       rank_paths, k_paths,
                                       ledger=ResourceLedger(instance))
        return Solution(algorithm=self.name, assignments=assignments)
