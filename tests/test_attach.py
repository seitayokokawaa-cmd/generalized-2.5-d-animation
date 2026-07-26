"""Attach flights: a thrown object leaves from the hand release point and
lands exactly on the target when its flight time elapses."""
from __future__ import annotations

import math

import pytest

from conftest import make_world

SCREENPLAY = """
motionforge: 1
meta:
  resolution: [192, 108]
  fps: 12
  seed: 4
characters:
  thrower: {body: human, height: 1.7}
scenes:
  - id: s
    duration: 6.0
    place:
      - {char: thrower, at: [0, 0]}
      - {obj: ball, at: [0.6, 0]}
    timeline:
      - {t: 0.5, char: thrower, do: pickup, obj: ball, hand: right}
      - {t: 2.0, char: thrower, do: throw, obj: ball, to: [4, 0]}
"""

THROW_T = 2.0
RELEASE_T = THROW_T + 0.35      # attach.py releases 0.35 s into the throw
TARGET = (4.0, 0.0)


@pytest.fixture(scope="module")
def scene():
    world = make_world(SCREENPLAY)
    return world.scenes[0]


def test_object_is_held_after_pickup(scene):
    links = scene.links
    hold = links.held_by("ball", 1.5)
    assert hold is not None
    assert hold.char_id == "thrower"
    # before the grab delay elapses it is not yet held
    assert links.held_by("ball", 0.5) is None


def test_flight_starts_at_hand_release_point(scene):
    links = scene.links
    fp = links.flight_pos("ball", RELEASE_T)
    assert fp is not None
    (hand_pos, _ang, _facing) = links._hand("thrower", "near",
                                            RELEASE_T - 1e-3)
    assert math.isclose(fp[0], hand_pos[0], abs_tol=1e-9)
    assert math.isclose(fp[1], hand_pos[1], abs_tol=1e-9)


def test_flight_lands_on_target_by_t0_plus_duration(scene):
    links = scene.links
    links.flight_pos("ball", RELEASE_T)          # primes the flight cache
    flight = links.flights["ball"][0]
    T = flight.duration
    assert T > 0
    # at exactly t0 + duration (and after) the object sits on the target
    for t in (RELEASE_T + T, RELEASE_T + T + 0.5):
        fp = links.flight_pos("ball", t)
        assert fp is not None
        assert math.isclose(fp[0], TARGET[0], abs_tol=1e-9)
        assert math.isclose(fp[1], TARGET[1], abs_tol=1e-9)


def test_flight_follows_a_ballistic_arc(scene):
    links = scene.links
    fp0 = links.flight_pos("ball", RELEASE_T)
    flight = links.flights["ball"][0]
    T = flight.duration
    # horizontal velocity is constant: x is linear from release to target
    for u in (0.25, 0.5, 0.75):
        fp = links.flight_pos("ball", RELEASE_T + u * T)
        want_x = fp0[0] + (TARGET[0] - fp0[0]) * u
        assert math.isclose(fp[0], want_x, abs_tol=1e-9)
    # mid-flight the ball is above the straight release->target chord
    mid = links.flight_pos("ball", RELEASE_T + 0.5 * T)
    chord_y = (fp0[1] + TARGET[1]) * 0.5
    assert mid[1] > chord_y


def test_no_flight_before_release(scene):
    links = scene.links
    # while held (after grab, before release) the object is not in flight
    assert links.flight_pos("ball", 1.5) is None
    assert links.held_by("ball", RELEASE_T - 0.01) is not None
