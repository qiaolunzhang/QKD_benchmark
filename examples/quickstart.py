"""qkdbench in 20 lines: build an instance, run a baseline, verify, print.

    python examples/quickstart.py
"""
from qkdbench import evaluate, get_algorithm, make_instance

# 1. One shared instance (JSON-serializable; fingerprint pins it down).
inst = make_instance("german7", n_req=20, seed=1,
                     num_slots=5, wavelengths=2, modules_per_node=2)
print(f"instance {inst.name}  fingerprint={inst.fingerprint()}")

# 2. Any registered algorithm by name.
algo = get_algorithm("greedy_sp", k_paths=3)

# 3. The framework runs it, verifies feasibility and computes metrics.
result = evaluate(inst, algo)
print(f"served {result.served}/{result.total_requests} "
      f"({result.acceptance_ratio:.0%}), "
      f"delivered {result.delivered_kb:.0f} kb, "
      f"feasible={result.feasible}, {result.runtime_s * 1e3:.1f} ms")
