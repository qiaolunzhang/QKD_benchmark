"""Synthetic topology generators: waxman / grid / ring /
random_geometric / barabasi_albert.

All generators are fully deterministic per seed; providers whose output
depends on randomness *require* a seed (fail loudly instead of silently
producing an unreproducible network).  Link lengths come from Euclidean
distances between node coordinates (all generators place nodes on a
plane measured in km) or from an explicit ``edge_km`` parameter.

The Waxman generator follows the INFOCOM'27 RCKTA-FSE port of the
Quantum-Source-Placement model: ``P(u,v) = delta * exp(-d / (epsilon *
L))``, disconnected components stitched by their nearest cross-component
pair, rng seeded ``random.Random(5000 + seed)``.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from ...core.network import Link, Network, Node
from ...core.registry import registry
from .base import TopologyProvider, euclidean_km


def _network(topology_id: str, node_ids: List[str],
             coords: Optional[Dict[str, Tuple[float, float]]],
             edges: Dict[Tuple[str, str], float], meta: dict) -> Network:
    nodes = [Node(id=n, coords=coords.get(n) if coords else None)
             for n in node_ids]
    links = [Link(id=f"{a}-{b}", endpoints=(a, b), length_km=km)
             for (a, b), km in sorted(edges.items())]
    return Network(topology_id=topology_id, topology_version="1.0",
                   nodes=nodes, links=links, metadata=meta)


def _require_seed(name: str, seed) -> int:
    if seed is None:
        raise ValueError(f"topology {name!r} is random: a seed is required")
    return int(seed)


def _ekey(a: int, b: int) -> Tuple[str, str]:
    a, b = str(a), str(b)
    return (a, b) if a <= b else (b, a)


@registry.register("topology", "waxman")
class WaxmanTopology(TopologyProvider):
    """Waxman random graph in a square area (km), stitched connected.

    Config: ``num_nodes`` (20), ``area_km`` (100), ``delta`` (0.8),
    ``epsilon`` (0.01), ``min_len`` (1.0).
    """

    name = "waxman"
    capabilities = {"synthetic", "seeded", "seeded_lengths", "geo_coords"}

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        seed = _require_seed(self.name, seed)
        n = int(config.get("num_nodes", 20))
        area = float(config.get("area_km", 100.0))
        delta = float(config.get("delta", 0.8))
        epsilon = float(config.get("epsilon", 0.01))
        min_len = float(config.get("min_len", 1.0))

        rng = random.Random(5000 + seed)
        pos = {i: (rng.uniform(0, area), rng.uniform(0, area))
               for i in range(1, n + 1)}

        def dist(a, b):
            return euclidean_km(pos[a], pos[b])

        pairs = [(a, b) for a in range(1, n + 1) for b in range(a + 1, n + 1)]
        L = max(dist(a, b) for a, b in pairs)
        adj = {i: set() for i in range(1, n + 1)}
        edges = {}
        for a, b in pairs:
            d = dist(a, b)
            if rng.random() <= delta * math.exp(-d / (epsilon * L)):
                edges[_ekey(a, b)] = round(max(d, min_len), 2)
                adj[a].add(b)
                adj[b].add(a)

        # stitch components with their nearest cross-component edge
        def components():
            seen, comps = set(), []
            for start in range(1, n + 1):
                if start in seen:
                    continue
                stack, comp = [start], set()
                while stack:
                    x = stack.pop()
                    if x in comp:
                        continue
                    comp.add(x)
                    seen.add(x)
                    stack.extend(adj[x] - comp)
                comps.append(comp)
            return comps

        comps = components()
        while len(comps) > 1:
            best, bd = None, float("inf")
            for i in range(len(comps)):
                for j in range(i + 1, len(comps)):
                    for u in comps[i]:
                        for v in comps[j]:
                            d = dist(u, v)
                            if d < bd:
                                bd, best = d, (u, v)
            u, v = best
            edges[_ekey(u, v)] = round(max(bd, min_len), 2)
            adj[u].add(v)
            adj[v].add(u)
            comps = components()

        coords = {str(i): pos[i] for i in pos}
        return _network(self.name, [str(i) for i in range(1, n + 1)],
                        coords, edges,
                        {"generator": "waxman", "seed": seed,
                         "num_nodes": n, "area_km": area,
                         "delta": delta, "epsilon": epsilon})


@registry.register("topology", "grid")
class GridTopology(TopologyProvider):
    """rows x cols lattice, every edge ``edge_km`` long (deterministic).

    Config: ``rows`` (5), ``cols`` (5), ``edge_km`` (10.0).
    Node id = ``r * cols + c + 1`` (same convention as RCKTA-FSE).
    """

    name = "grid"
    capabilities = {"synthetic", "geo_coords"}

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        rows = int(config.get("rows", 5))
        cols = int(config.get("cols", 5))
        edge_km = float(config.get("edge_km", 10.0))

        def nid(r, c):
            return r * cols + c + 1

        edges = {}
        for r in range(rows):
            for c in range(cols):
                if c < cols - 1:
                    edges[_ekey(nid(r, c), nid(r, c + 1))] = edge_km
                if r < rows - 1:
                    edges[_ekey(nid(r, c), nid(r + 1, c))] = edge_km
        coords = {str(nid(r, c)): (c * edge_km, -r * edge_km)
                  for r in range(rows) for c in range(cols)}
        node_ids = [str(nid(r, c)) for r in range(rows) for c in range(cols)]
        return _network(self.name, node_ids, coords, edges,
                        {"generator": "grid", "rows": rows, "cols": cols,
                         "edge_km": edge_km})


@registry.register("topology", "ring")
class RingTopology(TopologyProvider):
    """N-node cycle, every edge ``edge_km`` long (deterministic).

    Config: ``num_nodes`` (5), ``edge_km`` (5.0).
    """

    name = "ring"
    capabilities = {"synthetic"}

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        n = int(config.get("num_nodes", 5))
        edge_km = float(config.get("edge_km", 5.0))
        if n < 3:
            raise ValueError("ring needs num_nodes >= 3")
        edges = {_ekey(i, i % n + 1): edge_km for i in range(1, n + 1)}
        return _network(self.name, [str(i) for i in range(1, n + 1)],
                        None, edges,
                        {"generator": "ring", "num_nodes": n,
                         "edge_km": edge_km})


@registry.register("topology", "random_geometric")
class RandomGeometricTopology(TopologyProvider):
    """Nodes uniform in a square; connect pairs within ``radius_km``;
    components stitched by their nearest cross-component pair.

    Config: ``num_nodes`` (20), ``area_km`` (50.0), ``radius_km`` (15.0),
    ``min_len`` (1.0).
    """

    name = "random_geometric"
    capabilities = {"synthetic", "seeded", "seeded_lengths", "geo_coords"}

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        seed = _require_seed(self.name, seed)
        n = int(config.get("num_nodes", 20))
        area = float(config.get("area_km", 50.0))
        radius = float(config.get("radius_km", 15.0))
        min_len = float(config.get("min_len", 1.0))

        rng = random.Random(7000 + seed)
        pos = {i: (rng.uniform(0, area), rng.uniform(0, area))
               for i in range(1, n + 1)}
        edges, adj = {}, {i: set() for i in range(1, n + 1)}
        for a in range(1, n + 1):
            for b in range(a + 1, n + 1):
                d = euclidean_km(pos[a], pos[b])
                if d <= radius:
                    edges[_ekey(a, b)] = round(max(d, min_len), 2)
                    adj[a].add(b)
                    adj[b].add(a)

        # stitch (same approach as waxman, kept local and simple)
        def components():
            seen, comps = set(), []
            for start in range(1, n + 1):
                if start in seen:
                    continue
                stack, comp = [start], set()
                while stack:
                    x = stack.pop()
                    if x in comp:
                        continue
                    comp.add(x)
                    seen.add(x)
                    stack.extend(adj[x] - comp)
                comps.append(comp)
            return comps

        comps = components()
        while len(comps) > 1:
            best, bd = None, float("inf")
            for i in range(len(comps)):
                for j in range(i + 1, len(comps)):
                    for u in comps[i]:
                        for v in comps[j]:
                            d = euclidean_km(pos[u], pos[v])
                            if d < bd:
                                bd, best = d, (u, v)
            u, v = best
            edges[_ekey(u, v)] = round(max(bd, min_len), 2)
            adj[u].add(v)
            adj[v].add(u)
            comps = components()

        coords = {str(i): pos[i] for i in pos}
        return _network(self.name, [str(i) for i in range(1, n + 1)],
                        coords, edges,
                        {"generator": "random_geometric", "seed": seed,
                         "num_nodes": n, "area_km": area,
                         "radius_km": radius})


@registry.register("topology", "barabasi_albert")
class BarabasiAlbertTopology(TopologyProvider):
    """Barabasi-Albert preferential attachment; nodes placed uniformly in
    a square so link lengths are Euclidean distances.

    Config: ``num_nodes`` (20), ``m`` (2), ``area_km`` (50.0),
    ``min_len`` (1.0).
    """

    name = "barabasi_albert"
    capabilities = {"synthetic", "seeded", "seeded_lengths", "geo_coords"}

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        import networkx as nx

        seed = _require_seed(self.name, seed)
        n = int(config.get("num_nodes", 20))
        m = int(config.get("m", 2))
        area = float(config.get("area_km", 50.0))
        min_len = float(config.get("min_len", 1.0))

        g = nx.barabasi_albert_graph(n, m, seed=seed)   # nodes 0..n-1
        rng = random.Random(9000 + seed)
        pos = {i: (rng.uniform(0, area), rng.uniform(0, area))
               for i in range(n)}
        edges = {}
        for a, b in g.edges():
            d = euclidean_km(pos[a], pos[b])
            edges[_ekey(a + 1, b + 1)] = round(max(d, min_len), 2)
        coords = {str(i + 1): pos[i] for i in pos}
        return _network(self.name, [str(i) for i in range(1, n + 1)],
                        coords, edges,
                        {"generator": "barabasi_albert", "seed": seed,
                         "num_nodes": n, "m": m, "area_km": area})
