"""Earliest-deadline-first shortest-path greedy baseline.

The simplest sensible baseline, and the reference example of how to write
an algorithm for qkdbench (one file, one class, one decorator):

* sort requests by deadline (EDF), then by volume (big first);
* for each request, scan its k shortest simple paths (by length);
* on each path, find the cheapest feasible TP: the fewest slots whose
  finite-size key yield covers the volume, placed at the earliest start
  slot where a wavelength is free on every link and both endpoints of
  every link still have a QKD module available;
* first fit wins; unservable requests are skipped.
"""
from __future__ import annotations

from itertools import islice

import networkx as nx

from ..core.algorithm import Algorithm, register_algorithm
from ..core.instance import Instance, edge_key
from ..core.solution import Assignment, Solution
from ..scenario.qkd_models import get_qkd_model


@register_algorithm
class GreedyShortestPath(Algorithm):
    """EDF + shortest-path first-fit greedy (baseline ``greedy_sp``)."""

    name = "greedy_sp"

    def solve(self, instance: Instance) -> Solution:
        k_paths = self.params.get("k_paths", 3)
        table = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        g = instance.graph()
        default_modules = instance.metadata.get("default_modules", 2)

        wl_used = set()    # (link, wavelength, slot)
        mod_used = {}      # (node, slot) -> count

        def modules_free(link, slot, extra):
            """Can `link` go active in `slot` given `extra` pending uses?"""
            for node in link:
                cap = instance.modules.get(node, default_modules)
                if mod_used.get((node, slot), 0) + extra.get((node, slot), 0) + 1 > cap:
                    return False
            return True

        assignments = []
        order = sorted(instance.requests,
                       key=lambda r: (r.deadline_slot, -r.volume_kb))
        for req in order:
            placed = self._place(req, g, instance, table, k_paths,
                                 wl_used, mod_used, modules_free)
            if placed is not None:
                assignments.append(placed)

        return Solution(algorithm=self.name, assignments=assignments)

    def _place(self, req, g, instance, table, k_paths,
               wl_used, mod_used, modules_free):
        try:
            paths = islice(
                nx.shortest_simple_paths(g, req.src, req.dst,
                                         weight="length_km"),
                k_paths)
            paths = list(paths)
        except nx.NetworkXNoPath:
            return None

        max_tau = int(min(table.max_tau_s / instance.slot_seconds,
                          instance.num_slots))
        for path in paths:
            links = [edge_key(a, b) for a, b in zip(path, path[1:])]
            length = sum(instance.edges[l] for l in links)
            if not table.feasible(length):
                continue  # beyond the QKD model's reach
            for n_slots in range(1, max_tau + 1):
                keys = table.tp_keys_kb(length, n_slots,
                                        instance.slot_seconds)
                if keys + 1e-9 < req.volume_kb:
                    continue  # too few slots at this distance
                latest_start = req.deadline_slot - n_slots + 1
                for start in range(1, latest_start + 1):
                    slots = range(start, start + n_slots)
                    for wl in range(instance.wavelengths):
                        if self._fits(links, wl, slots, instance,
                                      wl_used, mod_used, modules_free):
                            self._commit(links, wl, slots, wl_used, mod_used)
                            return Assignment(
                                request_id=req.id, route=links,
                                wavelength=wl, tp_start=start,
                                tp_end=start + n_slots - 1)
                break  # more slots only cost more; try next path
        return None

    @staticmethod
    def _fits(links, wl, slots, instance, wl_used, mod_used, modules_free):
        for slot in slots:
            extra = {}
            for link in links:
                if (link, wl, slot) in wl_used:
                    return False
                if not modules_free(link, slot, extra):
                    return False
                for node in link:
                    extra[(node, slot)] = extra.get((node, slot), 0) + 1
        return True

    @staticmethod
    def _commit(links, wl, slots, wl_used, mod_used):
        for slot in slots:
            for link in links:
                wl_used.add((link, wl, slot))
                for node in link:
                    mod_used[(node, slot)] = mod_used.get((node, slot), 0) + 1
