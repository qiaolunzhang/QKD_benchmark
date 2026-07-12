"""TopologyProvider ABC and the ``build_topology`` entry point.

A topology provider turns a config dict (plus an optional seed) into a
:class:`~qkdbench.core.network.Network` — the *only* stored form of a
topology (ARCHITECTURE.md §4).  Providers are registered in the unified
registry under kind ``"topology"``::

    from qkdbench.core.registry import registry

    @registry.register("topology", "my_topo")
    class MyTopo(TopologyProvider):
        capabilities = {"geo_coords"}
        def build(self, config, seed=None) -> Network: ...

    net = build_topology("my_topo", {"n": 10}, seed=1)

Capability vocabulary (extend as needed):

* ``geo_coords``      — nodes carry real geographic coordinates
* ``builtin``         — shipped as a YAML data file with provenance
* ``synthetic``       — generated from parameters
* ``seeded``          — output depends on the seed (must be passed)
* ``seeded_lengths``  — link *lengths* are drawn per seed
* ``file``            — loaded from a user-supplied file
* ``directed``        — provider can emit directed networks (v1: none)
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Optional, Set

from ...core.network import Network
from ...core.registry import registry


class TopologyProvider(ABC):
    """Builds a :class:`Network` from a config dict and an optional seed."""

    #: registry name (also used as default ``topology_id``)
    name: str = ""
    #: declared capabilities, matched against scenario requirements
    capabilities: Set[str] = set()

    @abstractmethod
    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        """Materialize the topology.

        Args:
            config: provider-specific parameters (may be empty).
            seed: randomness seed; providers whose output depends on
                randomness must require it and derive *all* randomness
                from it.
        """

    # ------------------------------------------------------------- helpers
    @classmethod
    def describe(cls) -> str:
        return f"{cls.name} (capabilities: {sorted(cls.capabilities)})"


def build_topology(name: str, config: Optional[dict] = None,
                   seed: Optional[int] = None) -> Network:
    """Look up a registered topology provider by name and build it."""
    provider_cls = registry.get("topology", name)
    provider = provider_cls()
    return provider.build(dict(config or {}), seed=seed)


def haversine_km(coord_a, coord_b) -> float:
    """Great-circle distance in km between two ``(lon, lat)`` points."""
    lon1, lat1 = coord_a
    lon2, lat2 = coord_b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def euclidean_km(coord_a, coord_b) -> float:
    """Planar distance between two ``(x_km, y_km)`` points."""
    return ((coord_a[0] - coord_b[0]) ** 2
            + (coord_a[1] - coord_b[1]) ** 2) ** 0.5
