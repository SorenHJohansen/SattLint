"""Benchmark: SattLine parser and analyzer performance."""

from pathlib import Path

from sattline_parser.api import build_lark_parser, parse_source_text
from sattline_parser.utils.text_processing import strip_sl_comments_with_mapping

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sample_sattline_files"
_FIXTURE_FILE = _FIXTURE_DIR / "SattLineFullGrammarTest.s"


def _load_fixture() -> str:
    if _FIXTURE_FILE.exists():
        return _FIXTURE_FILE.read_text(encoding="utf-8")
    msg = f"Fixture not found: {_FIXTURE_FILE}"
    raise FileNotFoundError(msg)


_FIXTURE_TEXT = _load_fixture()
_PARSE_READY_FIXTURE_TEXT = strip_sl_comments_with_mapping(_FIXTURE_TEXT).text
_PARSER = build_lark_parser()


def test_benchmark_parse(benchmark):
    result = benchmark(parse_source_text, _FIXTURE_TEXT, parser=_PARSER)
    assert result.parse_tree is not None


def test_benchmark_parse_raw(benchmark):
    result = benchmark(_PARSER.parse, _PARSE_READY_FIXTURE_TEXT)
    assert result is not None
