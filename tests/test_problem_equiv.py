"""Prove the composed constraint modules == the frozen monolithic verifier.

The verifier is the benchmark's credibility core, so refactoring it into
composable modules must not change a single verdict.  This differentials
the new ``verify`` (composed) against ``_reference_verify`` (frozen old
code) over many valid and deliberately-corrupted solutions.
"""
import random

from qkdbench import Assignment, Solution, edge_key, get_algorithm, make_instance
from qkdbench.core.verifier import verify, _reference_verify
from qkdbench.problems import get_problem, list_problems
from qkdbench.core.errors import ConfigError


def _corrupt(sol, inst, rng):
    """Return a mutated copy of sol with a random illegal tweak."""
    a = [Assignment(x.request_id, list(x.route), x.wavelength,
                    x.tp_start, x.tp_end) for x in sol.assignments]
    if not a:
        return Solution(algorithm="x", assignments=a)
    kind = rng.choice(["dup", "deadline", "wl", "bogus", "keys", "horizon"])
    i = rng.randrange(len(a))
    if kind == "dup":
        a.append(a[i])
    elif kind == "deadline":
        a[i].tp_end = inst.num_slots + 2
    elif kind == "wl":
        a[i].wavelength = 999
    elif kind == "bogus":
        a[i].route = [("1", "999")]
    elif kind == "keys":
        a[i].tp_start = a[i].tp_end          # shrink TP to 1 slot
    elif kind == "horizon":
        a[i].tp_start = 0
    return Solution(algorithm="x", assignments=a)


def test_composed_matches_reference():
    rng = random.Random(12345)
    topos = ["triangle", "poliqi5", "german7"]
    mism = 0
    for _ in range(60):
        topo = rng.choice(topos)
        inst = make_instance(topo, n_req=rng.randint(3, 15),
                             seed=rng.randint(1, 50))
        sol = get_algorithm("greedy_sp").solve(inst)
        for candidate in (sol, _corrupt(sol, inst, rng)):
            new = verify(inst, candidate)
            ref = _reference_verify(inst, candidate)
            assert new.ok == ref.ok, (topo, new.violations, ref.violations)
            assert set(new.violations) == set(ref.violations), \
                (topo, sorted(new.violations), sorted(ref.violations))
    assert mism == 0


def test_preset_registered_and_objectives():
    assert "static_routing_rra" in list_problems()
    prob = get_problem("static_routing_rra")
    inst = make_instance("german7", n_req=20, seed=1)
    sol = get_algorithm("greedy_sp").solve(inst)
    obj = prob.evaluate_objectives(inst, sol)
    assert obj["max_accepted_demands"] == 9
    assert obj["max_surplus_keys"] >= 0


def test_compose_rejects_missing_dependency():
    from qkdbench.problems.base import Problem
    from qkdbench.core.registry import registry
    # a constraint needing routing, but no decision provides it
    ks = registry.get("constraint", "key_sufficiency")()
    try:
        Problem("bad", decisions=[], constraints=[ks], objectives=[])
        assert False, "should have raised ConfigError"
    except ConfigError:
        pass
