"""P1 algorithm tests: feasibility, ordering relations, MILP dominance."""
import statistics

import pytest

from qkdbench import evaluate, get_algorithm, make_instance, verify

HEURISTICS = ["greedy_sp", "key_aware_sp", "fse_greedy", "local_search"]


def test_all_feasible_on_german7():
    for seed in (1, 2, 3):
        inst = make_instance("german7", n_req=20, seed=seed)
        for name in HEURISTICS + ["milp_p1"]:
            sol = get_algorithm(name).solve(inst)
            assert verify(inst, sol).ok, f"{name} seed {seed}"


def _mean_served(name, topo="german7", n=20, seeds=(1, 2, 3)):
    vals = []
    for s in seeds:
        inst = make_instance(topo, n_req=n, seed=s)
        vals.append(evaluate(inst, get_algorithm(name)).served)
    return statistics.mean(vals)


def test_ordering_relations():
    g = _mean_served("greedy_sp")
    assert _mean_served("key_aware_sp") >= g          # key-aware >= baseline
    assert _mean_served("fse_greedy") >= g            # fse serves >= baseline
    assert _mean_served("local_search") >= _mean_served("fse_greedy")


def test_fse_greedy_delivers_more_keys_than_greedy():
    # same served, but longer TPs bank more surplus keys
    inst = make_instance("german7", n_req=20, seed=1)
    g = evaluate(inst, get_algorithm("greedy_sp"))
    f = evaluate(inst, get_algorithm("fse_greedy"))
    assert f.served == g.served
    assert f.delivered_kb >= g.delivered_kb


def test_local_search_deterministic():
    inst = make_instance("german7", n_req=20, seed=1)
    a = evaluate(inst, get_algorithm("local_search"))
    b = evaluate(inst, get_algorithm("local_search"))
    assert (a.served, a.delivered_kb) == (b.served, b.delivered_kb)


def test_milp_optimal_on_triangle():
    inst = make_instance("triangle", n_req=3, seed=1)
    sol = get_algorithm("milp_p1").solve(inst)
    assert verify(inst, sol).ok
    assert sol.extras.get("solver_status") == "optimal"


@pytest.mark.parametrize("topo,n,seed", [
    ("poliqi5", 8, 1), ("poliqi5", 8, 2),
    ("german7", 12, 1), ("german7", 12, 2),
])
def test_heuristics_never_beat_milp(topo, n, seed):
    inst = make_instance(topo, n_req=n, seed=seed)
    milp = get_algorithm("milp_p1", time_limit_s=60).solve(inst)
    if milp.extras.get("solver_status") != "optimal":
        pytest.skip("CBC hit its time limit; no exact bound to compare")
    opt = len(milp.assignments)
    for name in HEURISTICS:
        served = len(get_algorithm(name).solve(inst).assignments)
        assert served <= opt, f"{name} served {served} > MILP optimum {opt}"
