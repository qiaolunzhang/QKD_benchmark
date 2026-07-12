"""FileTopology: load a topology from a user-supplied file.

Registered as ``"file"``; the format is inferred from the extension (or
forced with ``config["format"]``):

* **GraphML** (``.graphml``) — edge attribute ``length_km`` (or
  ``length`` / ``weight``) when present, else the haversine distance of
  node ``Longitude`` / ``Latitude`` attributes (Topology-Zoo style).
* **JSON / YAML** (``.json`` / ``.yaml`` / ``.yml``) — either the
  builtin topology schema (``id`` / ``version`` / ``source`` / ``nodes``
  / ``links``, see :mod:`.builtin`) or a serialized
  :meth:`Network.to_dict` payload (detected by ``topology_id``).
* **CSV** (``.csv``) — link table with header ``a,b,length_km``;
  an optional node table (``config["nodes_file"]``) with header
  ``id[,lon,lat]`` adds isolated nodes and coordinates.

Example::

    net = build_topology("file", {"path": "mynet.graphml"})
"""
from __future__ import annotations

import csv
import json
import pathlib
from typing import Optional

from ...core.network import Link, Network, Node, edge_key
from ...core.registry import registry
from .base import TopologyProvider, haversine_km
from .builtin import network_from_spec


@registry.register("topology", "file")
class FileTopology(TopologyProvider):
    """Load GraphML / JSON / YAML / CSV topology files."""

    name = "file"
    capabilities = {"file", "geo_coords"}

    def build(self, config: dict, seed: Optional[int] = None) -> Network:
        path = pathlib.Path(config["path"])
        fmt = config.get("format") or path.suffix.lstrip(".").lower()
        if fmt == "graphml":
            return self._from_graphml(path, config)
        if fmt in ("yaml", "yml", "json"):
            return self._from_mapping(path, fmt, config, seed)
        if fmt == "csv":
            return self._from_csv(path, config)
        raise ValueError(f"unsupported topology file format {fmt!r} "
                         f"(graphml/json/yaml/csv)")

    # ----------------------------------------------------------- graphml
    def _from_graphml(self, path, config) -> Network:
        import networkx as nx

        g = nx.Graph(nx.read_graphml(path))   # collapse multi-edges
        nodes, coords = [], {}
        for n, d in g.nodes(data=True):
            lon, lat = d.get("Longitude"), d.get("Latitude")
            c = (float(lon), float(lat)) if lon is not None \
                and lat is not None else None
            nid = str(d.get("label", n))
            coords[str(n)] = c
            nodes.append(Node(id=nid, coords=c))
        ids = {str(n): str(d.get("label", n)) for n, d in g.nodes(data=True)}
        if len(set(ids.values())) != len(ids):     # non-unique labels
            ids = {str(n): str(n) for n in g.nodes()}
            nodes = [Node(id=str(n), coords=coords[str(n)])
                     for n in g.nodes()]
        links = []
        for u, v, d in g.edges(data=True):
            km = d.get("length_km", d.get("length", d.get("weight")))
            if km is None:
                cu, cv = coords[str(u)], coords[str(v)]
                if cu is None or cv is None:
                    raise ValueError(
                        f"{path}: edge ({u},{v}) has no length attribute "
                        f"and endpoints lack coordinates")
                km = round(haversine_km(cu, cv), 2)
            a, b = edge_key(ids[str(u)], ids[str(v)])
            links.append(Link(id=f"{a}-{b}", endpoints=(a, b),
                              length_km=float(km)))
        return Network(topology_id=config.get("id", path.stem),
                       topology_version=config.get("version", "file"),
                       nodes=nodes, links=links,
                       metadata={"source": f"graphml file {path}"})

    # ------------------------------------------------------- json / yaml
    def _from_mapping(self, path, fmt, config, seed) -> Network:
        if fmt == "json":
            data = json.loads(path.read_text())
        else:
            import yaml
            data = yaml.safe_load(path.read_text())
        if "topology_id" in data:              # serialized Network
            return Network.from_dict(data)
        for field in ("id", "version", "source", "nodes", "links"):
            if field not in data:
                raise ValueError(f"{path}: missing field {field!r} "
                                 f"(builtin topology schema)")
        return network_from_spec(data, config, seed=seed)

    # ---------------------------------------------------------------- csv
    def _from_csv(self, path, config) -> Network:
        links, node_ids = [], []
        seen = set()
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                a, b = edge_key(row["a"], row["b"])
                links.append(Link(id=f"{a}-{b}", endpoints=(a, b),
                                  length_km=float(row["length_km"])))
                for n in (a, b):
                    if n not in seen:
                        seen.add(n)
                        node_ids.append(n)
        coords = {}
        if config.get("nodes_file"):
            node_ids = []
            with open(config["nodes_file"], newline="") as fh:
                for row in csv.DictReader(fh):
                    nid = str(row["id"])
                    node_ids.append(nid)
                    if row.get("lon") and row.get("lat"):
                        coords[nid] = (float(row["lon"]), float(row["lat"]))
            missing = seen - set(node_ids)
            if missing:
                raise ValueError(f"{path}: links reference nodes missing "
                                 f"from nodes_file: {sorted(missing)}")
        nodes = [Node(id=n, coords=coords.get(n)) for n in node_ids]
        return Network(topology_id=config.get("id", path.stem),
                       topology_version=config.get("version", "file"),
                       nodes=nodes, links=links,
                       metadata={"source": f"csv file {path}"})
