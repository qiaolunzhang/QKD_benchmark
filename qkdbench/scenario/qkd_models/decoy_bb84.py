"""Simplified decoy-state BB84: closed-form *asymptotic* key rate.

Model (secret bits per second)::

    R = 0.5 * q * mu * t * eta_det * f_rep * [1 - f_ec*h2(E) - h2(E)]

with

* ``t = 10^(-alpha_db_km * L / 10)`` — channel transmittance over ``L`` km,
* ``0.5`` — BB84 basis-sifting factor,
* ``q`` — residual protocol/duty-cycle efficiency (default 1.0),
* ``mu * t * eta_det`` — signal detection probability per pulse
  (linearized gain; the dark-count contribution ``y0`` is kept in the
  QBER but dropped from the gain, valid while ``mu*t*eta_det >> y0``),
* ``E = (0.5*y0 + e_mis * mu*t*eta_det) / (y0 + mu*t*eta_det)`` — QBER:
  dark counts are random (error 1/2), signal photons err with the
  misalignment probability ``e_mis``,
* ``h2`` — binary entropy; ``f_ec*h2(E)`` is the error-correction leak
  (``f_ec`` = reconciliation inefficiency) and ``h2(E)`` the
  privacy-amplification term, i.e. an error penalty of the familiar
  ``1 - 2*h2(E)`` shape (exactly that for ``f_ec = 1``).

Assumptions / simplifications (documented on purpose):

* **Asymptotic** limit — infinite decoy states, perfect single-photon
  yield/error estimation, *no finite-size effects* (contrast with
  :class:`~qkdbench.scenario.qkd_models.finite_size.FiniteSizeTable`);
  consequently the rate is independent of ``tau_s``.
* Single-photon fraction and after-pulsing ignored; one lumped
  misalignment error; detector dark counts folded into ``y0``.

Feasible while the bracket is positive; QBER grows toward 1/2 as the
signal fades into dark counts, so beyond a cutoff distance (~152 km with
default parameters) the rate is zero and ``feasible=False``.
"""
from __future__ import annotations

import math

from ...core.registry import registry
from .base import KeyGenerationModel, KeyGenResult


def _h2(p: float) -> float:
    """Binary entropy (bits)."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


@registry.register("qkd_model", "decoy_bb84")
class SimplifiedDecoyBB84(KeyGenerationModel):
    """Closed-form asymptotic decoy-state BB84 (see module docstring).

    Args:
        mu: mean signal-pulse photon number.
        eta_det: detector efficiency.
        f_rep_hz: pulse repetition rate (Hz).
        alpha_db_km: fibre attenuation (dB/km).
        e_mis: optical misalignment error probability.
        y0: background/dark-count yield per pulse.
        f_ec: error-correction inefficiency (>= 1).
        q: residual protocol efficiency multiplier.
    """

    name = "decoy_bb84"
    version = "1.0"

    def __init__(self, mu: float = 0.5, eta_det: float = 0.1,
                 f_rep_hz: float = 1e6, alpha_db_km: float = 0.2,
                 e_mis: float = 0.01, y0: float = 1e-5,
                 f_ec: float = 1.16, q: float = 1.0):
        super().__init__(mu=float(mu), eta_det=float(eta_det),
                         f_rep_hz=float(f_rep_hz),
                         alpha_db_km=float(alpha_db_km),
                         e_mis=float(e_mis), y0=float(y0),
                         f_ec=float(f_ec), q=float(q))
        self.mu = float(mu)
        self.eta_det = float(eta_det)
        self.f_rep_hz = float(f_rep_hz)
        self.alpha_db_km = float(alpha_db_km)
        self.e_mis = float(e_mis)
        self.y0 = float(y0)
        self.f_ec = float(f_ec)
        self.q = float(q)

    def _evaluate(self, length_km, tau_s) -> KeyGenResult:
        loss_db = self.alpha_db_km * length_km
        t = 10.0 ** (-loss_db / 10.0)
        sig = self.mu * t * self.eta_det          # signal detections/pulse
        qber = (0.5 * self.y0 + self.e_mis * sig) / (self.y0 + sig)
        bracket = 1.0 - self.f_ec * _h2(qber) - _h2(qber)
        skr_kbps = 0.5 * self.q * sig * self.f_rep_hz * bracket / 1000.0
        if skr_kbps <= 0.0:
            return KeyGenResult(
                feasible=False, skr_kbps=0.0, qber=qber, loss_db=loss_db,
                reason=(f"QBER {qber:.3f} at {length_km} km leaves no "
                        f"positive asymptotic key rate"))
        return KeyGenResult(feasible=True, skr_kbps=skr_kbps,
                            qber=qber, loss_db=loss_db)
