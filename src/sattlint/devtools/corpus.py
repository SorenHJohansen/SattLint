"""Executable corpus runner and evaluation helpers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from sattlint import engine as engine_module
from sattlint.analyzers.sattline_semantics import SattLineSemanticsReport, analyze_sattline_semantics
from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.devtools._corpus_artifacts import (
    CorpusExecutionArtifacts,
    as_json_array,
    as_json_object,
    build_execution_error_artifacts,
    coerce_artifact_fragments,
    coerce_optional_str,
    collect_artifact_fragment_failures,
    load_json_object,
    write_case_artifacts,
    write_json,
)
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.repo_paths import repo_root_from

_write_json = write_json

REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "analysis"
DEFAULT_MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "manifests"
DEFAULT_CASES_DIRNAME = "corpus_cases"
DEFAULT_FINDINGS_FILENAME = "findings.json"
DEFAULT_STATUS_FILENAME = "status.json"
DEFAULT_SUMMARY_FILENAME = "summary.json"
CORPUS_RESULTS_FILENAME = "corpus_results.json"
CORPUS_RESULTS_SCHEMA_KIND = "sattlint.corpus_results"
CORPUS_RESULTS_SCHEMA_VERSION = 1
_CASE_ID_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | dict[str, JsonValue] | list[JsonValue]
type JsonObject = dict[str, JsonValue]


def _json_object_factory() -> JsonObject:
    return {}


@dataclass(frozen=True, slots=True)
class CorpusExpectation:
    expected_finding_ids: tuple[str, ...] = ()
    forbidden_finding_ids: tuple[str, ...] = ()
    artifact_fragments: JsonObject = field(default_factory=_json_object_factory)


@dataclass(frozen=True, slots=True)
class CorpusCaseManifest:
    case_id: str
    target_file: str
    mode: str
    expectation: CorpusExpectation
    required_artifacts: tuple[str, ...] = ()
    workspace_root: str | None = None
    program_dir: str | None = None
    abb_lib_dir: str | None = None
    other_lib_dirs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CorpusEvaluation:
    case_id: str
    passed: bool
    missing_finding_ids: tuple[str, ...] = ()
    unexpected_finding_ids: tuple[str, ...] = ()
    artifact_fragment_failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "missing_finding_ids": list(self.missing_finding_ids),
            "unexpected_finding_ids": list(self.unexpected_finding_ids),
            "artifact_fragment_failures": list(self.artifact_fragment_failures),
        }


@dataclass(frozen=True, slots=True)
class CorpusRunResult:
    manifest: CorpusCaseManifest
    evaluation: CorpusEvaluation
    findings_report: str
    findings_schema: dict[str, Any] | None = None
    missing_artifacts: tuple[str, ...] = ()
    artifact_dir: str | None = None
    execution_error: str | None = None

    @property
    def passed(self) -> bool:
        return self.evaluation.passed and not self.missing_artifacts and self.execution_error is None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "case_id": self.manifest.case_id,
            "target_file": self.manifest.target_file,
            "mode": self.manifest.mode,
            "findings_report": self.findings_report,
            "passed": self.passed,
            "missing_artifacts": list(self.missing_artifacts),
            "evaluation": self.evaluation.to_dict(),
        }
        if self.findings_schema is not None:
            payload["findings_schema"] = self.findings_schema
        if self.artifact_dir is not None:
            payload["artifact_dir"] = self.artifact_dir
        if self.execution_error is not None:
            payload["execution_error"] = self.execution_error
        return payload


@dataclass(frozen=True, slots=True)
class CorpusSuiteResult:
    cases: tuple[CorpusRunResult, ...]
    output_dir: str
    manifest_root: str | None = None

    @property
    def passed(self) -> bool:
        return all(case.passed for case in self.cases)

    def to_dict(self) -> dict[str, Any]:
        findings_schema = next(
            (case.findings_schema for case in self.cases if case.findings_schema is not None),
            None,
        )
        failed_cases = [case.manifest.case_id for case in self.cases if not case.passed]
        execution_error_count = sum(1 for case in self.cases if case.execution_error is not None)
        missing_artifact_case_count = sum(1 for case in self.cases if case.missing_artifacts)
        payload = {
            "kind": CORPUS_RESULTS_SCHEMA_KIND,
            "schema_version": CORPUS_RESULTS_SCHEMA_VERSION,
            "entry_report": CORPUS_RESULTS_FILENAME,
            "output_dir": self.output_dir,
            "manifest_root": self.manifest_root,
            "summary": {
                "case_count": len(self.cases),
                "passed_count": sum(1 for case in self.cases if case.passed),
                "failed_count": len(failed_cases),
                "execution_error_count": execution_error_count,
                "missing_artifact_case_count": missing_artifact_case_count,
            },
            "failed_case_ids": failed_cases,
            "cases": [case.to_dict() for case in self.cases],
        }
        if findings_schema is not None:
            payload["findings_schema"] = findings_schema
        return payload


def load_corpus_manifest(path: Path) -> CorpusCaseManifest:
    payload = load_json_object(path)
    expectation_payload = as_json_object(payload.get("expectation")) or {}
    return CorpusCaseManifest(
        case_id=str(payload["case_id"]),
        target_file=str(payload["target_file"]),
        mode=str(payload.get("mode") or "workspace"),
        expectation=CorpusExpectation(
            expected_finding_ids=tuple(
                str(item) for item in as_json_array(expectation_payload.get("expected_finding_ids"))
            ),
            forbidden_finding_ids=tuple(
                str(item) for item in as_json_array(expectation_payload.get("forbidden_finding_ids"))
            ),
            artifact_fragments=cast(
                JsonObject, coerce_artifact_fragments(expectation_payload.get("artifact_fragments"))
            ),
        ),
        required_artifacts=tuple(str(item) for item in as_json_array(payload.get("required_artifacts"))),
        workspace_root=coerce_optional_str(payload.get("workspace_root")),
        program_dir=coerce_optional_str(payload.get("program_dir")),
        abb_lib_dir=coerce_optional_str(payload.get("abb_lib_dir")),
        other_lib_dirs=tuple(str(item) for item in as_json_array(payload.get("other_lib_dirs"))),
    )


def discover_corpus_manifests(manifest_dir: Path) -> tuple[Path, ...]:
    if not manifest_dir.exists():
        return ()
    return tuple(sorted(path for path in manifest_dir.rglob("*.json") if path.is_file()))


def evaluate_finding_ids(
    manifest: CorpusCaseManifest,
    actual_finding_ids: list[str] | tuple[str, ...],
) -> CorpusEvaluation:
    actual = set(actual_finding_ids)
    expected = set(manifest.expectation.expected_finding_ids)
    forbidden = set(manifest.expectation.forbidden_finding_ids)

    missing = tuple(sorted(expected - actual))
    unexpected = tuple(sorted(actual & forbidden))

    return CorpusEvaluation(
        case_id=manifest.case_id,
        passed=(not missing and not unexpected),
        missing_finding_ids=missing,
        unexpected_finding_ids=unexpected,
    )


def execute_corpus_case(
    manifest_path: Path,
    artifact_dir: Path,
    *,
    repo_root: Path = REPO_ROOT,
    manifest: CorpusCaseManifest | None = None,
) -> CorpusRunResult:
    manifest = load_corpus_manifest(manifest_path) if manifest is None else manifest
    target_path = _resolve_manifest_target_path(manifest_path, manifest.target_file, repo_root)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    execution_error: str | None = None
    try:
        if manifest.mode.casefold() == "strict":
            artifacts = _execute_strict_case(
                manifest,
                target_path=target_path,
                repo_root=repo_root,
            )
        elif manifest.mode.casefold() == "workspace":
            artifacts = _execute_workspace_case(
                manifest,
                manifest_path=manifest_path,
                target_path=target_path,
                repo_root=repo_root,
            )
        else:
            raise ValueError(f"Unsupported corpus mode: {manifest.mode}")
    except Exception as exc:  # noqa: BLE001
        execution_error = str(exc)
        artifacts = build_execution_error_artifacts(
            case_id=manifest.case_id,
            mode=manifest.mode,
            target_path=target_path,
            repo_root=repo_root,
            error_message=execution_error,
        )

    write_case_artifacts(artifact_dir, artifacts)
    try:
        evaluated = run_corpus_case(
            manifest_path,
            artifact_dir,
            findings_filename=DEFAULT_FINDINGS_FILENAME,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        error_message = f"Failed to evaluate corpus case {manifest.case_id}: {exc}"
        execution_error = error_message if execution_error is None else f"{execution_error}; {error_message}"
        error_artifacts = build_execution_error_artifacts(
            case_id=manifest.case_id,
            mode=manifest.mode,
            target_path=target_path,
            repo_root=repo_root,
            error_message=error_message,
        )
        write_case_artifacts(artifact_dir, error_artifacts)
        return CorpusRunResult(
            manifest=manifest,
            evaluation=CorpusEvaluation(case_id=manifest.case_id, passed=True),
            findings_report=DEFAULT_FINDINGS_FILENAME,
            findings_schema=error_artifacts.findings.schema_metadata,
            artifact_dir=sanitize_path_for_report(artifact_dir, repo_root=repo_root),
            execution_error=execution_error,
        )
    return CorpusRunResult(
        manifest=evaluated.manifest,
        evaluation=evaluated.evaluation,
        findings_report=evaluated.findings_report,
        findings_schema=evaluated.findings_schema,
        missing_artifacts=evaluated.missing_artifacts,
        artifact_dir=sanitize_path_for_report(artifact_dir, repo_root=repo_root),
        execution_error=execution_error,
    )


def run_corpus_suite(
    output_dir: Path,
    *,
    manifest_dir: Path | None = None,
    manifest_paths: Iterable[Path] | None = None,
    repo_root: Path = REPO_ROOT,
    write_results: bool = True,
) -> CorpusSuiteResult:
    resolved_manifest_dir = manifest_dir.resolve() if manifest_dir is not None else None
    selected_manifest_paths = tuple(
        sorted(
            path.resolve()
            for path in (manifest_paths or discover_corpus_manifests(resolved_manifest_dir or DEFAULT_MANIFEST_DIR))
        )
    )

    cases_dir = output_dir / DEFAULT_CASES_DIRNAME
    results: list[CorpusRunResult] = []
    for manifest_path in selected_manifest_paths:
        try:
            manifest = load_corpus_manifest(manifest_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            results.append(
                _build_manifest_load_failure_result(
                    manifest_path,
                    artifact_dir=cases_dir / _slug_case_id(manifest_path.stem),
                    repo_root=repo_root,
                    error_message=(
                        "Failed to load corpus manifest "
                        f"{sanitize_path_for_report(manifest_path, repo_root=repo_root) or manifest_path.as_posix()}: {exc}"
                    ),
                )
            )
            continue
        results.append(
            execute_corpus_case(
                manifest_path,
                cases_dir / _slug_case_id(manifest.case_id),
                repo_root=repo_root,
                manifest=manifest,
            )
        )
    suite = CorpusSuiteResult(
        cases=tuple(results),
        output_dir=sanitize_path_for_report(output_dir, repo_root=repo_root) or output_dir.as_posix(),
        manifest_root=(
            None
            if resolved_manifest_dir is None
            else sanitize_path_for_report(resolved_manifest_dir, repo_root=repo_root)
        ),
    )
    if write_results:
        _write_json(output_dir / CORPUS_RESULTS_FILENAME, suite.to_dict())
    return suite


def run_corpus_case(
    manifest_path: Path,
    artifact_dir: Path,
    *,
    findings_filename: str = DEFAULT_FINDINGS_FILENAME,
) -> CorpusRunResult:
    manifest = load_corpus_manifest(manifest_path)
    findings_path = artifact_dir / findings_filename
    if not findings_path.exists():
        raise FileNotFoundError(f"Corpus findings artifact does not exist: {findings_path}")

    findings_payload = cast(dict[str, Any], json.loads(findings_path.read_text(encoding="utf-8")))
    findings = FindingCollection.from_dict(findings_payload)
    evaluation = evaluate_finding_ids(
        manifest,
        [finding.rule_id or finding.id for finding in findings.findings],
    )
    missing_artifacts = tuple(
        artifact_name for artifact_name in manifest.required_artifacts if not (artifact_dir / artifact_name).exists()
    )
    artifact_fragment_failures = collect_artifact_fragment_failures(
        manifest.expectation.artifact_fragments, artifact_dir
    )
    evaluation = CorpusEvaluation(
        case_id=evaluation.case_id,
        passed=(evaluation.passed and not artifact_fragment_failures),
        missing_finding_ids=evaluation.missing_finding_ids,
        artifact_fragment_failures=artifact_fragment_failures,
    )

    return CorpusRunResult(
        manifest=manifest,
        evaluation=evaluation,
        findings_report=findings_filename,
        findings_schema=findings.schema_metadata,
        missing_artifacts=missing_artifacts,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sattlint-corpus-runner",
        description="Execute corpus manifests and emit corpus_results.json together with per-case artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory that receives corpus_results.json and per-case artifacts.",
    )
    parser.add_argument(
        "--manifest-dir",
        default=str(DEFAULT_MANIFEST_DIR),
        help="Directory that contains corpus manifest JSON files.",
    )
    parser.add_argument(
        "--manifest",
        action="append",
        default=[],
        help="Specific manifest path to execute. May be provided multiple times.",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).resolve()
    manifest_dir = Path(args.manifest_dir).resolve() if args.manifest_dir else None
    manifest_paths = tuple(Path(path).resolve() for path in args.manifest)

    suite = run_corpus_suite(
        output_dir,
        manifest_dir=manifest_dir,
        manifest_paths=manifest_paths or None,
        repo_root=REPO_ROOT,
        write_results=False,
    )
    report_path = output_dir / CORPUS_RESULTS_FILENAME
    summary = suite.to_dict()
    output_error: OSError | None = None
    try:
        _write_json(report_path, summary)
    except OSError as exc:
        output_error = exc
    print(
        format_cli_summary(
            {
                "case_count": summary["summary"]["case_count"],
                "failed_count": summary["summary"]["failed_count"],
                "findings_schema": summary.get("findings_schema"),
                "corpus_results_report": sanitize_path_for_report(report_path, repo_root=REPO_ROOT)
                or report_path.as_posix(),
            }
        )
    )
    if output_error is not None:
        print(f"corpus output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if suite.passed else 1


def _print_cli_summary(status_report: dict[str, Any]) -> None:  # pyright: ignore[reportUnusedFunction]
    print(format_cli_summary(status_report))


def _normalize_severity(value: str) -> str:
    normalized = value.casefold()
    if normalized in {"error", "critical", "high"}:
        return "high"
    if normalized in {"warning", "medium"}:
        return "medium"
    return "low"


def _slug_case_id(case_id: str) -> str:
    slug = _CASE_ID_SANITIZER.sub("-", case_id).strip("-.")
    return slug or "case"


def _resolve_manifest_target_path(manifest_path: Path, raw_path: str, repo_root: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    manifest_relative = (manifest_path.parent / candidate).resolve()
    if manifest_relative.exists():
        return manifest_relative
    return (repo_root / candidate).resolve()


def _resolve_optional_directory(
    raw_path: str | None,
    *,
    manifest_path: Path,
    repo_root: Path,
) -> Path | None:
    if not raw_path:
        return None
    return _resolve_manifest_target_path(manifest_path, raw_path, repo_root)


def _infer_code_mode(target_path: Path) -> engine_module.CodeMode:
    if target_path.suffix.casefold() in {".x", ".z"}:
        return engine_module.CodeMode.OFFICIAL
    return engine_module.CodeMode.DRAFT


def format_cli_summary(status_report: dict[str, Any]) -> str:
    lines: list[str] = []
    findings_schema = status_report.get("findings_schema")
    if findings_schema:
        lines.append(
            f"Findings schema: {findings_schema.get('kind', 'unknown')} v{findings_schema.get('schema_version', '?')}"
        )
    lines.append(f"Corpus cases: {status_report['case_count']}")
    lines.append(f"Failed cases: {status_report['failed_count']}")
    lines.append(f"Corpus results: {status_report['corpus_results_report']}")
    return "\n".join(lines)


def _execute_strict_case(
    manifest: CorpusCaseManifest,
    *,
    target_path: Path,
    repo_root: Path,
) -> CorpusExecutionArtifacts:
    result = engine_module.validate_single_file_syntax(target_path)
    findings = _build_strict_finding_collection(result, repo_root=repo_root)
    sanitized_target = sanitize_path_for_report(target_path, repo_root=repo_root)
    status = {
        "kind": "sattlint.corpus.case_status",
        "case_id": manifest.case_id,
        "mode": manifest.mode,
        "execution_status": "ok",
        "target_file": sanitized_target,
        "validation_ok": result.ok,
        "stage": result.stage,
        "finding_count": len(findings.findings),
        "findings_schema": findings.schema_metadata,
    }
    summary = {
        "kind": "sattlint.corpus.case_summary",
        "case_id": manifest.case_id,
        "mode": manifest.mode,
        "target_file": sanitized_target,
        "stage": result.stage,
        "validation_ok": result.ok,
        "message": result.message,
        "finding_count": len(findings.findings),
        "findings_schema": findings.schema_metadata,
    }
    return CorpusExecutionArtifacts(findings=findings, status=status, summary=summary)


def _build_strict_finding_collection(
    result: engine_module.SyntaxValidationResult,
    *,
    repo_root: Path,
) -> FindingCollection:
    if result.ok:
        return FindingCollection(())
    rule_id = f"syntax.{result.stage}"
    path = sanitize_path_for_report(result.file_path, repo_root=repo_root)
    command = f"sattlint syntax-check {path}" if path else None
    finding = FindingRecord(
        id=rule_id,
        rule_id=rule_id,
        category="syntax",
        severity="high",
        confidence="high",
        message=result.message or "SattLine syntax validation failed.",
        source="corpus-runner",
        analyzer="syntax-check",
        artifact="findings",
        location=FindingLocation(
            path=path,
            line=result.line,
            column=result.column,
        ),
        owner_surface="syntax-check",
        minimal_reproducer=command,
        suggested_next_command=command,
        data={
            "stage": result.stage,
        },
    )
    return FindingCollection((finding,))


def _corpus_analysis_context_config(
    *,
    target_path: Path,
    workspace_root: Path,
    program_dir: Path,
    abb_lib_dir: Path,
    other_lib_dirs: Iterable[Path],
    debug: bool,
) -> dict[str, object]:
    mode = _infer_code_mode(target_path)
    return {
        "abb_lib_dir": str(abb_lib_dir),
        "analyzed_targets": [target_path.stem],
        "debug": debug,
        "mode": getattr(mode, "value", str(mode)),
        "other_lib_dirs": [str(path) for path in other_lib_dirs],
        "program_dir": str(program_dir),
        "use_cache": False,
        "workspace_root": str(workspace_root),
    }


def _execute_workspace_case(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> CorpusExecutionArtifacts:
    workspace_root = (
        _resolve_optional_directory(
            manifest.workspace_root,
            manifest_path=manifest_path,
            repo_root=repo_root,
        )
        or repo_root
    )
    program_dir = (
        _resolve_optional_directory(
            manifest.program_dir,
            manifest_path=manifest_path,
            repo_root=repo_root,
        )
        or target_path.parent
    )
    abb_lib_dir = (
        _resolve_optional_directory(
            manifest.abb_lib_dir,
            manifest_path=manifest_path,
            repo_root=repo_root,
        )
        or program_dir
    )
    other_lib_dirs = [
        _resolve_manifest_target_path(manifest_path, raw_path, repo_root) for raw_path in manifest.other_lib_dirs
    ]

    loader = engine_module.SattLineProjectLoader(
        program_dir=program_dir,
        other_lib_dirs=other_lib_dirs,
        abb_lib_dir=abb_lib_dir,
        mode=_infer_code_mode(target_path),
        scan_root_only=False,
        debug=False,
    )
    graph = loader.resolve(target_path.stem, strict=False)
    root_bp = graph.ast_by_name.get(target_path.stem)
    if root_bp is None:
        raise RuntimeError(
            f"Target {target_path.stem!r} was not parsed. "
            f"Resolved targets: {sorted(graph.ast_by_name)}; missing: {graph.missing}"
        )

    unavailable_libraries = graph.unavailable_libraries
    project_bp = engine_module.merge_project_basepicture(root_bp, graph)
    semantic_report = analyze_sattline_semantics(
        project_bp,
        debug=False,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=not engine_module.is_within_directory(target_path, program_dir),
        config=_corpus_analysis_context_config(
            target_path=target_path,
            workspace_root=workspace_root,
            program_dir=program_dir,
            abb_lib_dir=abb_lib_dir,
            other_lib_dirs=other_lib_dirs,
            debug=False,
        ),
    )
    findings = _build_semantic_finding_collection(
        semantic_report,
        target_path=target_path,
        repo_root=repo_root,
    )
    rule_counts = Counter(issue.rule.id for issue in semantic_report.issues)
    sanitized_target = sanitize_path_for_report(target_path, repo_root=repo_root)
    status = {
        "kind": "sattlint.corpus.case_status",
        "case_id": manifest.case_id,
        "mode": manifest.mode,
        "execution_status": "ok",
        "target_file": sanitized_target,
        "resolved_target_count": len(graph.ast_by_name),
        "warning_count": len(graph.warnings),
        "missing_dependency_count": len(graph.missing),
        "finding_count": len(findings.findings),
        "findings_schema": findings.schema_metadata,
        "unavailable_libraries": sorted(unavailable_libraries),
    }
    summary = {
        "kind": "sattlint.corpus.case_summary",
        "case_id": manifest.case_id,
        "mode": manifest.mode,
        "target_file": sanitized_target,
        "finding_count": len(findings.findings),
        "findings_schema": findings.schema_metadata,
        "rule_counts": dict(sorted(rule_counts.items())),
        "resolved_targets": sorted(graph.ast_by_name),
        "missing_dependencies": list(graph.missing),
        "warnings": list(graph.warnings),
    }
    return CorpusExecutionArtifacts(findings=findings, status=status, summary=summary)


def _build_semantic_finding_collection(
    report: SattLineSemanticsReport,
    *,
    target_path: Path,
    repo_root: Path,
) -> FindingCollection:
    target_display_path = sanitize_path_for_report(target_path, repo_root=repo_root)
    records = tuple(
        FindingRecord(
            id=issue.rule.id,
            rule_id=issue.rule.id,
            category=issue.rule.category,
            severity=_normalize_severity(issue.rule.severity),
            confidence="high",
            message=issue.message,
            source=issue.rule.source,
            analyzer="sattline-semantics",
            artifact="findings",
            location=FindingLocation(
                path=target_display_path,
                module_path=tuple(issue.module_path or ()),
            ),
            detail=issue.rule.explanation or issue.rule.description,
            suggestion=issue.rule.suggestion,
            data={
                "applies_to": issue.rule.applies_to,
                "source_kind": issue.source_kind,
                **(issue.data or {}),
            },
        )
        for issue in report.issues
    )
    return FindingCollection(records)


def _build_manifest_load_failure_result(
    manifest_path: Path,
    *,
    artifact_dir: Path,
    repo_root: Path,
    error_message: str,
) -> CorpusRunResult:
    manifest_display_path = sanitize_path_for_report(manifest_path, repo_root=repo_root) or manifest_path.as_posix()
    manifest = CorpusCaseManifest(
        case_id=manifest_path.stem,
        target_file=manifest_display_path,
        mode="manifest",
        expectation=CorpusExpectation(),
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifacts = build_execution_error_artifacts(
        case_id=manifest.case_id,
        mode=manifest.mode,
        target_path=manifest_path,
        repo_root=repo_root,
        error_message=error_message,
    )
    write_case_artifacts(artifact_dir, artifacts)
    return CorpusRunResult(
        manifest=manifest,
        evaluation=CorpusEvaluation(case_id=manifest.case_id, passed=True),
        findings_report=DEFAULT_FINDINGS_FILENAME,
        findings_schema=artifacts.findings.schema_metadata,
        artifact_dir=sanitize_path_for_report(artifact_dir, repo_root=repo_root),
        execution_error=error_message,
    )


__all__ = [
    "CORPUS_RESULTS_FILENAME",
    "CORPUS_RESULTS_SCHEMA_KIND",
    "CORPUS_RESULTS_SCHEMA_VERSION",
    "CorpusCaseManifest",
    "CorpusEvaluation",
    "CorpusExpectation",
    "CorpusRunResult",
    "CorpusSuiteResult",
    "discover_corpus_manifests",
    "evaluate_finding_ids",
    "execute_corpus_case",
    "load_corpus_manifest",
    "main",
    "run_corpus_case",
    "run_corpus_suite",
]
