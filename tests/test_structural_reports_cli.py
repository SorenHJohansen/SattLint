# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false

from __future__ import annotations

import json

from sattlint.devtools.structural import structural_reports


def test_structural_ratchet_main_reports_format_json_failures(monkeypatch, capsys, tmp_path):
    expected = {
        "status": "fail",
        "path": "ratchet.json",
        "expected_metrics": {"function_over_budget_count": 12},
        "current_metrics": {"function_over_budget_count": 18},
        "regressions": [
            {
                "metric": "function_over_budget_count",
                "expected_max": 12,
                "actual": 18,
            }
        ],
    }
    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: {"ratchet": expected},
    )

    exit_code = structural_reports.main(
        ["--repo-root", str(tmp_path), "--ratchet-path", str(tmp_path / "ratchet.json"), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected
