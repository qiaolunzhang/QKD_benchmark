"""Exponential fibre-loss model: the simplest physical model.

``skr = r0_kbps * 10^(-alpha_db_km * L / 10)`` — the rate at zero
distance attenuated by standard fibre loss.  Links are cut off
(``feasible=False``) once the rate drops below ``min_kbps``.
"""
from __future__ import annotations

import math

from ...core.registry import registry
from .base import KeyGenerationModel, KeyGenResult


@registry.register("qkd_model", "distance_exponential")
class DistanceExponential(KeyGenerationModel):
    """SKR decays exponentially with distance (fibre loss only).

    Args:
        r0_kbps: rate at zero distance (kb/s).
        alpha_db_km: fibre attenuation (dB/km; 0.2 is standard SMF-28
            at 1550 nm).
        min_kbps: below this rate the link is declared infeasible.
    """

    name = "distance_exponential"
    version = "1.0"

    def __init__(self, r0_kbps: float = 100.0, alpha_db_km: float = 0.2,
                 min_kbps: float = 1e-3):
        super().__init__(r0_kbps=float(r0_kbps),
                         alpha_db_km=float(alpha_db_km),
                         min_kbps=float(min_kbps))
        self.r0_kbps = float(r0_kbps)
        self.alpha_db_km = float(alpha_db_km)
        self.min_kbps = float(min_kbps)

    def _evaluate(self, length_km, tau_s) -> KeyGenResult:
        loss_db = self.alpha_db_km * length_km
        skr = self.r0_kbps * 10.0 ** (-loss_db / 10.0)
        if skr < self.min_kbps:
            return KeyGenResult(
                feasible=False, skr_kbps=0.0, loss_db=loss_db,
                reason=(f"{skr:.3e} kb/s at {length_km} km below the "
                        f"{self.min_kbps} kb/s cutoff"))
        return KeyGenResult(feasible=True, skr_kbps=skr, loss_db=loss_db)

    def max_reach_km(self, **_) -> float:
        """Analytic reach: distance where skr hits ``min_kbps``."""
        if self.alpha_db_km <= 0:
            return math.inf
        return 10.0 * math.log10(self.r0_kbps / self.min_kbps) \
            / self.alpha_db_km
