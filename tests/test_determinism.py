"""Determinism: the same screenplay must render byte-identical frames from
two separately compiled Worlds, including mid-walk and inside a ragdoll
episode (which triggers the eager physics sim + seeded rng streams)."""
from __future__ import annotations

import pytest

from motionforge.render.frames import render_frame
from motionforge.scene.world import World

from conftest import compile_ok

SCREENPLAY = """
motionforge: 1
meta:
  resolution: [192, 108]
  fps: 6
  seed: 11
characters:
  asha: {body: human, height: 1.7}
scenes:
  - id: main
    duration: 5.0
    background: {sky: dawn, weather: rain, ground: {kind: grass}}
    place:
      - {char: asha, at: [-1.5, 0], depth: near}
      - {obj: tree, at: [3, 0], depth: mid}
    timeline:
      - {t: 0.5, char: asha, do: walk, to: [1.5, 0], until: 3.0}
      - {t: 3.2, char: asha, ragdoll: {impulse: [2.5, 3.0], until: 4.2, recover: 0.6}}
    captions:
      - {t: 0.0, until: 1.0, text: "Chapter One", style: caption}
"""

# idle+caption, mid-walk, inside the ragdoll window, during recovery blend
T_SAMPLES = [0.25, 1.7, 3.7, 4.6]


def _build_world() -> World:
    # full separate compile: parse -> validate -> World
    return World(compile_ok(SCREENPLAY))


@pytest.fixture(scope="module")
def two_worlds():
    return _build_world(), _build_world()


@pytest.fixture(scope="module")
def frames(two_worlds):
    w1, w2 = two_worlds
    a = [render_frame(w1, t).rgb24() for t in T_SAMPLES]
    b = [render_frame(w2, t).rgb24() for t in T_SAMPLES]
    return a, b


@pytest.mark.parametrize("i,t", list(enumerate(T_SAMPLES)))
def test_frames_byte_identical_across_worlds(frames, i, t):
    a, b = frames
    assert a[i] == b[i], f"frame at t={t} differs between two compiled Worlds"


def test_frames_have_expected_size_and_content(frames):
    a, _ = frames
    for buf in a:
        assert len(buf) == 192 * 108 * 3
        # a rendered frame is never uniformly one color
        assert len(set(buf[i:i + 3] for i in range(0, len(buf), 3))) > 8


def test_distinct_times_render_distinct_frames(frames):
    a, _ = frames
    # idle vs mid-walk vs ragdoll must actually differ (the test is not vacuous)
    assert a[0] != a[1]
    assert a[1] != a[2]


def test_resample_same_world_is_stable(two_worlds):
    """Re-rendering the same t on the same World (after the ragdoll sim has
    been compiled lazily) still gives identical bytes."""
    w1, _ = two_worlds
    for t in (1.7, 3.7):
        first = render_frame(w1, t).rgb24()
        second = render_frame(w1, t).rgb24()
        assert first == second
