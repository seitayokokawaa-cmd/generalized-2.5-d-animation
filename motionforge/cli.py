"""MotionForge command-line interface.

Subcommands:
    render    Render a screenplay to a finished MP4.
    validate  Check a screenplay and report problems in plain language.
    preview   Render a single frame as PNG.
    spec      Print the complete screenplay language reference.
    auto      Let an LLM write, validate, fix, and render a film from an idea.
"""
from __future__ import annotations

import argparse
import sys

from motionforge import __version__


def _cmd_render(args: argparse.Namespace) -> int:
    from motionforge.pipeline import render_file

    return render_file(args.screenplay, args.output, quality=args.quality)


def _cmd_validate(args: argparse.Namespace) -> int:
    from motionforge.pipeline import validate_file

    return validate_file(args.screenplay)


def _cmd_preview(args: argparse.Namespace) -> int:
    from motionforge.pipeline import preview_file

    return preview_file(args.screenplay, args.time, args.output)


def _cmd_spec(args: argparse.Namespace) -> int:
    from motionforge.ai.specgen import generate_spec

    text = generate_spec()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote language reference to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def _cmd_auto(args: argparse.Namespace) -> int:
    from motionforge.ai.autoloop import auto_create

    return auto_create(
        args.idea,
        args.output,
        model=args.model,
        max_rounds=args.max_rounds,
        keep_screenplay=args.keep_screenplay,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="motionforge",
        description="Turn a written screenplay into a finished 2.5D animated MP4 film.",
    )
    parser.add_argument("--version", action="version", version=f"motionforge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("render", help="Render a screenplay to MP4")
    p.add_argument("screenplay", help="Path to the screenplay .yaml file")
    p.add_argument("-o", "--output", default=None, help="Output MP4 path (default: <screenplay>.mp4)")
    p.add_argument(
        "--quality",
        choices=["draft", "normal", "high"],
        default="normal",
        help="draft = fast preview quality, high = maximum polish",
    )
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("validate", help="Check a screenplay and report problems")
    p.add_argument("screenplay", help="Path to the screenplay .yaml file")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("preview", help="Render a single frame as PNG")
    p.add_argument("screenplay", help="Path to the screenplay .yaml file")
    p.add_argument("-t", "--time", type=float, required=True, help="Film time in seconds")
    p.add_argument("-o", "--output", default=None, help="Output PNG path (default: <screenplay>_t<time>.png)")
    p.set_defaults(func=_cmd_preview)

    p = sub.add_parser("spec", help="Print the full screenplay language reference")
    p.add_argument("-o", "--output", default=None, help="Write to a file instead of stdout")
    p.set_defaults(func=_cmd_spec)

    p = sub.add_parser("auto", help="LLM writes, validates, fixes, and renders a film from an idea")
    p.add_argument("idea", help="A one-line (or longer) story idea")
    p.add_argument("-o", "--output", default="auto_film.mp4", help="Output MP4 path")
    p.add_argument("--model", default=None, help="Model id to use (default: latest Claude)")
    p.add_argument("--max-rounds", type=int, default=6, help="Max write/fix rounds before giving up")
    p.add_argument(
        "--keep-screenplay",
        default=None,
        help="Also save the final screenplay YAML to this path",
    )
    p.set_defaults(func=_cmd_auto)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
