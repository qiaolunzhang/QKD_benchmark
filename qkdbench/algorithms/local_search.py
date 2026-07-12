"""Multi-start large-neighbourhood search (``local_search``).

The greedy constructors commit to one demand ordering.  ``local_search``
escapes that by (a) building several initial solutions from random demand
orders and (b) repeatedly perturbing the best one — evicting a random
fraction of served demands and re-inserting every unserved demand — and
keeping any move that serves more demands (ties broken by surplus keys).
It follows the LS/LNS scheme of the RCKTA-FSE work.

Determinism: all randomness derives from ``params["seed"]`` (default 0),
so two runs with the same seed are bit-identical.
"""
from __future__ import annotations

import random

from ..core.algorithm import Algorithm, register_algorithm
from ..core.solution import Assignment, Solution
from ..core.verifier import route_length_km
from ..scenario.qkd_models import get_qkd_model
from ._common import (ResourceLedger, candidate_paths, extend_for_surplus,
                      max_feasible_slots, place_min_tp)


@register_algorithm
class LocalSearch(Algorithm):
    """Multi-start + large-neighbourhood search over P1 solutions."""

    name = "local_search"

    def solve(self, instance) -> Solution:
        self.k_paths = self.params.get("k_paths", 3)
        self.budget = self.params.get("budget_iters", 50)
        self.restarts = self.params.get("restarts", 4)
        self.model = get_qkd_model(instance.rate_table,
                                   **instance.qkd_model_params)
        self.instance = instance
        self.max_slots = max_feasible_slots(instance, self.model)
        self.graph = instance.graph()
        rng = random.Random(self.params.get("seed", 0))

        best = None
        for r in range(self.restarts):
            order = list(instance.requests)
            rng.shuffle(order)
            sol = self._construct(order)
            sol = self._improve(sol, rng)
            if best is None or self._score(sol) > self._score(best):
                best = sol

        assignments = list(best.values())
        ledger = self._ledger_from(assignments)
        extend_for_surplus(assignments, instance, self.model, ledger)
        return Solution(algorithm=self.name, assignments=assignments)

    # ------------------------------------------------------------ helpers
    def _construct(self, order, base=None):
        """Insert demands (in ``order``) into an optional partial solution."""
        served = dict(base or {})
        ledger = self._ledger_from(served.values())
        for req in order:
            if req.id in served:
                continue
            cands = candidate_paths(self.graph, req.src, req.dst, self.k_paths)
            cands.sort(key=lambda c: c[1])
            placed = place_min_tp(req, cands, self.instance, self.model,
                                  ledger, self.max_slots)
            if placed is not None:
                served[req.id] = placed
        return served

    def _improve(self, sol, rng):
        best = sol
        by_id = {r.id: r for r in self.instance.requests}
        for _ in range(self.budget):
            if not best:
                break
            served_ids = list(best)
            k = max(1, int(len(served_ids) * rng.uniform(0.1, 0.3)))
            evict = set(rng.sample(served_ids, min(k, len(served_ids))))
            kept = {i: a for i, a in best.items() if i not in evict}
            # re-insert everything not currently served, EDF order
            missing = [by_id[i] for i in by_id if i not in kept]
            missing.sort(key=lambda r: (r.deadline_slot, -r.volume_kb))
            cand = self._construct(missing, base=kept)
            if self._score(cand) > self._score(best):
                best = cand
        return best

    def _ledger_from(self, assignments):
        ledger = ResourceLedger(self.instance)
        for a in assignments:
            from ..core.instance import edge_key
            links = [edge_key(*l) for l in a.route]
            ledger.commit(links, a.wavelength,
                          range(a.tp_start, a.tp_end + 1))
        return ledger

    def _score(self, served):
        """(served count, surplus keys) — maximised lexicographically."""
        surplus = 0.0
        for a in served.values():
            req = self.instance.request_by_id(a.request_id)
            keys = self.model.tp_keys_kb(
                route_length_km(self.instance, a.route), a.n_slots,
                self.instance.slot_seconds)
            surplus += keys - req.volume_kb
        return (len(served), round(surplus, 6))
