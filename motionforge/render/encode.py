"""Full film rendering: parallel frames piped into ffmpeg, audio muxed in.

Bit-exact flags keep the MP4 reproducible for the same input on the same
ffmpeg build; frames themselves are byte-identical everywhere.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import sys
import tempfile

import imageio_ffmpeg

from ..dsl.ir import Production
from ..scene.world import World
from .frames import render_frame

_worker_world: World = None  # per-process cache


def _init_worker(production: Production) -> None:
    global _worker_world
    _worker_world = World(production)


def _render_frame_bytes(i_and_fps) -> bytes:
    i, fps = i_and_fps
    t = i / fps
    return render_frame(_worker_world, t).rgb24()


def render_video(production: Production, out_path: str, workers: int = 0,
                 quiet: bool = False) -> None:
    width, height = production.meta.resolution
    fps = production.meta.fps
    duration = production.duration
    n_frames = max(int(round(duration * fps)), 1)
    if workers <= 0:
        workers = max(1, (os.cpu_count() or 2) - 1)

    world = World(production)
    with tempfile.TemporaryDirectory(prefix="motionforge_") as tmp:
        wav_path = os.path.join(tmp, "audio.wav")
        from ..audio.mix import build_soundtrack, write_wav
        if not quiet:
            print("mixing soundtrack...", file=sys.stderr)
        write_wav(wav_path, build_soundtrack(world))

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            exe, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
            "-i", wav_path,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-threads", "4",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            "-fflags", "+bitexact", "-flags:v", "+bitexact",
            "-flags:a", "+bitexact", "-map_metadata", "-1",
            out_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            if workers == 1 or n_frames < 24:
                _init_worker(production)
                for i in range(n_frames):
                    proc.stdin.write(_render_frame_bytes((i, fps)))
                    if not quiet and i % fps == 0:
                        print(f"  {i // fps}s / {duration:.1f}s", file=sys.stderr)
            else:
                try:
                    ctx = mp.get_context("fork")
                except ValueError:      # Windows/macOS-spawn platforms
                    ctx = mp.get_context("spawn")
                with ctx.Pool(workers, initializer=_init_worker,
                              initargs=(production,)) as pool:
                    args = ((i, fps) for i in range(n_frames))
                    for i, frame in enumerate(
                            pool.imap(_render_frame_bytes, args, chunksize=6)):
                        proc.stdin.write(frame)
                        if not quiet and i % (fps * 2) == 0:
                            print(f"  {i / fps:.0f}s / {duration:.1f}s",
                                  file=sys.stderr)
            proc.stdin.close()
            ret = proc.wait()
            if ret != 0:
                raise RuntimeError(f"ffmpeg exited with status {ret}")
        except BrokenPipeError:
            proc.wait()
            raise RuntimeError("ffmpeg terminated early — encoding failed")
