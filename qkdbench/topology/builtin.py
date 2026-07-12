"""Built-in topologies.

Small, well-studied networks to start from.  Each factory returns
``(nodes, edges)`` with ``edges = {(a, b): length_km}`` and string node
names, ready to drop into an :class:`~qkdbench.core.instance.Instance`.

Provenance:

* ``triangle`` / ``poliqi5`` / ``german7`` follow the RCKTA-FSE line of
  work (INFOCOM'27); German-7 is the 7-node German backbone with 11 links
  whose lengths are drawn U[2, 8] km per seed, keeping the whole
  finite-size reach table in play.
"""
from __future__ import annotations

import random

from ..core.instance import edge_key

_GERMAN7_LINKS = [(1, 2), (1, 7), (2, 3), (2, 6), (2, 7), (3, 4), (3, 6),
                  (4, 5), (4, 6), (5, 6), (6, 7)]


def triangle(length_km: float = 5.0):
    """3-node complete graph."""
    nodes = ["1", "2", "3"]
    edges = {edge_key(a, b): length_km
             for a, b in [(1, 2), (1, 3), (2, 3)]}
    return nodes, edges


def poliqi5(length_km: float = 5.0):
    """PoliQi 5-node ring (Politecnico di Milano testbed layout)."""
    nodes = [str(n) for n in range(1, 6)]
    ring = [(1, 2), (2, 3), (3, 4), (4, 5), (1, 5)]
    edges = {edge_key(a, b): length_km for a, b in ring}
    return nodes, edges


def german7(seed: int = 0, lo_km: float = 2.0, hi_km: float = 8.0):
    """7-node German backbone, 11 links, lengths U[lo, hi] km per seed."""
    rng = random.Random(2000 + seed)   # same convention as INFOCOM'27
    nodes = [str(n) for n in range(1, 8)]
    edges = {edge_key(a, b): round(rng.uniform(lo_km, hi_km), 2)
             for a, b in _GERMAN7_LINKS}
    return nodes, edges


TOPOLOGIES = {
    "triangle": triangle,
    "poliqi5": poliqi5,
    "german7": german7,
}


def get_topology(name: str, **kwargs):
    if name not in TOPOLOGIES:
        raise KeyError(f"unknown topology {name!r}; "
                       f"available: {sorted(TOPOLOGIES)}")
    return TOPOLOGIES[name](**kwargs)
