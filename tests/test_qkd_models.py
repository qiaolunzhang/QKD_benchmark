"""Phase 3: QKD physical model layer.

Covers: registration/factory, per-model physics sanity, bit-exact
equivalence of FiniteSizeTable with the legacy RateTable, model swap
with zero algorithm changes, and memoization.
"""
import math

import pytest

from qkdbench import (Instance, evaluate, get_algorithm, get_qkd_model,
                      get_rate_table, make_instance)
from qkdbench.core.registry import registry
from qkdbench.scenario.qkd_models import (ConstantRate, DistanceExponential,
                                          FiniteSizeTable, KeyGenResult,
                                          KeyGenerationModel,
                                          SimplifiedDecoyBB84,
                                          available_models)
from qkdbench.scenario.qkd_models.base import _cached_evaluate

ALL_MODELS = ["constant", "distance_exponential", "finite_size_table",
              "decoy_bb84"]


# ------------------------------------------------------ registry / factory
def test_all_four_models_registered():
    for name in ALL_MODELS:
        cls = registry.get("qkd_model", name)
        model = get_qkd_model(name)
        assert isinstance(model, cls)
        assert isinstance(model, KeyGenerationModel)
        assert model.name == name and model.version
    assert set(ALL_MODELS) <= set(available_models())


def test_factory_maps_legacy_table_names():
    for table in ("fse_1540_alone", "fse_1310_coex"):
        model = get_qkd_model(table)
        assert isinstance(model, FiniteSizeTable)
        assert model.table == table


def test_factory_forwards_params():
    assert get_qkd_model("constant", rate_kbps=7.5).rate_kbps == 7.5
    assert get_qkd_model("finite_size_table",
                         table="fse_1310_coex").table == "fse_1310_coex"


# ----------------------------------------------------------------- constant
def test_constant_rate_is_constant():
    m = get_qkd_model("constant", rate_kbps=50.0)
    for km in (0.0, 1.0, 100.0, 5000.0):
        res = m.evaluate(km)
        assert res.feasible and res.skr_kbps == 50.0
    assert m.max_reach_km() == math.inf
    assert m.tp_keys_kb(42.0, n_slots=3, slot_seconds=2.0) == 50.0 * 6.0


# ----------------------------------------------------------------- distance
def test_distance_exponential_monotone_and_cutoff():
    m = get_qkd_model("distance_exponential")   # r0=100, alpha=0.2
    assert m.evaluate(0.0).skr_kbps == pytest.approx(100.0)
    rates = [m.evaluate(km).skr_kbps for km in range(0, 251, 10)]
    assert all(a > b for a, b in zip(rates, rates[1:]))
    # analytic reach: 10*log10(1e5)/0.2 = 250 km
    assert m.max_reach_km() == pytest.approx(250.0)
    assert m.feasible(249.0) and not m.feasible(251.0)
    beyond = m.evaluate(300.0)
    assert not beyond.feasible and beyond.skr_kbps == 0.0 and beyond.reason


# -------------------------------------------------- finite-size equivalence
@pytest.mark.parametrize("table", ["fse_1540_alone", "fse_1310_coex"])
def test_finite_size_bitwise_identical_to_legacy_rate_table(table):
    model = get_qkd_model(table)
    legacy = get_rate_table(table)
    distances = list(legacy.buckets) + [7.3, 12.9, 33.333]
    for km in distances:
        assert model.bucket(km) == legacy.bucket(km)
        for tau in range(1, int(legacy.max_tau_s) + 1):
            assert model.evaluate(km, tau_s=tau).skr_kbps \
                == legacy.rate_kbps(km, tau)
            assert model.tp_keys_kb(km, tau) == legacy.tp_keys_kb(km, tau)
    assert model.max_tau_s == legacy.max_tau_s
    assert model.max_reach_km() == legacy.max_reach_km
    # beyond reach: infeasible, never a crash
    res = model.evaluate(legacy.max_reach_km + 1.0, tau_s=1)
    assert not res.feasible and res.skr_kbps == 0.0
    assert not model.feasible(legacy.max_reach_km + 1.0)


def test_finite_size_defaults_tau_to_one_second():
    m = get_qkd_model("fse_1540_alone")
    assert m.evaluate(5.0).skr_kbps == m.evaluate(5.0, tau_s=1).skr_kbps


# --------------------------------------------------------------- decoy BB84
def test_decoy_bb84_magnitude_monotone_cutoff():
    m = get_qkd_model("decoy_bb84")
    r5 = m.evaluate(5.0)
    assert r5.feasible and 0.1 <= r5.skr_kbps <= 100.0   # kbps at 5 km
    assert 0.0 < r5.qber < 0.05 and r5.loss_db == pytest.approx(1.0)
    rates = [m.evaluate(km).skr_kbps for km in range(0, 150, 10)]
    assert all(a > b for a, b in zip(rates, rates[1:]))
    # beyond the QBER cutoff (~152 km with defaults) no key survives
    assert not m.feasible(200.0)
    assert 100.0 < m.max_reach_km() < 200.0
    far = m.evaluate(300.0)
    assert not far.feasible and far.skr_kbps == 0.0 and far.reason


# ------------------------------------- swap model, algorithm untouched (§5)
def test_model_swap_zero_algorithm_change_on_german7():
    algo = get_algorithm("greedy_sp", k_paths=3)
    fse = evaluate(make_instance("german7", n_req=20, seed=1), algo)
    fast = evaluate(make_instance("german7", n_req=20, seed=1,
                                  rate_table="constant",
                                  qkd_model_params={"rate_kbps": 1000.0}),
                    algo)
    assert fse.feasible and fast.feasible
    # unlimited-reach constant model can only serve more, never fewer
    assert fast.served >= fse.served
    # model identity is recorded with each result
    assert fse.extras["qkd_model"] == "finite_size_table"
    assert fast.extras["qkd_model"] == "constant"
    assert fse.extras["qkd_model_version"] == "1.0"


def test_qkd_model_params_round_trip_and_fingerprint():
    a = make_instance("german7", n_req=5, seed=1)
    b = make_instance("german7", n_req=5, seed=1,
                      rate_table="constant",
                      qkd_model_params={"rate_kbps": 50.0})
    assert a.fingerprint() != b.fingerprint()
    back = Instance.from_json(b.to_json())
    assert back.qkd_model_params == {"rate_kbps": 50.0}
    assert back.fingerprint() == b.fingerprint()


# ------------------------------------------------------------------ memoize
def test_memoize_returns_cached_result_object():
    m = get_qkd_model("distance_exponential")
    r1 = m.evaluate(42.0)
    r2 = m.evaluate(42.0)
    assert r1 is r2                          # same cached object
    # a second instance with identical params shares the cache entry
    assert get_qkd_model("distance_exponential").evaluate(42.0) is r1
    # different params miss the cache
    other = get_qkd_model("distance_exponential", r0_kbps=200.0)
    assert other.evaluate(42.0) is not r1
    # lengths are quantized to 3 decimals for the cache key
    assert m.evaluate(42.0004) is r1


def test_memoize_hit_counter_increases():
    before = _cached_evaluate.cache_info().hits
    m = get_qkd_model("decoy_bb84")
    m.evaluate(11.5, tau_s=2)
    m.evaluate(11.5, tau_s=2)
    assert _cached_evaluate.cache_info().hits > before
