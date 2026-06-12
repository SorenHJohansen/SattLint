"""Observability tooling: exposes metrics and logs for agent consumption."""

import argparse
import json
import subprocess  # nosec B404 - internal devtool wrapper runs trusted local commands only
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from defusedxml import ElementTree

from sattlint import cli_output

from .pipeline._pipeline_parsing_helpers import parse_pytest_junit

ARTIFACTS_DIR = Path("artifacts")
OBSERVABILITY_FILE = ARTIFACTS_DIR / "observability.json"


def _default_test_metrics(*, stale: bool) -> dict[str, Any]:
    return {
        "test_count": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "stale": stale,
    }


def _pytest_json_candidates() -> tuple[Path, ...]:
    return (
        ARTIFACTS_DIR / "audit" / "pipeline" / "pytest.json",
        ARTIFACTS_DIR / "analysis" / "pytest.json",
        ARTIFACTS_DIR / "pytest.json",
    )


def _pytest_junit_candidates() -> tuple[Path, ...]:
    return (
        ARTIFACTS_DIR / "audit" / "pipeline" / "pytest.junit.xml",
        ARTIFACTS_DIR / "analysis" / "pytest.junit.xml",
        ARTIFACTS_DIR / "pytest.junit.xml",
    )


def _as_mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], value)


def _coerce_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        try:
            return int(value)
        except ValueError:
            return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _build_test_metrics(summary: Mapping[str, object]) -> dict[str, Any]:
    test_count = _coerce_int(summary.get("tests"))
    failed = _coerce_int(summary.get("failures")) + _coerce_int(summary.get("errors"))
    skipped = _coerce_int(summary.get("skipped"))
    passed = max(test_count - failed - skipped, 0)
    return {
        "test_count": test_count,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "stale": False,
    }


def _read_pytest_json_metrics(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    payload_mapping = _as_mapping(payload)
    if payload_mapping is None:
        return None
    summary = _as_mapping(payload_mapping.get("summary"))
    if summary is None:
        return None
    return _build_test_metrics(summary)


def _read_pytest_junit_metrics(path: Path) -> dict[str, Any] | None:
    try:
        payload = parse_pytest_junit(path)
    except (OSError, ElementTree.ParseError, ValueError):
        return None
    summary = _as_mapping(payload.get("summary"))
    if summary is None:
        return None
    return _build_test_metrics(summary)


def _has_fix(finding: object) -> bool:
    finding_mapping = _as_mapping(finding)
    if finding_mapping is None:
        return False
    return finding_mapping.get("fix") is not None


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(  # nosec B603 - trusted internal command list for local devtools only
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except (OSError, RuntimeError, ValueError) as e:
        return 1, "", str(e)


def get_test_metrics() -> dict[str, Any]:
    """Get test-related metrics."""
    for candidate in _pytest_json_candidates():
        if not candidate.exists():
            continue
        metrics = _read_pytest_json_metrics(candidate)
        if metrics is not None:
            return metrics
    for candidate in _pytest_junit_candidates():
        if not candidate.exists():
            continue
        metrics = _read_pytest_junit_metrics(candidate)
        if metrics is not None:
            return metrics
    return _default_test_metrics(stale=True)


def get_coverage_metrics() -> dict[str, Any]:
    """Get coverage metrics from coverage.xml if available."""
    metrics = {
        "line_coverage": 0.0,
        "branch_coverage": 0.0,
    }
    coverage_file = ARTIFACTS_DIR / "coverage.xml"
    if coverage_file.exists():
        try:
            root = ElementTree.fromstring(coverage_file.read_text(encoding="utf-8"))
            # Get line-rate and branch-rate from the root coverage element
            line_rate = root.get("line-rate")
            branch_rate = root.get("branch-rate")
            if line_rate is not None:
                metrics["line_coverage"] = float(line_rate) * 100
            if branch_rate is not None:
                metrics["branch_coverage"] = float(branch_rate) * 100
        except (ElementTree.ParseError, OSError, TypeError, ValueError):
            return metrics
    return metrics


def get_lint_metrics() -> dict[str, Any]:
    """Get lint metrics from ruff."""
    metrics = {"ruff_errors": 0}
    _, stdout, _ = run_command([sys.executable, "-m", "ruff", "check", "src", "--output-format=json"])
    try:
        findings = json.loads(stdout)
    except json.JSONDecodeError:
        return metrics
    if not isinstance(findings, list):
        return metrics
    findings_list = cast(list[object], findings)
    metrics["ruff_errors"] = len(findings_list)
    metrics["ruff_fixable"] = sum(1 for finding in findings_list if _has_fix(finding))
    return metrics


def get_build_metrics(lint_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get build/install metrics."""
    active_lint_metrics = get_lint_metrics() if lint_metrics is None else lint_metrics
    returncode, _, _ = run_command([sys.executable, "-c", "import sattlint"])
    return {
        "install_success": returncode == 0,
        "lint_success": active_lint_metrics.get("ruff_errors", 1) == 0,
    }


def collect_all_metrics() -> dict[str, Any]:
    """Collect all observability metrics."""
    lint_metrics = get_lint_metrics()
    return {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "test": get_test_metrics(),
        "coverage": get_coverage_metrics(),
        "lint": lint_metrics,
        "build": get_build_metrics(lint_metrics),
    }


def write_metrics(metrics: dict[str, Any]) -> None:
    """Write metrics to the observability file."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    with open(OBSERVABILITY_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


def read_metrics() -> dict[str, Any]:
    """Read metrics from the observability file."""
    if OBSERVABILITY_FILE.exists():
        with open(OBSERVABILITY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and persist SattLint observability metrics.")
    cli_output.add_output_format_argument(
        parser,
        help_text="Output format for stdout summary.",
    )
    return parser


def _format_cli_summary(metrics: dict[str, Any], *, include_written_message: bool) -> str:
    lines: list[str] = []
    if include_written_message:
        lines.append(f"Observability metrics written to {OBSERVABILITY_FILE}")
    lines.append(f"Line coverage: {metrics['coverage']['line_coverage']:.1f}%")
    lines.append(f"Branch coverage: {metrics['coverage']['branch_coverage']:.1f}%")
    lines.append(f"Lint errors: {metrics['lint']['ruff_errors']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Main entry point: collect and write metrics."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    output_format = cli_output.resolve_output_format(args)
    metrics = collect_all_metrics()
    output_error: OSError | None = None
    try:
        write_metrics(metrics)
    except OSError as exc:
        output_error = exc
    summary_payload: dict[str, Any] = {
        "metrics_file": OBSERVABILITY_FILE.as_posix(),
        "metrics": metrics,
    }
    if output_error is not None:
        summary_payload["output_error"] = str(output_error)
    cli_output.emit_text_or_json(
        text=_format_cli_summary(metrics, include_written_message=output_error is None),
        json_payload=summary_payload,
        output_format=output_format,
        emit_text_fn=print,
    )
    if output_error is not None:
        sys.stderr.write(f"Observability metrics write error: {output_error}\n")
        return 1
    return 0


if __name__ == "__main__":
    main()
