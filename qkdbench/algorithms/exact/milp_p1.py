"""Compact MILP for the static P1 problem (``milp_p1``), solved with CBC.

This is the exact optimum against which the P1 heuristics are measured.
It is a set-packing-style formulation over *candidate placements*:

For each demand ``d`` we enumerate a small set of options — one per
(candidate path ``p``, wavelength ``w``, TP interval ``[t1, t2]``) — but
only those that are physically valid: ``t2`` is within the deadline and
the TP already delivers at least the demand's volume.  The key yield is a
**precomputed constant coefficient** (via the instance's QKD model), so
no physics ever enters the solver.

Binary ``x[o] = 1`` iff option ``o`` is chosen.  Constraints:

* at most one option per demand;
* each (link, wavelength, slot) used by at most one chosen option;
* each (node, slot) uses no more QKD modules than installed.

Objective: maximise served demands, with a tiny surplus-key term
(``1e-6``) to break ties toward more delivered keys — matching the
heuristics' secondary criterion.
"""
from __future__ import annotations

from ...core.algorithm import Algorithm, register_algorithm
from ...core.errors import QKDBenchError
from ...core.instance import edge_key
from ...core.solution import Assignment, Solution
from ...scenario.qkd_models import get_qkd_model
from .._common import candidate_paths, max_feasible_slots

try:
    import pulp
    _HAVE_PULP = True
except ImportError:                      # pragma: no cover
    _HAVE_PULP = False


@register_algorithm
class MilpP1(Algorithm):
    """Compact set-packing MILP for P1 (CBC via PuLP)."""

    name = "milp_p1"

    def solve(self, instance) -> Solution:
        if not _HAVE_PULP:
            raise QKDBenchError(
                "milp_p1 needs PuLP/CBC — install with "
                '`pip install "qkdbench[ilp]"`')

        k_paths = self.params.get("k_paths", 5)
        time_limit = self.params.get("time_limit_s", 300)
        model = get_qkd_model(instance.rate_table, **instance.qkd_model_params)
        graph = instance.graph()
        max_slots = max_feasible_slots(instance, model)
        slot_s = instance.slot_seconds
        default_modules = instance.metadata.get("default_modules", 2)

        # ---- enumerate valid options per demand -----------------------
        # One option per (candidate path, wavelength, TP interval) that is
        # within the deadline and already delivers the demand's volume.
        # Every serving TP length is enumerated (not just the shortest),
        # so the solver is free to pick a longer TP for more surplus keys.
        options = []   # (idx, req, links, wl, t1, t2, surplus_kb)
        by_demand = {}
        for req in instance.requests:
            by_demand[req.id] = []
            for links, length in candidate_paths(graph, req.src, req.dst,
                                                 k_paths):
                if not model.feasible(length):
                    continue
                for n in range(1, max_slots + 1):
                    keys = model.tp_keys_kb(length, n, slot_s)
                    if keys + 1e-9 < req.volume_kb:
                        continue
                    surplus = keys - req.volume_kb
                    for start in range(1, req.deadline_slot - n + 2):
                        for wl in range(instance.wavelengths):
                            idx = len(options)
                            options.append((idx, req, links, wl, start,
                                            start + n - 1, surplus))
                            by_demand[req.id].append(idx)

        prob = pulp.LpProblem("qkd_p1", pulp.LpMaximize)
        x = {o[0]: pulp.LpVariable(f"x_{o[0]}", cat="Binary") for o in options}

        # objective: served + 1e-6 * surplus
        prob += pulp.lpSum(x[o[0]] * (1.0 + 1e-6 * max(o[6], 0.0))
                           for o in options)

        # one option per demand
        for rid, idxs in by_demand.items():
            if idxs:
                prob += pulp.lpSum(x[i] for i in idxs) <= 1

        # wavelength exclusivity and module capacity
        wl_slots = {}   # (link, wl, slot) -> [idx]
        mod_slots = {}  # (node, slot) -> [idx]
        for idx, req, links, wl, t1, t2, _ in options:
            for slot in range(t1, t2 + 1):
                for link in links:
                    wl_slots.setdefault((link, wl, slot), []).append(idx)
                    for node in link:
                        mod_slots.setdefault((node, slot), []).append(idx)
        for key, idxs in wl_slots.items():
            if len(idxs) > 1:
                prob += pulp.lpSum(x[i] for i in idxs) <= 1
        for (node, slot), idxs in mod_slots.items():
            cap = instance.modules.get(node, default_modules)
            prob += pulp.lpSum(x[i] for i in idxs) <= cap

        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)
        prob.solve(solver)

        status = pulp.LpStatus[prob.status]
        if status == "Infeasible":
            return Solution(algorithm=self.name, assignments=[],
                            extras={"solver_status": "proven_infeasible"})

        chosen = []
        for idx, req, links, wl, t1, t2, _ in options:
            if x[idx].value() is not None and x[idx].value() > 0.5:
                chosen.append(Assignment(request_id=req.id, route=links,
                                         wavelength=wl, tp_start=t1,
                                         tp_end=t2))
        extras = {"solver_status": status.lower(),
                  "num_options": len(options)}
        if status != "Optimal":
            extras["note"] = "time/'node' limit — solution may be suboptimal"
        return Solution(algorithm=self.name, assignments=chosen, extras=extras)
