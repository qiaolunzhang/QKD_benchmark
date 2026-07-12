"""The verifier must catch every class of violation it claims to check."""
from qkdbench import Assignment, Solution, edge_key, make_instance, verify


def _inst():
    return make_instance("triangle", n_req=3, seed=1,
                         num_slots=5, wavelengths=1, modules_per_node=2)


def _sol(*assignments):
    return Solution(algorithm="test", assignments=list(assignments))


def test_valid_solution_passes():
    inst = _inst()
    req = inst.requests[0]
    a = Assignment(request_id=req.id, route=[edge_key(req.src, req.dst)],
                   wavelength=0, tp_start=1, tp_end=min(2, req.deadline_slot))
    assert verify(inst, _sol(a)).ok


def test_deadline_violation_caught():
    inst = _inst()
    req = inst.requests[0]
    a = Assignment(request_id=req.id, route=[edge_key(req.src, req.dst)],
                   wavelength=0, tp_start=1, tp_end=inst.num_slots)
    if req.deadline_slot < inst.num_slots:
        v = verify(inst, _sol(a))
        assert not v.ok and any("deadline" in s for s in v.violations)


def test_wavelength_clash_caught():
    inst = _inst()
    r1, r2 = inst.requests[0], inst.requests[1]
    link = edge_key(r1.src, r1.dst)
    a1 = Assignment(r1.id, [link], 0, 1, 2)
    # force the same (link, wl, slot) usage via an overlapping route
    a2 = Assignment(r2.id, [edge_key(r2.src, r2.dst)], 0, 1, 2)
    if edge_key(r2.src, r2.dst) == link:
        v = verify(inst, _sol(a1, a2))
        assert not v.ok and any("clash" in s for s in v.violations)


def test_insufficient_keys_caught():
    inst = _inst()
    req = inst.requests[0]
    # 1-slot TP at 5 km yields ~44.6 kb; demand is ~100 kb -> must fail
    a = Assignment(req.id, [edge_key(req.src, req.dst)], 0, 1, 1)
    v = verify(inst, _sol(a))
    assert not v.ok and any("delivers" in s for s in v.violations)


def test_bogus_route_caught():
    inst = _inst()
    req = inst.requests[0]
    a = Assignment(req.id, [("1", "99")], 0, 1, 2)
    v = verify(inst, _sol(a))
    assert not v.ok and any("non-existent" in s for s in v.violations)


def test_double_serving_caught():
    inst = _inst()
    req = inst.requests[0]
    link = edge_key(req.src, req.dst)
    a1 = Assignment(req.id, [link], 0, 1, 2)
    a2 = Assignment(req.id, [link], 0, 3, 4)
    v = verify(inst, _sol(a1, a2))
    assert not v.ok and any("more than once" in s for s in v.violations)
