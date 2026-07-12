"""P1 constraint modules — the verifier, split into composable checks.

Each module reproduces exactly one facet of the original monolithic
verifier, with the same violation messages, so composing them yields a
bit-identical verdict (guaranteed by ``tests/test_problem_equiv.py``,
which differentials this against a frozen copy of the old verifier).

Shared gating mirrors the original's ``continue`` semantics: an
assignment is *admissible* for the resource/key checks only if its
request id is known, it is the first assignment for that id, its route is
non-empty and uses existing links, and (for wavelength/module/key checks)
its TP lies within the horizon.
"""
from __future__ import annotations

from typing import List

from ..core.instance import Instance, edge_key
from ..core.solution import Solution
from ..core.registry import registry
from ..scenario.qkd_models import get_qkd_model
from .base import ConstraintModule


def _default_modules(instance):
    return instance.metadata.get("default_modules", 2)


def _route_edges(assignment):
    return [edge_key(*link) for link in assignment.route]


def _iter_known_first(instance, solution):
    """Yield (assignment, route_edges) for known-id, first-seen,
    non-empty, existing-link assignments (gates 1-4 of the original)."""
    req_ids = {r.id for r in instance.requests}
    seen = set()
    for a in solution.assignments:
        if a.request_id not in req_ids or a.request_id in seen:
            continue
        seen.add(a.request_id)
        route = _route_edges(a)
        if not route:
            continue
        if any(e not in instance.edges for e in route):
            continue
        yield a, route


def _tp_in_horizon(instance, a):
    return 1 <= a.tp_start <= a.tp_end <= instance.num_slots


@registry.register("constraint", "serve_once")
class ServeOnce(ConstraintModule):
    name = "serve_once"
    requires = frozenset({"solution.routing"})

    def check(self, instance, solution) -> List[str]:
        v, seen = [], set()
        req_ids = {r.id for r in instance.requests}
        for a in solution.assignments:
            tag = f"request {a.request_id}"
            if a.request_id not in req_ids:
                v.append(f"{tag}: unknown request id")
                continue
            if a.request_id in seen:
                v.append(f"{tag}: served more than once")
                continue
            seen.add(a.request_id)
        return v


@registry.register("constraint", "route_validity")
class RouteValidity(ConstraintModule):
    name = "route_validity"
    requires = frozenset({"solution.routing"})
    provides = frozenset({"single_path"})

    def check(self, instance, solution) -> List[str]:
        v = []
        req_ids = {r.id for r in instance.requests}
        seen = set()
        for a in solution.assignments:
            tag = f"request {a.request_id}"
            if a.request_id not in req_ids or a.request_id in seen:
                continue
            seen.add(a.request_id)
            route = _route_edges(a)
            if not route:
                v.append(f"{tag}: empty route")
                continue
            bad = [e for e in route if e not in instance.edges]
            if bad:
                v.append(f"{tag}: route uses non-existent links {bad}")
                continue
            req = instance.request_by_id(a.request_id)
            nodes = a.route_nodes()
            if len(set(nodes)) != len(nodes):
                v.append(f"{tag}: route is not a simple path ({nodes})")
            if {nodes[0], nodes[-1]} != {req.src, req.dst}:
                v.append(f"{tag}: route connects {nodes[0]}--{nodes[-1]}, "
                         f"request is {req.src}--{req.dst}")
            for i, link in enumerate(route):
                if set(link) != {nodes[i], nodes[i + 1]}:
                    v.append(f"{tag}: route links do not form a chain")
                    break
        return v


@registry.register("constraint", "tp_window")
class TpWindow(ConstraintModule):
    name = "tp_window"
    requires = frozenset({"solution.routing"})

    def check(self, instance, solution) -> List[str]:
        v = []
        for a, _ in _iter_known_first(instance, solution):
            tag = f"request {a.request_id}"
            if not _tp_in_horizon(instance, a):
                v.append(f"{tag}: TP [{a.tp_start},{a.tp_end}] outside "
                         f"horizon 1..{instance.num_slots}")
                continue
            req = instance.request_by_id(a.request_id)
            if a.tp_end > req.deadline_slot:
                v.append(f"{tag}: TP ends at slot {a.tp_end} after deadline "
                         f"{req.deadline_slot}")
        return v


@registry.register("constraint", "wavelength_capacity")
class WavelengthCapacity(ConstraintModule):
    name = "wavelength_capacity"
    requires = frozenset({"solution.routing", "link.wavelengths"})

    def check(self, instance, solution) -> List[str]:
        v = []
        wl_usage = {}
        for a, route in _iter_known_first(instance, solution):
            if not _tp_in_horizon(instance, a):
                continue
            tag = f"request {a.request_id}"
            if not (0 <= a.wavelength < instance.wavelengths):
                v.append(f"{tag}: wavelength {a.wavelength} out of range "
                         f"0..{instance.wavelengths - 1}")
            for slot in range(a.tp_start, a.tp_end + 1):
                for link in route:
                    key = (link, a.wavelength, slot)
                    if key in wl_usage:
                        v.append(f"{tag}: wavelength clash with request "
                                 f"{wl_usage[key]} on link {link}, "
                                 f"wl {a.wavelength}, slot {slot}")
                    else:
                        wl_usage[key] = a.request_id
        return v


@registry.register("constraint", "module_capacity")
class ModuleCapacity(ConstraintModule):
    name = "module_capacity"
    requires = frozenset({"solution.routing", "node.device_slots"})

    def check(self, instance, solution) -> List[str]:
        v = []
        mod_usage = {}
        for a, route in _iter_known_first(instance, solution):
            if not _tp_in_horizon(instance, a):
                continue
            for slot in range(a.tp_start, a.tp_end + 1):
                for link in route:
                    for node in link:
                        mod_usage[(node, slot)] = \
                            mod_usage.get((node, slot), 0) + 1
        default = _default_modules(instance)
        for (node, slot), used in sorted(mod_usage.items()):
            cap = instance.modules.get(node, default)
            if used > cap:
                v.append(f"node {node}, slot {slot}: {used} active link-ends "
                         f"exceed {cap} QKD modules")
        return v


@registry.register("constraint", "key_sufficiency")
class KeySufficiency(ConstraintModule):
    name = "key_sufficiency"
    requires = frozenset({"solution.routing", "demand.volume_kb"})

    def check(self, instance, solution) -> List[str]:
        v = []
        model = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        for a, route in _iter_known_first(instance, solution):
            if not _tp_in_horizon(instance, a):
                continue
            tag = f"request {a.request_id}"
            req = instance.request_by_id(a.request_id)
            length = sum(instance.edges[e] for e in route)
            try:
                keys = model.tp_keys_kb(length, a.n_slots,
                                        instance.slot_seconds)
            except KeyError as exc:
                v.append(f"{tag}: {exc}")
                keys = 0.0
            if keys + 1e-9 < req.volume_kb:
                v.append(f"{tag}: TP delivers {keys:.2f} kb < requested "
                         f"{req.volume_kb:.2f} kb "
                         f"(route {length:.1f} km, {a.n_slots} slots)")
        return v


#: constraint module order for the P1 preset (matches original verifier)
P1_CONSTRAINTS = ["serve_once", "route_validity", "tp_window",
                  "wavelength_capacity", "module_capacity", "key_sufficiency"]
