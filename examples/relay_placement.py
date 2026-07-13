"""Trusted-relay placement (P3): greedy vs. exact minimum cost.

Users need keys with partners they cannot reach in one QKD hop; the
benchmark asks for the cheapest set of intermediate trusted relays that
connects every demand over QKD-feasible links.

    python examples/relay_placement.py
"""
from qkdbench import evaluate, get_algorithm, make_placement_instance

inst = make_placement_instance("usnet24", n_demands=12, seed=1)
print(f"instance {inst.name}: {len(inst.demands)} demands, "
      f"{len(inst.metadata['users'])} users, "
      f"{len(inst.nodes) - len(inst.metadata['users'])} candidate relays")

for name in ("greedy_placement", "milp_placement"):
    r = evaluate(inst, get_algorithm(name))
    print(f"{name:>16}: {r.served} relays, "
          f"cost {r.objectives['deployment_cost']:.0f}, "
          f"feasible={r.feasible}, {r.runtime_s * 1e3:.0f} ms "
          f"{r.extras.get('solver_status', '')}")
