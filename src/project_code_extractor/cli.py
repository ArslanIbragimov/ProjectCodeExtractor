"""Command-line interface for Project Code Extractor."""

import argparse
import os
import re
import sys
import warnings
from collections.abc import Iterable, Sequence
from pathlib import Path

import pyperclip

from . import __version__
from .extractor import ProjectCodeExtractor

_SIZE_UNITS = {
    "": 1,
    "b": 1,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
}


def parse_file_size(value: str) -> int:
    """Parse a byte size such as ``512``, ``100KB``, or ``2MiB``."""
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*([kmg]i?b?|b)?\s*", value, re.IGNORECASE
    )
    if not match:
        raise argparse.ArgumentTypeError(
            f"invalid file size {value!r}; use bytes or a KB/MB/GB/KiB/MiB/GiB suffix"
        )

    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit in {"k", "m", "g"}:
        unit += "b"
    multiplier = _SIZE_UNITS.get(unit)
    if multiplier is None:
        raise argparse.ArgumentTypeError(f"unsupported file size unit in {value!r}")
    return int(number * multiplier)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-code-extractor",
        description="Extract text files from a project into one clipboard-, file-, or stdout-ready document.",
        epilog=(
            "examples:\n"
            "  project-code-extractor .\n"
            "  project-code-extractor /path/to/project --output project.txt\n"
            "  project-code-extractor . --format markdown --stdout\n"
            "  project-code-extractor . --exclude '*.lock' --max-file-size 500KB"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="project directory to extract (default: current directory)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="write extracted output to this file"
    )
    parser.add_argument(
        "--stdout", action="store_true", help="write extracted output to stdout"
    )

    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="copy to the clipboard even when --output or --stdout is used",
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "markdown"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="include hidden files and directories except .git",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="additional gitignore-style exclusion pattern; may be used multiple times",
    )
    parser.add_argument(
        "--exclude-file",
        action="append",
        default=[],
        type=Path,
        metavar="FILE",
        help="additional file with gitignore-style exclusion patterns; may be used multiple times",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="text encoding used to read files (default: utf-8)",
    )
    parser.add_argument(
        "--max-file-size",
        type=parse_file_size,
        metavar="SIZE",
        help="skip files larger than SIZE, for example 500KB or 2MiB",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="follow symlinked files and directories",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print each skipped file and its reason",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress the extraction summary"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _read_pattern_files(paths: Iterable[Path]) -> list[str]:
    patterns: list[str] = []
    for path in paths:
        expanded_path = path.expanduser()
        try:
            patterns.extend(
                expanded_path.read_text(encoding="utf-8", errors="replace").splitlines()
            )
        except OSError as exc:
            raise ValueError(
                f"cannot read exclude file {expanded_path}: {exc}"
            ) from exc
    return patterns


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        file_patterns = _read_pattern_files(args.exclude_file)
    except ValueError as exc:
        parser.error(str(exc))

    additional_patterns = list(file_patterns) + list(args.exclude)

    try:
        extractor = ProjectCodeExtractor(
            args.project_path,
            include_hidden=args.include_hidden,
            additional_exclude_patterns=additional_patterns,
            encoding=args.encoding,
            output_format=args.output_format,
            max_file_size=args.max_file_size,
            follow_symlinks=args.follow_symlinks,
            excluded_paths=([args.output] if args.output is not None else [])
            + list(args.exclude_file),
        )
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            result = extractor.extract_code()
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for warning in caught_warnings:
        print(f"warning: {warning.message}", file=sys.stderr)

    if args.output is not None:
        output_path = args.output.expanduser()
        try:
            output_path.write_text(result.content, encoding="utf-8")
        except OSError as exc:
            print(
                f"error: cannot write output file {output_path}: {exc}", file=sys.stderr
            )
            return 1

    if args.stdout:
        try:
            sys.stdout.write(result.content)
            if result.content and not result.content.endswith("\n"):
                sys.stdout.write("\n")
        except BrokenPipeError:
            # Let downstream commands such as `head` close the pipe without a traceback.
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            return 0

    copy_implicitly = not args.stdout and args.output is None
    if args.clipboard or copy_implicitly:
        try:
            extractor.save_to_clipboard(result.content)
        except pyperclip.PyperclipException as exc:
            print(f"error: cannot copy to clipboard: {exc}", file=sys.stderr)
            return 1

    if args.verbose:
        for skipped_file in result.skipped_files:
            print(
                f"skipped {skipped_file.path}: {skipped_file.reason}", file=sys.stderr
            )

    if not args.quiet:
        print(
            f"Extracted {len(result.files)} file(s); skipped {len(result.skipped_files)} file(s).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
