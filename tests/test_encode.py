"""Encode smoke test: a tiny screenplay renders to a real MP4 with both a
video and an audio stream."""
from __future__ import annotations

import os
import subprocess

import imageio_ffmpeg
import pytest

from motionforge.render.encode import render_video

from conftest import compile_ok

SCREENPLAY = """
motionforge: 1
meta:
  resolution: [192, 108]
  fps: 12
  seed: 1
characters:
  bob: {body: human, height: 1.7}
scenes:
  - id: s
    duration: 1.0
    background: {sky: day, ground: {kind: grass}}
    place:
      - {char: bob, at: [0, 0]}
    timeline:
      - {t: 0.1, char: bob, do: wave, until: 0.9}
audio:
  music: {mood: happy, volume: 0.5}
"""


@pytest.fixture(scope="module")
def mp4_path(tmp_path_factory):
    prod = compile_ok(SCREENPLAY)
    # the DSL floor for fps is 12; drop to 6 after parsing so the encode
    # smoke test stays tiny (1 s x 6 fps = 6 frames)
    prod.meta.fps = 6
    out = str(tmp_path_factory.mktemp("encode") / "smoke.mp4")
    render_video(prod, out, workers=1, quiet=True)
    return out


def test_mp4_exists_and_is_substantial(mp4_path):
    assert os.path.isfile(mp4_path)
    assert os.path.getsize(mp4_path) > 10 * 1024


def test_mp4_has_video_and_audio_streams(mp4_path):
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run([exe, "-hide_banner", "-i", mp4_path],
                          capture_output=True, text=True)
    info = proc.stderr
    assert "Video:" in info, info
    assert "Audio:" in info, info
    assert "h264" in info
    assert "aac" in info
    assert "192x108" in info
