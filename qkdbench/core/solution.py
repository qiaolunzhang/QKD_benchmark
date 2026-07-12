"""Standard solution representation.

Every algorithm returns a :class:`Solution` — a set of per-request
:class:`Assignment` objects.  Keeping the schema algorithm-agnostic is what
lets the independent verifier (:mod:`qkdbench.core.verifier`) check any
solution against the same constraint set.

Problem semantics (v0.1, optical-bypass form of RCKTA-FSE):

* A served request gets one *transmission period* (TP): a route (simple
  path), a wavelength channel and a slot interval ``[tp_start, tp_end]``.
* During the TP the wavelength is occupied on every link of the route, and
  one QKD module is busy at each endpoint of every link of the route.
* The secret keys produced by the TP are given by the finite-size rate
  table: ``rate(route_length_km, tau) * tau`` with
  ``tau = (tp_end - tp_start + 1) * slot_seconds``.  Keys are delivered at
  the *end* of the TP, so serving the request needs
  ``tp_end <= deadline_slot`` and produced keys >= requested volume.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Tuple

from .instance import Edge


@dataclass
class Assignment:
    """The resources granted to one served request."""
    request_id: int
    route: List[Edge]          # links as sorted-endpoint tuples, in path order
    wavelength: int            # 0-based channel index, < instance.wavelengths
    tp_start: int              # first slot of the TP (1-based, inclusive)
    tp_end: int                # last slot of the TP (1-based, inclusive)

    @property
    def n_slots(self) -> int:
        return self.tp_end - self.tp_start + 1

    def route_nodes(self) -> List[str]:
        """Node sequence of the route (for display)."""
        if not self.route:
            return []
        nodes = []
        # orient the first link using the second one
        a, b = self.route[0]
        if len(self.route) > 1 and a in self.route[1]:
            a, b = b, a
        nodes += [a, b]
        for link in self.route[1:]:
            nxt = link[0] if link[1] == nodes[-1] else link[1]
            nodes.append(nxt)
        return nodes


@dataclass
class Solution:
    """What an algorithm hands back to the benchmark."""
    algorithm: str
    assignments: List[Assignment] = field(default_factory=list)
    extras: dict = field(default_factory=dict)   # algorithm-specific info

    @property
    def served_ids(self):
        return {a.request_id for a in self.assignments}

    def to_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "assignments": [asdict(a) for a in self.assignments],
            "extras": self.extras,
        }
