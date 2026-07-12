"""End-to-end: baseline solves, verifier approves, runner records."""
from qkdbench import (evaluate, get_algorithm, list_algorithms,
                      make_instance, run_benchmark, verify)


def test_greedy_sp_feasible_on_all_builtin_topologies():
    for topo in ("triangle", "poliqi5", "german7"):
        inst = make_instance(topo, n_req=15, seed=3)
        algo = get_algorithm("greedy_sp")
        sol = algo.solve(inst)
        assert verify(inst, sol).ok, topo
        assert len(sol.assignments) > 0, f"{topo}: baseline served nothing"


def test_evaluate_records_metrics():
    inst = make_instance("german7", n_req=20, seed=1)
    res = evaluate(inst, get_algorithm("greedy_sp"))
    assert res.status == "ok" and res.feasible
    assert 0 < res.served <= res.total_requests == 20
    assert res.delivered_kb > 0 and res.surplus_kb >= 0
    assert res.fingerprint == inst.fingerprint()


def test_runner_csv(tmp_path):
    csv_path = tmp_path / "out.csv"
    instances = [make_instance("poliqi5", n_req=8, seed=s) for s in (1, 2)]
    results = run_benchmark(instances, ["greedy_sp"],
                            csv_path=csv_path, verbose=False)
    assert len(results) == 2
    lines = csv_path.read_text().strip().splitlines()
    assert len(lines) == 3  # header + 2 rows
    # resumable: append mode adds rows without duplicating the header
    run_benchmark(instances[:1], ["greedy_sp"], csv_path=csv_path,
                  verbose=False)
    assert len(csv_path.read_text().strip().splitlines()) == 4


def test_registry_lists_builtins():
    assert "greedy_sp" in list_algorithms()
