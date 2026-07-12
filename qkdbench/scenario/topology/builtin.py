"""Builtin topologies loaded from YAML data files (never hardcoded in .py).

Each ``data/*.yaml`` file describes one topology with full provenance:

.. code-block:: yaml

    id: german7
    version: "1.0"
    source: <citation / provenance, mandatory>
    directed: false
    checksum: abc123...        # optional; verified after build when the
                               # topology is deterministic and unscaled
    fiber_factor: 1.0          # optional global length multiplier
    length_policy:             # optional: lengths drawn per seed
      mode: uniform
      lo: 2.0
      hi: 8.0
      base_seed: 2000          # rng = random.Random(base_seed + seed)
    nodes:
      - {id: "1", coords: [13.39, 52.52]}   # coords = (lon, lat), optional
    links:
      - {a: "1", b: "2", length_km: 29.1}   # length omitted under policy

Link lengths under a ``length_policy`` are drawn *in file order* with
``random.Random(base_seed + seed)`` and rounded to 2 decimals — for
``german7`` (base_seed 2000, U[2, 8]) this is bit-for-bit identical to the
Phase-0 implementation in :mod:`qkdbench.topology.builtin` and to the
INFOCOM'27 RCKTA-FSE convention (``usnet24`` uses base_seed 1000, same as
the RCKTA journal setup).

One provider class per YAML file is generated at import time and
registered under the file's ``id``.
"""
from __future__ import annotations

import pathlib
import random
from typing import Optional

import yaml

from ...core.network import Link, Network, Node, edge_key
from ...core.registry import registry
from .base import TopologyProvider

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"


def load_spec(path) -> dict:
    """Read and minimally validate one topology YAML file."""
    with open(path) as fh:
        spec = yaml.safe_load(fh)
    for field in ("id", "version", "source", "nodes", "links"):
        if field not in spec:
            raise ValueError(f"{path}: topology YAML missing "
                             f"required field {field!r}")
    return spec


def network_from_spec(spec: dict, config: dict,
                      seed: Optional[int] = None) -> Network:
    """Build a :class:`Network` from a parsed topology spec.

    ``config`` may override ``fiber_factor`` and the ``length_policy``
    bounds (``lo`` / ``hi``).  The stored checksum is verified only when
    the build is deterministic (no length policy) and unscaled.
    """
    policy = spec.get("length_policy")
    fiber_factor = float(config.get("fiber_factor",
                                    spec.get("fiber_factor", 1.0)))

    rng = None
    if policy is not None:
        if policy.get("mode") != "uniform":
            raise ValueError(f"{spec['id']}: unknown length_policy mode "
                             f"{policy.get('mode')!r}")
        rng = random.Random(int(policy.get("base_seed", 0))
                            + (0 if seed is None else int(seed)))
        lo = float(config.get("lo", policy["lo"]))
        hi = float(config.get("hi", policy["hi"]))

    nodes = [Node(id=str(n["id"]),
                  coords=tuple(n["coords"]) if n.get("coords") else None)
             for n in spec["nodes"]]

    links = []
    for entry in spec["links"]:   # file order matters under a policy
        a, b = edge_key(entry["a"], entry["b"])
        if rng is not None:
            km = round(rng.uniform(lo, hi), 2)
        else:
            km = float(entry["length_km"])
        if fiber_factor != 1.0:
            km = round(km * fiber_factor, 4)
        links.append(Link(id=f"{a}-{b}", endpoints=(a, b), length_km=km))

    net = Network(
        topology_id=spec["id"],
        topology_version=str(spec["version"]),
        directed=bool(spec.get("directed", False)),
        nodes=nodes, links=links,
        metadata={"source": spec["source"].strip()
                  if isinstance(spec["source"], str) else spec["source"],
                  "fiber_factor": fiber_factor,
                  **({"length_seed": seed} if rng is not None else {})},
    )

    recorded = spec.get("checksum")
    if recorded and rng is None and fiber_factor == 1.0:
        if net.checksum != recorded:
            raise ValueError(
                f"{spec['id']} v{spec['version']}: checksum mismatch "
                f"(data file says {recorded}, built {net.checksum}) — "
                f"the YAML data was modified without bumping version")
    return net


class BuiltinTopology(TopologyProvider):
    """Topology backed by a YAML data file in ``data/``."""

    data_file: str = ""   # set on generated subclasses
    _spec: dict = None    # parsed YAML, cached per class

    @classmethod
    def spec(cls) -> dict:
        if cls._spec is None:
            cls._spec = load_spec(cls.data_file)
        return cls._spec

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        return network_from_spec(self.spec(), config, seed=seed)


def _register_data_files():
    for path in sorted(DATA_DIR.glob("*.yaml")):
        spec = load_spec(path)
        caps = {"builtin"}
        if any(n.get("coords") for n in spec["nodes"]):
            caps.add("geo_coords")
        if spec.get("length_policy"):
            caps |= {"seeded", "seeded_lengths"}
        cls = type("Builtin_%s" % spec["id"], (BuiltinTopology,), {
            "name": spec["id"],
            "capabilities": caps,
            "data_file": str(path),
            "_spec": spec,
            "__doc__": "Builtin topology %r from %s" % (spec["id"], path.name),
        })
        registry.register("topology", spec["id"])(cls)


_register_data_files()
