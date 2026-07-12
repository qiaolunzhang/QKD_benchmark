"""Core round-trip, fingerprint and rate-table tests."""
import pytest

from qkdbench import Instance, make_instance, get_rate_table


def test_instance_json_roundtrip(tmp_path):
    inst = make_instance("german7", n_req=10, seed=1)
    path = tmp_path / "inst.json"
    inst.to_json(path)
    back = Instance.from_json(path)
    assert back == inst
    assert back.fingerprint() == inst.fingerprint()


def test_fingerprint_sensitivity():
    a = make_instance("german7", n_req=10, seed=1)
    b = make_instance("german7", n_req=10, seed=2)
    assert a.fingerprint() != b.fingerprint()
    # same generator inputs -> identical instance
    assert a.fingerprint() == make_instance("german7", n_req=10,
                                            seed=1).fingerprint()


def test_rate_table_monotone_and_reach():
    t = get_rate_table("fse_1540_alone")
    # rate grows with TP duration (the finite-size effect)
    assert t.rate_kbps(10, 5) > t.rate_kbps(10, 1)
    # longer distance -> lower rate
    assert t.rate_kbps(30, 5) < t.rate_kbps(10, 5)
    # beyond max reach -> zero keys
    assert t.tp_keys_kb(200, 5) == 0.0
    with pytest.raises(KeyError):
        get_rate_table("no_such_table")
