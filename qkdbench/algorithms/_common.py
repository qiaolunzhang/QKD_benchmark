"""Shared building blocks for the P1 routing/wavelength/TP algorithms.

Every P1 heuristic makes the same three physical/resource decisions per
served request — a route, a wavelength, a transmission-period (TP)
interval — subject to the same bookkeeping the verifier enforces
(wavelength exclusivity per (link, wl, slot) and QKD-module capacity per
(node, slot)).  Rather than copy that bookkeeping into every algorithm,
they share it here:

* :class:`ResourceLedger` — tracks wavelength and module occupancy and
  answers "does this (links, wl, slots) placement fit?".
* :func:`candidate_paths` — the k shortest simple paths of a demand.
* :func:`min_slots_for` — fewest TP slots whose finite-size key yield
  covers a demand's volume on a given route (``None`` if unreachable).
* :func:`greedy_construct` — the generic EDF/first-fit constructor that
  ``key_aware_sp`` and ``fse_greedy`` (and, via them, ``local_search``)
  specialise through a path-ranking and a request-ordering callback.

Physics is reached only through the instance's QKD model
(``get_qkd_model``); no key-rate formula ever appears here.
"""
from __future__ import annotations

from itertools import islice
from typing import Callable, List, Optional

import networkx as nx

from ..core.instance import Instance, edge_key
from ..core.solution import Assignment


class ResourceLedger:
    """Wavelength and QKD-module occupancy, matching the verifier's rules."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.default_modules = instance.metadata.get("default_modules", 2)
        self.wl_used = set()     # (link, wavelength, slot)
        self.mod_used = {}       # (node, slot) -> active link-ends

    def copy(self) -> "ResourceLedger":
        other = ResourceLedger(self.instance)
        other.wl_used = set(self.wl_used)
        other.mod_used = dict(self.mod_used)
        return other

    def fits(self, links, wl, slots) -> bool:
        """Can ``links`` use wavelength ``wl`` over ``slots`` right now?"""
        for slot in slots:
            extra = {}
            for link in links:
                if (link, wl, slot) in self.wl_used:
                    return False
                for node in link:
                    cap = self.instance.modules.get(node, self.default_modules)
                    pending = extra.get((node, slot), 0)
                    if self.mod_used.get((node, slot), 0) + pending + 1 > cap:
                        return False
                for node in link:
                    extra[(node, slot)] = extra.get((node, slot), 0) + 1
        return True

    def commit(self, links, wl, slots) -> None:
        for slot in slots:
            for link in links:
                self.wl_used.add((link, wl, slot))
                for node in link:
                    self.mod_used[(node, slot)] = \
                        self.mod_used.get((node, slot), 0) + 1

    def release(self, assignment: Assignment) -> None:
        """Undo a committed assignment (used by local search evictions)."""
        links = [edge_key(*l) for l in assignment.route]
        for slot in range(assignment.tp_start, assignment.tp_end + 1):
            for link in links:
                self.wl_used.discard((link, assignment.wavelength, slot))
                for node in link:
                    key = (node, slot)
                    if self.mod_used.get(key):
                        self.mod_used[key] -= 1


def candidate_paths(graph, src, dst, k_paths: int):
    """Up to ``k_paths`` shortest simple paths as ``(links, length_km)``."""
    try:
        paths = list(islice(
            nx.shortest_simple_paths(graph, src, dst, weight="length_km"),
            k_paths))
    except nx.NetworkXNoPath:
        return []
    out = []
    for path in paths:
        links = [edge_key(a, b) for a, b in zip(path, path[1:])]
        length = sum(graph[a][b]["length_km"] for a, b in zip(path, path[1:]))
        out.append((links, length))
    return out


def min_slots_for(model, length_km, volume_kb, max_slots,
                  slot_seconds) -> Optional[int]:
    """Fewest TP slots whose key yield covers ``volume_kb`` (or ``None``)."""
    if not model.feasible(length_km):
        return None
    for n in range(1, max_slots + 1):
        if model.tp_keys_kb(length_km, n, slot_seconds) + 1e-9 >= volume_kb:
            return n
    return None


def max_feasible_slots(instance, model) -> int:
    """Longest TP (slots) the horizon and the model both allow."""
    return int(min(model.max_tau_s / instance.slot_seconds,
                   instance.num_slots))


def place_min_tp(req, cands, instance, model, ledger, max_slots) -> \
        Optional[Assignment]:
    """First-fit placement using the *smallest* TP that serves ``req``.

    ``cands`` is a pre-ranked list of ``(links, length_km)``; the first
    route + earliest start + lowest free wavelength that fits wins.  This
    is the resource-frugal placement shared by the greedy baselines.
    """
    for links, length in cands:
        n = min_slots_for(model, length, req.volume_kb, max_slots,
                          instance.slot_seconds)
        if n is None:
            continue
        latest_start = req.deadline_slot - n + 1
        for start in range(1, latest_start + 1):
            slots = range(start, start + n)
            for wl in range(instance.wavelengths):
                if ledger.fits(links, wl, slots):
                    ledger.commit(links, wl, slots)
                    return Assignment(request_id=req.id, route=links,
                                      wavelength=wl, tp_start=start,
                                      tp_end=start + n - 1)
    return None


def greedy_construct(instance, model, order_key, rank_paths, k_paths,
                     ledger=None) -> List[Assignment]:
    """Generic EDF/first-fit constructor.

    Args:
        order_key: sort key over demands (processing order).
        rank_paths: ``(req, cands) -> reordered cands`` — how a demand
            chooses among its shortest paths.
        ledger: reuse an existing ledger (local search) or start fresh.
    """
    graph = instance.graph()
    ledger = ledger or ResourceLedger(instance)
    max_slots = max_feasible_slots(instance, model)
    out = []
    for req in sorted(instance.requests, key=order_key):
        cands = candidate_paths(graph, req.src, req.dst, k_paths)
        if not cands:
            continue
        cands = rank_paths(req, cands)
        placed = place_min_tp(req, cands, instance, model, ledger, max_slots)
        if placed is not None:
            out.append(placed)
    return out


def extend_for_surplus(assignments, instance, model, ledger) -> None:
    """Grow each served TP into free earlier slots to raise surplus keys.

    Serving is already decided; this only lengthens existing TPs where
    the wavelength and modules stay free, so ``served`` never changes and
    delivered keys only increase (the finite-size rate rises with TP
    length).  Mutates ``assignments`` and ``ledger`` in place.
    """
    max_slots = max_feasible_slots(instance, model)
    for i, a in enumerate(assignments):
        links = [edge_key(*l) for l in a.route]
        req = instance.request_by_id(a.request_id)
        best = a
        cur_slots = a.n_slots
        # try longer TPs (up to horizon/deadline), extending the start
        # earlier; keep the longest that still fits once the current TP
        # is released.
        for n in range(max_slots, cur_slots, -1):
            if n > req.deadline_slot:
                continue
            ledger.release(a)
            placed = None
            latest_start = req.deadline_slot - n + 1
            for start in range(1, latest_start + 1):
                slots = range(start, start + n)
                if ledger.fits(links, a.wavelength, slots):
                    placed = Assignment(request_id=a.request_id, route=a.route,
                                        wavelength=a.wavelength, tp_start=start,
                                        tp_end=start + n - 1)
                    break
            if placed is not None:
                ledger.commit(links, a.wavelength,
                              range(placed.tp_start, placed.tp_end + 1))
                best = placed
                break
            ledger.commit(links, a.wavelength,
                          range(a.tp_start, a.tp_end + 1))  # restore
        assignments[i] = best
