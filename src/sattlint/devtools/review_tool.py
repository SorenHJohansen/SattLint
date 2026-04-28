"""Agent review tool: runs a comprehensive review of code changes for agent consumption."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Import our devtools for reuse
from .doc_gardener import run_scan as doc_gardener_scan
from .observability import collect_all_metrics
# We'll import the arch linter function if we refactor it, but for now we'll run as subprocess

ARTIFACTS_DIR = Path("artifacts")
REVIEW_FILE = ARTIFACTS_DIR / "review_report.json"


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def run_architecture_lint() -> Dict[str, Any]:
    """Run the architecture linter and return results."""
    returncode, stdout, stderr = run_command(
        [sys.executable, "-m", "sattlint.devtools.layer_linter"]
    )
    # Parse output to get violations count
    violations = 0
    if returncode != 0:
        # Try to extract number from output like "Found X architecture violations:"
        import re
        match = re.search(r"Found (\d+) architecture violations:", stdout + stderr)
        if match:
            violations = int(match.group(1))
    return {
        "passed": returncode == 0,
        "violations": violations,
        "stdout": stdout,
        "stderr": stderr,
    }


def run_doc_gardener() -> Dict[str, Any]:
    """Run the doc gardener scan and return results."""
    try:
        result = doc_gardener_scan()
        return {
            "passed": result["total_findings"] == 0,
            "findings": result["total_findings"],
            "by_severity": result["by_severity"],
            "by_category": result["by_category"],
        }
    except Exception as e:
        return {
            "passed": False,
            "error": str(e),
        }


def run_tests() -> Dict[str, Any]:
    """Run the test suite and return results."""
    returncode, stdout, stderr = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-v"]
    )
    # Parse pytest output for summary
    passed = 0
    failed = 0
    skipped = 0
    for line in stdout.splitlines():
        if "passed" in line and "failed" in line and "skipped" in line:
            # Typical pytest summary line: "5 passed, 2 failed, 3 skipped in 0.12s"
            import re
            nums = re.findall(r"(\d+)", line)
            if len(nums) >= 3:
                passed = int(nums[0])
                failed = int(nums[1])
                skipped = int(nums[2])
            break
    return {
        "passed": returncode == 0 and failed == 0,
        "returncode": returncode,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "stdout": stdout,
        "stderr": stderr,
    }


def run_linting() -> Dict[str, Any]:
    """Run ruff linting and return results."""
    returncode, stdout, stderr = run_command(
        ["uvx", "ruff", "check", "src"]
    )
    # Count warnings and errors
    warnings = 0
    errors = 0
    for line in stdout.splitlines():
        if line.strip() and line.startswith("src/"):
            if "warning" in line.lower():
                warnings += 1
            if "error" in line.lower():
                errors += 1
    return {
        "passed": returncode == 0,
        "warnings": warnings,
        "errors": errors,
        "stdout": stdout,
        "stderr": stderr,
    }


def run_format_check() -> Dict[str, Any]:
    """Check code formatting with ruff."""
    returncode, stdout, stderr = run_command(
        ["uvx", "ruff", "format", "--check", "src"]
    )
    return {
        "passed": returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
    }


def collect_observability() -> Dict[str, Any]:
    """Collect current observability metrics."""
    return collect_all_metrics()


def run_full_review() -> Dict[str, Any]:
    """Run all review checks and return a comprehensive report."""
    print("Running architecture lint...")
    arch_result = run_architecture_lint()
    print("Running doc gardener...")
    doc_result = run_doc_gardener()
    print("Running tests...")
    test_result = run_tests()
    print("Running linting...")
    lint_result = run_linting()
    print("Running format check...")
    format_result = run_format_check()
    print("Collecting observability...")
    obs_result = collect_observability()

    # Determine overall pass/fail
    overall_passed = (
        arch_result["passed"]
        and doc_result["passed"]
        and test_result["passed"]
        and lint_result["passed"]
        and format_result["passed"]
    )

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall_passed": overall_passed,
        "checks": {
            "architecture": arch_result,
            "documentation": doc_result,
            "tests": test_result,
            "linting": lint_result,
            "formatting": format_result,
            "observability": obs_result,
        },
        "summary": {
            "architecture_violations": arch_result.get("violations", 0),
            "doc_findings": doc_result.get("findings", 0),
            "tests_passed": test_result.get("passed", 0),
            "tests_failed": test_result.get("failed", 0),
            "lint_warnings": lint_result.get("warnings", 0),
            "lint_errors": lint_result.get("errors", 0),
            "format_passed": format_result["passed"],
        },
    }

    # Write report to artifacts
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    with open(REVIEW_FILE, "w") as f:
        json.dump(report, f, indent=2)

    return report


def print_review(report: Dict[str, Any]) -> None:
    """Print a human-readable summary of the review."""
    print("\n" + "="*60)
    print("AGENT REVIEW REPORT")
    print("="*60)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Overall Status: {'PASS' if report['overall_passed'] else 'FAIL'}")
    print("\nSummary:")
    summary = report["summary"]
    print(f"  Architecture Violations: {summary['architecture_violations']}")
    print(f"  Documentation Findings: {summary['doc_findings']}")
    print(f"  Tests: {summary['tests_passed']} passed, {summary['tests_failed']} failed")
    print(f"  Linting: {summary['lint_warnings']} warnings, {summary['lint_errors']} errors")
    print(f"  Formatting: {'PASS' if summary['format_passed'] else 'FAIL'}")

    print("\nDetails:")
    for check_name, check_result in report["checks"].items():
        print(f"  {check_name.upper()}:")
        if isinstance(check_result, dict) and "passed" in check_result:
            print(f"    Passed: {check_result['passed']}")
        # Print a few key details per check
        if check_name == "architecture":
            print(f"    Violations: {check_result.get('violations', 0)}")
        elif check_name == "documentation":
            print(f"    Findings: {check_result.get('findings', 0)}")
            if check_result.get("by_severity"):
                print(f"    By Severity: {check_result['by_severity']}")
        elif check_name == "tests":
            print(f"    Passed: {check_result.get('passed', 0)}")
            print(f"    Failed: {check_result.get('failed', 0)}")
            print(f"    Skipped: {check_result.get('skipped', 0)}")
        elif check_name == "linting":
            print(f"    Warnings: {check_result.get('warnings', 0)}")
            print(f"    Errors: {check_result.get('errors', 0)}")
        elif check_name == "formatting":
            print(f"    Passed: {check_result.get('passed', False)}")
        elif check_name == "observability":
            # Just show a couple of metrics
            cov = check_result.get("coverage", {})
            print(f"    Line Coverage: {cov.get('line_coverage', 0):.1f}%")
            print(f"    Branch Coverage: {cov.get('branch_coverage', 0):.1f}%")

    print("\n" + "="*60)


def main() -> None:
    """Main entry point: run review and print results."""
    report = run_full_review()
    print_review(report)
    print(f"\nFull report written to {REVIEW_FILE}")
    sys.exit(0 if report["overall_passed"] else 1)


if __name__ == "__main__":
    main()