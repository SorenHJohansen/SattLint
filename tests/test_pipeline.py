from sattlint.devtools import pipeline
from sattlint.reporting.variables_report import IssueKind


def test_command_payload_sanitizes_absolute_command_paths():
    windows_python = "C:" + r"\Users\Example\Workspace\SattLint\.venv\Scripts\python.exe"
    junit_path = (
        "--junitxml="
        + "C:"
        + r"\Users\Example\Workspace\SattLint\artifacts\analysis\pytest.junit.xml"
    )
    result = pipeline.CommandResult(
        name="pytest",
        command=[
            windows_python,
            "-m",
            "pytest",
            junit_path,
        ],
        exit_code=0,
        duration_seconds=1.0,
        stdout="",
        stderr="",
    )

    payload = pipeline._command_payload(result)

    assert payload["command"][0].endswith("python.exe") or payload["command"][0] == "<external>/python.exe"
    assert "--junitxml=" in payload["command"][3]


def test_collect_environment_report_has_python_executable(monkeypatch):
    original_executable = getattr(pipeline.sys, "executable", "python")

    report = pipeline._collect_environment_report()

    assert "python" in report["python"]["executable"].lower()


def test_collect_architecture_report_includes_shadowing_cli_filter():
    report = pipeline._collect_architecture_report()

    assert IssueKind.SHADOWING.value in report["cli_variable_filter_issue_kinds"]
    assert report["variables_report_summary_support"][IssueKind.SHADOWING.value] is True
