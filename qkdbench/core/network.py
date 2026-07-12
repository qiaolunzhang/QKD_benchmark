"""Physical network model: Node / Link / Network (ARCHITECTURE.md §3).

The :class:`Network` is the *only* stored form of a topology.  Logical
QKD topologies are derived from it at runtime, and service topologies
(paths chosen by an algorithm) live in the Solution — never here.

Every Network carries its identity triple ``(topology_id,
topology_version, checksum)`` so that two "german7" networks with
different link lengths can never be silently mixed up: the checksum is
a deterministic hash of the actual nodes and links.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Edge = Tuple[str, str]


def edge_key(a, b) -> Edge:
    """Canonical (sorted) edge representation."""
    a, b = str(a), str(b)
    return (a, b) if a <= b else (b, a)


@dataclass
class Node:
    """One network node.

    Attributes:
        id: unique node name within the network.
        type: node role — ``"user"`` / ``"qkd"`` / ``"relay"`` /
            ``"optical"`` / ``"satellite"`` / ``"ground_station"``.
        trusted: whether the node may act as a trusted relay.
        coords: optional ``(x, y)`` geographic coordinates.
        device_slots: number of QKD modules (transceivers) available.
        metadata: free-form annotations only — anything an algorithm or
            verifier reads must be a typed field.
    """
    id: str
    type: str = "qkd"
    trusted: bool = True
    coords: Optional[Tuple[float, float]] = None
    device_slots: int = 2
    metadata: dict = field(default_factory=dict)


@dataclass
class Link:
    """One physical link between two nodes.

    Attributes:
        id: unique link name within the network.
        endpoints: sorted node-id pair ``(a, b)`` with ``a <= b``
            (use :func:`edge_key`).
        type: ``"fiber"`` or ``"fso"`` (free-space optics).
        length_km: physical length in km.
        wavelengths: number of wavelength channels on the link.
        attenuation_db_km: optional fiber attenuation; when ``None`` the
            QKD model's default applies.
        metadata: free-form annotations only.
    """
    id: str
    endpoints: Edge
    type: str = "fiber"
    length_km: float = 0.0
    wavelengths: int = 1
    attenuation_db_km: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Network:
    """A physical topology plus its identity triple.

    Attributes:
        topology_id: name of the topology, e.g. ``"german7"``.
        topology_version: version string of the topology data.
        checksum: deterministic hash of nodes+links (see
            :meth:`compute_checksum`); auto-filled when left ``None``.
        directed: v1 networks are undirected.
        nodes / links: the actual topology.
        metadata: provenance annotations (source reference, seed, ...).
    """
    topology_id: str
    topology_version: str = "1.0"
    checksum: Optional[str] = None
    directed: bool = False
    nodes: List[Node] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.checksum is None:
            self.checksum = self.compute_checksum()

    # ------------------------------------------------------------ helpers
    def node_ids(self) -> List[str]:
        return [n.id for n in self.nodes]

    def node_by_id(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(f"no node with id {node_id!r}")

    def edge_lengths(self) -> Dict[Edge, float]:
        """``{(a, b): length_km}`` view over the links (a <= b)."""
        return {link.endpoints: link.length_km for link in self.links}

    def graph(self):
        """The topology as a ``networkx`` graph with link data on edges."""
        import networkx as nx

        g = nx.DiGraph() if self.directed else nx.Graph()
        for n in self.nodes:
            g.add_node(n.id, type=n.type, trusted=n.trusted,
                       device_slots=n.device_slots)
        for link in self.links:
            a, b = link.endpoints
            g.add_edge(a, b, id=link.id, length_km=link.length_km,
                       wavelengths=link.wavelengths)
        return g

    def compute_checksum(self) -> str:
        """12-hex-digit hash of the nodes and links (order-independent).

        Two networks with identical content always hash the same, so a
        stored checksum can be re-verified after loading from JSON.
        """
        payload = {
            "directed": self.directed,
            "nodes": sorted(
                [n.id, n.type, n.trusted, list(n.coords) if n.coords else None,
                 n.device_slots] for n in self.nodes),
            "links": sorted(
                [link.id, list(link.endpoints), link.type, link.length_km,
                 link.wavelengths, link.attenuation_db_km]
                for link in self.links),
        }
        blob = json.dumps(payload, sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()[:12]

    # ------------------------------------------------------- serialization
    def to_dict(self) -> dict:
        return {
            "topology_id": self.topology_id,
            "topology_version": self.topology_version,
            "checksum": self.checksum,
            "directed": self.directed,
            "nodes": [{"id": n.id, "type": n.type, "trusted": n.trusted,
                       "coords": list(n.coords) if n.coords else None,
                       "device_slots": n.device_slots,
                       "metadata": n.metadata} for n in self.nodes],
            "links": [{"id": link.id, "endpoints": list(link.endpoints),
                       "type": link.type, "length_km": link.length_km,
                       "wavelengths": link.wavelengths,
                       "attenuation_db_km": link.attenuation_db_km,
                       "metadata": link.metadata} for link in self.links],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Network":
        d = dict(d)
        d["nodes"] = [Node(**{**n, "coords": tuple(n["coords"])
                              if n.get("coords") else None})
                      for n in d["nodes"]]
        d["links"] = [Link(**{**link, "endpoints": edge_key(*link["endpoints"])})
                      for link in d["links"]]
        return cls(**d)
