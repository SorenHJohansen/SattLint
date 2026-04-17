"""Parse ABB library files and report failures."""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from sattlint.engine import create_sl_parser  # noqa: E402
from sattline_parser import strip_sl_comments  # noqa: E402
from sattlint.grammar.parser_decode import preprocess_sl_text, is_compressed  # noqa: E402


def _default_abb_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1] / "Libs" / "HA" / "ABBLib"


def parse_text(parser, text: str) -> None:
    cleaned = strip_sl_comments(text)
    parser.parse(cleaned)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse ABB library files and report parser failures.")
    parser.add_argument(
        "--library-dir",
        default=str(_default_abb_dir()),
        help="Directory containing ABB library files",
    )
    args = parser.parse_args(argv)

    abb_dir = pathlib.Path(args.library_dir).expanduser().resolve()
    if not abb_dir.exists() or not abb_dir.is_dir():
        print(f"Library directory not found: {abb_dir}", file=sys.stderr)
        return 2

    parser = create_sl_parser()

    pretty_files = sorted(abb_dir.glob("Pretty*.txt"))
    pretty_map = {p.stem.removeprefix("Pretty"): p for p in pretty_files}
    pretty_errors: list[tuple[str, str]] = []
    for path in pretty_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            parse_text(parser, text)
        except Exception as ex:  # noqa: BLE001
            pretty_errors.append((path.name, str(ex)))

    x_files = sorted(abb_dir.glob("*.x"))
    compressed_errors: list[tuple[str, str]] = []
    for path in x_files:
        base_name = path.stem.removesuffix("Lib") if path.stem.endswith("Lib") else path.stem
        if base_name not in pretty_map:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if is_compressed(text):
            text, _ = preprocess_sl_text(text)
        try:
            parse_text(parser, text)
        except Exception as ex:  # noqa: BLE001
            compressed_errors.append((path.name, str(ex)))

    print(f"Pretty files: {len(pretty_files)} errors: {len(pretty_errors)}")
    print(f"Compressed .x files: {len(x_files)} errors: {len(compressed_errors)}")
    if pretty_errors:
        print("Pretty errors (first 10):")
        for name, err in pretty_errors[:10]:
            print(f"- {name}: {err}")
    if compressed_errors:
        print("Compressed errors (first 10):")
        for name, err in compressed_errors[:10]:
            print(f"- {name}: {err}")

    return 1 if pretty_errors or compressed_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
