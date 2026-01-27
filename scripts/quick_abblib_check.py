import pathlib
import sys
import signal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from sattlint.engine import create_sl_parser, strip_sl_comments  # noqa: E402
from sattlint.grammar.parser_decode import preprocess_sl_text, is_compressed  # noqa: E402

ABB_DIR = pathlib.Path(
    r"c:/Users/SQHJ/OneDrive - Novo Nordisk/Workspace/GitHub.com/SattLint/Libs/HA/ABBLib"
)


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Parsing timeout")


def parse_with_timeout(parser, text: str, timeout_sec: int = 10) -> tuple[bool, str]:
    """Try to parse with a timeout. Returns (success, error_msg)."""
    try:
        # Windows doesn't support signal.alarm, so skip timeout on Windows
        if sys.platform != 'win32':
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_sec)

        cleaned = strip_sl_comments(text)
        parser.parse(cleaned)

        if sys.platform != 'win32':
            signal.alarm(0)

        return (True, "")
    except TimeoutException as ex:
        return (False, f"TIMEOUT after {timeout_sec}s")
    except Exception as ex:
        if sys.platform != 'win32':
            signal.alarm(0)
        return (False, str(ex)[:150])


def main() -> int:
    parser = create_sl_parser()

    print("="*70)
    print("Testing Pretty files (uncompressed)")
    print("="*70)

    pretty_files = sorted(ABB_DIR.glob("Pretty*.txt"))
    pretty_errors = []

    for i, path in enumerate(pretty_files, 1):
        print(f"[{i}/{len(pretty_files)}] {path.name:<35}", end=" ", flush=True)
        text = path.read_text(encoding="utf-8", errors="ignore")
        success, error = parse_with_timeout(parser, text, timeout_sec=15)

        if success:
            print("[OK]")
        else:
            print(f"[ERROR]")
            pretty_errors.append((path.name, error))
            print(f"    {error}")

    print(f"\nPretty files: {len(pretty_files)}, Errors: {len(pretty_errors)}")

    print("\n" + "="*70)
    print("Testing compressed .x files")
    print("="*70)

    # Map to only check files with Pretty equivalents
    pretty_map = {p.stem.removeprefix("Pretty"): p for p in pretty_files}

    compressed_errors = []
    checked_count = 0

    for path in sorted(ABB_DIR.glob("*.x")):
        base_name = path.stem

        if base_name not in pretty_map:
            continue

        checked_count += 1
        print(f"[{checked_count}/10] {path.name:<35}", end=" ", flush=True)

        text = path.read_text(encoding="utf-8", errors="ignore")

        if is_compressed(text):
            print("[compressed] ", end="", flush=True)
            text, _ = preprocess_sl_text(text)
        else:
            print("[plain] ", end="", flush=True)

        success, error = parse_with_timeout(parser, text, timeout_sec=15)

        if success:
            print("[OK]")
        else:
            print(f"[ERROR]")
            compressed_errors.append((path.name, error))
            print(f"    {error}")

    print(f"\nCompressed files: {checked_count}, Errors: {len(compressed_errors)}")

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Pretty files: {len(pretty_files)} checked, {len(pretty_errors)} errors")
    print(f"Compressed files: {checked_count} checked, {len(compressed_errors)} errors")

    if pretty_errors or compressed_errors:
        return 1
    else:
        print("\n[SUCCESS] All files parsed correctly!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
