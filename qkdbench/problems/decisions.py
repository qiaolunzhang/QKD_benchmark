"""P1 decision modules.

Decisions name what an algorithm must produce and which Solution field
carries it.  For P1 an algorithm chooses, per served demand, a route, a
wavelength and a transmission-period interval — all carried by the single
``routing`` solution component (an :class:`~qkdbench.core.solution.Assignment`
list).  They are declared as separate modules so future problems can drop
or swap one (e.g. replace ``wavelength_assignment`` in an all-optical
variant) without touching the others.
"""
from __future__ import annotations

from ..core.registry import registry
from .base import DecisionModule


@registry.register("decision", "path_selection")
class PathSelection(DecisionModule):
    name = "path_selection"
    solution_component = "routing"
    requires = frozenset({"demand.src", "demand.dst"})
    provides = frozenset({"single_path"})
    conflicts = frozenset({"multipath"})


@registry.register("decision", "wavelength_assignment")
class WavelengthAssignment(DecisionModule):
    name = "wavelength_assignment"
    solution_component = "routing"
    requires = frozenset({"link.wavelengths"})


@registry.register("decision", "tp_scheduling")
class TpScheduling(DecisionModule):
    name = "tp_scheduling"
    solution_component = "routing"
    requires = frozenset({"demand.deadline_slot"})
