"""Problem presets — named module compositions.

A preset is just a convenient name for a fixed set of decision, constraint
and objective modules.  ``static_routing_rra`` is the v1 P1 problem
(static routing + wavelength assignment + TP scheduling under finite-size
key rates).  Future presets (dynamic admission + key pools, trusted-relay
placement) register here the same way.
"""
from __future__ import annotations

from ..core.registry import registry
from .base import Problem
from .constraints import P1_CONSTRAINTS
from . import constraints as _c        # noqa: F401  (register constraints)
from . import decisions as _d          # noqa: F401  (register decisions)
from . import objectives as _o         # noqa: F401  (register objectives)
from . import dynamic as _dyn          # noqa: F401  (register P2 modules)
from . import placement as _plc        # noqa: F401  (register P3 modules)

P1_DECISIONS = ["path_selection", "wavelength_assignment", "tp_scheduling"]
P1_OBJECTIVES = ["max_accepted_demands", "max_surplus_keys"]


def _build(kind, names):
    return [registry.get(kind, n)() for n in names]


@registry.register("problem", "static_routing_rra")
def static_routing_rra(**params) -> Problem:
    """Static routing + resource allocation (P1)."""
    return Problem(
        name="static_routing_rra",
        decisions=_build("decision", P1_DECISIONS),
        constraints=_build("constraint", P1_CONSTRAINTS),
        objectives=_build("objective", P1_OBJECTIVES),
        params=params,
    )
