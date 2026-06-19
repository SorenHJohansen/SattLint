# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import json

import sattlint.devtools.sandbox.fuzzer as fuzzer
from sattline_parser.fuzz_harness import FuzzResult, TimeoutError
from sattline_parser.models.ast_model import BasePicture, ModuleHeader


def _result(
    input_desc: str,
    *,
    success: bool = True,
    error: Exception | None = None,
) -> FuzzResult:
    return FuzzResult(
        input_desc=input_desc,
        success=success,
        result=BasePicture(header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)))
        if success and error is None
        else None,
        error=error,
        duration_ms=10.0,
    )


def test_analyze_fuzz_crashes_filters_expected_errors_and_timeouts() -> None:
    results = [
        _result("ok"),
        _result("expected-parse", success=False, error=ValueError("parse failed")),
        _result("timeout", success=False, error=TimeoutError("timeout")),
        _result("crash", success=False, error=RuntimeError("boom")),
    ]

    crashes = fuzzer.analyze_fuzz_crashes(results)

    assert [crash["input_desc"] for crash in crashes] == ["crash"]
    assert crashes[0]["error_type"] == "RuntimeError"


def test_run_fuzz_campaign_combines_corpus_and_random_results(monkeypatch) -> None:
    monkeypatch.setattr(
        "sattlint.devtools.sandbox.fuzzer.run_corpus_regression",
        lambda **_kwargs: [_result("corpus-a"), _result("corpus-b", success=False, error=ValueError("bad"))],
    )
    monkeypatch.setattr(
        "sattlint.devtools.sandbox.fuzzer.run_random_fuzz",
        lambda **_kwargs: [_result("random-a"), _result("random-b", success=False, error=RuntimeError("boom"))],
    )

    campaign = fuzzer.run_fuzz_campaign(random_rounds=2, assert_stable=False)

    payload = campaign.to_dict()
    assert payload["summary"]["total_runs"] == 4
    assert payload["summary"]["success_count"] == 2
    assert payload["summary"]["expected_parse_error_count"] == 1
    assert payload["summary"]["unexpected_crash_count"] == 1
    assert payload["crashes"][0]["input_desc"] == "random-b"


def test_write_fuzz_results_writes_machine_readable_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sattlint.devtools.sandbox.fuzzer.run_corpus_regression",
        lambda **_kwargs: [_result("corpus-a")],
    )
    monkeypatch.setattr(
        "sattlint.devtools.sandbox.fuzzer.run_random_fuzz",
        lambda **_kwargs: [_result("random-a", success=False, error=RuntimeError("boom"))],
    )

    campaign = fuzzer.run_fuzz_campaign(random_rounds=1, assert_stable=False)
    output_path = fuzzer.write_fuzz_results(tmp_path, campaign)

    assert output_path.name == fuzzer.FUZZ_RESULTS_FILENAME
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["kind"] == fuzzer.FUZZ_RESULTS_SCHEMA_KIND
    assert payload["summary"]["unexpected_crash_count"] == 1
    assert payload["crashes"][0]["input_desc"] == "random-a"


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


def test_run_fuzz_target_classifies_success_expected_error_and_crash() -> None:
    def _runner(source: str) -> None:
        if source == "bad-parse":
            raise ValueError("parse error")
        if source == "crash":
            raise RuntimeError("boom")

    report = fuzzer.run_fuzz_target(
        fuzzer.FuzzTarget(target_id="demo", runner=_runner),
        corpus_inputs=[("ok", "ok"), ("bad", "bad-parse"), ("crash", "crash")],
        random_rounds=0,
    )

    assert [record.status for record in report.records] == ["success", "expected-parse-error", "unexpected-crash"]
    assert [record.input_desc for record in fuzzer.analyze_crashes(report)] == ["corpus:crash"]


def test_write_fuzzer_report_writes_machine_readable_payload(tmp_path) -> None:
    report = fuzzer.FuzzerReport(
        records=[
            fuzzer.FuzzExecutionRecord(
                target_id="parser",
                input_desc="random:0(seed=101)",
                status="success",
                duration_ms=1.5,
            )
        ]
    )

    output_path = fuzzer.write_fuzzer_report(tmp_path, report)

    assert output_path == tmp_path / fuzzer.FUZZER_REPORT_FILENAME
    payload = output_path.read_text(encoding="utf-8")
    assert fuzzer.FUZZER_REPORT_SCHEMA_KIND in payload
    assert "random:0(seed=101)" in payload
