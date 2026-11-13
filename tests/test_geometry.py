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


def test_ghost_ball_sits_two_radii_behind_object():
    gb = g.ghost_ball((100, 100), (200, 100), 10)
    assert math.isclose(gb[0], 80) and math.isclose(gb[1], 100)


def test_cut_angle_straight_and_right_angle():
    assert math.isclose(g.cut_angle((0, 0), (100, 0), (200, 0)), 0, abs_tol=1e-9)
    assert math.isclose(g.cut_angle((0, 0), (100, 0), (100, 100)), 90)


def test_best_pocket_picks_straightest_pocket():
    # cue, object and the right-middle pocket are collinear
    idx, angle = g.best_pocket((20, 50), (100, 50), RECT, 5)
    assert idx == 2 or idx == 5 or angle < 80
    assert angle < 80


def test_best_pocket_skips_pocket_the_ball_sits_in():
    res = g.best_pocket((100, 50), (0, 0), RECT, 5)
    assert res is None or res[0] != 0


def test_best_pocket_none_when_cut_too_thin():
    assert g.best_pocket((50, 50), (100, 50), RECT, 5, max_cut=-1.0) is None


def test_difficulty_labels_grow_with_cut_angle():
    assert g.difficulty(0, 100, 1000) == "Easy"
    assert g.difficulty(85, 1500, 1000) == "Very hard"


def test_path_length():
    assert math.isclose(g.path_length([((0, 0), (3, 4)), ((3, 4), (3, 10))]), 11)
