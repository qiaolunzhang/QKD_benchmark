"""Finite-size-effect-aware greedy (``fse_greedy``).

Inspired by the DA-FSE heuristic of the RCKTA-FSE line of work
(INFOCOM'27).  The finite-size secret-key rate *grows* with the TP
duration, so a longer transmission period yields more keys per slot —
banking surplus that dynamic key-pool variants of the problem later
spend.  This adapts that insight to the static single-TP P1 problem in
two stages:

1. **Serve** with the resource-frugal minimum TP, in earliest-deadline
   order — identical serving behaviour to ``greedy_sp``, so ``fse_greedy``
   never serves *fewer* demands.
2. **Extend** each served TP into still-free earlier slots, keeping the
   longest that fits.  Serving is untouched; only delivered/surplus keys
   go up.

The full DA-FSE (multi-path flow decomposition, quantum-key-pool
accounting, trusted-relay vs optical-bypass architectures) is a P1
extension tracked for a later phase; this is the single-TP projection.
"""
from __future__ import annotations

from ..core.algorithm import Algorithm, register_algorithm
from ..core.solution import Solution
from ..scenario.qkd_models import get_qkd_model
from ._common import (ResourceLedger, candidate_paths, extend_for_surplus,
                      greedy_construct)


@register_algorithm
class FseGreedy(Algorithm):
    """EDF min-TP serving + surplus-maximising TP extension."""

    name = "fse_greedy"

    def solve(self, instance) -> Solution:
        k_paths = self.params.get("k_paths", 3)
        model = get_qkd_model(instance.rate_table, **instance.qkd_model_params)
        ledger = ResourceLedger(instance)

        def order_key(req):
            return (req.deadline_slot, -req.volume_kb)

        def rank_paths(req, cands):
            return sorted(cands, key=lambda c: c[1])   # shortest first

        assignments = greedy_construct(instance, model, order_key,
                                       rank_paths, k_paths, ledger=ledger)
        extend_for_surplus(assignments, instance, model, ledger)
        return Solution(algorithm=self.name, assignments=assignments)
