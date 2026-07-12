"""Phase 2: topology providers — builtin YAML data, synthetic, loaders,
logical graph, and the change-one-line topology swap."""
import pytest

from qkdbench import (build_topology, evaluate, get_algorithm, get_topology,
                      logical_graph, make_instance, verify)
from qkdbench.core.errors import UnknownComponentError
from qkdbench.core.registry import registry

#: the six v1 builtin topologies with their expected sizes
BUILTIN_SIZES = {
    "german7": (7, 11),
    "germany50": (50, 88),
    "usnet24": (24, 43),
    "nsfnet14": (14, 21),
    "cost239_11": (11, 26),
    "geant2": (30, 48),
}


# ------------------------------------------------------------- builtin YAML
def test_builtin_topologies_build_with_expected_sizes():
    import networkx as nx
    for name, (n_nodes, n_links) in BUILTIN_SIZES.items():
        net = build_topology(name, seed=1)
        assert len(net.nodes) == n_nodes, name
        assert len(net.links) == n_links, name
        assert net.topology_id == name and net.checksum
        assert net.metadata.get("source"), f"{name}: YAML must carry source"
        assert nx.is_connected(net.graph()), name
        assert all(l.length_km > 0 for l in net.links), name


def test_german7_lengths_bitwise_equal_phase0():
    # the provider draws lengths with random.Random(2000 + seed) in link
    # file order — locked to the Phase-0 implementation, bit for bit
    for seed in (0, 1, 5):
        _, old_edges = get_topology("german7", seed=seed)
        net = build_topology("german7", seed=seed)
        assert net.edge_lengths() == old_edges, seed


def test_yaml_checksum_stable():
    # deterministic topologies: same build twice, and the checksum
    # recorded in the YAML data file matches the rebuilt network
    import yaml
    from qkdbench.scenario.topology.builtin import DATA_DIR
    for name in ("germany50", "nsfnet14", "cost239_11", "geant2"):
        a, b = build_topology(name), build_topology(name)
        assert a.checksum == b.checksum
        spec = yaml.safe_load((DATA_DIR / f"{name}.yaml").read_text())
        assert spec["checksum"] == a.checksum, name
        assert spec["version"] and spec["source"]


def test_seeded_lengths_vary_by_seed_only():
    a = build_topology("usnet24", seed=1)
    b = build_topology("usnet24", seed=1)
    c = build_topology("usnet24", seed=2)
    assert a.checksum == b.checksum != c.checksum
    # same graph structure regardless of seed
    assert sorted(l.endpoints for l in a.links) == \
        sorted(l.endpoints for l in c.links)


def test_germany50_fiber_factor_scales_lengths():
    raw = build_topology("germany50")
    scaled = build_topology("germany50", {"fiber_factor": 0.16})
    for lr, ls in zip(raw.links, scaled.links):
        assert ls.length_km == pytest.approx(lr.length_km * 0.16, abs=1e-3)


# ---------------------------------------------------------------- synthetic
def test_synthetic_deterministic_per_seed():
    for name in ("waxman", "random_geometric", "barabasi_albert"):
        a = build_topology(name, {"num_nodes": 12}, seed=3)
        b = build_topology(name, {"num_nodes": 12}, seed=3)
        c = build_topology(name, {"num_nodes": 12}, seed=4)
        assert a.checksum == b.checksum, name
        assert a.checksum != c.checksum, name
        with pytest.raises(ValueError):
            build_topology(name, {"num_nodes": 12})   # seed required


def test_synthetic_grid_and_ring():
    import networkx as nx
    grid = build_topology("grid", {"rows": 3, "cols": 4, "edge_km": 10.0})
    assert len(grid.nodes) == 12 and len(grid.links) == 3 * 3 + 2 * 4
    assert all(l.length_km == 10.0 for l in grid.links)
    ring = build_topology("ring", {"num_nodes": 6, "edge_km": 4.0})
    assert len(ring.nodes) == 6 and len(ring.links) == 6
    assert nx.is_connected(ring.graph())


def test_synthetic_connected():
    import networkx as nx
    for name in ("waxman", "random_geometric", "barabasi_albert"):
        net = build_topology(name, {"num_nodes": 15}, seed=1)
        assert nx.is_connected(net.graph()), name


# ------------------------------------------------------------- file loaders
def test_file_loader_csv(tmp_path):
    links = tmp_path / "links.csv"
    links.write_text("a,b,length_km\nx,y,5.0\ny,z,7.5\n")
    net = build_topology("file", {"path": str(links)})
    assert len(net.nodes) == 3 and len(net.links) == 2
    nodes = tmp_path / "nodes.csv"
    nodes.write_text("id,lon,lat\nx,9.0,45.0\ny,9.1,45.1\nz,9.2,45.2\n")
    net = build_topology("file", {"path": str(links),
                                  "nodes_file": str(nodes)})
    assert net.node_by_id("x").coords == (9.0, 45.0)


def test_file_loader_yaml_uses_builtin_schema(tmp_path):
    from qkdbench.scenario.topology.builtin import DATA_DIR
    import shutil
    p = tmp_path / "my_topo.yaml"
    shutil.copy(DATA_DIR / "cost239_11.yaml", p)
    net = build_topology("file", {"path": str(p)})
    assert (len(net.nodes), len(net.links)) == BUILTIN_SIZES["cost239_11"]
    assert net.checksum == build_topology("cost239_11").checksum


def test_file_loader_graphml(tmp_path):
    import networkx as nx
    g = nx.Graph()
    g.add_node("a", Longitude=9.19, Latitude=45.46)   # Milan
    g.add_node("b", Longitude=8.54, Latitude=47.37)   # Zurich
    g.add_edge("a", "b")                              # no length attr
    path = tmp_path / "toy.graphml"
    nx.write_graphml(g, path)
    net = build_topology("file", {"path": str(path)})
    assert len(net.links) == 1
    assert net.links[0].length_km == pytest.approx(217, abs=5)  # haversine


# ------------------------------------------------------------ logical graph
def test_logical_graph_filters_beyond_reach_on_germany50():
    net = build_topology("germany50")   # real distances 25.9-252.2 km
    phys = net.graph()
    logical = logical_graph(net, "fse_1540_alone")   # reach <= 70 km
    assert logical.number_of_nodes() == phys.number_of_nodes()
    assert 0 < logical.number_of_edges() < phys.number_of_edges()
    max_reach = 70.0
    for _, _, d in logical.edges(data=True):
        assert d["length_km"] <= max_reach
    dropped = logical.graph["infeasible_links"]
    assert len(dropped) == phys.number_of_edges() - logical.number_of_edges()
    for a, b in dropped:
        assert phys.edges[a, b]["length_km"] > max_reach


# ------------------------------- swap topology, algorithm untouched (§9)
def test_greedy_sp_verifies_on_every_builtin_topology():
    # length_scale re-fits national-scale topologies into the QKD reach
    # window (the INFOCOM'27 fiber_factor device); it is recorded in the
    # instance metadata
    scale = {"nsfnet14": 0.01, "cost239_11": 0.05, "geant2": 0.05,
             "germany50": 0.05}
    algo = get_algorithm("greedy_sp")
    for topo in BUILTIN_SIZES:
        inst = make_instance(topo, n_req=12, seed=3,
                             length_scale=scale.get(topo))
        sol = algo.solve(inst)
        rep = verify(inst, sol)
        assert rep.ok, (topo, rep.violations)
        assert len(sol.assignments) > 0, f"{topo}: served nothing"
        if topo in scale:
            assert inst.metadata["length_scale"] == scale[topo]
            assert inst.network.metadata["length_scale"] == scale[topo]


def test_make_instance_accepts_synthetic_providers():
    inst = make_instance("waxman", n_req=8, seed=2,
                         topology_kwargs={"num_nodes": 10})
    assert inst.network.topology_id == "waxman"
    assert inst.wavelengths == 2 and set(inst.modules.values()) == {2}
    res = evaluate(inst, get_algorithm("greedy_sp"))
    assert res.feasible


def test_make_instance_unknown_topology_raises():
    with pytest.raises((UnknownComponentError, KeyError)):
        make_instance("atlantis99", n_req=5, seed=1)


def test_config_swaps_topology_with_one_yaml_key(tmp_path):
    # ARCHITECTURE.md §9 acceptance: changing the topology means editing
    # exactly one value in the experiment YAML; problem/algorithm untouched
    from qkdbench import ExperimentConfig, run_benchmark
    template = """
name: swap_{topo}
algorithms: [greedy_sp]
instances:
  topology: {topo}
  n_requests: 10
  seeds: [1]
"""
    for topo in ("german7", "usnet24"):
        path = tmp_path / f"{topo}.yaml"
        path.write_text(template.format(topo=topo))
        cfg = ExperimentConfig.from_yaml(path)
        instances = list(cfg.build_instances())
        assert instances[0].network.topology_id == topo
        results = run_benchmark(instances, cfg.algorithms, verbose=False)
        assert results[0].feasible


def test_registry_has_all_providers():
    names = set(registry.names("topology"))
    assert set(BUILTIN_SIZES) <= names
    assert {"waxman", "grid", "ring", "random_geometric",
            "barabasi_albert", "file", "triangle", "poliqi5"} <= names
