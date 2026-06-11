from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail when a forbidden source pattern appears in the scanned files.")
    parser.add_argument("--pattern", required=True, help="Regular expression to reject")
    parser.add_argument("--label", required=True, help="Short human-readable label for the pattern")
    parser.add_argument("files", nargs="*", help="Files to scan")
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def _normalize_relative(raw_path: str | Path) -> str:
    path = Path(raw_path)
    if path.is_absolute():
        path = path.resolve().relative_to(REPO_ROOT)
    return path.as_posix().strip("/")


def _iter_matches(path: Path, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        (line_number, line.rstrip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if pattern.search(line)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    pattern = re.compile(args.pattern)
    violations: list[str] = []

    for raw_file in args.files:
        relative_path = _normalize_relative(raw_file)
        path = REPO_ROOT / relative_path
        if not path.is_file():
            continue

        for line_number, line in _iter_matches(path, pattern):
            violations.append(f"{relative_path}:{line_number}: forbidden {args.label}: {line}")

    if not violations:
        return 0

    sys.stdout.write("\n".join(violations) + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
