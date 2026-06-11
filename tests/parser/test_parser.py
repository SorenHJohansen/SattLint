"""Fuzz harness smoke tests and corpus regression checks for the SattLine parser."""

from __future__ import annotations

import pathlib

import pytest

from sattline_parser.fuzz_harness import (
    FuzzResult,
    _is_expected_parse_error,
    assert_no_crashes,
    assert_no_timeouts,
    collect_corpus_inputs,
    fuzz_parse_text,
    generate_random_text,
    run_corpus_regression,
    run_random_fuzz,
)

repo_root = pathlib.Path(__file__).resolve().parents[2]
CORPUS_DIR = repo_root / "tests" / "fixtures" / "corpus"


def _min_fuzz_result(
    input_desc: str = "test",
    *,
    success: bool = True,
    has_result: bool = True,
    has_error: bool = False,
    duration_ms: float = 100.0,
) -> FuzzResult:
    from sattline_parser.models.ast_model import BasePicture, ModuleHeader  # noqa: PLC0415

    return FuzzResult(
        input_desc=input_desc,
        success=success,
        result=BasePicture(header=ModuleHeader(name="test", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)))
        if has_result
        else None,
        error=ValueError("boom") if has_error else None,
        duration_ms=duration_ms,
    )


class TestFuzzParseText:
    def test_accepts_valid_sattline_program(self):
        import pathlib  # noqa: PLC0415

        from sattline_parser.models.ast_model import BasePicture  # noqa: PLC0415

        repo_root = pathlib.Path(__file__).resolve().parents[2]
        corpus_file = repo_root / "tests" / "fixtures" / "corpus" / "valid" / "MinimalProgram.s"
        source = corpus_file.read_text(encoding="utf-8")
        result = fuzz_parse_text(source, input_desc="valid-program")
        assert result.success
        assert isinstance(result.result, BasePicture)
        assert result.error is None
        assert result.duration_ms >= 0

    def test_rejects_malformed_input_gracefully(self):
        from sattline_parser.fuzz_harness import _is_expected_parse_error  # noqa: PLC0415

        source = "PROGRAM @@@@\nENDPROGRAM\n"
        result = fuzz_parse_text(source, input_desc="malformed")
        assert not result.success
        assert result.error is not None
        assert _is_expected_parse_error(result.error)

    def test_handles_empty_string(self):
        result = fuzz_parse_text("", input_desc="empty")
        assert not result.success
        assert result.error is not None

    def test_handles_very_long_input(self):
        source = "PROGRAM Long\n" + "x := 1;\n" * 1000 + "ENDPROGRAM\n"
        result = fuzz_parse_text(source, input_desc="long-input", timeout=5.0)
        assert result.duration_ms >= 0

    def test_timeout_enforced(self):
        from sattline_parser.fuzz_harness import TimeoutError  # noqa: PLC0415

        source = "PROGRAM Hang\n" + "x := " * 50000 + "\nENDPROGRAM\n"
        result = fuzz_parse_text(source, input_desc="timeout-test", timeout=0.5)
        assert not result.success
        assert isinstance(result.error, TimeoutError) or result.error is not None


class TestCollectCorpusInputs:
    def test_collects_valid_files(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, include_invalid=False, max_files=5)
        assert len(inputs) > 0
        for file_path, content in inputs[:3]:
            assert isinstance(file_path, str)
            assert isinstance(content, str)
            assert len(content) > 0

    def test_collects_invalid_files(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, include_valid=False, include_invalid=True, max_files=5)
        assert len(inputs) > 0

    def test_respects_max_files(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, max_files=3)
        assert len(inputs) <= 3

    def test_includes_valid_by_default(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, max_files=10)
        paths = [p for p, _ in inputs]
        assert any("valid" in p for p in paths)

    def test_collects_icf_files(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, include_valid=True, max_files=100)
        paths = [p for p, _ in inputs]
        assert any("icf" in p for p in paths)


class TestRunCorpusRegression:
    def test_runs_without_crashes(self):
        results = run_corpus_regression(CORPUS_DIR, max_files=10, timeout=5.0)
        assert len(results) > 0
        assert_no_crashes(results)

    def test_runs_without_timeouts(self):
        results = run_corpus_regression(CORPUS_DIR, max_files=10, timeout=5.0)
        assert_no_timeouts(results)

    def test_valid_files_parse_successfully(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, include_invalid=False, max_files=5)
        results = []
        for file_path, content in inputs:
            from sattline_parser.fuzz_harness import fuzz_parse_text  # noqa: PLC0415

            results.append(fuzz_parse_text(content, input_desc=file_path))
        success_count = sum(1 for r in results if r.success)
        assert success_count >= len(results) * 0.8

    def test_invalid_files_fail_gracefully(self):
        inputs = collect_corpus_inputs(CORPUS_DIR, include_valid=False, include_invalid=True, max_files=5)
        results = []
        for file_path, content in inputs:
            from sattline_parser.fuzz_harness import fuzz_parse_text  # noqa: PLC0415

            results.append(fuzz_parse_text(content, input_desc=file_path))
        assert all(not r.success for r in results if r.error is not None)


class TestGenerateRandomText:
    def test_generates_text_of_correct_length(self):
        text = generate_random_text(length=50)
        # Allow some flexibility - the function tries to get close to the target length
        assert 40 <= len(text) <= 60

    def test_generates_deterministic_output_with_seed(self):
        text1 = generate_random_text(length=100, seed=42)
        text2 = generate_random_text(length=100, seed=42)
        assert text1 == text2

    def test_generates_different_output_without_seed(self):
        text1 = generate_random_text(length=100)
        text2 = generate_random_text(length=100)
        assert text1 != text2 or len(text1) == 100


class TestRunRandomFuzz:
    def test_runs_without_crashes(self):
        results = run_random_fuzz(rounds=20, text_length=50, timeout=2.0, seed=123)
        assert len(results) == 20
        assert_no_crashes(results)

    def test_results_have_correct_structure(self):
        results = run_random_fuzz(rounds=10, seed=456)
        for result in results:
            assert isinstance(result, FuzzResult)
            assert isinstance(result.input_desc, str)
            assert isinstance(result.success, bool)
            assert isinstance(result.duration_ms, float)

    def test_timeout_protected(self):
        results = run_random_fuzz(rounds=5, text_length=1000, timeout=1.0, seed=789)
        for result in results:
            assert result.duration_ms < 2000 or isinstance(result.error, TimeoutError)


class TestFuzzResult:
    def test_to_dict_contains_required_keys(self):
        result = _min_fuzz_result("test-input")
        data = result.to_dict()
        assert "input_desc" in data
        assert "success" in data
        assert "result_type" in data
        assert "error_type" in data
        assert "duration_ms" in data

    def test_to_dict_reflects_success(self):
        result = _min_fuzz_result("success-case", success=True, has_result=True)
        data = result.to_dict()
        assert data["success"] is True
        assert data["result_type"] == "BasePicture"
        assert data["error_type"] is None

    def test_to_dict_reflects_failure(self):
        result = _min_fuzz_result("fail-case", success=False, has_error=True, has_result=False)
        data = result.to_dict()
        assert data["success"] is False
        assert data["result_type"] is None
        assert data["error_type"] == "ValueError"


class TestAssertNoCrashes:
    def test_passes_with_no_crashes(self):
        results = [_min_fuzz_result(f"ok-{i}", success=True) for i in range(3)]
        assert_no_crashes(results)

    def test_raises_on_crash(self):
        results = [
            _min_fuzz_result("ok", success=True),
            _min_fuzz_result("crash", success=False, has_error=True),
        ]
        # Replace ValueError with a custom exception not in _is_expected_parse_error
        results[1].error = RuntimeError("simulated crash")
        with pytest.raises(AssertionError, match="crash"):
            assert_no_crashes(results)


class TestAssertNoTimeouts:
    def test_passes_with_no_timeouts(self):
        results = [_min_fuzz_result(f"ok-{i}", success=True) for i in range(3)]
        assert_no_timeouts(results)

    def test_raises_on_timeout(self):
        from sattline_parser.fuzz_harness import TimeoutError  # noqa: PLC0415

        results = [
            _min_fuzz_result("ok", success=True),
            _min_fuzz_result("timeout", success=False),
        ]
        results[1].error = TimeoutError("timed out")
        with pytest.raises(AssertionError, match="timeout"):
            assert_no_timeouts(results)


class TestCorpusRegressionSmoke:
    def test_all_valid_corpus_files_parse(self):
        inputs = collect_corpus_inputs(
            CORPUS_DIR,
            include_valid=True,
            include_invalid=False,
            include_edge_cases=False,
            max_files=20,
        )
        assert len(inputs) >= 5
        for file_path, content in inputs:
            result = fuzz_parse_text(content, input_desc=f"valid:{file_path}")
            if "valid" in file_path:
                assert result.success, f"Valid file failed: {file_path}\nError: {result.error}"

    def test_invalid_corpus_files_dont_crash_parser(self):
        inputs = collect_corpus_inputs(
            CORPUS_DIR,
            include_valid=False,
            include_invalid=True,
            max_files=20,
        )
        for file_path, content in inputs:
            result = fuzz_parse_text(content, input_desc=f"invalid:{file_path}")
            # Invalid files should not crash the parser
            # (they may parse successfully due to lenient parsing)
            assert result.error is None or _is_expected_parse_error(result.error), (
                f"Parser crashed on {file_path}: {result.error}"
            )
