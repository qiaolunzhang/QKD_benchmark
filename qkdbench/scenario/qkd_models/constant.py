"""Constant-rate model: same SKR at any distance (debug / control)."""
from __future__ import annotations

import math

from ...core.registry import registry
from .base import KeyGenerationModel, KeyGenResult


@registry.register("qkd_model", "constant")
class ConstantRate(KeyGenerationModel):
    """``skr = rate_kbps`` everywhere; every link is feasible.

    Useful as an experimental control: running the same instance under
    ``constant`` isolates the routing/scheduling difficulty from the
    physical-layer difficulty.
    """

    name = "constant"
    version = "1.0"

    def __init__(self, rate_kbps: float = 100.0):
        super().__init__(rate_kbps=float(rate_kbps))
        self.rate_kbps = float(rate_kbps)

    def _evaluate(self, length_km, tau_s) -> KeyGenResult:
        return KeyGenResult(feasible=True, skr_kbps=self.rate_kbps)

    def max_reach_km(self, **_) -> float:
        return math.inf
