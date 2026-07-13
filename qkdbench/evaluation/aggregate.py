"""Multi-seed aggregation with confidence intervals.

Benchmark results are only meaningful across seeds — a single run hides
variance.  This aggregates a results CSV into per-(algorithm, group) rows
carrying the mean, standard deviation and a Student-t 95% confidence
interval, so plots and tables report ``mean ± CI`` (the reproducibility
bar the JSAC reviewers, rightly, asked for).

No SciPy dependency: the two-sided 95% t critical values are tabulated for
small degrees of freedom (the regime that matters for seed counts).
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

# two-sided 95% Student-t critical values, df = 1..30, then large-sample z
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
        13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
        19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
        25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def t_critical_95(df: int) -> float:
    if df <= 0:
        return float("nan")
    return _T95.get(df, 1.96)   # z_0.975 for large samples


@dataclass
class Aggregate:
    mean: float
    std: float
    n: int
    ci95: float                 # half-width; report mean ± ci95

    def as_tuple(self):
        return (round(self.mean, 6), round(self.ci95, 6), self.n)


def summarize(values: List[float]) -> Aggregate:
    n = len(values)
    if n == 0:
        return Aggregate(float("nan"), float("nan"), 0, float("nan"))
    mean = sum(values) / n
    if n == 1:
        return Aggregate(mean, 0.0, 1, 0.0)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = math.sqrt(var)
    ci = t_critical_95(n - 1) * std / math.sqrt(n)
    return Aggregate(mean, std, n, ci)


def aggregate_csv(csv_path, metric: str = "served",
                  group_keys=("algorithm", "instance")) -> Dict[tuple, Aggregate]:
    """Aggregate one metric column of a results CSV.

    Groups rows by ``group_keys`` (default per algorithm+instance, i.e.
    across seeds of the same instance name is *not* what you want for a
    sweep — pass e.g. ``("algorithm",)`` plus a derived group, or strip
    the seed from the instance name upstream).  Returns
    ``{group_tuple: Aggregate}``.
    """
    buckets: Dict[tuple, List[float]] = defaultdict(list)
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            key = tuple(row[k] for k in group_keys)
            try:
                buckets[key].append(float(row[metric]))
            except (KeyError, ValueError):
                continue
    return {k: summarize(v) for k, v in buckets.items()}


def aggregate_by(csv_path, metric: str, algorithm_key="algorithm",
                 x_from_instance=None) -> Dict[str, Dict[float, Aggregate]]:
    """Aggregate ``metric`` across seeds into curves per algorithm.

    ``x_from_instance(instance_name) -> x`` extracts the sweep variable
    (e.g. the request count) from the instance name; rows sharing
    (algorithm, x) are averaged across their seeds.  Returns
    ``{algorithm: {x: Aggregate}}`` ready for :mod:`qkdbench.evaluation.plots`.
    """
    if x_from_instance is None:
        x_from_instance = _default_x
    buckets: Dict[str, Dict[float, List[float]]] = defaultdict(
        lambda: defaultdict(list))
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                x = x_from_instance(row["instance"])
                buckets[row[algorithm_key]][x].append(float(row[metric]))
            except (KeyError, ValueError, TypeError):
                continue
    return {algo: {x: summarize(vals) for x, vals in xs.items()}
            for algo, xs in buckets.items()}


def _default_x(instance_name: str) -> float:
    """Pull the sweep integer out of names like ``german7_nreq20_s3``."""
    import re
    m = re.search(r"(?:nreq|dyn|place)(\d+)", instance_name)
    if not m:
        raise ValueError(f"cannot parse sweep x from {instance_name!r}")
    return float(m.group(1))
