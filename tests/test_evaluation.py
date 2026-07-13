"""Phase 7: aggregation, plotting, provenance, capability checks."""
import json

from qkdbench import get_algorithm, make_instance, run_benchmark
from qkdbench.evaluation.aggregate import summarize, t_critical_95, aggregate_by
from qkdbench.evaluation.plots import plot_metric
from qkdbench.runner.provenance import build_metadata, config_hash, write_metadata
from qkdbench.validation.capability import check_compatibility, require_compatible
from qkdbench.core.errors import CapabilityError


def test_summarize_ci():
    agg = summarize([9, 5, 8])
    assert agg.n == 3 and abs(agg.mean - 7.333333) < 1e-5
    assert agg.ci95 > 0
    # single sample -> zero-width CI, not a crash
    assert summarize([4]).ci95 == 0.0
    assert summarize([]).n == 0
    assert t_critical_95(4) == 2.776 and t_critical_95(999) == 1.96


def _sweep_csv(tmp_path):
    csv_path = tmp_path / "sweep.csv"
    instances = [make_instance("german7", n_req=n, seed=s)
                 for n in (10, 20) for s in (1, 2, 3)]
    run_benchmark(instances, ["greedy_sp"], csv_path=csv_path, verbose=False)
    return csv_path


def test_aggregate_by_and_plot(tmp_path):
    csv_path = _sweep_csv(tmp_path)
    curves = aggregate_by(csv_path, "served")
    assert "greedy_sp" in curves
    assert set(curves["greedy_sp"]) == {10.0, 20.0}
    for x, agg in curves["greedy_sp"].items():
        assert agg.n == 3
    out = tmp_path / "fig.pdf"
    plot_metric(csv_path, "served", out_path=out)
    assert out.exists() and out.stat().st_size > 0


def test_provenance_metadata(tmp_path):
    instances = [make_instance("german7", n_req=10, seed=1)]
    meta = build_metadata("t", {"a": 1}, instances, timestamp="2026-01-01")
    assert meta["num_instances"] == 1
    assert list(meta["instance_fingerprints"].values())[0] == \
        instances[0].fingerprint()
    assert meta["python"] and meta["qkdbench_version"]
    # config_hash is stable
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})
    path = tmp_path / "meta.json"
    write_metadata(path, meta)
    assert json.load(open(path))["experiment"] == "t"


def test_capability_check():
    # a static baseline lacks 'dynamic' -> incompatible with P2
    static = get_algorithm("greedy_sp")
    msgs = check_compatibility("dynamic_admission_keypool", static)
    assert msgs and "dynamic" in msgs[0]
    try:
        require_compatible("dynamic_admission_keypool", static)
        assert False
    except CapabilityError:
        pass
    # the online controller is compatible
    online = get_algorithm("greedy_admission")
    assert check_compatibility("dynamic_admission_keypool", online) == []
    # any algorithm is fine for the static problem
    assert check_compatibility("static_routing_rra", static) == []
