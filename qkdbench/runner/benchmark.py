"""Benchmark runner: algorithms x instances -> verified results -> CSV.

The runner is the only component that produces metrics.  For each
(algorithm, instance) pair it

1. runs ``algorithm.solve(instance)`` under a wall-clock timer,
2. passes the solution through the independent verifier,
3. computes delivered/surplus keys from the *verified* assignments,
4. appends a :class:`~qkdbench.core.result.Result` row.

Results append to CSV incrementally, so long sweeps can be interrupted
and resumed without losing finished cells.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Iterable, List

from ..core.algorithm import Algorithm, get_algorithm
from ..core.instance import Instance
from ..core.result import CSV_FIELDS, Result
from ..core.verifier import route_length_km, verify
from ..scenario.qkd_models import get_qkd_model


def evaluate(instance: Instance, algorithm: Algorithm,
             seed: int = 0) -> Result:
    """Run one algorithm on one instance and verify the outcome."""
    t0 = time.perf_counter()
    try:
        solution = algorithm.solve(instance)
        runtime = time.perf_counter() - t0
    except Exception as exc:  # algorithm crashed: record, don't abort sweep
        return Result(algorithm=algorithm.name, instance=instance.name,
                      fingerprint=instance.fingerprint(), seed=seed,
                      total_requests=len(instance.requests),
                      runtime_s=time.perf_counter() - t0,
                      feasible=False, status="error",
                      violations=[f"{type(exc).__name__}: {exc}"])

    if instance.horizon_s is not None:      # dynamic problem (P2)
        return _evaluate_dynamic(instance, algorithm, solution, runtime, seed)

    verdict = verify(instance, solution)
    model = get_qkd_model(instance.rate_table, **instance.qkd_model_params)
    delivered = surplus = 0.0
    if verdict.ok:
        for a in solution.assignments:
            req = instance.request_by_id(a.request_id)
            keys = model.tp_keys_kb(route_length_km(instance, a.route),
                                    a.n_slots, instance.slot_seconds)
            delivered += keys
            surplus += keys - req.volume_kb

    return Result(
        algorithm=algorithm.name, instance=instance.name,
        fingerprint=instance.fingerprint(), seed=seed,
        served=len(solution.assignments) if verdict.ok else 0,
        total_requests=len(instance.requests),
        delivered_kb=round(delivered, 3), surplus_kb=round(surplus, 3),
        runtime_s=round(runtime, 6),
        feasible=verdict.ok,
        status="ok" if verdict.ok else "infeasible",
        violations=verdict.violations,
        extras={**solution.extras, "qkd_model": model.name,
                "qkd_model_version": model.version},
    )


def _evaluate_dynamic(instance, algorithm, solution, runtime, seed) -> Result:
    """Verify and score a dynamic (P2) solution via its problem modules."""
    from ..problems.base import get_problem

    problem = get_problem("dynamic_admission_keypool")
    verdict = problem.verify(instance, solution)
    objectives = problem.evaluate_objectives(instance, solution) \
        if verdict.ok else {}
    return Result(
        algorithm=algorithm.name, instance=instance.name,
        fingerprint=instance.fingerprint(), seed=seed,
        served=len(solution.admitted_ids) if verdict.ok else 0,
        total_requests=len(instance.demands),
        runtime_s=round(runtime, 6),
        feasible=verdict.ok,
        status="ok" if verdict.ok else "infeasible",
        violations=verdict.violations,
        objectives=objectives,
        extras=dict(solution.extras),
    )


def run_benchmark(instances: Iterable[Instance], algorithm_names,
                  algo_params: dict = None, csv_path=None,
                  verbose: bool = True) -> List[Result]:
    """Full sweep; optionally append rows to ``csv_path`` as they finish."""
    algo_params = algo_params or {}
    results = []
    writer, fh = None, None
    if csv_path is not None:
        path = Path(csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists()
        fh = open(path, "a", newline="")
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()

    try:
        for inst in instances:
            for name in algorithm_names:
                algo = get_algorithm(name, **algo_params.get(name, {}))
                res = evaluate(inst, algo,
                               seed=inst.metadata.get("seed", 0))
                results.append(res)
                if writer:
                    writer.writerow(res.to_row())
                    fh.flush()
                if verbose:
                    print(f"[{res.status:>10}] {inst.name:<28} "
                          f"{name:<12} served {res.served}/"
                          f"{res.total_requests}  "
                          f"{res.runtime_s * 1e3:8.1f} ms")
                    for v in res.violations[:5]:
                        print(f"             ! {v}")
    finally:
        if fh:
            fh.close()
    return results
