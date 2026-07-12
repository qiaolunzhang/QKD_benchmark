"""Finite-size secret-key-rate tables.

Rates come from the ``SKR_finite_python`` generator (Yin et al. 2020 tight
finite-key bounds; decoy-state BB84, 10 MHz repetition rate, parameters
optimized per cell).  Two regimes are tabulated:

* ``fse_1540_alone`` — quantum channel at 1540 nm on a dedicated fibre.
* ``fse_1310_coex``  — quantum at 1310 nm coexisting with a 5 dBm
  classical channel at 1540 nm (Raman-noise limited; 2-4x lower rates).

Table format: ``{distance_km: {tp_duration_s: rate_kbps}}``.  The key
volume delivered by one transmission period (TP) of duration ``tau`` at
``distance`` is ``rate(distance, tau) * tau`` — note the rate itself grows
with ``tau``: that non-linearity is the finite-size effect the benchmark
is built around.

Distances are rounded *up* to the nearest tabulated value (conservative),
so arbitrary link lengths are supported up to the maximum reach.
"""
from __future__ import annotations

FSE_1540_ALONE_KBPS = {
    5:  {1: 44.6305, 2: 62.1236, 3: 72.1569, 4: 79.1026, 5: 84.3713, 6: 88.5923, 7: 92.0996, 8: 95.0909, 9: 97.6927, 10: 99.9906},
    10: {1: 29.4564, 2: 42.9745, 3: 50.8401, 4: 56.3197, 5: 60.4912, 6: 63.8412, 7: 66.6293, 8: 69.0103, 9: 71.0833, 10: 72.9156},
    15: {1: 18.9633, 2: 29.3199, 3: 35.4511, 4: 39.7550, 5: 43.0460, 6: 45.6963, 7: 47.9067, 8: 49.7972, 9: 51.4450, 10: 52.9029},
    20: {1: 11.8115, 2: 19.6627, 3: 24.4085, 4: 27.7709, 5: 30.3556, 6: 32.4445, 7: 34.1911, 8: 35.6876, 9: 36.9939, 10: 38.1511},
    25: {1: 7.0280, 2: 12.9027, 3: 16.5449, 4: 19.1542, 5: 21.1732, 6: 22.8120, 7: 24.1863, 8: 25.3666, 9: 26.3988, 10: 27.3144},
    30: {1: 3.9068, 2: 8.2321, 3: 10.9978, 4: 13.0063, 5: 14.5728, 6: 15.8510, 7: 16.9269, 8: 17.8536, 9: 18.6658, 10: 19.3875},
    35: {1: 1.9378, 2: 5.0579, 3: 7.1309, 4: 8.6614, 5: 9.8667, 6: 10.8564, 7: 11.6934, 8: 12.4168, 9: 13.0526, 10: 13.6188},
    40: {1: 0.7538, 2: 2.9463, 3: 4.4749, 4: 5.6267, 5: 6.5445, 6: 7.3041, 7: 7.9501, 8: 8.5108, 9: 9.0053, 10: 9.4468},
    45: {1: 0.0, 2: 1.5806, 3: 2.6848, 4: 3.5383, 5: 4.2282, 6: 4.8048, 7: 5.2985, 8: 5.7293, 9: 6.1107, 10: 6.4524},
    50: {1: 0.0, 2: 0.7311, 3: 1.5077, 4: 2.1278, 5: 2.6382, 6: 3.0698, 7: 3.4425, 8: 3.7698, 9: 4.0611, 10: 4.3232},
    55: {1: 0.0, 2: 0.2319, 3: 0.7591, 4: 1.1983, 5: 1.5682, 6: 1.8857, 7: 2.1628, 8: 2.4081, 9: 2.6277, 10: 2.8263},
    60: {1: 0.0, 2: 0.0, 3: 0.3050, 4: 0.6057, 5: 0.8668, 6: 1.0952, 7: 1.2972, 8: 1.4778, 9: 1.6408, 10: 1.7891},
    65: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.2454, 5: 0.4232, 6: 0.5828, 7: 0.7264, 8: 0.8564, 9: 0.9749, 10: 1.0835},
    70: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.1569, 6: 0.2640, 7: 0.3626, 8: 0.4535, 9: 0.5373, 10: 0.6150},
}

FSE_1310_COEX_KBPS = {
    5:  {1: 34.9236, 2: 49.9401, 3: 58.6242, 4: 64.6574, 5: 69.2432, 6: 72.9219, 7: 75.9814, 8: 78.5926, 9: 80.8650, 10: 82.8728},
    10: {1: 17.3438, 2: 27.1708, 3: 33.0103, 4: 37.1162, 5: 40.2585, 6: 42.7906, 7: 44.9032, 8: 46.7105, 9: 48.2862, 10: 49.6805},
    15: {1: 7.8545, 2: 14.1042, 3: 17.9571, 4: 20.7106, 5: 22.8380, 6: 24.5631, 7: 26.0087, 8: 27.2495, 9: 28.3342, 10: 29.2959},
    20: {1: 3.0094, 2: 6.8269, 3: 9.3028, 4: 11.1121, 5: 12.5281, 6: 13.6864, 7: 14.6630, 8: 15.5052, 9: 16.2441, 10: 16.9011},
    25: {1: 0.7491, 2: 2.9479, 3: 4.4809, 4: 5.6360, 5: 6.5565, 6: 7.3183, 7: 7.9662, 8: 8.5285, 9: 9.0244, 10: 9.4672},
    30: {1: 0.0, 2: 1.0148, 3: 1.9141, 4: 2.6221, 5: 3.2006, 6: 3.6873, 7: 4.1062, 8: 4.4730, 9: 4.7988, 10: 5.0914},
    35: {1: 0.0, 2: 0.0, 3: 0.6404, 4: 1.0491, 5: 1.3954, 6: 1.6936, 7: 1.9546, 8: 2.1861, 9: 2.3937, 10: 2.5817},
    40: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.2946, 5: 0.4871, 6: 0.6589, 7: 0.8129, 8: 0.9520, 9: 1.0786, 10: 1.1945},
    45: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.1687, 7: 0.2522, 8: 0.3298, 9: 0.4020, 10: 0.4692},
    50: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0876, 10: 0.1229},
}

_TABLES = {
    "fse_1540_alone": FSE_1540_ALONE_KBPS,
    "fse_1310_coex": FSE_1310_COEX_KBPS,
}


class RateTable:
    """Lookup helper around one tabulated rate regime."""

    def __init__(self, name: str = "fse_1540_alone"):
        if name not in _TABLES:
            raise KeyError(f"unknown rate table {name!r}; "
                           f"available: {sorted(_TABLES)}")
        self.name = name
        self.table = _TABLES[name]
        self.buckets = sorted(self.table)
        self.max_reach_km = self.buckets[-1]
        self.max_tau_s = max(self.table[self.buckets[0]])

    def bucket(self, distance_km: float):
        """Smallest tabulated distance >= ``distance_km`` (round-up), or
        ``None`` if beyond the maximum tabulated reach."""
        for b in self.buckets:
            if distance_km <= b + 1e-9:
                return b
        return None

    def rate_kbps(self, distance_km: float, tau_s: float) -> float:
        """Secret-key rate (kb/s) at ``distance_km`` for a TP of ``tau_s``."""
        b = self.bucket(distance_km)
        if b is None:
            return 0.0
        tau = int(round(tau_s))
        if tau not in self.table[b]:
            raise KeyError(f"TP duration {tau_s}s not tabulated "
                           f"(1..{self.max_tau_s}s)")
        return self.table[b][tau]

    def tp_keys_kb(self, distance_km: float, n_slots: int,
                   slot_seconds: float = 1.0) -> float:
        """Keys (kb) delivered by one TP of ``n_slots`` slots."""
        tau = n_slots * slot_seconds
        return self.rate_kbps(distance_km, tau) * tau


def get_rate_table(name: str) -> RateTable:
    return RateTable(name)


def available_tables():
    return sorted(_TABLES)
