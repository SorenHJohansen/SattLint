# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false
from __future__ import annotations

import contextlib
import json

from sattlint.devtools import (
    FAULT_INJECTION_RESULTS_FILENAME,
    FAULT_INJECTION_SCHEMA_KIND,
    FaultInjector,
    FaultSpec,
    run_fault_injection_campaign,
    write_fault_injection_results,
)


def test_fault_injector_raises_only_on_configured_occurrence():
    injector = FaultInjector(
        specs=(
            FaultSpec(
                checkpoint="parse-source",
                fault_id="parse-on-second-pass",
                exception_type="value",
                message="boom",
                trigger_count=2,
            ),
        )
    )

    injector.checkpoint("parse-source")

    try:
        injector.checkpoint("parse-source")
    except ValueError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover - defensive assertion branch
        raise AssertionError("fault did not trigger on the configured occurrence")

    assert injector.checkpoint_counts == {"parse-source": 2}
    assert injector.triggered_fault_ids == ["parse-on-second-pass"]


def test_run_fault_injection_campaign_records_baseline_and_expected_faults():
    def case_fn(injector: FaultInjector) -> None:
        injector.checkpoint("load")
        injector.checkpoint("parse")
        injector.checkpoint("parse")

    results = run_fault_injection_campaign(
        "parser-case",
        case_fn,
        fault_specs=(
            FaultSpec(checkpoint="parse", fault_id="parse-second", exception_type="syntax", trigger_count=2),
            FaultSpec(checkpoint="emit", fault_id="never-hit", exception_type="runtime"),
        ),
    )

    records = {record.fault_id or record.status: record for record in results.records}
    assert records["baseline-pass"].checkpoint_counts == {"load": 1, "parse": 2}
    assert records["parse-second"].status == "fault-injected"
    assert records["parse-second"].checkpoint == "parse"
    assert records["parse-second"].exception_type == "SyntaxError"
    assert records["never-hit"].status == "missed-fault"
    assert records["never-hit"].checkpoint_counts == {"load": 1, "parse": 2}


def test_run_fault_injection_campaign_marks_unexpected_errors_when_fault_does_not_trigger():
    def case_fn(_injector: FaultInjector) -> None:
        raise RuntimeError("case failed")

    results = run_fault_injection_campaign(
        "unexpected-error",
        case_fn,
        fault_specs=(FaultSpec(checkpoint="parse", fault_id="parse-fault"),),
        include_baseline=False,
    )

    assert len(results.records) == 1
    record = results.records[0]
    assert record.status == "unexpected-error"
    assert record.fault_id == "parse-fault"
    assert record.exception_type == "RuntimeError"
    assert record.checkpoint is None


def test_run_fault_injection_campaign_marks_real_errors_unexpected_when_injected_fault_was_caught():
    def case_fn(injector: FaultInjector) -> None:
        with contextlib.suppress(RuntimeError):
            injector.checkpoint("parse")
        raise ValueError("case failed later")

    results = run_fault_injection_campaign(
        "unexpected-after-caught-fault",
        case_fn,
        fault_specs=(FaultSpec(checkpoint="parse", fault_id="parse-fault"),),
        include_baseline=False,
    )

    assert len(results.records) == 1
    record = results.records[0]
    assert record.status == "unexpected-error"
    assert record.fault_id == "parse-fault"
    assert record.exception_type == "ValueError"
    assert record.checkpoint is None


def test_write_fault_injection_results_writes_machine_readable_report(tmp_path):
    def case_fn(injector: FaultInjector) -> None:
        injector.checkpoint("load")

    results = run_fault_injection_campaign(
        "write-report",
        case_fn,
        fault_specs=(FaultSpec(checkpoint="load", fault_id="load-fault", exception_type="io"),),
    )

    output_path = write_fault_injection_results(tmp_path, results)

    assert output_path.name == FAULT_INJECTION_RESULTS_FILENAME
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["kind"] == FAULT_INJECTION_SCHEMA_KIND
    assert payload["summary"]["status_counts"] == {"baseline-pass": 1, "fault-injected": 1}
    assert payload["records"][1]["fault_id"] == "load-fault"
