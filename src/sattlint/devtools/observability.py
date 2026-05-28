"""Observability tooling: exposes metrics and logs for agent consumption."""

import json
import subprocess  # nosec B404 - internal devtool wrapper runs trusted local commands only
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

ARTIFACTS_DIR = Path("artifacts")
OBSERVABILITY_FILE = ARTIFACTS_DIR / "observability.json"


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
    except Exception as e:
        return 1, "", str(e)


def get_test_metrics() -> dict[str, Any]:
    """Get test-related metrics."""
    metrics = {
        "test_count": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0.0,
    }
    # Try to run pytest with json output if available
    # Fallback to parsing output if needed
    # For now, we'll just run a simple test count
    # In a real setup, we might use pytest-json-report or similar
    return metrics


def get_coverage_metrics() -> dict[str, Any]:
    """Get coverage metrics from coverage.xml if available."""
    metrics = {
        "line_coverage": 0.0,
        "branch_coverage": 0.0,
    }
    coverage_file = ARTIFACTS_DIR / "coverage.xml"
    if coverage_file.exists():
        try:
            tree = ElementTree.parse(coverage_file)
            root = tree.getroot()
            if root is None:
                return metrics
            # Get line-rate and branch-rate from the root coverage element
            line_rate = root.get("line-rate")
            branch_rate = root.get("branch-rate")
            if line_rate is not None:
                metrics["line_coverage"] = float(line_rate) * 100
            if branch_rate is not None:
                metrics["branch_coverage"] = float(branch_rate) * 100
        except Exception:
            return metrics
    return metrics


def get_lint_metrics() -> dict[str, Any]:
    """Get lint metrics from ruff."""
    metrics = {
        "ruff_warnings": 0,
        "ruff_errors": 0,
        "ruff_fixable": 0,
    }
    # Run ruff and count warnings/errors
    _, stdout, _ = run_command(["uvx", "ruff", "check", "src"])
    # Parse output to count warnings and errors
    # Simple approach: each line starting with src/ and containing a warning/error
    for line in stdout.splitlines():
        if line.strip() and line.startswith("src/"):
            if "warning" in line.lower():
                metrics["ruff_warnings"] += 1
            if "error" in line.lower():
                metrics["ruff_errors"] += 1
    # Check for fixable errors
    _, _, _ = run_command(["uvx", "ruff", "check", "--fix", "--output-format=concise", "src"])
    # In a real implementation, we'd compare before/after or use a specific flag
    # For now, we'll leave fixable as 0
    return metrics


def get_build_metrics() -> dict[str, Any]:
    """Get build/install metrics."""
    metrics = {
        "install_success": False,
        "lint_success": False,
        "test_success": False,
    }
    # Check if we can install the package in dev mode
    returncode, _, _ = run_command(["uv", "pip", "install", "--system", "-e", ".[dev]"])
    metrics["install_success"] = returncode == 0
    # We could run lint and test here, but that might be heavy. Instead, we rely on separate metrics.
    return metrics


def collect_all_metrics() -> dict[str, Any]:
    """Collect all observability metrics."""
    return {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "test": get_test_metrics(),
        "coverage": get_coverage_metrics(),
        "lint": get_lint_metrics(),
        "build": get_build_metrics(),
    }


def write_metrics(metrics: dict[str, Any]) -> None:
    """Write metrics to the observability file."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    with open(OBSERVABILITY_FILE, "w") as f:
        json.dump(metrics, f, indent=2)


def read_metrics() -> dict[str, Any]:
    """Read metrics from the observability file."""
    if OBSERVABILITY_FILE.exists():
        with open(OBSERVABILITY_FILE) as f:
            return json.load(f)
    return {}


def main() -> int:
    """Main entry point: collect and write metrics."""
    metrics = collect_all_metrics()
    output_error: OSError | None = None
    try:
        write_metrics(metrics)
    except OSError as exc:
        output_error = exc
    else:
        print(f"Observability metrics written to {OBSERVABILITY_FILE}")
    # Print a summary
    print(f"Line coverage: {metrics['coverage']['line_coverage']:.1f}%")
    print(f"Branch coverage: {metrics['coverage']['branch_coverage']:.1f}%")
    print(f"Lint warnings: {metrics['lint']['ruff_warnings']}")
    print(f"Lint errors: {metrics['lint']['ruff_errors']}")
    if output_error is not None:
        print(f"Observability metrics write error: {output_error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    main()
