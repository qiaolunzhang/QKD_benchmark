"""How to plug YOUR algorithm into qkdbench — one class, one decorator.

The example algorithm below is deliberately naive: it serves each request
on its single shortest path with the full-horizon TP, first wavelength
that fits.  Copy this file, rename the class, replace `solve`.

    python examples/add_your_algorithm.py
"""
import networkx as nx

from qkdbench import (Algorithm, Assignment, Solution, edge_key, evaluate,
                      get_algorithm, get_qkd_model, make_instance,
                      register_algorithm)


@register_algorithm
class NaiveFullHorizon(Algorithm):
    """Serve everything on the shortest path with a max-length TP."""

    name = "naive_full_horizon"

    def solve(self, instance):
        # physics only via the instance's QKD model — never your own
        # key-rate formula (docs/CONTRIBUTING.md)
        table = get_qkd_model(instance.rate_table,
                              **instance.qkd_model_params)
        g = instance.graph()
        used = set()  # (link, wavelength, slot)
        out = []
        for req in instance.requests:
            path = nx.shortest_path(g, req.src, req.dst, weight="length_km")
            links = [edge_key(a, b) for a, b in zip(path, path[1:])]
            length = sum(instance.edges[l] for l in links)
            n_slots = min(req.deadline_slot,
                          int(table.max_tau_s / instance.slot_seconds))
            if table.tp_keys_kb(length, n_slots,
                                instance.slot_seconds) < req.volume_kb:
                continue  # not enough keys even with the longest TP
            for wl in range(instance.wavelengths):
                cells = {(l, wl, s) for l in links
                         for s in range(1, n_slots + 1)}
                if not (cells & used):
                    used |= cells
                    out.append(Assignment(request_id=req.id, route=links,
                                          wavelength=wl, tp_start=1,
                                          tp_end=n_slots))
                    break
        return Solution(algorithm=self.name, assignments=out)


if __name__ == "__main__":
    inst = make_instance("german7", n_req=20, seed=1)
    for name in ("greedy_sp", "naive_full_horizon"):
        r = evaluate(inst, get_algorithm(name))
        print(f"{name:>20}: served {r.served}/{r.total_requests}, "
              f"feasible={r.feasible}"
              + (f"  violations={r.violations[:2]}" if not r.feasible else ""))
