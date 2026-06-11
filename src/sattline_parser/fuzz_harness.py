"""Standalone fuzz harness for SattLine parser.

Provides timeout-protected parsing, crash capture, and corpus-seeded fuzzing
for parser entry points.
"""

from __future__ import annotations

import concurrent.futures
import pathlib
import random
import time
import typing as t

from .api import parse_source_text
from .models.ast_model import BasePicture


def _repo_root_from(anchor: pathlib.Path) -> pathlib.Path:
    current = anchor.resolve()
    if current.is_file():
        current = current.parent
    while True:
        if (current / "pyproject.toml").is_file() and (current / "AGENTS.md").is_file():
            return current
        if current.parent == current:
            raise RuntimeError(f"Could not locate repository root from {anchor}")
        current = current.parent


REPO_ROOT = _repo_root_from(pathlib.Path(__file__))
CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus"
DEFAULT_TIMEOUT_SECONDS = 10


class FuzzResult:
    __slots__ = ("duration_ms", "error", "input_desc", "result", "success")

    def __init__(
        self,
        input_desc: str,
        *,
        success: bool,
        result: BasePicture | None = None,
        error: Exception | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        self.input_desc = input_desc
        self.success = success
        self.result = result
        self.error = error
        self.duration_ms = duration_ms

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "input_desc": self.input_desc,
            "success": self.success,
            "result_type": type(self.result).__name__ if self.result else None,
            "error_type": type(self.error).__name__ if self.error else None,
            "error_message": str(self.error) if self.error else None,
            "duration_ms": self.duration_ms,
        }


def _run_with_timeout(
    source: str,
    timeout: float,
) -> tuple[BasePicture | None, Exception | None, float]:
    start = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(parse_source_text, source)
            try:
                result = future.result(timeout=timeout)
                duration = (time.perf_counter() - start) * 1000
                return result, None, duration
            except concurrent.futures.TimeoutError:
                duration = (time.perf_counter() - start) * 1000
                return None, TimeoutError(f"Parse timed out after {timeout}s"), duration
    except Exception as exc:  # noqa: BLE001
        duration = (time.perf_counter() - start) * 1000
        return None, exc, duration


def fuzz_parse_text(
    source: str,
    input_desc: str | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> FuzzResult:
    if input_desc is None:
        input_desc = f"text({len(source)} chars)"
    result, error, duration_ms = _run_with_timeout(source, timeout)
    return FuzzResult(
        input_desc=input_desc,
        success=error is None and isinstance(result, BasePicture),
        result=result if isinstance(result, BasePicture) else None,
        error=error,
        duration_ms=duration_ms,
    )


def collect_corpus_inputs(
    corpus_dir: pathlib.Path | None = None,
    *,
    include_valid: bool = True,
    include_invalid: bool = True,
    include_edge_cases: bool = True,
    include_semantic: bool = False,
    max_files: int | None = None,
) -> list[tuple[str, str]]:
    if corpus_dir is None:
        corpus_dir = CORPUS_DIR
    subdirs: list[pathlib.Path] = []
    if include_valid:
        subdirs.append(corpus_dir / "valid")
        subdirs.append(corpus_dir / "icf")
    if include_invalid:
        subdirs.append(corpus_dir / "invalid")
    if include_edge_cases:
        subdirs.append(corpus_dir / "edge_cases")
    if include_semantic:
        subdirs.append(corpus_dir / "semantic")

    inputs: list[tuple[str, str]] = []
    for subdir in subdirs:
        if not subdir.exists():
            continue
        files: list[pathlib.Path] = sorted(subdir.glob("*.s"))
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                inputs.append((str(file_path), content))
            except OSError:
                continue
    if max_files is not None:
        inputs = inputs[:max_files]
    return inputs


def run_corpus_regression(
    corpus_dir: pathlib.Path | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_files: int | None = None,
) -> list[FuzzResult]:
    inputs = collect_corpus_inputs(corpus_dir, max_files=max_files)
    results: list[FuzzResult] = []
    for file_path, content in inputs:
        desc = pathlib.Path(file_path).name
        result = fuzz_parse_text(content, input_desc=f"corpus:{desc}", timeout=timeout)
        results.append(result)
    return results


def generate_random_text(
    length: int = 100,
    *,
    seed: int | None = None,
) -> str:
    rng = random.Random(seed) if seed is not None else random  # nosec B311
    tokens = [
        "PROGRAM",
        "ENDPROGRAM",
        "ModuleTypeDef",
        "SubModule",
        "EndModuletype",
        "SingleModule",
        "EndModule",
        "EQUATION:",
        "ENDEQUATION",
        "SEQUENCE:",
        "ENDSEQUENCE",
        "Step",
        "Transition",
        "VAR",
        "END_VAR",
        ":=",
        ";",
        ",",
        "(",
        ")",
        ".",
        "TRUE",
        "FALSE",
        "AND",
        "OR",
        "NOT",
        "IF",
        "THEN",
        "ELSE",
        "END_IF",
        "123",
        "3.14",
        "'hello'",
        '"world"',
        "x",
        "y",
        "z",
        "Result",
        "State",
        "\n",
        " ",
        "\t",
    ]
    result: list[str] = []
    current_length = 0
    while current_length < length:
        remaining_length = length - current_length
        fitting_tokens = [token for token in tokens if len(token) <= remaining_length]
        if not fitting_tokens:
            break
        # Fuzz harness intentionally uses non-cryptographic randomness.
        token = rng.choice(fitting_tokens)  # nosec B311
        result.append(token)
        current_length += len(token)
    return "".join(result)


def run_random_fuzz(
    rounds: int = 100,
    *,
    text_length: int = 100,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    seed: int | None = None,
) -> list[FuzzResult]:
    if seed is not None:
        random.seed(seed)
    results: list[FuzzResult] = []
    for i in range(rounds):
        source = generate_random_text(text_length, seed=seed + i if seed else None)
        result = fuzz_parse_text(
            source,
            input_desc=f"random:{i}({text_length} chars)",
            timeout=timeout,
        )
        results.append(result)
    return results


def assert_no_crashes(results: list[FuzzResult]) -> None:
    crashes = [r for r in results if r.error and not _is_expected_parse_error(r.error)]
    if crashes:
        messages = "\n".join(f"  - {r.input_desc}: {type(r.error).__name__}: {r.error}" for r in crashes[:5])
        raise AssertionError(f"{len(crashes)} crash(es) detected:\n{messages}")


def assert_no_timeouts(results: list[FuzzResult]) -> None:
    timeouts = [r for r in results if isinstance(r.error, TimeoutError)]
    if timeouts:
        messages = "\n".join(f"  - {r.input_desc}: {r.duration_ms:.1f}ms" for r in timeouts[:5])
        raise AssertionError(f"{len(timeouts)} timeout(s) detected:\n{messages}")


def _is_expected_parse_error(error: Exception) -> bool:
    from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken  # noqa: PLC0415

    return isinstance(
        error, UnexpectedInput | UnexpectedCharacters | UnexpectedEOF | UnexpectedToken | ValueError | SyntaxError
    )


def is_expected_parse_error(error: Exception) -> bool:
    return _is_expected_parse_error(error)


class TimeoutError(Exception):
    pass
