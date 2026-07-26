"""Track sampling: easing, hold semantics, out-of-range clamping."""
from __future__ import annotations

import math

import pytest

from motionforge.core import ease as easing
from motionforge.motion.tracks import Track, angle_track


def test_clamp_before_first_and_after_last_key():
    tr = Track(0.0)
    tr.add(2.0, 10.0, "linear")
    assert tr.sample(-5.0) == 0.0        # before the first key
    assert tr.sample(0.0) == 0.0
    assert tr.sample(2.0) == 10.0
    assert tr.sample(99.0) == 10.0       # after the last key: hold last value


def test_linear_interpolation():
    tr = Track(0.0)
    tr.add(2.0, 10.0, "linear")
    assert math.isclose(tr.sample(1.0), 5.0)
    assert math.isclose(tr.sample(0.5), 2.5)


@pytest.mark.parametrize("ez", ["in", "out", "in_out", "bounce", "elastic"])
def test_easing_matches_ease_module(ez):
    tr = Track(0.0)
    tr.add(4.0, 8.0, ez)
    fn = easing.EASES[ez]
    for t in (0.5, 1.0, 2.0, 3.4):
        u = t / 4.0
        assert math.isclose(tr.sample(t), 8.0 * fn(u), abs_tol=1e-12)


def test_easing_is_per_destination_key():
    tr = Track(0.0)
    tr.add(1.0, 1.0, "linear")
    tr.add(2.0, 3.0, "in")               # this segment eases quadratically
    # halfway through segment two: 1 + 2 * ease_in(0.5) = 1.5
    assert math.isclose(tr.sample(1.5), 1.0 + 2.0 * 0.25)


def test_hold_ease_steps_at_the_end():
    tr = Track(0.0)
    tr.add(2.0, 10.0, "hold")
    assert tr.sample(1.0) == 0.0
    assert tr.sample(1.999) == 0.0
    assert tr.sample(2.0) == 10.0


def test_step_ease_jumps_at_the_start():
    tr = Track(0.0)
    tr.add(2.0, 10.0, "step")
    assert tr.sample(0.0) == 0.0
    assert tr.sample(0.001) == 10.0
    assert tr.sample(2.0) == 10.0


def test_hold_method_anchors_current_value():
    tr = Track(0.0)
    tr.add(1.0, 5.0, "linear")
    tr.hold(3.0)                          # value stays 5 from t=1..3
    tr.add(4.0, 9.0, "linear")
    assert math.isclose(tr.sample(2.0), 5.0)
    assert math.isclose(tr.sample(3.0), 5.0)
    assert math.isclose(tr.sample(3.5), 7.0)   # then eases to the new key
    assert math.isclose(tr.sample(4.0), 9.0)


def test_vec2_values_lerp_componentwise():
    tr = Track((0.0, 0.0))
    tr.add(2.0, (4.0, -2.0), "linear")
    x, y = tr.sample(1.0)
    assert math.isclose(x, 2.0) and math.isclose(y, -1.0)
    assert tr.sample(10.0) == (4.0, -2.0)


def test_out_of_order_add_clamps_time_deterministically():
    tr = Track(0.0)
    tr.add(2.0, 10.0, "linear")
    tr.add(1.0, 20.0, "linear")           # clamped to t=2, not reordered
    assert tr.keys[-1][0] == 2.0
    assert tr.sample(2.0) == 20.0
    assert tr.sample(5.0) == 20.0
    assert math.isclose(tr.sample(1.0), 5.0)   # first segment unaffected


def test_empty_track_samples_none():
    assert Track().sample(1.0) is None


def test_angle_track_takes_shortest_arc():
    tr = angle_track(350.0)
    tr.add(2.0, 10.0, "linear")
    # 350 -> 10 through 360, not backward through 180
    assert math.isclose(tr.sample(1.0) % 360.0, 0.0, abs_tol=1e-9)
