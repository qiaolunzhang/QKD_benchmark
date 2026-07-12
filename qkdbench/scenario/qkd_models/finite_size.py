"""Finite-size table model — the benchmark's differentiating physics.

Wraps the Yin-2020 finite-key rate tables of
:mod:`qkdbench.keyrate.finite_size` (the tables stay there — single data
source; the legacy :class:`~qkdbench.keyrate.finite_size.RateTable` is
this model's internal implementation).  The rate depends on **both** the
distance and the TP duration ``tau_s``: longer TPs accumulate more raw
detections, so the finite-size penalty shrinks and the *rate itself*
grows with ``tau`` — the non-linearity the benchmark is built around.

Two regimes are available via the ``table`` constructor parameter:
``fse_1540_alone`` (dedicated fibre) and ``fse_1310_coex`` (coexisting
with classical traffic).  Those two names are also accepted directly by
:func:`~qkdbench.scenario.qkd_models.get_qkd_model` for backward
compatibility with the Phase-0 ``rate_table`` field.
"""
from __future__ import annotations

from ...core.registry import registry
from ...keyrate.finite_size import RateTable
from .base import KeyGenerationModel, KeyGenResult


@registry.register("qkd_model", "finite_size_table")
class FiniteSizeTable(KeyGenerationModel):
    """Tabulated finite-size SKR; rate depends on (distance, tau).

    ``evaluate`` requires ``tau_s`` in principle; when omitted the
    shortest tabulated TP (``tau = 1`` s) is used.
    """

    name = "finite_size_table"
    version = "1.0"

    def __init__(self, table: str = "fse_1540_alone"):
        super().__init__(table=table)
        self._table = RateTable(table)   # single data source (keyrate/)

    @property
    def table(self) -> str:
        """Name of the underlying rate table (regime)."""
        return self._table.name

    def _evaluate(self, length_km, tau_s) -> KeyGenResult:
        tau = 1.0 if tau_s is None else tau_s
        bucket = self._table.bucket(length_km)
        if bucket is None:
            return KeyGenResult(
                feasible=False, skr_kbps=0.0,
                reason=(f"{length_km} km beyond the {self._table.name} "
                        f"reach ({self._table.max_reach_km} km)"))
        skr = self._table.rate_kbps(length_km, tau)  # KeyError if tau
        if skr <= 0.0:                               # is not tabulated
            return KeyGenResult(
                feasible=False, skr_kbps=0.0,
                reason=(f"zero tabulated rate at {bucket} km "
                        f"for tau={tau} s"))
        return KeyGenResult(feasible=True, skr_kbps=skr)

    # ------------------------------------------------- reach / feasibility
    def feasible(self, length_km: float) -> bool:
        """Within tabulated reach (some tau yields key, maybe not tau=1)."""
        return self._table.bucket(length_km) is not None

    def max_reach_km(self, **_) -> float:
        return float(self._table.max_reach_km)

    # --------------------------------- legacy RateTable compatibility face
    @property
    def max_tau_s(self) -> float:
        return self._table.max_tau_s

    @property
    def buckets(self):
        return self._table.buckets

    def bucket(self, distance_km: float):
        return self._table.bucket(distance_km)

    def rate_kbps(self, distance_km: float, tau_s: float) -> float:
        return self._table.rate_kbps(distance_km, tau_s)
