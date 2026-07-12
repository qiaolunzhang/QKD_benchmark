# Contributing to qkdbench — the short version

## Adding an algorithm (one file, one class, one decorator)

```python
from qkdbench import Algorithm, Solution, register_algorithm

@register_algorithm
class MyAlgo(Algorithm):
    name = "my_algo"          # unique registry name
    def solve(self, instance) -> Solution: ...
```

Rules:

1. **Consume the `Instance`, produce a `Solution` — nothing else.**
   All inputs come from the instance (topology, demands, slots,
   wavelengths, modules); all outputs are `Assignment`s. The framework
   verifies and scores; algorithms never report their own metrics.
2. **Physics only through the QKD model interface.** Get rates via

   ```python
   from qkdbench import get_qkd_model
   model = get_qkd_model(instance.rate_table, **instance.qkd_model_params)
   model.tp_keys_kb(length_km, n_slots, instance.slot_seconds)
   model.feasible(length_km)
   ```

3. **Determinism.** Any randomness must come from a seed in
   `self.params`; two runs on the same instance must give the same
   `Solution`.
4. Tunables go in `self.params` (constructor kwargs), not module
   globals — the runner records them.

## Forbidden

- **No key-rate physics inside algorithms.** Never write a key-rate,
  loss, or QBER formula in algorithm code, and never import
  `qkdbench.keyrate` or `qkdbench.scenario.qkd_models.<model>` classes
  directly from an algorithm — go through `get_qkd_model`. This is the
  same rule the verifier follows: every component prices keys with the
  *identical* model object, or comparisons are meaningless.
- No mutation of the `Instance` (it is shared across algorithms).
- No reading of other algorithms' results, files, or global state.
- No self-grading: `Solution.extras` may carry diagnostics, but
  served/delivered metrics are computed by the runner from verified
  assignments only.

## Tests (required before a PR)

- `pytest` fully green with your algorithm registered.
- A smoke test: your algorithm on `german7` (and ideally `poliqi5` /
  `triangle`) produces a solution that passes `qkdbench.verify` —
  see `tests/test_benchmark.py` for the pattern.
- If you add a QKD model: subclass `KeyGenerationModel`, register it
  with `@registry.register("qkd_model", name)`, bump `version` on any
  change that alters numbers, and add sanity tests (monotonicity,
  magnitude, reach cutoff) — see `tests/test_qkd_models.py`.
- Never regenerate instances per algorithm; build once, share, and let
  the fingerprint prove it.
