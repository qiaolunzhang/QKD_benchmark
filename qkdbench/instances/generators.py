"""Seeded instance generators.

Instances are generated once, saved as JSON and shared by every
algorithm — never regenerated per algorithm, so comparisons are always on
identical inputs (the fingerprint proves it).

Topologies come from the registered providers in
:mod:`qkdbench.scenario.topology` — any registered name works
(``german7`` / ``germany50`` / ``usnet24`` / ``nsfnet14`` /
``cost239_11`` / ``geant2`` / ``waxman`` / ``grid`` / ...); the legacy
``qkdbench.topology.builtin.get_topology`` factories remain available as
a fallback for unregistered names (Phase-0 API).
"""
from __future__ import annotations

import random
from typing import List, Optional

from ..core.demand import Request
from ..core.errors import UnknownComponentError
from ..core.instance import Instance
from ..core.network import Link, Network, Node
from ..scenario.topology import build_topology


def uniform_requests(nodes: List[str], n_req: int, num_slots: int,
                     seed: int, mean_volume_kb: float = 100.0,
                     spread: float = 0.3, min_deadline: int = 2,
                     pairs=None) -> List[Request]:
    """``n_req`` requests cycling over node pairs.

    Volumes are U[(1-spread), (1+spread)] * mean; deadlines
    U[min_deadline, num_slots].  Deterministic per seed.
    """
    rng = random.Random(seed)
    if pairs is None:
        pairs = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:]]
    reqs = []
    for k in range(n_req):
        s, t = pairs[k % len(pairs)]
        vol = mean_volume_kb * (1 + rng.uniform(-spread, spread))
        dl = rng.randint(min_deadline, num_slots)
        reqs.append(Request(id=k + 1, src=s, dst=t,
                            volume_kb=round(vol, 1), deadline_slot=dl))
    return reqs


def _legacy_network(topology: str, seed: int, topo_kwargs: dict) -> Network:
    """Phase-0 fallback: build via ``topology.builtin.get_topology``."""
    from ..topology.builtin import get_topology

    kwargs = dict(topo_kwargs)
    if topology == "german7":
        kwargs.setdefault("seed", seed)
    nodes, edges = get_topology(topology, **kwargs)
    return Network(
        topology_id=topology, topology_version="1.0",
        nodes=[Node(id=n) for n in nodes],
        links=[Link(id=f"{a}-{b}", endpoints=(a, b), length_km=km)
               for (a, b), km in sorted(edges.items())],
        metadata={"builder": "get_topology", **kwargs},
    )


def make_instance(topology: str, n_req: int, seed: int,
                  num_slots: int = 5, wavelengths: int = 2,
                  modules_per_node: int = 2, mean_volume_kb: float = 100.0,
                  rate_table: str = "fse_1540_alone",
                  qkd_model_params: dict = None,
                  length_scale: Optional[float] = None,
                  topology_kwargs: dict = None) -> Instance:
    """One-stop instance factory used by configs and examples.

    Args:
        topology: any registered topology provider name (builtin YAML,
            synthetic generator or ``"file"``); legacy ``get_topology``
            names still work as a fallback.
        rate_table: QKD model name (legacy rate-table names map to the
            finite-size table model).
        qkd_model_params: optional model parameters passed through to
            the instance (e.g. ``{"rate_kbps": 50}``).
        length_scale: optional multiplier applied to *every* link length
            after the topology is built (recorded in the metadata) — the
            INFOCOM'27 ``fiber_factor`` device for re-fitting a
            national-scale topology (NSFNET, COST239, GEANT2, ...) into
            the finite-size QKD reach window.
        topology_kwargs: provider config dict (e.g. ``num_nodes`` for
            waxman, ``fiber_factor`` for germany50, ``path`` for file).
    """
    topo_kwargs = dict(topology_kwargs or {})
    try:
        network = build_topology(topology, config=topo_kwargs, seed=seed)
    except UnknownComponentError:
        network = _legacy_network(topology, seed, topo_kwargs)

    # uniform scenario parameters (v1): same wavelength count on every
    # link, same module count on every node
    for link in network.links:
        link.wavelengths = wavelengths
        if length_scale is not None:
            link.length_km = round(link.length_km * length_scale, 4)
    for node in network.nodes:
        node.device_slots = modules_per_node
    if length_scale is not None:
        network.metadata["length_scale"] = length_scale
    network.checksum = network.compute_checksum()   # content changed above

    requests = uniform_requests(network.node_ids(), n_req, num_slots, seed,
                                mean_volume_kb=mean_volume_kb)
    meta = {"generator": "make_instance", "topology": topology,
            "seed": seed, "mean_volume_kb": mean_volume_kb}
    if length_scale is not None:
        meta["length_scale"] = length_scale
    if topo_kwargs:
        meta["topology_kwargs"] = topo_kwargs
    return Instance(
        name=f"{topology}_nreq{n_req}_s{seed}",
        network=network, demands=requests,
        num_slots=num_slots,
        rate_table=rate_table,
        qkd_model_params=dict(qkd_model_params or {}),
        metadata=meta,
    )


def make_dynamic_instance(topology: str, n_demands: int, seed: int,
                          arrival_rate: float = 1.0, mean_holding: float = 5.0,
                          rate_lo_kbps: float = 5.0, rate_hi_kbps: float = 20.0,
                          wavelengths: int = 2, rate_table: str = "constant",
                          qkd_model_params: dict = None,
                          pool_capacity_kb: float = 1e6,
                          pool_init_kb: float = 0.0,
                          length_scale: Optional[float] = None,
                          topology_kwargs: dict = None) -> Instance:
    """Factory for a dynamic admission + key-pool instance (P2).

    Demands arrive as a Poisson process (rate ``arrival_rate``) with
    exponential holding times (mean ``mean_holding``), each requiring a
    sustained key rate drawn uniformly in
    ``[rate_lo_kbps, rate_hi_kbps]`` between a random reachable node pair.
    Every link gets a :class:`~qkdbench.core.key_pool.KeyPool` whose
    generation rate is the link's secret-key rate under the instance's
    QKD model.  All randomness derives from ``seed``.
    """
    from ..core.key_pool import KeyPool
    from ..scenario.qkd_models import get_qkd_model

    base = make_instance(topology, 0, seed, wavelengths=wavelengths,
                         rate_table=rate_table,
                         qkd_model_params=qkd_model_params,
                         length_scale=length_scale,
                         topology_kwargs=topology_kwargs)
    network = base.network
    model = get_qkd_model(rate_table, **(qkd_model_params or {}))

    # per-link key pools; generation rate = link secret-key rate x lambdas
    pools = []
    for link in network.links:
        gen = model.evaluate(link.length_km).skr_kbps * link.wavelengths
        a, b = link.endpoints
        pools.append(KeyPool(pool_id=f"{a}-{b}", link=(a, b),
                             gen_kbps=round(gen, 6),
                             capacity_kb=pool_capacity_kb,
                             init_kb=pool_init_kb))

    # Poisson arrivals + exponential holding; random reachable pairs
    rng = random.Random(seed)
    node_ids = network.node_ids()
    demands, t = [], 0.0
    for k in range(n_demands):
        t += rng.expovariate(arrival_rate)
        src, dst = rng.sample(node_ids, 2)
        demands.append(Request(
            id=k + 1, src=src, dst=dst, volume_kb=0.0, deadline_slot=0,
            arrival_t=round(t, 6),
            holding_t=round(rng.expovariate(1.0 / mean_holding), 6),
            rate_kbps=round(rng.uniform(rate_lo_kbps, rate_hi_kbps), 3)))
    horizon = round(t + mean_holding, 6)

    meta = {"generator": "make_dynamic_instance", "topology": topology,
            "seed": seed, "arrival_rate": arrival_rate,
            "mean_holding": mean_holding}
    return Instance(
        name=f"{topology}_dyn{n_demands}_s{seed}",
        network=network, demands=demands,
        rate_table=rate_table, qkd_model_params=dict(qkd_model_params or {}),
        key_pools=pools, horizon_s=horizon, metadata=meta)
