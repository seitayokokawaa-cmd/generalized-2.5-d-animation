"""Foot-lock invariant: while a foot is planted its world x never moves
(zero slide), consecutive plants advance monotonically toward the
destination, and the final plant lands on the destination x."""
from __future__ import annotations

import math

import pytest

from motionforge.motion.program import CharProgram

from conftest import make_world

SCREENPLAY = """
motionforge: 1
meta:
  resolution: [192, 108]
  fps: 12
  seed: 2
characters:
  walker: {body: human, height: 1.7}
scenes:
  - id: s
    duration: 6.0
    place:
      - {char: walker, at: [-2, 0]}
    timeline:
      - {t: 0.5, char: walker, do: walk, to: [2, 0], until: 5.5}
"""

T0, T1 = 0.5, 5.5
START_X, DEST_X = -2.0, 2.0
DT = 0.005


@pytest.fixture(scope="module")
def plant_history():
    world = make_world(SCREENPLAY)
    ent = world.scenes[0].entity("walker")
    prog = ent.program
    assert isinstance(prog, CharProgram)

    seg = prog.segments[0]
    assert seg.mode == "walk"
    dir_sign = seg.dir

    # per-leg list of (t, world_x) samples where the leg was planted
    history = {}
    n = int(round((T1 - T0) / DT))
    for i in range(n + 1):
        t = T0 + i * DT
        st = prog.state(t)
        for leg, plant in st.plants.items():
            # plants are path-local distance along the segment; map to world x
            wx = seg.p0[0] + plant * dir_sign
            history.setdefault(leg, []).append((t, wx))
    return history


def _sessions(samples):
    """Group consecutive-in-time planted samples into plant sessions."""
    sessions = []
    prev_t = None
    for (t, wx) in samples:
        if prev_t is not None and t - prev_t < DT * 1.5:
            sessions[-1].append(wx)
        else:
            sessions.append([wx])
        prev_t = t
    return sessions


def test_both_legs_plant(plant_history):
    assert set(plant_history) == {"near", "far"}


def test_no_slide_while_planted(plant_history):
    for leg, samples in plant_history.items():
        for session in _sessions(samples):
            lo, hi = min(session), max(session)
            assert hi - lo < 1e-9, (
                f"leg '{leg}' slid {hi - lo:.6g} m during one plant "
                f"(from {lo} to {hi})")


def test_plants_advance_monotonically(plant_history):
    for leg, samples in plant_history.items():
        sessions = _sessions(samples)
        assert len(sessions) >= 3, f"leg '{leg}' took too few steps"
        positions = [s[0] for s in sessions]
        for a, b in zip(positions, positions[1:]):
            assert b > a + 1e-9, (
                f"leg '{leg}' plants moved backward/stalled: {a} -> {b}")
        # every plant lies on the path
        for p in positions:
            assert START_X - 1e-6 <= p <= DEST_X + 1e-6


def test_leading_foot_final_plant_at_destination(plant_history):
    """The stride is fitted so the last step lands exactly on the mark:
    the leading foot's final plant must be the destination x."""
    finals = {leg: samples[-1][1] for leg, samples in plant_history.items()}
    leading = max(finals.values())
    assert abs(leading - DEST_X) <= 0.05, (
        f"leading foot final plant at {leading}, wanted {DEST_X} +-0.05")


def test_trailing_foot_final_plant_at_destination(plant_history):
    """Fixed: the gait now overdrives the phase by one step across the final
    quarter of the walk, so the trailing foot takes a catch-up step and both
    feet finish at the destination."""
    for leg, samples in plant_history.items():
        final = samples[-1][1]
        assert abs(final - DEST_X) <= 0.05, (
            f"leg '{leg}' final plant at {final}, wanted {DEST_X} +-0.05")


def test_character_arrives_at_destination():
    world = make_world(SCREENPLAY)
    prog = world.scenes[0].entity("walker").program
    x, y = prog.position(T1)
    assert math.isclose(x, DEST_X, abs_tol=1e-6)
    assert math.isclose(y, 0.0, abs_tol=1e-6)
