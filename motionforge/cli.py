"""MotionForge command-line interface."""
from __future__ import annotations

import argparse
import json
import sys


def cmd_check(args: argparse.Namespace) -> int:
    from .dsl.parser import parse_file
    prod, report = parse_file(args.screenplay)
    if prod is not None:
        from .dsl.validator import validate
        validate(prod, report)
    if args.json:
        print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        print(report.format())
    return 0 if report.ok else 1


def _load_valid(path: str):
    from .core.errors import ScreenplayError
    from .dsl.parser import parse_file
    prod, report = parse_file(path)
    if prod is not None:
        from .dsl.validator import validate
        validate(prod, report)
    if prod is None or not report.ok:
        raise ScreenplayError(report)
    if report.warnings:
        print(report.format(), file=sys.stderr)
    return prod


def cmd_frame(args: argparse.Namespace) -> int:
    from .render.frames import render_frame_png
    prod = _load_valid(args.screenplay)
    out = args.output or "frame.png"
    render_frame_png(prod, args.time, out)
    print(f"wrote {out} (t={args.time:.3f}s of {prod.duration:.3f}s)")
    return 0


def cmd_storyboard(args: argparse.Namespace) -> int:
    from .render.storyboard import render_storyboard
    prod = _load_valid(args.screenplay)
    out = args.output or "storyboard.png"
    n = render_storyboard(prod, out, columns=args.columns, count=args.count)
    print(f"wrote {out} ({n} frames)")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from .render.encode import render_video
    prod = _load_valid(args.screenplay)
    out = args.output or "out.mp4"
    render_video(prod, out, workers=args.workers, quiet=args.quiet)
    print(f"wrote {out} ({prod.duration:.2f}s)")
    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    from .spec.generate import generate_spec
    text = generate_spec()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    from .ai.autopilot import autopilot
    return autopilot(idea=args.idea, output=args.output, model=args.model,
                     max_rounds=args.max_rounds, keep=args.keep)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="motionforge",
        description="Deterministic 2.5D animation studio: screenplay in, MP4 film out.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="validate a screenplay; report every problem")
    p.add_argument("screenplay")
    p.add_argument("--json", action="store_true", help="machine-readable report")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("frame", help="render a single frame to PNG")
    p.add_argument("screenplay")
    p.add_argument("-t", "--time", type=float, default=0.0, help="film time in seconds")
    p.add_argument("-o", "--output")
    p.set_defaults(fn=cmd_frame)

    p = sub.add_parser("storyboard", help="render a grid of frames to PNG")
    p.add_argument("screenplay")
    p.add_argument("-o", "--output")
    p.add_argument("--columns", type=int, default=4)
    p.add_argument("--count", type=int, default=12)
    p.set_defaults(fn=cmd_storyboard)

    p = sub.add_parser("render", help="render the full film to MP4")
    p.add_argument("screenplay")
    p.add_argument("-o", "--output")
    p.add_argument("--workers", type=int, default=0, help="0 = all cores")
    p.add_argument("-q", "--quiet", action="store_true")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("spec", help="emit the complete language reference (for LLMs)")
    p.add_argument("-o", "--output")
    p.set_defaults(fn=cmd_spec)

    p = sub.add_parser("auto", help="AI autopilot: idea -> screenplay -> checked -> MP4")
    p.add_argument("idea")
    p.add_argument("-o", "--output", default="film.mp4")
    p.add_argument("--model", default=None, help="LLM model id (default: env or claude)")
    p.add_argument("--max-rounds", type=int, default=6)
    p.add_argument("--keep", action="store_true", help="keep the generated screenplay file")
    p.set_defaults(fn=cmd_auto)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except Exception as e:  # surface clean errors, not tracebacks, to authors
        from .core.errors import ScreenplayError
        if isinstance(e, ScreenplayError):
            print(e.report.format(), file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
