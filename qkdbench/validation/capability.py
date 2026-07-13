"""Pre-run capability checking (ARCHITECTURE.md §8, §12).

Before an experiment runs, the scenario, problem and algorithm should be
confirmed compatible — a static shortest-path baseline cannot solve a
dynamic admission problem, and saying so up front beats a confusing crash
mid-sweep.  Capabilities and requirements are plain string tags; the
checker returns *all* mismatches at once.
"""
from __future__ import annotations

from typing import List

from ..core.errors import CapabilityError

#: tags a problem preset needs the algorithm to support
PROBLEM_REQUIRES = {
    "static_routing_rra": set(),                 # any algorithm may attempt
    "dynamic_admission_keypool": {"dynamic"},    # needs an online controller
    "trusted_relay_placement": set(),
}


def algorithm_capabilities(algorithm) -> set:
    return set(getattr(algorithm, "capabilities", set()) or set())


def check_compatibility(problem_name: str, algorithm) -> List[str]:
    """Return a list of mismatch messages (empty = compatible)."""
    needed = PROBLEM_REQUIRES.get(problem_name, set())
    have = algorithm_capabilities(algorithm)
    missing = needed - have
    msgs = []
    for tag in sorted(missing):
        msgs.append(
            f"algorithm {getattr(algorithm, 'name', algorithm)!r} does not "
            f"support {tag!r}, required by problem {problem_name!r}")
    return msgs


def require_compatible(problem_name: str, algorithm) -> None:
    """Raise :class:`CapabilityError` if incompatible."""
    msgs = check_compatibility(problem_name, algorithm)
    if msgs:
        raise CapabilityError(msgs)
