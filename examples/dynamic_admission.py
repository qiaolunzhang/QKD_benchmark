"""Dynamic admission + key-pool problem (P2) in a few lines.

Demands arrive over continuous time; the online controller admits each
onto a route whose links still have spare key-generation rate, or blocks
it.  The benchmark verifies the admissions against every link's key-pool
capacity and reports the acceptance ratio.

    python examples/dynamic_admission.py
"""
from qkdbench import evaluate, get_algorithm, make_dynamic_instance

for arrival_rate in (2.0, 6.0, 10.0):
    inst = make_dynamic_instance(
        "german7", n_demands=80, seed=1,
        arrival_rate=arrival_rate, mean_holding=8.0,
        rate_lo_kbps=20.0, rate_hi_kbps=40.0,
        rate_table="constant", qkd_model_params={"rate_kbps": 30})
    r = evaluate(inst, get_algorithm("greedy_admission"))
    acc = r.objectives["acceptance_ratio"]
    print(f"arrival_rate={arrival_rate:4.1f}  "
          f"admitted {r.served:2d}/{r.total_requests}  "
          f"acceptance {acc:.0%}  feasible={r.feasible}")
