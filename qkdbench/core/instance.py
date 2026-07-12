"""Problem instance: the single source of truth shared by every algorithm.

An :class:`Instance` bundles a :class:`~qkdbench.core.network.Network`
(the physical topology), the key-delivery
:class:`~qkdbench.core.demand.Demand` list and the scenario parameters
(time model, QKD rate table).  Every algorithm consumes the *same*
instance object (or its JSON serialization), and
:meth:`Instance.fingerprint` gives a short hash so results can always be
traced back to the exact instance that produced them.

Design notes
------------
* Instances are serialized to **JSON** (not pickle): human-readable,
  git-diffable and stable across Python versions.
* The physical layer (key rate vs. distance) lives in
  :mod:`qkdbench.scenario.qkd_models` and is referenced by name
  (``rate_table``, optionally parameterized by ``qkd_model_params``),
  so all algorithms agree on the same physical model.
* Convenience properties (``nodes``, ``edges``, ``requests``,
  ``wavelengths``, ``modules``) present flat Phase-0 views over the
  structured model, so existing algorithms keep working unchanged.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List

from .demand import Demand, Request  # noqa: F401  (Request = alias)
from .network import Edge, Network, edge_key  # noqa: F401


@dataclass
class Instance:
    """A complete benchmark scenario.

    Attributes:
        name: human-readable identifier, e.g. ``"german7_nreq20_s1"``.
        network: the physical topology (nodes, links, identity triple).
        demands: list of :class:`Demand`.
        num_slots: number of time slots in the planning horizon (``nT``).
        slot_seconds: duration of one slot in seconds (``theta``).
        rate_table: name of the QKD model to use (any registered
            ``qkd_model`` name; the legacy rate-table names
            ``fse_1540_alone`` / ``fse_1310_coex`` map to the
            finite-size table model — see
            :mod:`qkdbench.scenario.qkd_models`).
        qkd_model_params: optional model constructor parameters, e.g.
            ``{"rate_kbps": 50}`` or ``{"table": "fse_1310_coex"}``.
        metadata: free-form provenance info (generator, seed, ...).
    """
    name: str
    network: Network
    demands: List[Demand] = field(default_factory=list)
    num_slots: int = 5
    slot_seconds: float = 1.0
    rate_table: str = "fse_1540_alone"
    qkd_model_params: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    # ------------------------------------------- flat views (Phase-0 API)
    @property
    def nodes(self) -> List[str]:
        """Node ids, in network order."""
        return self.network.node_ids()

    @property
    def edges(self) -> Dict[Edge, float]:
        """``{(a, b): length_km}`` with ``a <= b``."""
        return self.network.edge_lengths()

    @property
    def requests(self) -> List[Demand]:
        """Alias of :attr:`demands` (Phase-0 name)."""
        return self.demands

    @property
    def wavelengths(self) -> int:
        """Wavelength channels per link (v1: identical on every link)."""
        if not self.network.links:
            return 1
        return self.network.links[0].wavelengths

    @property
    def modules(self) -> Dict[str, int]:
        """``{node_id: QKD module count}`` from the nodes' device slots."""
        return {n.id: n.device_slots for n in self.network.nodes}

    # ------------------------------------------------------------ helpers
    def graph(self):
        """The topology as a ``networkx`` graph with ``length_km`` data."""
        return self.network.graph()

    def request_by_id(self, rid: int) -> Demand:
        for d in self.demands:
            if d.id == rid:
                return d
        raise KeyError(f"no demand with id {rid}")

    # ------------------------------------------------------- serialization
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "network": self.network.to_dict(),
            "demands": [asdict(d) for d in self.demands],
            "num_slots": self.num_slots,
            "slot_seconds": self.slot_seconds,
            "rate_table": self.rate_table,
            "qkd_model_params": self.qkd_model_params,
            "metadata": self.metadata,
        }

    def to_json(self, path=None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, sort_keys=True)
        if path is not None:
            with open(path, "w") as fh:
                fh.write(text + "\n")
        return text

    @classmethod
    def from_dict(cls, d: dict) -> "Instance":
        d = dict(d)
        d["network"] = Network.from_dict(d["network"])
        d["demands"] = [Demand(**r) for r in d["demands"]]
        return cls(**d)

    @classmethod
    def from_json(cls, path_or_text) -> "Instance":
        try:
            text = open(path_or_text).read()
        except (OSError, TypeError):
            text = path_or_text
        return cls.from_dict(json.loads(text))

    def fingerprint(self) -> str:
        """12-hex-digit hash identifying this exact instance."""
        blob = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()[:12]
