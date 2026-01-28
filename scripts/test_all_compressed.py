"""Batch-parse compressed ABB library files and summarize errors."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from sattlint.engine import create_sl_parser, strip_sl_comments  # noqa: E402
from sattlint.grammar.parser_decode import preprocess_sl_text, is_compressed  # noqa: E402

ABB_DIR = pathlib.Path(
    r"c:/Users/SQHJ/OneDrive - Novo Nordisk/Workspace/GitHub.com/SattLint/Libs/HA/ABBLib"
)


def parse_text(parser, text: str) -> tuple[bool, str]:
    """Try to parse. Returns (success, error_msg)."""
    try:
        cleaned = strip_sl_comments(text)
        parser.parse(cleaned)
        return (True, "")
    except Exception as ex:
        return (False, str(ex)[:120])


def main() -> int:
    parser = create_sl_parser()

    # Map to only check files with Pretty equivalents
    pretty_files = sorted(ABB_DIR.glob("Pretty*.txt"))
    pretty_map = {p.stem.removeprefix("Pretty"): p for p in pretty_files}

    all_errors = []

    for ext in [".x", ".y", ".z"]:
        print("="*70)
        print(f"Testing compressed {ext} files")
        print("="*70)

        errors = []
        checked_count = 0

        for path in sorted(ABB_DIR.glob(f"*{ext}")):
            base_name = path.stem

            if base_name not in pretty_map:
                continue

            checked_count += 1
            print(f"[{checked_count:2d}] {path.name:<35}", end=" ", flush=True)

            text = path.read_text(encoding="utf-8", errors="ignore")

            if is_compressed(text):
                text, _ = preprocess_sl_text(text)

            success, error = parse_text(parser, text)

            if success:
                print("[OK]")
            else:
                print(f"[ERROR]")
                errors.append((path.name, error))
                print(f"    {error}")
                all_errors.append((path.name, error))

        print(f"\n{ext} files checked: {checked_count}, Errors: {len(errors)}\n")

    print("="*70)
    print("FINAL SUMMARY")
    print("="*70)

    if all_errors:
        print(f"Total errors: {len(all_errors)}")
        for name, error in all_errors:
            print(f"  - {name}: {error}")
        return 1
    else:
        print("[SUCCESS] All compressed files (.x, .y, .z) parsed correctly!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
