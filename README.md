# qkdbench

**A beginner-friendly benchmark framework for resource-optimization
algorithms in QKD networks.**

Research papers on QKD network optimization (routing, wavelength
assignment, key provisioning, scheduling, relay placement, ...) each ship
their own topologies, traffic models, key-rate assumptions and metrics —
results are rarely comparable. `qkdbench` fixes the playing field:

- **Shared instances** — scenarios are materialized to JSON with a
  fingerprint; every algorithm consumes byte-identical inputs.
- **Independent verification** — an algorithm returns a `Solution`; the
  framework checks feasibility and recomputes every metric. No algorithm
  grades its own homework.
- **One-file integration** — subclass `Algorithm`, add
  `@register_algorithm`, done. No core code changes.
- **Physics included** — finite-size secret-key-rate tables
  (decoy-state BB84, Yin et al. 2020 bounds; dedicated-fibre and
  coexistence regimes) so algorithms compete on decisions, not on
  physical assumptions.
- **Config-driven** — one YAML file per experiment, incremental CSV
  output, seeded reproducibility.

## Install

```bash
git clone https://github.com/qiaolunzhang/QKD_benchmark.git
cd QKD_benchmark
conda create -n qkdbench python=3.12 -y
conda activate qkdbench
pip install -e ".[dev]"
pytest            # sanity check
```

## 60-second tour

```python
from qkdbench import make_instance, get_algorithm, evaluate

inst = make_instance("german7", n_req=20, seed=1)   # shared, fingerprinted
result = evaluate(inst, get_algorithm("greedy_sp")) # run + verify + score
print(result.served, "/", result.total_requests)
```

Or from the command line:

```bash
qkdbench run -c configs/demo.yaml     # sweep -> results/demo.csv
qkdbench list-algorithms
qkdbench list-topologies
```

## Add your algorithm (the whole point)

```python
from qkdbench import Algorithm, Solution, register_algorithm

@register_algorithm
class MyAlgo(Algorithm):
    name = "my_algo"

    def solve(self, instance):
        assignments = ...   # your decisions
        return Solution(algorithm=self.name, assignments=assignments)
```

See [`examples/add_your_algorithm.py`](examples/add_your_algorithm.py)
for a complete runnable version, and
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design (scenario /
problem / algorithm / evaluation separation, roadmap to dynamic
admission, key pools and relay placement).

## Status

v0.1 — problem P1 (static routing + wavelength + transmission-period
scheduling under finite-size key rates), built-in topologies
(`triangle`, `poliqi5`, `german7`), `greedy_sp` baseline. The roadmap in
[`TODO.md`](TODO.md) tracks NSFNET/COST239/USNET/GEANT topologies, MILP
and DA-FSE algorithms, dynamic key-pool problems and relay placement.

## License

MIT
