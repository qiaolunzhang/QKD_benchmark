"""Scenario layer: the objective world an experiment runs in.

v1 sub-modules:

* :mod:`qkdbench.scenario.topology` — first-class topology providers
  (builtin YAML data, synthetic generators, file loaders) plus the
  physical -> logical QKD graph derivation.
* :mod:`qkdbench.scenario.qkd_models` — QKD physical models (constant /
  distance-exponential / finite-size tables / simplified decoy BB84).

Traffic models (Phase 3+) will move here too.
"""
from . import qkd_models  # noqa: F401  (import registers all models)
from . import topology    # noqa: F401  (import registers all providers)
from .qkd_models import (KeyGenerationModel, KeyGenResult,  # noqa: F401
                         get_qkd_model)
from .topology import (TopologyProvider, build_topology,  # noqa: F401
                       logical_graph)

__all__ = ["topology", "TopologyProvider", "build_topology", "logical_graph",
           "qkd_models", "KeyGenerationModel", "KeyGenResult",
           "get_qkd_model"]
