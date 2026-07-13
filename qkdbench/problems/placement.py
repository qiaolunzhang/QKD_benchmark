"""Trusted-relay placement problem (P3) modules.

QKD has a hard distance limit, so a long connection must be split into
QKD-reachable hops by *trusted relays* — intermediate nodes equipped with
QKD devices that receive and re-encrypt keys.  P3 asks for a minimum-cost
set of relay nodes such that every demand pair is connected by a path
whose links are all QKD-reachable and whose intermediate nodes are all
equipped.

Users (the demand endpoints) are always equipped and cost nothing; the
placement decision is over the other candidate nodes.  A single shared
:func:`covered_demands` routine backs both the algorithms and the
verifier, so they judge coverage identically.
"""
from __future__ import annotations

from typing import List, Set

import networkx as nx

from ..core.registry import registry
from ..scenario.qkd_models import get_qkd_model
from .base import ConstraintModule, DecisionModule, ObjectiveModule, Problem


def demand_endpoints(instance) -> Set[str]:
    """Nodes that are the source or destination of some demand."""
    ends = set()
    for d in instance.demands:
        ends.add(d.src)
        ends.add(d.dst)
    return ends


def user_nodes(instance) -> Set[str]:
    """Always-equipped user nodes (free, implicitly active).

    Taken from ``metadata['users']`` when the instance declares them;
    otherwise every demand endpoint is treated as a user."""
    users = instance.metadata.get("users")
    return set(users) if users else demand_endpoints(instance)


def feasible_link_graph(instance, model) -> nx.Graph:
    """Graph of only the QKD-reachable links (a link a QKD hop can span)."""
    g = nx.Graph()
    g.add_nodes_from(instance.nodes)
    for (a, b), length in instance.edges.items():
        if model.feasible(length):
            g.add_edge(a, b)
    return g


def covered_demands(instance, model, active_nodes) -> Set[int]:
    """Ids of demands connectable through ``active_nodes``.

    A demand (s, t) is covered iff s and t are connected in the
    feasible-link graph restricted to ``active_nodes`` together with s and
    t themselves (every intermediate hop node must be active)."""
    fg = feasible_link_graph(instance, model)
    active = set(active_nodes)
    covered = set()
    for d in instance.demands:
        allowed = active | {d.src, d.dst}
        sub = fg.subgraph(allowed)
        if d.src in sub and d.dst in sub and \
                nx.has_path(sub, d.src, d.dst):
            covered.add(d.id)
    return covered


def install_cost(instance, node) -> float:
    return instance.metadata.get("install_costs", {}).get(node, 1.0)


# ----------------------------------------------------------- decisions
@registry.register("decision", "relay_placement")
class RelayPlacement(DecisionModule):
    name = "relay_placement"
    solution_component = "placement"
    requires = frozenset({"node.install_cost"})
    provides = frozenset({"placement"})


# ---------------------------------------------------------- constraints
@registry.register("constraint", "placement_validity")
class PlacementValidity(ConstraintModule):
    name = "placement_validity"
    requires = frozenset({"solution.placement"})

    def check(self, instance, solution) -> List[str]:
        v = []
        node_ids = set(instance.nodes)
        seen = set()
        for n in solution.placement:
            if n not in node_ids:
                v.append(f"placement: node {n!r} does not exist")
            if n in seen:
                v.append(f"placement: node {n!r} listed more than once")
            seen.add(n)
        return v


@registry.register("constraint", "demand_coverage")
class DemandCoverage(ConstraintModule):
    name = "demand_coverage"
    requires = frozenset({"solution.placement", "demand.src"})

    def check(self, instance, solution) -> List[str]:
        model = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        active = set(solution.placement) | user_nodes(instance)
        covered = covered_demands(instance, model, active)
        v = []
        for d in instance.demands:
            if d.id not in covered:
                v.append(f"demand {d.id} ({d.src}->{d.dst}) not covered by "
                         f"the trusted-relay placement")
        return v


# ----------------------------------------------------------- objectives
@registry.register("objective", "deployment_cost")
class DeploymentCost(ObjectiveModule):
    name = "deployment_cost"
    sense = "min"
    requires = frozenset({"solution.placement"})

    def value(self, instance, solution) -> float:
        return round(sum(install_cost(instance, n)
                         for n in solution.placement), 6)


@registry.register("objective", "num_relays")
class NumRelays(ObjectiveModule):
    name = "num_relays"
    sense = "min"
    requires = frozenset({"solution.placement"})

    def value(self, instance, solution) -> float:
        return float(len(set(solution.placement)))


P3_DECISIONS = ["relay_placement"]
P3_CONSTRAINTS = ["placement_validity", "demand_coverage"]
P3_OBJECTIVES = ["deployment_cost", "num_relays"]


@registry.register("problem", "trusted_relay_placement")
def trusted_relay_placement(**params) -> Problem:
    """Minimum-cost trusted-relay placement (P3)."""
    build = lambda kind, names: [registry.get(kind, n)() for n in names]
    return Problem(
        name="trusted_relay_placement",
        decisions=build("decision", P3_DECISIONS),
        constraints=build("constraint", P3_CONSTRAINTS),
        objectives=build("objective", P3_OBJECTIVES),
        params=params,
    )
