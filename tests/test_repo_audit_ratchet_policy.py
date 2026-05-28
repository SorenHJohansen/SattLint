from __future__ import annotations

from types import SimpleNamespace

from sattlint.devtools import repo_audit


def test_run_ratchet_policy_check_returns_no_findings_when_policy_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        repo_audit.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ratchet-policy: OK\n", stderr=""),
    )

    findings = repo_audit._run_ratchet_policy_check(SimpleNamespace(root=tmp_path))

    assert findings == []


def test_run_ratchet_policy_check_converts_errors_to_findings(monkeypatch, tmp_path):
    stderr = "\n".join(
        [
            "ratchet-policy: blocked",
            "- Touched coverage debt file must reach target: src/sattlint/engine.py is 13.70% but target is 100.00%.",
            "- Touched structural debt file did not shrink: src/sattlint/engine.py remains 1157 lines against baseline 1142.",
        ]
    )
    monkeypatch.setattr(
        repo_audit.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=stderr),
    )

    findings = repo_audit._run_ratchet_policy_check(SimpleNamespace(root=tmp_path))

    assert [finding.id for finding in findings] == ["ratchet-policy-coverage", "ratchet-policy-structural"]
    assert [finding.category for finding in findings] == ["coverage", "architecture"]
    assert [finding.path for finding in findings] == [
        "src/sattlint/engine.py",
        "src/sattlint/engine.py",
    ]
    assert all(finding.severity == "high" for finding in findings)
