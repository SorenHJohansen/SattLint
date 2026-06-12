from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._python_runtime import resolve_repo_python  # noqa: E402

SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

ARTIFACT_DIR_ENV = "SATTLINT_RUN_REPO_PYTHON_ARTIFACT_DIR"
ARTIFACT_PREFIX_ENV = "SATTLINT_RUN_REPO_PYTHON_ARTIFACT_PREFIX"


@dataclass(frozen=True)
class CaptureConfig:
    artifact_dir: Path
    artifact_prefix: str


@dataclass(frozen=True)
class CaptureArtifactPaths:
    stdout_path: Path
    stderr_path: Path
    exit_path: Path


def _cleanup_temp_path(path: Path) -> None:
    path.unlink(missing_ok=True)


def _write_capture_text_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: PermissionError | None = None
    for _ in range(5):
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                temp_path = Path(handle.name)
            os.replace(temp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            if temp_path is not None:
                _cleanup_temp_path(temp_path)
            time.sleep(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to write {path}")


write_text_artifact = _write_capture_text_artifact
_resolve_python = resolve_repo_python


def _load_capture_config(*, env: Mapping[str, str], repo_root: Path) -> CaptureConfig | None:
    artifact_dir_text = env.get(ARTIFACT_DIR_ENV)
    artifact_prefix = env.get(ARTIFACT_PREFIX_ENV)
    if artifact_dir_text is None and artifact_prefix is None:
        return None
    if artifact_dir_text is None or artifact_prefix is None:
        raise ValueError(f"capture mode requires both {ARTIFACT_DIR_ENV} and {ARTIFACT_PREFIX_ENV}")

    normalized_dir_text = artifact_dir_text.strip()
    normalized_prefix = artifact_prefix.strip()
    if not normalized_dir_text:
        raise ValueError(f"{ARTIFACT_DIR_ENV} must not be empty")
    if not normalized_prefix:
        raise ValueError(f"{ARTIFACT_PREFIX_ENV} must not be empty")
    if "/" in normalized_prefix or "\\" in normalized_prefix:
        raise ValueError(f"{ARTIFACT_PREFIX_ENV} must not contain path separators")

    artifact_dir = Path(normalized_dir_text)
    if not artifact_dir.is_absolute():
        artifact_dir = repo_root / artifact_dir

    return CaptureConfig(artifact_dir=artifact_dir, artifact_prefix=normalized_prefix)


def _build_artifact_paths(config: CaptureConfig) -> CaptureArtifactPaths:
    return CaptureArtifactPaths(
        stdout_path=config.artifact_dir / f"{config.artifact_prefix}.stdout",
        stderr_path=config.artifact_dir / f"{config.artifact_prefix}.stderr",
        exit_path=config.artifact_dir / f"{config.artifact_prefix}.exit",
    )


def _run_child_process(
    python_executable: Path,
    python_args: Sequence[str],
    *,
    repo_root: Path,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    command = [str(python_executable), *python_args]
    if capture_output:
        return subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
    )
    return subprocess.CompletedProcess(
        completed.args,
        completed.returncode,
        stdout="",
        stderr="",
    )


def _write_capture_artifacts(
    artifact_paths: CaptureArtifactPaths,
    completed: subprocess.CompletedProcess[str],
) -> None:
    write_text_artifact(artifact_paths.stdout_path, completed.stdout or "")
    write_text_artifact(artifact_paths.stderr_path, completed.stderr or "")
    write_text_artifact(artifact_paths.exit_path, f"{completed.returncode}\n")


def _echo_captured_output(completed: subprocess.CompletedProcess[str]) -> None:
    if completed.stdout:
        sys.stdout.write(completed.stdout)
        sys.stdout.flush()
    if completed.stderr:
        sys.stderr.write(completed.stderr)
        if not completed.stderr.endswith("\n"):
            sys.stderr.write("\n")
        sys.stderr.flush()


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None) -> int:
    python_args = list(sys.argv[1:] if argv is None else argv)
    if not python_args:
        print("usage: run_repo_python.py <python-args>", file=sys.stderr)
        return 2

    active_env = os.environ if env is None else env
    try:
        capture_config = _load_capture_config(env=active_env, repo_root=REPO_ROOT)
    except ValueError as exc:
        print(f"run_repo_python.py: {exc}", file=sys.stderr)
        return 2

    python_executable = _resolve_python(REPO_ROOT)
    if capture_config is None:
        completed = _run_child_process(
            python_executable,
            python_args,
            repo_root=REPO_ROOT,
            capture_output=False,
        )
        return completed.returncode

    completed = _run_child_process(
        python_executable,
        python_args,
        repo_root=REPO_ROOT,
        capture_output=True,
    )
    artifact_paths = _build_artifact_paths(capture_config)
    try:
        _write_capture_artifacts(artifact_paths, completed)
    except (OSError, RuntimeError) as exc:
        _echo_captured_output(completed)
        print(
            f"run_repo_python.py: failed to write capture artifacts for prefix "
            f"'{capture_config.artifact_prefix}': {exc}",
            file=sys.stderr,
        )
        return completed.returncode or 1
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
