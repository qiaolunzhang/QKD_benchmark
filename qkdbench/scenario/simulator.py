"""Discrete-event simulator for the dynamic admission problem (P2).

The engine advances an event queue of demand arrivals and departures in
time order.  On each arrival it asks an online *controller* whether (and
where) to admit the demand; admitted demands hold their committed key
rate on every link of their route until they depart.

Two entry points share this one model so an algorithm and the verifier
never disagree:

* :func:`simulate` drives a controller and records its decisions as a
  :class:`~qkdbench.core.solution.Solution` (the online algorithm's
  output).
* :func:`replay_violations` independently re-runs a solution's recorded
  admissions and reports any that break the key-rate capacity of a link's
  pool — the verifier's P2 check.

v1 dynamics are rate-based (see :mod:`qkdbench.core.key_pool`): a link can
carry committed demands up to its pool generation rate ``gen_kbps``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from ..core.instance import Instance, edge_key
from ..core.solution import Admission, Solution


@dataclass
class ArrivalEvent:
    time: float
    demand_id: int


def link_gen_rates(instance: Instance) -> Dict[tuple, float]:
    """``{link: generation rate kb/s}`` from the instance's key pools."""
    return {edge_key(*p.link): p.gen_kbps for p in instance.key_pools}


class SimState:
    """Live committed-rate bookkeeping exposed to the online controller."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.gen = link_gen_rates(instance)
        self.committed: Dict[tuple, float] = {l: 0.0 for l in self.gen}
        self.now = 0.0

    def headroom(self, link) -> float:
        """Spare key rate on ``link`` (generation minus committed)."""
        link = edge_key(*link)
        return self.gen.get(link, 0.0) - self.committed.get(link, 0.0)

    def path_fits(self, route, rate) -> bool:
        return all(self.headroom(l) + 1e-9 >= rate for l in route)

    def _apply(self, route, rate):
        for l in route:
            l = edge_key(*l)
            self.committed[l] = self.committed.get(l, 0.0) + rate


def _event_order(instance):
    """Arrival events sorted by time, then demand id (deterministic)."""
    evs = [ArrivalEvent(d.arrival_t, d.id) for d in instance.demands]
    return sorted(evs, key=lambda e: (e.time, e.demand_id))


def simulate(instance: Instance, controller) -> Solution:
    """Run ``controller`` over the arrival stream; record its admissions.

    ``controller`` must expose ``reset(instance)`` and
    ``act(demand, state) -> route_or_None``.  Departures are handled
    internally (each admitted demand frees its rate at
    ``arrival_t + holding_t``).
    """
    controller.reset(instance)
    state = SimState(instance)
    by_id = {d.id: d for d in instance.demands}

    # departure heap as a simple sorted list of (time, demand_id, route, rate)
    active: List[tuple] = []
    admissions: List[Admission] = []

    def drain_departures(until):
        active.sort()
        while active and active[0][0] <= until + 1e-12:
            _, _, route, rate = active.pop(0)
            for l in route:
                l = edge_key(*l)
                state.committed[l] = max(0.0, state.committed.get(l, 0.0) - rate)

    for ev in _event_order(instance):
        drain_departures(ev.time)
        state.now = ev.time
        demand = by_id[ev.demand_id]
        route = controller.act(demand, state)
        if route:
            route = [edge_key(*l) for l in route]
            rate = demand.rate_kbps or 0.0
            state._apply(route, rate)
            depart = ev.time + (demand.holding_t or 0.0)
            active.append((depart, demand.id, route, rate))
            admissions.append(Admission(demand_id=demand.id, route=route,
                                        admit_t=ev.time))

    sol = controller.finalize() if hasattr(controller, "finalize") else None
    if sol is None:
        sol = Solution(algorithm=getattr(controller, "name", "online"))
    sol.admissions = admissions
    return sol


def replay_violations(instance: Instance, solution: Solution) -> List[str]:
    """Independently replay recorded admissions; return capacity/validity
    violations (the P2 verifier's core check)."""
    v: List[str] = []
    gen = link_gen_rates(instance)
    committed: Dict[tuple, float] = {l: 0.0 for l in gen}
    by_id = {d.id: d for d in instance.demands}
    admitted_ids = set()

    # interleave admits and departures in time order
    events = []
    for a in solution.admissions:
        d = by_id.get(a.demand_id)
        if d is None:
            v.append(f"admission {a.demand_id}: unknown demand id")
            continue
        events.append((a.admit_t, 0, a))                       # admit first
        events.append((a.admit_t + (d.holding_t or 0.0), 1, a))  # then depart
    events.sort(key=lambda e: (e[0], e[1], e[2].demand_id))

    for _, kind, a in events:
        d = by_id[a.demand_id]
        route = [edge_key(*l) for l in a.route]
        rate = d.rate_kbps or 0.0
        if kind == 0:   # admit
            tag = f"demand {a.demand_id}"
            if a.demand_id in admitted_ids:
                v.append(f"{tag}: admitted more than once")
                continue
            admitted_ids.add(a.demand_id)
            if abs(a.admit_t - (d.arrival_t or 0.0)) > 1e-9:
                v.append(f"{tag}: admitted at t={a.admit_t} != arrival "
                         f"t={d.arrival_t}")
            bad = [l for l in route if l not in instance.edges]
            if bad:
                v.append(f"{tag}: route uses non-existent links {bad}")
                continue
            for l in route:
                committed[l] = committed.get(l, 0.0) + rate
                if committed[l] > gen.get(l, 0.0) + 1e-6:
                    v.append(f"{tag}: link {l} committed rate "
                             f"{committed[l]:.3f} exceeds generation "
                             f"{gen.get(l, 0.0):.3f} kb/s")
        else:           # depart
            for l in route:
                committed[l] = max(0.0, committed.get(l, 0.0) - rate)
    return v
