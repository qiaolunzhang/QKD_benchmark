"""Independent feasibility verifier.

This module is the credibility core of the benchmark: *every* solution —
whether produced by a bundled baseline or a third-party algorithm — is
checked against the same constraint set before its metrics are recorded.
Algorithms never grade their own homework.

Checked constraints (problem v0.1, see :mod:`qkdbench.core.solution`):

1.  Each request is served at most once, and its id exists.
2.  Routes are simple connected paths between the request endpoints, using
    only edges of the instance.
3.  TP interval is within the horizon and ends by the request deadline.
4.  Wavelength capacity: a (link, wavelength, slot) is used by at most one
    TP.
5.  Module capacity: per node and slot, the number of active incident
    route-links does not exceed the node's QKD modules.
6.  Key sufficiency: the TP delivers at least the requested volume
    (per the QKD model of the instance).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .instance import Instance, edge_key
from .solution import Solution
from ..scenario.qkd_models import get_qkd_model


@dataclass
class Verdict:
    ok: bool
    violations: List[str] = field(default_factory=list)

    def __bool__(self):
        return self.ok


def route_length_km(instance: Instance, route) -> float:
    return sum(instance.edges[edge_key(*link)] for link in route)


def verify(instance: Instance, solution: Solution) -> Verdict:
    """Check ``solution`` against ``instance``; returns all violations.

    Delegates to the ``static_routing_rra`` problem's composed constraint
    modules (:mod:`qkdbench.problems.constraints`).  The standalone
    :func:`_reference_verify` below is a frozen copy of the original
    monolithic checker, kept only so ``tests/test_problem_equiv.py`` can
    prove the composed version is bit-identical.
    """
    from ..problems.base import get_problem
    return get_problem("static_routing_rra").verify(instance, solution)


def _reference_verify(instance: Instance, solution: Solution) -> Verdict:
    """Frozen monolithic verifier (differential-test reference only)."""
    v: List[str] = []
    table = get_qkd_model(instance.rate_table, **instance.qkd_model_params)
    req_ids = {r.id for r in instance.requests}
    default_modules = instance.metadata.get("default_modules", 2)

    seen = set()
    wl_usage = {}      # (link, wavelength, slot) -> request_id
    mod_usage = {}     # (node, slot) -> count

    for a in solution.assignments:
        tag = f"request {a.request_id}"

        # 1. request exists / served once
        if a.request_id not in req_ids:
            v.append(f"{tag}: unknown request id")
            continue
        if a.request_id in seen:
            v.append(f"{tag}: served more than once")
            continue
        seen.add(a.request_id)
        req = instance.request_by_id(a.request_id)

        # 2. route is a simple path src--dst over instance edges
        route = [edge_key(*link) for link in a.route]
        if not route:
            v.append(f"{tag}: empty route")
            continue
        bad_edge = [e for e in route if e not in instance.edges]
        if bad_edge:
            v.append(f"{tag}: route uses non-existent links {bad_edge}")
            continue
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

        # 3. TP interval within horizon and deadline
        if not (1 <= a.tp_start <= a.tp_end <= instance.num_slots):
            v.append(f"{tag}: TP [{a.tp_start},{a.tp_end}] outside horizon "
                     f"1..{instance.num_slots}")
            continue
        if a.tp_end > req.deadline_slot:
            v.append(f"{tag}: TP ends at slot {a.tp_end} after deadline "
                     f"{req.deadline_slot}")

        # 4./5. resource bookkeeping
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
                for node in link:
                    mod_usage[(node, slot)] = mod_usage.get((node, slot), 0) + 1

        # 6. key sufficiency
        length = route_length_km(instance, route)
        try:
            keys = table.tp_keys_kb(length, a.n_slots, instance.slot_seconds)
        except KeyError as exc:
            v.append(f"{tag}: {exc}")
            keys = 0.0
        if keys + 1e-9 < req.volume_kb:
            v.append(f"{tag}: TP delivers {keys:.2f} kb < requested "
                     f"{req.volume_kb:.2f} kb "
                     f"(route {length:.1f} km, {a.n_slots} slots)")

    for (node, slot), used in sorted(mod_usage.items()):
        cap = instance.modules.get(node, default_modules)
        if used > cap:
            v.append(f"node {node}, slot {slot}: {used} active link-ends "
                     f"exceed {cap} QKD modules")

    return Verdict(ok=not v, violations=v)
