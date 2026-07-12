"""Key-generation model interface (ARCHITECTURE.md §5).

A :class:`KeyGenerationModel` answers exactly one question — *how many
secret-key bits per second does a QKD link of a given length produce?* —
and is the **only** place in the framework where physics lives.
Algorithms, the verifier and the logical-topology derivation all consume
the same model object through this interface, so every component agrees
on the same physical reality (and algorithms never smuggle in their own
key-rate formulas; see ``docs/CONTRIBUTING.md``).

v1 signature note: link attributes are just a length (``length_km``),
so ``evaluate`` takes the length directly rather than a ``Link`` object;
richer per-link data travels through ``device_profile`` / ``environment``
without coupling the model to the network classes.

Memoization: ``evaluate`` results are LRU-cached process-wide on
``(model name, version, frozen params, round(length_km, 3), tau_s)`` —
repeated lookups during a sweep are free, and two model instances with
identical parameters share cache entries (so results are bit-identical
across algorithms by construction).  Materializing expensive models into
precomputed tables under ``datasets/`` is a Phase 7 item; until then the
in-process cache is the single speed/consistency device.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True)
class KeyGenResult:
    """Outcome of one model evaluation.

    Attributes:
        feasible: can this link generate (positive) secret key at all?
        skr_kbps: secret-key rate in kb/s (0.0 when infeasible).
        qber: quantum bit error rate, if the model computes one.
        loss_db: total channel loss in dB, if the model computes one.
        reason: human-readable explanation when ``feasible`` is False.
    """
    feasible: bool
    skr_kbps: float
    qber: Optional[float] = None
    loss_db: Optional[float] = None
    reason: Optional[str] = None


@lru_cache(maxsize=65536)
def _cached_evaluate(model: "KeyGenerationModel", length_km: float,
                     tau_s) -> KeyGenResult:
    """Process-wide memo; the model hashes on (name, version, params)."""
    return model._evaluate(length_km, tau_s)


class KeyGenerationModel(ABC):
    """ABC for QKD physical models.

    Subclasses set the class attributes ``name`` (registry key) and
    ``version`` (bumped on any change that alters numbers), call
    ``super().__init__(**params)`` with their constructor parameters
    (hashable values only — they form the memoization key and are
    recorded in results), and implement :meth:`_evaluate`.
    """

    #: registry name, e.g. ``"constant"`` — set by subclasses
    name: str = None
    #: model version, recorded in Instance/Result — set by subclasses
    version: str = "0.0"

    def __init__(self, **params):
        self._params = dict(params)

    # ------------------------------------------------------------ identity
    @property
    def params(self) -> dict:
        """Constructor parameters (copy)."""
        return dict(self._params)

    def _identity(self):
        return (self.name, self.version, tuple(sorted(self._params.items())))

    def __eq__(self, other):
        return (isinstance(other, KeyGenerationModel)
                and self._identity() == other._identity())

    def __hash__(self):
        return hash(self._identity())

    def __repr__(self):
        args = ", ".join(f"{k}={v!r}" for k, v in sorted(self._params.items()))
        return f"{type(self).__name__}({args})"

    # ----------------------------------------------------------- interface
    def evaluate(self, length_km: float, tau_s: float = None,
                 device_profile=None, time=None,
                 environment=None) -> KeyGenResult:
        """Secret-key rate of a link of ``length_km`` km.

        Args:
            length_km: link length (v1: the only link attribute that
                matters; quantized to 3 decimals for memoization).
            tau_s: transmission-period duration in seconds, for models
                whose rate depends on it (finite-size effects).
            device_profile, time, environment: reserved extension hooks
                (v1 models ignore them; passing any of them bypasses
                the memo cache).
        """
        length_km = round(float(length_km), 3)
        if device_profile is not None or time is not None \
                or environment is not None:
            return self._evaluate(length_km, tau_s)
        return _cached_evaluate(self, length_km, tau_s)

    @abstractmethod
    def _evaluate(self, length_km: float, tau_s) -> KeyGenResult:
        """Model-specific computation (uncached; called via memo)."""

    # -------------------------------------------------------- conveniences
    #: longest TP duration (s) the model can rate; ``inf`` = no limit
    max_tau_s: float = math.inf

    def tp_keys_kb(self, length_km: float, n_slots: int,
                   slot_seconds: float = 1.0) -> float:
        """Keys (kb) delivered by one TP of ``n_slots`` slots."""
        tau = n_slots * slot_seconds
        return self.evaluate(length_km, tau_s=tau).skr_kbps * tau

    def feasible(self, length_km: float) -> bool:
        """Can a link of this length generate secret key at all?"""
        return self.evaluate(length_km).feasible

    def max_reach_km(self, hi_km: float = 20000.0,
                     tol_km: float = 1e-3) -> float:
        """Longest feasible link length (generic bisection fallback;
        models with an analytic or tabulated reach override this)."""
        if not self.feasible(0.0):
            return 0.0
        if self.feasible(hi_km):
            return math.inf
        lo, hi = 0.0, hi_km
        while hi - lo > tol_km:
            mid = (lo + hi) / 2.0
            if self.feasible(mid):
                lo = mid
            else:
                hi = mid
        return lo
