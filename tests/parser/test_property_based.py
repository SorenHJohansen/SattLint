# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

from sattline_parser.fuzz_harness import TimeoutError
from sattlint.devtools import parser_properties, property_tests
from sattlint.devtools.parser_properties import (
    assert_parser_deterministic,
    assert_valid_program_has_no_crash,
    generate_simple_module,
    generate_simple_program,
)
from sattlint.devtools.sandbox import fuzzer
from sattlint.engine import validate_single_file_syntax

REPO_ROOT = Path(__file__).resolve().parents[2]


def _validate_generated_source(tmp_path: Path, filename: str, source: str):
    source_file = tmp_path / filename
    source_file.write_text(source, encoding="utf-8")
    return validate_single_file_syntax(source_file)


def test_generate_simple_program_passes_strict_syntax_check(tmp_path: Path) -> None:
    result = _validate_generated_source(tmp_path, "GeneratedProgram.s", generate_simple_program())

    assert result.ok is True
    assert result.stage == "ok"


def test_generate_simple_module_passes_strict_syntax_check(tmp_path: Path) -> None:
    result = _validate_generated_source(tmp_path, "GeneratedModule.s", generate_simple_module())

    assert result.ok is True
    assert result.stage == "ok"


def test_generated_programs_support_parser_properties() -> None:
    source = generate_simple_program()

    assert_parser_deterministic(source)
    assert assert_valid_program_has_no_crash(source) is True


def test_generated_modules_support_parser_properties() -> None:
    source = generate_simple_module()

    assert_parser_deterministic(source)
    assert assert_valid_program_has_no_crash(source) is True


def test_assert_parser_deterministic_reports_header_and_submodule_mismatches(monkeypatch) -> None:
    header_mismatch = deque(
        [
            SimpleNamespace(header=SimpleNamespace(name="First"), submodules=[]),
            SimpleNamespace(header=SimpleNamespace(name="Second"), submodules=[]),
        ]
    )
    monkeypatch.setattr(parser_properties, "parser_core_parse_source_text", lambda _source: header_mismatch.popleft())

    with pytest.raises(AssertionError, match="header name"):
        assert_parser_deterministic("program")

    submodule_mismatch = deque(
        [
            SimpleNamespace(header=SimpleNamespace(name="Same"), submodules=[1]),
            SimpleNamespace(header=SimpleNamespace(name="Same"), submodules=[1, 2]),
        ]
    )
    monkeypatch.setattr(
        parser_properties, "parser_core_parse_source_text", lambda _source: submodule_mismatch.popleft()
    )

    with pytest.raises(AssertionError, match="submodule count"):
        assert_parser_deterministic("program")


def test_assert_valid_program_has_no_crash_returns_false_for_parser_errors(monkeypatch) -> None:
    def _raise_syntax_error(_source: str):
        raise SyntaxError("bad source")

    monkeypatch.setattr(parser_properties, "parser_core_parse_source_text", _raise_syntax_error)

    assert assert_valid_program_has_no_crash("broken") is False


def test_iter_generated_programs_and_modules_seed_and_count(monkeypatch) -> None:
    seed_calls: list[int] = []
    generated_programs = deque(["program-1", "program-2"])
    generated_modules = deque(["module-1", "module-2", "module-3"])

    monkeypatch.setattr(parser_properties.random, "seed", lambda value: seed_calls.append(value))
    monkeypatch.setattr(parser_properties, "generate_simple_program", lambda: generated_programs.popleft())
    monkeypatch.setattr(parser_properties, "generate_simple_module", lambda: generated_modules.popleft())

    assert list(parser_properties.iter_generated_programs(count=2, seed=7)) == ["program-1", "program-2"]
    assert list(parser_properties.iter_generated_modules(count=3, seed=11)) == ["module-1", "module-2", "module-3"]
    assert seed_calls == [7, 11]


def test_check_parser_property_records_false_results_and_exceptions(monkeypatch) -> None:
    seed_calls: list[int] = []
    generated_sources = deque(["A" * 80, "B" * 80, "C" * 80])

    monkeypatch.setattr(parser_properties.random, "seed", lambda value: seed_calls.append(value))
    monkeypatch.setattr(parser_properties, "generate_simple_program", lambda: generated_sources.popleft())

    def _property_fn(source: str) -> bool:
        if source.startswith("B"):
            return False
        if source.startswith("C"):
            raise RuntimeError("boom")
        return True

    failures = parser_properties.check_parser_property(_property_fn, count=3, seed=19)

    assert seed_calls == [19]
    assert failures[0] == ("B" * 60, None)
    assert failures[1][0] == "C" * 60
    assert isinstance(failures[1][1], RuntimeError)


def test_generate_seeded_property_inputs_is_deterministic() -> None:
    first = property_tests.generate_seeded_property_inputs((3, 7), text_length=80)
    second = property_tests.generate_seeded_property_inputs((3, 7), text_length=80)

    assert first == second
    assert all(seed in {3, 7} for seed, _ in first)


def test_run_property_tests_records_deterministic_corpus_and_graceful_random_checks(monkeypatch) -> None:
    monkeypatch.setattr(property_tests, "generate_random_text", lambda *, length, seed: f"seed-{seed}-len-{length}")
    monkeypatch.setattr(property_tests, "collect_corpus_inputs", lambda **_kwargs: [("ValidCase.s", "valid-source")])

    def fake_fuzz_parse_text(source: str, *, input_desc: str, timeout: float):
        if source == "valid-source":
            return SimpleNamespace(success=True, error=None)
        return SimpleNamespace(success=False, error=ValueError(f"expected parse issue from {input_desc}"))

    monkeypatch.setattr(property_tests, "fuzz_parse_text", fake_fuzz_parse_text)

    results = property_tests.run_property_tests(seeds=(11, 23), text_length=12, timeout=0.5, max_corpus_files=1)
    payload = results.to_dict()

    assert payload["summary"]["total_checks"] == 5
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["properties"] == {
        "random-inputs-fail-gracefully": 2,
        "seeded-generation-is-deterministic": 2,
        "valid-corpus-parses": 1,
    }


def test_run_property_tests_reports_expected_properties(monkeypatch) -> None:
    valid_source = (REPO_ROOT / "tests" / "fixtures" / "corpus" / "valid" / "MinimalProgram.s").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(
        property_tests,
        "collect_corpus_inputs",
        lambda **_kwargs: [("tests/fixtures/corpus/valid/MinimalProgram.s", valid_source)],
    )

    results = property_tests.run_property_tests(seeds=(5, 9), text_length=90, max_corpus_files=1)
    payload = results.to_dict()

    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["properties"] == {
        "random-inputs-fail-gracefully": 2,
        "seeded-generation-is-deterministic": 2,
        "valid-corpus-parses": 1,
    }


def test_write_property_test_results_writes_machine_readable_report(tmp_path: Path) -> None:
    results = property_tests.PropertyTestResults(
        records=[
            property_tests.PropertyCheckRecord(
                property_id="seeded-generation-is-deterministic",
                input_desc="seed:11",
                passed=True,
            )
        ]
    )

    output_path = property_tests.write_property_test_results(tmp_path, results)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.name == property_tests.PROPERTY_TEST_RESULTS_FILENAME
    assert payload["kind"] == property_tests.PROPERTY_TEST_SCHEMA_KIND
    assert payload["summary"]["passed"] == 1


def test_build_seed_corpus_forwards_collect_inputs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_collect_corpus_inputs(**kwargs):
        captured.update(kwargs)
        return [("fixture", "PROGRAM Demo\nENDPROGRAM\n")]

    monkeypatch.setattr(fuzzer, "collect_corpus_inputs", _fake_collect_corpus_inputs)

    result = fuzzer.build_seed_corpus(max_files=3, include_invalid=False, include_edge_cases=False)

    assert result == [("fixture", "PROGRAM Demo\nENDPROGRAM\n")]
    assert captured == {
        "include_valid": True,
        "include_invalid": False,
        "include_edge_cases": False,
        "max_files": 3,
    }


def test_run_fuzz_target_classifies_success_expected_errors_timeouts_and_crashes(monkeypatch) -> None:
    outcomes = deque(
        [
            (None, 10.0),
            (ValueError("expected parse failure"), 11.0),
            (TimeoutError("timed out"), 12.0),
            (RuntimeError("boom"), 13.0),
        ]
    )
    monkeypatch.setattr(fuzzer, "_run_with_timeout", lambda _runner, _source, _timeout: outcomes.popleft())
    monkeypatch.setattr(fuzzer, "generate_random_text", lambda *, length, seed: f"seed-{seed}-len-{length}")

    report = fuzzer.run_fuzz_target(
        fuzzer.FuzzTarget(target_id="parser", runner=lambda _source: None),
        corpus_inputs=[("valid-a", "source-a"), ("valid-b", "source-b")],
        random_rounds=2,
        seed=101,
    )

    statuses = [record.status for record in report.records]
    assert statuses == ["success", "expected-parse-error", "timeout", "unexpected-crash"]
    assert [record.input_desc for record in fuzzer.analyze_crashes(report)] == ["random:1(seed=102)"]


def test_run_parser_fuzzer_uses_seed_corpus_and_target(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(fuzzer, "build_seed_corpus", lambda *, max_files: [("seed-a", "A")])

    def fake_run_fuzz_target(target, **kwargs):
        captured["target_id"] = target.target_id
        captured.update(kwargs)
        return fuzzer.FuzzerReport()

    monkeypatch.setattr(fuzzer, "run_fuzz_target", fake_run_fuzz_target)

    report = fuzzer.run_parser_fuzzer(corpus_max_files=3, random_rounds=4, text_length=55, timeout=0.5, seed=9)

    assert isinstance(report, fuzzer.FuzzerReport)
    assert captured == {
        "target_id": "parser",
        "corpus_inputs": [("seed-a", "A")],
        "random_rounds": 4,
        "text_length": 55,
        "timeout": 0.5,
        "seed": 9,
    }


def test_write_fuzzer_report_writes_machine_readable_report(tmp_path: Path) -> None:
    report = fuzzer.FuzzerReport(
        records=[
            fuzzer.FuzzExecutionRecord(
                target_id="parser",
                input_desc="random:1(seed=102)",
                status="unexpected-crash",
                duration_ms=13.0,
                error_type="RuntimeError",
                error_message="boom",
            )
        ]
    )
    output_path = fuzzer.write_fuzzer_report(tmp_path, report)

    assert output_path.name == fuzzer.FUZZER_REPORT_FILENAME
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["kind"] == fuzzer.FUZZER_REPORT_SCHEMA_KIND
    assert payload["summary"]["unexpected_crash_count"] == 1
    assert payload["records"][0]["input_desc"] == "random:1(seed=102)"
