"""Build and execute a repo-owned release smoke rehearsal against a built wheel."""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404 - repo-owned release smoke uses vetted subprocess calls with explicit argv
import sys
import tempfile
import venv
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sattlint import cli_output
from sattlint.devtools._io import sanitize_repo_path
from sattlint.devtools.artifact_registry import (
    RELEASE_SMOKE_SCHEMA_VERSION,
    RELEASE_SMOKE_STATUS_FILENAME,
    RELEASE_SMOKE_STATUS_SCHEMA_KIND,
    RELEASE_SMOKE_SUMMARY_FILENAME,
    RELEASE_SMOKE_SUMMARY_SCHEMA_KIND,
)
from sattlint.devtools.shared.pipeline_artifacts import write_json_artifact
from sattlint.repo_paths import repo_root_from

REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "release-smoke"
STATUS_SCHEMA_KIND = RELEASE_SMOKE_STATUS_SCHEMA_KIND
SUMMARY_SCHEMA_KIND = RELEASE_SMOKE_SUMMARY_SCHEMA_KIND
SCHEMA_VERSION = RELEASE_SMOKE_SCHEMA_VERSION
LSP_RUNTIME_DEPENDENCIES = ("pygls>=1.3.1",)


class _CommandRunner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        text: bool,
        capture_output: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]: ...


class _VirtualenvCreator(Protocol):
    def __call__(self, venv_dir: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class _SmokeStepDefinition:
    step_id: str
    display_name: str
    command: tuple[str, ...]
    timeout_seconds: float | None = None
    timeout_is_success: bool = False


@dataclass(frozen=True, slots=True)
class _SmokeStepResult:
    step_id: str
    display_name: str
    command: tuple[str, ...]
    exit_code: int
    status: str
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "command": list(self.command),
            "timed_out": self.timed_out,
        }

    def to_summary_payload(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "display_name": self.display_name,
            "status": self.status,
            "exit_code": self.exit_code,
            "command": list(self.command),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
        }


def _ensure_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _create_virtualenv(venv_dir: Path) -> None:
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(venv_dir)


def _run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    text: bool,
    capture_output: bool,
    check: bool,
    timeout: float | None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - commands are explicit argv sequences built from repo-controlled paths
        list(command),
        cwd=cwd,
        env=dict(env),
        text=text,
        capture_output=capture_output,
        check=check,
        timeout=timeout,
    )


def _venv_bin_dir(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin")


def _venv_python(venv_dir: Path) -> Path:
    return _venv_bin_dir(venv_dir) / ("python.exe" if os.name == "nt" else "python")


def _venv_script(venv_dir: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return _venv_bin_dir(venv_dir) / f"{name}{suffix}"


def _build_step_definitions(venv_dir: Path, *, wheel: Path, sample_file: Path) -> tuple[_SmokeStepDefinition, ...]:
    python_executable = _venv_python(venv_dir)
    sattlint_executable = _venv_script(venv_dir, "sattlint")
    lsp_executable = _venv_script(venv_dir, "sattlint-lsp")
    return (
        _SmokeStepDefinition(
            step_id="install_wheel",
            display_name="Install built wheel",
            command=(str(python_executable), "-m", "pip", "install", str(wheel)),
        ),
        _SmokeStepDefinition(
            step_id="install_lsp_runtime_dependencies",
            display_name="Install stable LSP runtime dependencies",
            command=(str(python_executable), "-m", "pip", "install", *LSP_RUNTIME_DEPENDENCIES),
        ),
        _SmokeStepDefinition(
            step_id="cli_version",
            display_name="Boot CLI version",
            command=(str(sattlint_executable), "--version"),
        ),
        _SmokeStepDefinition(
            step_id="syntax_check",
            display_name="Run syntax-check sample",
            command=(str(sattlint_executable), "syntax-check", str(sample_file)),
        ),
        _SmokeStepDefinition(
            step_id="repo_audit_boot",
            display_name="Boot stable repo-audit subcommand",
            command=(str(sattlint_executable), "repo-audit", "--profile", "full", "--list-checks"),
        ),
        _SmokeStepDefinition(
            step_id="lsp_boot",
            display_name="Boot stable LSP entrypoint",
            command=(str(lsp_executable),),
            timeout_seconds=1.0,
            timeout_is_success=True,
        ),
    )


def _run_step(
    definition: _SmokeStepDefinition,
    *,
    cwd: Path,
    env: Mapping[str, str],
    run_command: _CommandRunner,
) -> _SmokeStepResult:
    try:
        completed = run_command(
            definition.command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=definition.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        if not definition.timeout_is_success:
            return _SmokeStepResult(
                step_id=definition.step_id,
                display_name=definition.display_name,
                command=definition.command,
                exit_code=1,
                status="fail",
                stdout=_ensure_text(exc.stdout),
                stderr=_ensure_text(exc.stderr),
                timed_out=True,
            )
        return _SmokeStepResult(
            step_id=definition.step_id,
            display_name=definition.display_name,
            command=definition.command,
            exit_code=0,
            status="pass",
            stdout=_ensure_text(exc.stdout),
            stderr=_ensure_text(exc.stderr),
            timed_out=True,
        )
    return _SmokeStepResult(
        step_id=definition.step_id,
        display_name=definition.display_name,
        command=definition.command,
        exit_code=completed.returncode,
        status="pass" if completed.returncode == 0 else "fail",
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def execute_release_smoke(
    *,
    wheel: Path,
    sample_file: Path,
    output_dir: Path,
    repo_root: Path = REPO_ROOT,
    run_command: _CommandRunner = _run_subprocess,
    create_virtualenv: _VirtualenvCreator = _create_virtualenv,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved_repo_root = repo_root.resolve()
    resolved_wheel = wheel.resolve()
    resolved_sample_file = sample_file.resolve()
    resolved_output_dir = output_dir.resolve()
    sanitized_output_dir = sanitize_repo_path(resolved_output_dir, workspace_root=resolved_repo_root)
    sanitized_wheel = sanitize_repo_path(resolved_wheel, workspace_root=resolved_repo_root)
    sanitized_sample = sanitize_repo_path(resolved_sample_file, workspace_root=resolved_repo_root)
    canonical_command = (
        "sattlint-release-smoke "
        f"--wheel {sanitized_wheel} --sample-file {sanitized_sample} --output-dir {sanitized_output_dir}"
    )

    executed_steps: list[_SmokeStepResult] = []
    pending_steps: list[str] = []
    error_message: str | None = None

    if not resolved_wheel.is_file():
        error_message = f"wheel not found: {sanitized_wheel}"
    elif not resolved_sample_file.is_file():
        error_message = f"sample file not found: {sanitized_sample}"
    else:
        with tempfile.TemporaryDirectory(prefix="release-smoke-") as temp_dir_str:
            venv_dir = Path(temp_dir_str) / "venv"
            try:
                create_virtualenv(venv_dir)
                step_definitions = _build_step_definitions(
                    venv_dir,
                    wheel=resolved_wheel,
                    sample_file=resolved_sample_file,
                )
                env = dict(os.environ)
                env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
                env.setdefault("PYTHONUTF8", "1")
                pending_steps = [definition.step_id for definition in step_definitions]
                for definition in step_definitions:
                    result = _run_step(definition, cwd=resolved_repo_root, env=env, run_command=run_command)
                    executed_steps.append(result)
                    pending_steps = pending_steps[1:]
                    if result.exit_code != 0:
                        break
            except (OSError, subprocess.SubprocessError, RuntimeError) as error:
                error_message = str(error)

    failing_steps = [result.step_id for result in executed_steps if result.status == "fail"]
    overall_status = "pass" if not failing_steps and error_message is None else "fail"
    step_statuses = {result.step_id: result.to_status_payload() for result in executed_steps}
    status_report: dict[str, Any] = {
        "kind": RELEASE_SMOKE_STATUS_SCHEMA_KIND,
        "schema_version": RELEASE_SMOKE_SCHEMA_VERSION,
        "entry_report": "status.json",
        "overall_status": overall_status,
        "output_dir": sanitized_output_dir,
        "canonical_command": canonical_command,
        "wheel": sanitized_wheel,
        "sample_file": sanitized_sample,
        "step_statuses": step_statuses,
        "failing_steps": failing_steps,
        "pending_steps": pending_steps,
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
    }
    if error_message is not None:
        status_report["error"] = {"message": error_message}

    summary_report: dict[str, Any] = {
        "kind": RELEASE_SMOKE_SUMMARY_SCHEMA_KIND,
        "schema_version": RELEASE_SMOKE_SCHEMA_VERSION,
        "entry_report": "status.json",
        "output_dir": sanitized_output_dir,
        "canonical_command": canonical_command,
        "wheel": sanitized_wheel,
        "sample_file": sanitized_sample,
        "status": {
            "overall_status": overall_status,
            "failing_steps": failing_steps,
            "pending_steps": pending_steps,
        },
        "steps": [result.to_summary_payload() for result in executed_steps],
    }
    if error_message is not None:
        summary_report["error"] = {"message": error_message}

    return status_report, summary_report


def format_cli_summary(status_report: dict[str, Any]) -> str:
    failing_steps = ", ".join(str(step) for step in status_report["failing_steps"]) or "none"
    pending_steps = ", ".join(str(step) for step in status_report["pending_steps"]) or "none"
    return "\n".join(
        (
            f"Release smoke status: {status_report['overall_status']}",
            f"Failing steps: {failing_steps}",
            f"Pending steps: {pending_steps}",
            f"Status report: {status_report['status_report']}",
            f"Summary report: {status_report['summary_report']}",
        )
    )


def run_release_smoke(
    *,
    wheel: Path,
    sample_file: Path,
    output_dir: Path,
    repo_root: Path = REPO_ROOT,
    run_command: _CommandRunner = _run_subprocess,
    create_virtualenv: _VirtualenvCreator = _create_virtualenv,
    output_format: cli_output.OutputFormat = "text",
    emit_output_fn: Callable[[str], None] = print,
) -> int:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        status_report, summary_report = execute_release_smoke(
            wheel=wheel,
            sample_file=sample_file,
            output_dir=output_dir,
            repo_root=repo_root,
            run_command=run_command,
            create_virtualenv=create_virtualenv,
        )
        write_json_artifact(output_dir / RELEASE_SMOKE_STATUS_FILENAME, status_report, repo_root=repo_root)
        write_json_artifact(output_dir / RELEASE_SMOKE_SUMMARY_FILENAME, summary_report, repo_root=repo_root)
    except OSError as error:
        print(f"release smoke output error: {error}", file=sys.stderr)
        return 1
    cli_output.emit_text_or_json(
        text=format_cli_summary(status_report),
        json_payload=summary_report,
        output_format=output_format,
        emit_text_fn=emit_output_fn,
    )
    return 0 if status_report["overall_status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SattLint release smoke rehearsal against a built wheel.")
    cli_output.add_output_format_argument(
        parser,
        help_text="Output format for stdout summary.",
    )
    parser.add_argument("--wheel", required=True, type=Path, help="Built wheel to install into a temporary environment")
    parser.add_argument(
        "--sample-file",
        required=True,
        type=Path,
        help="Checked-in sample SattLine file used for syntax-check proof",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for status.json and summary.json"
    )
    parser.add_argument(
        "--repo-root", type=Path, default=REPO_ROOT, help="Repository root used for relative-path sanitization"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_format = cli_output.resolve_output_format(args)
    return run_release_smoke(
        wheel=args.wheel,
        sample_file=args.sample_file,
        output_dir=args.output_dir,
        repo_root=args.repo_root,
        output_format=output_format,
    )


if __name__ == "__main__":
    raise SystemExit(main())
