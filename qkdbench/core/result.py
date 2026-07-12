"""Standard benchmark result record.

One :class:`Result` per (algorithm, instance) run.  The runner fills in
the verified metrics — algorithms only produce a
:class:`~qkdbench.core.solution.Solution`; they never report their own
scores.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

CSV_FIELDS = [
    "algorithm", "instance", "fingerprint", "seed",
    "served", "total_requests", "acceptance_ratio",
    "delivered_kb", "surplus_kb", "runtime_s", "feasible", "status",
]


@dataclass
class Result:
    algorithm: str
    instance: str
    fingerprint: str
    seed: int = 0
    served: int = 0
    total_requests: int = 0
    delivered_kb: float = 0.0        # keys produced by all accepted TPs
    surplus_kb: float = 0.0          # delivered - requested (stored surplus)
    runtime_s: float = 0.0
    feasible: bool = True            # verifier verdict
    status: str = "ok"               # ok | infeasible | error
    violations: list = field(default_factory=list)
    objectives: dict = field(default_factory=dict)   # problem objective values
    extras: dict = field(default_factory=dict)

    @property
    def acceptance_ratio(self) -> float:
        return self.served / self.total_requests if self.total_requests else 0.0

    def to_row(self) -> dict:
        d = asdict(self)
        d["acceptance_ratio"] = round(self.acceptance_ratio, 6)
        return {k: d[k] for k in CSV_FIELDS}
