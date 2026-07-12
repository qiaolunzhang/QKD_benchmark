"""QKD physical models (ARCHITECTURE.md §5).

Importing this package registers all v1 models in the unified registry
(kind ``"qkd_model"``):

* ``constant``             — :class:`ConstantRate` (debug / control)
* ``distance_exponential`` — :class:`DistanceExponential` (fibre loss)
* ``finite_size_table``    — :class:`FiniteSizeTable` (Yin-2020 tables;
  our differentiating feature — rate depends on (distance, tau))
* ``decoy_bb84``           — :class:`SimplifiedDecoyBB84` (closed-form
  asymptotic)

Usage::

    from qkdbench.scenario.qkd_models import get_qkd_model

    model = get_qkd_model("distance_exponential", r0_kbps=200)
    model = get_qkd_model("fse_1310_coex")   # legacy rate-table alias

The two Phase-0 rate-table names (``fse_1540_alone`` / ``fse_1310_coex``)
are accepted as model names and map to ``FiniteSizeTable(table=name)``,
so existing instances and configs keep working unchanged.
"""
from ...core.registry import registry
from .base import KeyGenerationModel, KeyGenResult
from .constant import ConstantRate               # noqa: F401  (registers)
from .distance import DistanceExponential        # noqa: F401  (registers)
from .finite_size import FiniteSizeTable         # noqa: F401  (registers)
from .decoy_bb84 import SimplifiedDecoyBB84      # noqa: F401  (registers)

#: Phase-0 ``rate_table`` names accepted directly as model names
_TABLE_ALIASES = ("fse_1540_alone", "fse_1310_coex")


def get_qkd_model(name: str, **params) -> KeyGenerationModel:
    """Instantiate a registered QKD model by name.

    ``name`` may also be one of the legacy rate-table names, which
    resolve to ``FiniteSizeTable(table=name)``.
    """
    if name in _TABLE_ALIASES:
        params.setdefault("table", name)
        name = FiniteSizeTable.name
    cls = registry.get("qkd_model", name)
    return cls(**params)


def available_models():
    """Registered model names (aliases not included)."""
    return registry.names("qkd_model")


__all__ = ["KeyGenerationModel", "KeyGenResult", "ConstantRate",
           "DistanceExponential", "FiniteSizeTable", "SimplifiedDecoyBB84",
           "get_qkd_model", "available_models"]
