"""Network model: JSON round-trip, checksum stability, Instance compat."""
from qkdbench import Demand, Link, Network, Node, make_instance


def _net():
    return Network(
        topology_id="toy", topology_version="1.0",
        nodes=[Node(id="a", coords=(1.0, 2.0)), Node(id="b"),
               Node(id="c", device_slots=4)],
        links=[Link(id="a-b", endpoints=("a", "b"), length_km=5.0,
                    wavelengths=2),
               Link(id="b-c", endpoints=("b", "c"), length_km=7.5,
                    wavelengths=2, attenuation_db_km=0.2)],
    )


def test_network_json_roundtrip():
    net = _net()
    back = Network.from_dict(net.to_dict())
    assert back == net
    assert back.checksum == net.checksum
    # endpoints and coords come back as tuples, not JSON lists
    assert back.links[0].endpoints == ("a", "b")
    assert back.nodes[0].coords == (1.0, 2.0)


def test_checksum_stable_and_sensitive():
    net = _net()
    # auto-filled on construction, recomputable, order-independent
    assert net.checksum == net.compute_checksum()
    reordered = Network(topology_id="toy",
                        nodes=list(reversed(net.nodes)),
                        links=list(reversed(net.links)))
    assert reordered.checksum == net.checksum
    # any physical change must alter the checksum
    changed = _net()
    changed.links[0].length_km = 6.0
    assert changed.compute_checksum() != net.checksum


def test_instance_compat_properties():
    inst = make_instance("german7", n_req=10, seed=1,
                         wavelengths=2, modules_per_node=3)
    assert inst.network.topology_id == "german7"
    assert inst.network.checksum  # identity triple always present
    # flat Phase-0 views over the structured model
    assert inst.nodes == [str(n) for n in range(1, 8)]
    assert set(inst.edges) == {l.endpoints for l in inst.network.links}
    assert inst.requests is inst.demands and len(inst.demands) == 10
    assert isinstance(inst.demands[0], Demand)
    assert inst.wavelengths == 2
    assert inst.modules == {n: 3 for n in inst.nodes}
    assert inst.graph().number_of_edges() == 11
    assert inst.request_by_id(1).id == 1


def test_instance_fingerprint_deterministic():
    a = make_instance("german7", n_req=10, seed=1)
    b = make_instance("german7", n_req=10, seed=1)
    assert a.fingerprint() == b.fingerprint()
    assert a.network.checksum == b.network.checksum
