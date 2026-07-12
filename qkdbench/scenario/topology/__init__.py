"""First-class topology module (ARCHITECTURE.md §4).

Importing this package registers all providers in the unified registry
(kind ``"topology"``): the builtin YAML-backed topologies, the synthetic
generators and the file loader.

    from qkdbench.scenario.topology import build_topology, logical_graph

    net = build_topology("germany50")
    net = build_topology("waxman", {"num_nodes": 30}, seed=7)
    qkd = logical_graph(net, "fse_1540_alone")
"""
from .base import TopologyProvider, build_topology, haversine_km
from . import builtin      # noqa: F401  (registers data/*.yaml providers)
from . import synthetic    # noqa: F401  (registers waxman/grid/ring/...)
from . import loaders      # noqa: F401  (registers "file")
from .logical import logical_graph
from .dynamic import DynamicTopology

__all__ = ["TopologyProvider", "build_topology", "logical_graph",
           "haversine_km", "DynamicTopology"]
