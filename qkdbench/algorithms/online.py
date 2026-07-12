"""Online-algorithm interface and the ``greedy_admission`` baseline (P2).

An :class:`OnlineAlgorithm` makes irrevocable per-arrival decisions rather
than seeing the whole instance at once.  It plugs into the same benchmark
pipeline as offline algorithms: its ``solve(instance)`` runs the event
simulator (:mod:`qkdbench.scenario.simulator`), which calls back into
``act`` for each arriving demand, and returns the standard
:class:`~qkdbench.core.solution.Solution` (populated via ``admissions``).

Integrating a new online policy = subclass, implement ``act``.
"""
from __future__ import annotations

from itertools import islice

import networkx as nx

from ..core.algorithm import Algorithm, register_algorithm
from ..core.instance import edge_key
from ..core.solution import Solution
from ..scenario.simulator import simulate


class OnlineAlgorithm(Algorithm):
    """Base class for dynamic admission controllers.

    Subclasses implement :meth:`act`; ``reset`` and ``finalize`` are
    optional hooks.  ``solve`` wires the controller to the simulator so
    the runner treats online and offline algorithms identically.
    """

    capabilities = {"dynamic", "online"}

    def reset(self, instance):
        self.instance = instance

    def act(self, demand, state):
        """Return a route (list of links) to admit ``demand`` on, or
        ``None`` to reject.  ``state`` exposes ``headroom(link)`` and
        ``path_fits(route, rate)``."""
        raise NotImplementedError

    def finalize(self) -> Solution:
        return Solution(algorithm=self.name)

    def solve(self, instance) -> Solution:
        return simulate(instance, self)


@register_algorithm
class GreedyAdmission(OnlineAlgorithm):
    """Admit on the first shortest path with enough key-rate headroom.

    For each arriving demand, scan its k shortest paths (by length) and
    admit on the first whose every link still has spare generation rate to
    carry the demand's required rate; otherwise block.  This is the
    natural online baseline for P2 — the dynamic analogue of
    ``greedy_sp``.
    """

    name = "greedy_admission"

    def reset(self, instance):
        super().reset(instance)
        self.k_paths = self.params.get("k_paths", 3)
        self.graph = instance.graph()

    def act(self, demand, state):
        rate = demand.rate_kbps or 0.0
        try:
            paths = islice(
                nx.shortest_simple_paths(self.graph, demand.src, demand.dst,
                                         weight="length_km"),
                self.k_paths)
            paths = list(paths)
        except nx.NetworkXNoPath:
            return None
        for path in paths:
            route = [edge_key(a, b) for a, b in zip(path, path[1:])]
            if state.path_fits(route, rate):
                return route
        return None
