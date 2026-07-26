import math

from motionforge.core import mathutil as mu
from motionforge.core.camera import Camera, depth_word_to_z, parallax_factor
from motionforge.core.color import build_palette, mix, parse_color


def test_easing_endpoints():
    for name, fn in mu.EASING.items():
        assert abs(fn(0.0)) < 1e-6, name
        assert abs(fn(1.0) - 1.0) < 1e-6, name


def test_envelope_window():
    assert mu.envelope(-0.1, 2.0) == 0.0
    assert mu.envelope(2.1, 2.0) == 0.0
    assert mu.envelope(1.0, 2.0) == 1.0
    assert 0.0 < mu.envelope(0.1, 2.0) < 1.0


def test_det_random_is_stable_and_namespaced():
    a = mu.DetRandom(42, "scene1", "rain").random()
    b = mu.DetRandom(42, "scene1", "rain").random()
    c = mu.DetRandom(42, "scene1", "snow").random()
    assert a == b
    assert a != c


def test_hash_noise_range_and_stability():
    vals = [mu.hash_noise("k", i) for i in range(200)]
    assert all(0.0 <= v < 1.0 for v in vals)
    assert vals == [mu.hash_noise("k", i) for i in range(200)]


def test_mat2d_compose_and_apply():
    m = mu.Mat2D.translate(5, 0) @ mu.Mat2D.rotate(math.pi / 2)
    x, y = m.apply(1, 0)
    assert abs(x - 5) < 1e-9 and abs(y - 1) < 1e-9


def test_two_bone_ik_reaches_target():
    joint, end = mu.two_bone_ik((0, 0), (1.0, -1.0), 1.0, 1.0)
    assert abs(end[0] - 1.0) < 1e-9 and abs(end[1] + 1.0) < 1e-9
    assert abs(math.hypot(*joint) - 1.0) < 1e-9
    d2 = math.hypot(end[0] - joint[0], end[1] - joint[1])
    assert abs(d2 - 1.0) < 1e-9


def test_two_bone_ik_overreach_stretches_straight():
    joint, end = mu.two_bone_ik((0, 0), (10, 0), 1.0, 1.0)
    assert abs(end[0] - 2.0) < 1e-9 and abs(end[1]) < 1e-9


def test_color_parsing_forms():
    assert parse_color("#f00") == (255, 0, 0, 255)
    assert parse_color("#00ff0080") == (0, 255, 0, 128)
    assert parse_color("sky blue") == parse_color("skyblue")
    assert parse_color([1, 2, 3]) == (1, 2, 3, 255)
    pal = build_palette({"hero red": "#ab0000"})
    assert parse_color("hero_red", pal) == (171, 0, 0, 255)
    assert mix((0, 0, 0, 255), (255, 255, 255, 255), 0.5)[0] == 128


def test_camera_parallax_far_moves_less():
    cam = Camera(x=0.0)
    x0_near, _, _ = cam.project(0, 0, z=0)
    x0_far, _, _ = cam.project(0, 0, z=20)
    cam.x = 2.0
    x1_near, _, _ = cam.project(0, 0, z=0)
    x1_far, _, _ = cam.project(0, 0, z=20)
    near_shift = abs(x1_near - x0_near)
    far_shift = abs(x1_far - x0_far)
    assert far_shift < near_shift * 0.5


def test_camera_unproject_roundtrip():
    cam = Camera(x=3.2, y=1.1, zoom=1.7)
    for z in (-2.0, 0.0, 8.0, 40.0):
        sx, sy, _ = cam.project(4.5, 2.5, z)
        wx, wy = cam.unproject(sx, sy, z)
        assert abs(wx - 4.5) < 1e-6 and abs(wy - 2.5) < 1e-6


def test_depth_words():
    assert depth_word_to_z("near") < 0 < depth_word_to_z("far")
    assert depth_word_to_z(3.5) == 3.5
    assert parallax_factor(0.0) == 1.0
    assert parallax_factor(100.0) < 0.1
