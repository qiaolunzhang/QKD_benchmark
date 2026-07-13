"""Trusted-relay placement algorithms (P3).

* ``greedy_placement`` — reverse greedy: start with every candidate node
  equipped (maximum coverage), then drop nodes whose removal still leaves
  every coverable demand covered, cheapest-to-keep last.  Always returns a
  feasible placement covering everything that any placement could cover.
* ``milp_placement`` — exact minimum-cost placement via a node-activation
  multi-commodity-flow MILP (CBC): route one unit of flow per demand over
  QKD-feasible links, a link is usable only if both endpoints are active
  (an endpoint user, or a paid relay ``y_v = 1``); minimise total relay
  cost.
"""
from __future__ import annotations

from ..core.algorithm import Algorithm, register_algorithm
from ..core.errors import QKDBenchError
from ..core.instance import edge_key
from ..core.solution import Solution
from ..scenario.qkd_models import get_qkd_model
from ..problems.placement import (covered_demands, user_nodes,
                                  feasible_link_graph, install_cost)

try:
    import pulp
    _HAVE_PULP = True
except ImportError:                      # pragma: no cover
    _HAVE_PULP = False


@register_algorithm
class GreedyPlacement(Algorithm):
    """Reverse-greedy minimum-cost trusted-relay placement."""

    name = "greedy_placement"

    def solve(self, instance) -> Solution:
        model = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        endpoints = user_nodes(instance)
        candidates = [n for n in instance.nodes if n not in endpoints]
        target = covered_demands(instance, model,
                                 set(candidates) | endpoints)

        placement = set(candidates)
        # drop the most expensive removable nodes first
        for node in sorted(candidates,
                           key=lambda n: -install_cost(instance, n)):
            trial = placement - {node}
            if covered_demands(instance, model, trial | endpoints) >= target:
                placement = trial
        return Solution(algorithm=self.name, placement=sorted(placement),
                        extras={"coverable": len(target),
                                "total_demands": len(instance.demands)})


@register_algorithm
class MilpPlacement(Algorithm):
    """Exact minimum-cost placement (node-activation flow MILP, CBC)."""

    name = "milp_placement"

    def solve(self, instance) -> Solution:
        if not _HAVE_PULP:
            raise QKDBenchError(
                "milp_placement needs PuLP/CBC — install with "
                '`pip install "qkdbench[ilp]"`')
        time_limit = self.params.get("time_limit_s", 300)
        model = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        fg = feasible_link_graph(instance, model)
        endpoints = user_nodes(instance)
        candidates = [n for n in instance.nodes if n not in endpoints]

        # only demands that are coverable at all get a flow constraint
        coverable = covered_demands(instance, model,
                                    set(candidates) | endpoints)
        demands = [d for d in instance.demands if d.id in coverable]

        prob = pulp.LpProblem("relay_placement", pulp.LpMinimize)
        y = {v: pulp.LpVariable(f"y_{v}", cat="Binary") for v in candidates}

        def active(v):
            return 1 if v in endpoints else y[v]

        # directed arcs over feasible links
        arcs = []
        for a, b in fg.edges():
            arcs.append((a, b))
            arcs.append((b, a))

        prob += pulp.lpSum(install_cost(instance, v) * y[v] for v in candidates)

        for d in demands:
            f = {arc: pulp.LpVariable(f"f_{d.id}_{arc[0]}_{arc[1]}",
                                      lowBound=0, upBound=1) for arc in arcs}
            # flow conservation
            for node in fg.nodes():
                out_f = pulp.lpSum(f[(node, w)] for w in fg[node])
                in_f = pulp.lpSum(f[(w, node)] for w in fg[node])
                if node == d.src:
                    prob += out_f - in_f == 1
                elif node == d.dst:
                    prob += out_f - in_f == -1
                else:
                    prob += out_f - in_f == 0
            # a link is usable only if both endpoints are active
            for (a, b) in arcs:
                prob += f[(a, b)] <= active(a)
                prob += f[(a, b)] <= active(b)

        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)
        prob.solve(solver)
        status = pulp.LpStatus[prob.status]
        placement = sorted(v for v in candidates
                           if y[v].value() and y[v].value() > 0.5)
        return Solution(algorithm=self.name, placement=placement,
                        extras={"solver_status": status.lower(),
                                "coverable": len(coverable)})
