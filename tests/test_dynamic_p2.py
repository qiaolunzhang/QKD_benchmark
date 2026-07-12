"""Dynamic admission + key-pool problem (P2) tests."""
import networkx as nx
import pytest

from qkdbench import (evaluate, get_algorithm, register_algorithm, verify)
from qkdbench.algorithms.online import OnlineAlgorithm
from qkdbench.core.instance import Instance, edge_key
from qkdbench.instances.generators import make_dynamic_instance
from qkdbench.problems import get_problem, list_problems


def _inst(seed=1, n=60, ar=6.0, hold=8.0):
    return make_dynamic_instance(
        "german7", n_demands=n, seed=seed, arrival_rate=ar, mean_holding=hold,
        rate_lo_kbps=20.0, rate_hi_kbps=40.0, rate_table="constant",
        qkd_model_params={"rate_kbps": 30})


def test_p2_preset_registered():
    assert "dynamic_admission_keypool" in list_problems()


def test_dynamic_instance_shape_and_json():
    inst = _inst()
    assert inst.horizon_s is not None
    assert len(inst.key_pools) == len(inst.edges)
    assert all(d.rate_kbps and d.arrival_t is not None for d in inst.demands)
    back = Instance.from_json(inst.to_json())
    assert back.horizon_s == inst.horizon_s
    assert len(back.key_pools) == len(inst.key_pools)
    assert back.fingerprint() == inst.fingerprint()


def test_greedy_admission_feasible_and_deterministic():
    inst = _inst()
    r1 = evaluate(inst, get_algorithm("greedy_admission"))
    r2 = evaluate(inst, get_algorithm("greedy_admission"))
    assert r1.feasible and r1.status == "ok"
    assert (r1.served, r1.objectives) == (r2.served, r2.objectives)
    assert 0 <= r1.objectives["acceptance_ratio"] <= 1


def test_load_reduces_acceptance():
    light = evaluate(_inst(ar=1.0, hold=2.0), get_algorithm("greedy_admission"))
    heavy = evaluate(_inst(ar=10.0, hold=12.0), get_algorithm("greedy_admission"))
    assert heavy.objectives["acceptance_ratio"] <= \
        light.objectives["acceptance_ratio"]


def test_verifier_catches_overcommit():
    """A controller that ignores capacity must be flagged infeasible."""
    @register_algorithm
    class _AdmitAll(OnlineAlgorithm):
        name = "admit_all_overcommit"

        def reset(self, inst):
            super().reset(inst)
            self.g = inst.graph()

        def act(self, d, state):
            p = nx.shortest_path(self.g, d.src, d.dst, weight="length_km")
            return [edge_key(a, b) for a, b in zip(p, p[1:])]

    inst = _inst(ar=10.0, hold=12.0)
    r = evaluate(inst, get_algorithm("admit_all_overcommit"))
    assert not r.feasible
    assert any("exceeds generation" in s for s in r.violations)


def test_objectives_consistency():
    inst = _inst()
    prob = get_problem("dynamic_admission_keypool")
    sol = get_algorithm("greedy_admission").solve(inst)
    assert verify.__module__  # sanity import
    obj = prob.evaluate_objectives(inst, sol)
    assert abs(obj["acceptance_ratio"] + obj["blocking_probability"] - 1.0) < 1e-9
