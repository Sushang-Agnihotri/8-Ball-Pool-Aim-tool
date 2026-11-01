import math

from pool_aim import geometry as g

RECT = (0.0, 0.0, 200.0, 100.0)


def test_pockets():
    pk = g.pocket_centers(RECT)
    assert len(pk) == 6 and (100.0, 0.0) in pk and (200.0, 100.0) in pk


def test_nearest_pocket():
    p, d = g.nearest_pocket((5, 5), RECT)
    assert p == (0.0, 0.0) and math.isclose(d, math.hypot(5, 5))


def test_clamp():
    assert g.clamp_to_rect((-5, 500), RECT) == (0.0, 100.0)


def test_single_bank_reflects():
    segs = g.bank_segments((100, 50), (1, 1), RECT, 2)
    assert segs[0][1] == (150.0, 100.0)
    assert segs[1][1] == (200.0, 50.0)


def test_zero_or_nonfinite_direction():
    assert g.bank_segments((1, 1), (0, 0), RECT) == []
    assert g.bank_segments((1, 1), (math.nan, 1), RECT) == []
    assert g.bank_segments((1, 1), (math.inf, 1), RECT) == []


def test_axis_aligned_ray():
    segs = g.bank_segments((50, 50), (1, 0), RECT, 2)
    assert segs[0][1] == (200.0, 50.0) and segs[1][1] == (0.0, 50.0)
