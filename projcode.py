"""Compatibility wrapper for running Project Code Extractor from a source checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main() -> int:
    from project_code_extractor.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
