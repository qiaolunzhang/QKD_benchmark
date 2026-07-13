"""Trusted-relay placement problem (P3) tests."""
from qkdbench import Solution, evaluate, get_algorithm
from qkdbench.instances.generators import make_placement_instance
from qkdbench.problems import get_problem, list_problems


def _inst(topo="usnet24", n=10, seed=1):
    return make_placement_instance(topo, n_demands=n, seed=seed)


def test_p3_preset_registered():
    assert "trusted_relay_placement" in list_problems()


def test_placement_instance_needs_relays():
    inst = _inst()
    assert inst.metadata["problem_family"] == "placement"
    # every demand is a multi-hop pair (no single feasible link)
    assert all(d.deadline_slot == 0 for d in inst.demands)
    # empty placement must leave some demand uncovered
    prob = get_problem("trusted_relay_placement")
    empty = Solution(algorithm="none", placement=[])
    assert not prob.verify(inst, empty).ok


def test_greedy_feasible_and_covers():
    inst = _inst()
    r = evaluate(inst, get_algorithm("greedy_placement"))
    assert r.feasible and r.status == "ok"
    assert r.objectives["num_relays"] == r.served


def test_milp_no_worse_than_greedy():
    for seed in (1, 2, 3):
        inst = _inst(seed=seed)
        g = evaluate(inst, get_algorithm("greedy_placement"))
        m = evaluate(inst, get_algorithm("milp_placement", time_limit_s=60))
        assert g.feasible and m.feasible
        if m.extras.get("solver_status") == "optimal":
            assert m.objectives["deployment_cost"] <= \
                g.objectives["deployment_cost"] + 1e-6


def test_placement_deterministic():
    inst = _inst()
    a = evaluate(inst, get_algorithm("greedy_placement"))
    b = evaluate(inst, get_algorithm("greedy_placement"))
    assert a.objectives == b.objectives


def test_verifier_catches_invalid_node():
    inst = _inst()
    bad = Solution(algorithm="x", placement=["nonexistent_node"])
    r = get_problem("trusted_relay_placement").verify(inst, bad)
    assert not r.ok
    assert any("does not exist" in s for s in r.violations)
