import json

from sattlint.devtools import pipeline


def test_main_returns_failure_for_malformed_baseline_findings(monkeypatch, tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text("{not-json", encoding="utf-8")

    def fake_run_pipeline(output_dir, **kwargs):
        assert kwargs["baseline_findings"] == baseline_path.resolve()
        raise json.JSONDecodeError("Expecting property name enclosed in double quotes", "{not-json", 1)

    monkeypatch.setattr(pipeline, "_run_pipeline", fake_run_pipeline)

    exit_code = pipeline.main(
        [
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--profile",
            "quick",
            "--baseline-findings",
            str(baseline_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Expecting property name enclosed in double quotes" in captured.err
