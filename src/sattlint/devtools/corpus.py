"""Executable corpus runner and evaluation helpers."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser import parse_source_file
from sattline_parser.models.ast_model import BasePicture
from sattlint import cli_output
from sattlint import engine as engine_module
from sattlint.analysis_catalog import canonicalize_analyzer_key, get_default_analyzer_catalog
from sattlint.analyzers._sattline_semantic_issue_mapping import (
    describe_variable_issue,
    map_framework_issues,
    map_spec_issues,
    map_variable_issues,
    variable_issue_data,
)
from sattlint.analyzers._sattline_semantic_rules import FRAMEWORK_RULES_BY_KIND
from sattlint.analyzers.framework import Issue, build_analysis_context
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
from sattlint.models import VariableIssue
from sattlint.models._variable_issues import materialize_variable_issue_metadata
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.repo_paths import repo_root_from

from .artifact_registry import CORPUS_RESULTS_FILENAME, CORPUS_RESULTS_SCHEMA_KIND, CORPUS_RESULTS_SCHEMA_VERSION

_write_json = write_json

REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "analysis"
DEFAULT_MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "manifests"
DEFAULT_CASES_DIRNAME = "corpus_cases"
DEFAULT_FINDINGS_FILENAME = "findings.json"
_CASE_ID_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")
_ANALYZER_MODE_PREFIX = "analyzer-"

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
    load_strategy: str = "workspace"
    required_artifacts: tuple[str, ...] = ()
    workspace_root: str | None = None
    program_dir: str | None = None
    abb_lib_dir: str | None = None
    other_lib_dirs: tuple[str, ...] = ()
    analysis_config: JsonObject = field(default_factory=_json_object_factory)


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
class _LoadedCorpusWorkspace:
    workspace_root: Path
    program_dir: Path
    abb_lib_dir: Path
    other_lib_dirs: tuple[Path, ...]
    graph: Any
    project_bp: Any
    target_is_library: bool
    config: dict[str, object]


@dataclass(frozen=True, slots=True)
class _ResolvedCorpusAnalyzer:
    key: str
    spec: Any
    specs_by_key: dict[str, Any]
    rule_metadata_by_id: dict[str, object]


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
        load_strategy=str(payload.get("load_strategy") or "workspace"),
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
        analysis_config=cast(JsonObject, as_json_object(payload.get("analysis_config")) or {}),
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
    normalized_mode = manifest.mode.casefold()
    try:
        if normalized_mode == "strict":
            artifacts = _execute_strict_case(
                manifest,
                target_path=target_path,
                repo_root=repo_root,
            )
        elif normalized_mode == "workspace":
            artifacts = _execute_workspace_case(
                manifest,
                manifest_path=manifest_path,
                target_path=target_path,
                repo_root=repo_root,
            )
        elif normalized_mode.startswith(_ANALYZER_MODE_PREFIX):
            artifacts = _execute_analyzer_case(
                manifest,
                manifest_path=manifest_path,
                target_path=target_path,
                repo_root=repo_root,
                analyzer_key=manifest.mode[len(_ANALYZER_MODE_PREFIX) :],
            )
        else:
            raise ValueError(f"Unsupported corpus mode: {manifest.mode}")
    except (OSError, RuntimeError, ValueError) as exc:
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
    cli_output.add_output_format_argument(
        parser,
        help_text="Output format for stdout summary.",
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
    output_format = cli_output.resolve_output_format(args)

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
    status_report = {
        "case_count": summary["summary"]["case_count"],
        "failed_count": summary["summary"]["failed_count"],
        "findings_schema": summary.get("findings_schema"),
        "corpus_results_report": sanitize_path_for_report(report_path, repo_root=REPO_ROOT) or report_path.as_posix(),
    }
    if output_error is not None:
        status_report["output_error"] = str(output_error)
    cli_output.emit_text_or_json(
        text=format_cli_summary(status_report),
        json_payload=status_report,
        output_format=output_format,
        emit_text_fn=print,
    )
    if output_error is not None:
        print(f"corpus output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if suite.passed else 1


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


def _resolve_corpus_directories(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> tuple[Path, Path, Path, tuple[Path, ...]]:
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
    other_lib_dirs = tuple(
        _resolve_manifest_target_path(manifest_path, raw_path, repo_root) for raw_path in manifest.other_lib_dirs
    )
    return workspace_root, program_dir, abb_lib_dir, other_lib_dirs


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
    analysis_config: Mapping[str, JsonValue] | None = None,
) -> dict[str, object]:
    mode = _infer_code_mode(target_path)
    base_config: JsonObject = {
        "abb_lib_dir": str(abb_lib_dir),
        "analyzed_targets": [target_path.stem],
        "debug": debug,
        "mode": getattr(mode, "value", str(mode)),
        "other_lib_dirs": [str(path) for path in other_lib_dirs],
        "program_dir": str(program_dir),
        "use_cache": False,
        "workspace_root": str(workspace_root),
    }
    if analysis_config:
        return cast(dict[str, object], _merge_json_objects(base_config, analysis_config))
    return cast(dict[str, object], base_config)


def _merge_json_objects(
    base: JsonObject,
    overrides: Mapping[str, JsonValue],
) -> JsonObject:
    merged = dict(base)
    for raw_key, override_value in overrides.items():
        key = str(raw_key)
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, Mapping):
            merged[key] = _merge_json_objects(base_value, cast(Mapping[str, JsonValue], override_value))
            continue
        merged[key] = override_value
    return merged


def _load_corpus_workspace(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> _LoadedCorpusWorkspace:
    workspace_root, program_dir, abb_lib_dir, other_lib_dirs = _resolve_corpus_directories(
        manifest,
        manifest_path=manifest_path,
        target_path=target_path,
        repo_root=repo_root,
    )

    _loader, root_bp, graph = engine_module.load_project_graph(
        {
            "program_dir": program_dir,
            "other_lib_dirs": other_lib_dirs,
            "ABB_lib_dir": abb_lib_dir,
            "mode": _infer_code_mode(target_path),
            "scan_root_only": False,
            "debug": False,
        },
        target_path.stem,
        use_file_ast_cache=True,
        strict=False,
    )
    if root_bp is None:
        raise RuntimeError(
            f"Target {target_path.stem!r} was not parsed. "
            f"Resolved targets: {sorted(graph.ast_by_name)}; missing: {graph.missing}"
        )

    project_bp = engine_module.merge_project_basepicture(root_bp, graph)
    target_is_library = not engine_module.is_within_directory(target_path, program_dir)
    return _LoadedCorpusWorkspace(
        workspace_root=workspace_root,
        program_dir=program_dir,
        abb_lib_dir=abb_lib_dir,
        other_lib_dirs=other_lib_dirs,
        graph=graph,
        project_bp=project_bp,
        target_is_library=target_is_library,
        config=_corpus_analysis_context_config(
            target_path=target_path,
            workspace_root=workspace_root,
            program_dir=program_dir,
            abb_lib_dir=abb_lib_dir,
            other_lib_dirs=other_lib_dirs,
            debug=False,
            analysis_config=manifest.analysis_config,
        ),
    )


def _load_corpus_direct_parse_target(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> _LoadedCorpusWorkspace:
    workspace_root, program_dir, abb_lib_dir, other_lib_dirs = _resolve_corpus_directories(
        manifest,
        manifest_path=manifest_path,
        target_path=target_path,
        repo_root=repo_root,
    )
    base_picture = parse_source_file(target_path)
    graph = SimpleNamespace(
        ast_by_name={target_path.stem: base_picture},
        warnings=[],
        missing=[],
        unavailable_libraries=set(),
    )
    target_is_library = not engine_module.is_within_directory(target_path, program_dir)
    return _LoadedCorpusWorkspace(
        workspace_root=workspace_root,
        program_dir=program_dir,
        abb_lib_dir=abb_lib_dir,
        other_lib_dirs=other_lib_dirs,
        graph=graph,
        project_bp=base_picture,
        target_is_library=target_is_library,
        config=_corpus_analysis_context_config(
            target_path=target_path,
            workspace_root=workspace_root,
            program_dir=program_dir,
            abb_lib_dir=abb_lib_dir,
            other_lib_dirs=other_lib_dirs,
            debug=False,
            analysis_config=manifest.analysis_config,
        ),
    )


def _load_corpus_python_factory_target(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> _LoadedCorpusWorkspace:
    workspace_root, program_dir, abb_lib_dir, other_lib_dirs = _resolve_corpus_directories(
        manifest,
        manifest_path=manifest_path,
        target_path=target_path,
        repo_root=repo_root,
    )

    spec = importlib.util.spec_from_file_location(f"sattlint_corpus_{target_path.stem}", target_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load corpus Python factory from {target_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    builder = getattr(module, "build_basepicture", None)
    if not callable(builder):
        raise RuntimeError(f"Corpus Python factory {target_path} must define a callable build_basepicture().")

    base_picture = builder()
    if not isinstance(base_picture, BasePicture):
        raise RuntimeError(
            f"Corpus Python factory {target_path} returned {type(base_picture).__name__}, expected BasePicture."
        )

    graph = SimpleNamespace(
        ast_by_name={target_path.stem: base_picture},
        warnings=[],
        missing=[],
        unavailable_libraries=set(),
    )
    target_is_library = not engine_module.is_within_directory(target_path, program_dir)
    return _LoadedCorpusWorkspace(
        workspace_root=workspace_root,
        program_dir=program_dir,
        abb_lib_dir=abb_lib_dir,
        other_lib_dirs=other_lib_dirs,
        graph=graph,
        project_bp=base_picture,
        target_is_library=target_is_library,
        config=_corpus_analysis_context_config(
            target_path=target_path,
            workspace_root=workspace_root,
            program_dir=program_dir,
            abb_lib_dir=abb_lib_dir,
            other_lib_dirs=other_lib_dirs,
            debug=False,
            analysis_config=manifest.analysis_config,
        ),
    )


def _load_corpus_target(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> _LoadedCorpusWorkspace:
    strategy = manifest.load_strategy.casefold()
    if strategy == "workspace":
        return _load_corpus_workspace(
            manifest,
            manifest_path=manifest_path,
            target_path=target_path,
            repo_root=repo_root,
        )
    if strategy == "direct-parse":
        return _load_corpus_direct_parse_target(
            manifest,
            manifest_path=manifest_path,
            target_path=target_path,
            repo_root=repo_root,
        )
    if strategy == "python-factory":
        return _load_corpus_python_factory_target(
            manifest,
            manifest_path=manifest_path,
            target_path=target_path,
            repo_root=repo_root,
        )
    raise ValueError(f"Unsupported corpus load strategy: {manifest.load_strategy}")


def _execute_workspace_case(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
) -> CorpusExecutionArtifacts:
    loaded_workspace = _load_corpus_target(
        manifest,
        manifest_path=manifest_path,
        target_path=target_path,
        repo_root=repo_root,
    )
    unavailable_libraries = loaded_workspace.graph.unavailable_libraries
    semantic_report = analyze_sattline_semantics(
        loaded_workspace.project_bp,
        debug=False,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=loaded_workspace.target_is_library,
        config=loaded_workspace.config,
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
        "resolved_target_count": len(loaded_workspace.graph.ast_by_name),
        "warning_count": len(loaded_workspace.graph.warnings),
        "missing_dependency_count": len(loaded_workspace.graph.missing),
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
        "resolved_targets": sorted(loaded_workspace.graph.ast_by_name),
        "missing_dependencies": list(loaded_workspace.graph.missing),
        "warnings": list(loaded_workspace.graph.warnings),
    }
    return CorpusExecutionArtifacts(findings=findings, status=status, summary=summary)


def _resolve_corpus_analyzer(raw_key: str) -> _ResolvedCorpusAnalyzer:
    stripped_key = raw_key.strip()
    if not stripped_key:
        raise ValueError("Analyzer corpus mode is missing an analyzer key.")

    analyzer_key = canonicalize_analyzer_key(stripped_key)
    catalog = get_default_analyzer_catalog()
    specs_by_key = {analyzer.spec.key.casefold(): analyzer.spec for analyzer in catalog.analyzers}
    spec = specs_by_key.get(analyzer_key)
    if spec is None:
        available = ", ".join(sorted(specs_by_key))
        raise ValueError(f"Unknown analyzer corpus mode: {stripped_key!r}. Available analyzers: {available}")

    return _ResolvedCorpusAnalyzer(
        key=cast(str, getattr(spec, "key", analyzer_key)),
        spec=spec,
        specs_by_key=specs_by_key,
        rule_metadata_by_id={str(getattr(rule, "id", "")): rule for rule in catalog.rules},
    )


def _run_corpus_analyzer(
    spec: Any,
    *,
    context: Any,
    specs_by_key: Mapping[str, Any],
    completed_reports: dict[str, object] | None = None,
    active_keys: set[str] | None = None,
) -> object:
    completed: dict[str, object] = {} if completed_reports is None else completed_reports
    active: set[str] = set() if active_keys is None else active_keys

    spec_key = str(getattr(spec, "key", "") or "")
    canonical_key = spec_key.casefold()
    if canonical_key in completed:
        return completed[canonical_key]
    if canonical_key in active:
        raise RuntimeError(f"Analyzer dependency cycle detected for corpus mode: {spec_key}")

    active.add(canonical_key)
    try:
        for required_key in cast(tuple[str, ...], getattr(spec, "requires", ())):
            required_spec = specs_by_key.get(required_key.casefold())
            if required_spec is None:
                raise RuntimeError(f"Analyzer {spec_key!r} requires unavailable analyzer {required_key!r}.")
            _run_corpus_analyzer(
                required_spec,
                context=context,
                specs_by_key=specs_by_key,
                completed_reports=completed,
                active_keys=active,
            )
        report = spec.run(context)
    finally:
        active.discard(canonical_key)

    completed[canonical_key] = report
    shared_artifacts = getattr(context, "shared_artifacts", None)
    reports_by_analyzer_key = getattr(shared_artifacts, "reports_by_analyzer_key", None)
    if isinstance(reports_by_analyzer_key, dict):
        reports_by_analyzer_key[spec_key] = report
    return report


def _execute_analyzer_case(
    manifest: CorpusCaseManifest,
    *,
    manifest_path: Path,
    target_path: Path,
    repo_root: Path,
    analyzer_key: str,
) -> CorpusExecutionArtifacts:
    resolved_analyzer = _resolve_corpus_analyzer(analyzer_key)
    loaded_workspace = _load_corpus_target(
        manifest,
        manifest_path=manifest_path,
        target_path=target_path,
        repo_root=repo_root,
    )
    context = build_analysis_context(
        loaded_workspace.project_bp,
        graph=loaded_workspace.graph,
        debug=False,
        target_is_library=loaded_workspace.target_is_library,
        config=loaded_workspace.config,
        create_shared_artifacts=True,
    )
    report = _run_corpus_analyzer(
        resolved_analyzer.spec,
        context=context,
        specs_by_key=resolved_analyzer.specs_by_key,
    )
    findings = _build_analyzer_finding_collection(
        report,
        spec=resolved_analyzer.spec,
        analyzer_key=resolved_analyzer.key,
        rule_metadata_by_id=resolved_analyzer.rule_metadata_by_id,
        target_path=target_path,
        repo_root=repo_root,
    )
    rule_counts = Counter(finding.rule_id for finding in findings.findings)
    unavailable_libraries = loaded_workspace.graph.unavailable_libraries
    sanitized_target = sanitize_path_for_report(target_path, repo_root=repo_root)
    status = {
        "kind": "sattlint.corpus.case_status",
        "case_id": manifest.case_id,
        "mode": manifest.mode,
        "execution_status": "ok",
        "target_file": sanitized_target,
        "analyzer_key": resolved_analyzer.key,
        "resolved_target_count": len(loaded_workspace.graph.ast_by_name),
        "warning_count": len(loaded_workspace.graph.warnings),
        "missing_dependency_count": len(loaded_workspace.graph.missing),
        "finding_count": len(findings.findings),
        "findings_schema": findings.schema_metadata,
        "unavailable_libraries": sorted(unavailable_libraries),
    }
    summary = {
        "kind": "sattlint.corpus.case_summary",
        "case_id": manifest.case_id,
        "mode": manifest.mode,
        "target_file": sanitized_target,
        "analyzer_key": resolved_analyzer.key,
        "finding_count": len(findings.findings),
        "findings_schema": findings.schema_metadata,
        "rule_counts": dict(sorted(rule_counts.items())),
        "resolved_targets": sorted(loaded_workspace.graph.ast_by_name),
        "missing_dependencies": list(loaded_workspace.graph.missing),
        "warnings": list(loaded_workspace.graph.warnings),
    }
    return CorpusExecutionArtifacts(findings=findings, status=status, summary=summary)


def _build_analyzer_finding_collection(
    report: object,
    *,
    spec: Any,
    analyzer_key: str,
    rule_metadata_by_id: Mapping[str, object],
    target_path: Path,
    repo_root: Path,
) -> FindingCollection:
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list | tuple):
        raise RuntimeError(f"Analyzer {analyzer_key!r} did not return a list of issues.")

    semantic_issues = _map_analyzer_issues_to_semantic_issues(
        cast(list[object] | tuple[object, ...], issues),
        semantic_mapping_kind=coerce_optional_str(getattr(spec, "semantic_mapping_kind", None)),
    )
    if semantic_issues is not None:
        return _build_semantic_finding_collection_from_issues(
            semantic_issues,
            target_path=target_path,
            repo_root=repo_root,
            analyzer_key=analyzer_key,
            owner_surface="analyzers",
        )

    target_display_path = sanitize_path_for_report(target_path, repo_root=repo_root)
    records = tuple(
        _build_analyzer_finding_record(
            issue,
            analyzer_key=analyzer_key,
            rule_metadata_by_id=rule_metadata_by_id,
            target_display_path=target_display_path,
            repo_root=repo_root,
        )
        for issue in cast(list[object] | tuple[object, ...], issues)
    )
    return FindingCollection(records)


def _map_analyzer_issues_to_semantic_issues(
    issues: list[object] | tuple[object, ...],
    *,
    semantic_mapping_kind: str | None,
) -> list[object] | None:
    if semantic_mapping_kind is None:
        return None

    if semantic_mapping_kind == "variable":
        return list(map_variable_issues(cast(list[VariableIssue], list(issues))))
    if semantic_mapping_kind == "framework":
        return list(map_framework_issues(cast(list[Issue], list(issues)), FRAMEWORK_RULES_BY_KIND))
    if semantic_mapping_kind == "spec":
        return list(map_spec_issues(cast(list[Issue], list(issues))))
    return None


def _build_analyzer_finding_record(
    issue: object,
    *,
    analyzer_key: str,
    rule_metadata_by_id: Mapping[str, object],
    target_display_path: str | None,
    repo_root: Path,
) -> FindingRecord:
    issue_kind = _coerce_issue_kind(issue)
    issue_data = _build_analyzer_issue_data(issue, repo_root=repo_root)
    rule_id = coerce_optional_str(getattr(issue, "rule_id", None)) or issue_kind
    rule_metadata = rule_metadata_by_id.get(rule_id) or rule_metadata_by_id.get(issue_kind)
    variable_metadata = _materialize_variable_issue_metadata(issue)

    message = _build_analyzer_issue_message(issue)
    detail = (
        coerce_optional_str(getattr(issue, "explanation", None))
        or variable_metadata.get("explanation")
        or coerce_optional_str(getattr(rule_metadata, "explanation", None))
        or coerce_optional_str(getattr(rule_metadata, "description", None))
    )
    suggestion = (
        coerce_optional_str(getattr(issue, "suggestion", None))
        or variable_metadata.get("suggestion")
        or coerce_optional_str(getattr(rule_metadata, "suggestion", None))
    )
    severity = _normalize_severity(
        coerce_optional_str(getattr(issue, "severity", None))
        or coerce_optional_str(getattr(rule_metadata, "severity", None))
        or "warning"
    )
    confidence = (
        coerce_optional_str(getattr(issue, "confidence", None))
        or coerce_optional_str(getattr(rule_metadata, "confidence", None))
        or "medium"
    )
    category = (
        coerce_optional_str(getattr(rule_metadata, "category", None))
        or coerce_optional_str(issue_data.get("category"))
        or ("variable" if _is_variable_issue(issue) else issue_kind)
        or analyzer_key
    )
    source = coerce_optional_str(getattr(rule_metadata, "source", None)) or analyzer_key
    issue_data.setdefault("analyzer_key", analyzer_key)
    if issue_kind:
        issue_data.setdefault("source_kind", issue_kind)
    return FindingRecord(
        id=rule_id,
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=confidence,
        message=message,
        source=source,
        analyzer=analyzer_key,
        artifact="findings",
        location=FindingLocation(
            path=_coerce_issue_path(issue_data, target_display_path=target_display_path, repo_root=repo_root),
            line=_coerce_optional_int(issue_data.get("line")) or _coerce_optional_int(issue_data.get("start_line")),
            column=_coerce_optional_int(issue_data.get("column")) or _coerce_optional_int(issue_data.get("start_col")),
            symbol=coerce_optional_str(issue_data.get("symbol")) or coerce_optional_str(issue_data.get("variable")),
            module_path=_coerce_module_path(getattr(issue, "module_path", None) or issue_data.get("module_path")),
        ),
        detail=detail,
        suggestion=suggestion,
        owner_surface=("semantic" if analyzer_key == "sattline-semantics" else "analyzers"),
        data=issue_data,
    )


def _build_analyzer_issue_message(issue: object) -> str:
    message = coerce_optional_str(getattr(issue, "message", None))
    if message:
        return message

    variable_message = _describe_variable_issue(issue)
    if variable_message is not None:
        return variable_message

    return _coerce_issue_kind(issue) or "Analyzer reported an issue."


def _build_analyzer_issue_data(issue: object, *, repo_root: Path) -> dict[str, Any]:
    raw_data = getattr(issue, "data", None)
    if isinstance(raw_data, Mapping):
        return _normalize_issue_data_mapping(cast(Mapping[str, Any], raw_data), repo_root=repo_root)

    if _is_variable_issue(issue):
        return _normalize_issue_data_mapping(variable_issue_data(issue), repo_root=repo_root)

    return {}


def _normalize_issue_data_mapping(raw_data: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for raw_key, value in raw_data.items():
        key = str(raw_key)
        if key.casefold() in {"path", "file"}:
            normalized[key] = _sanitize_issue_path(value, repo_root=repo_root)
            continue
        normalized[key] = _normalize_issue_data_value(value, repo_root=repo_root)
    return normalized


def _normalize_issue_data_value(value: object, *, repo_root: Path) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return cast(JsonValue, value)
    if isinstance(value, Enum):
        return coerce_optional_str(value.value) or str(value)
    if isinstance(value, Path):
        return _sanitize_issue_path(value, repo_root=repo_root) or value.as_posix()
    if isinstance(value, Mapping):
        return cast(JsonValue, _normalize_issue_data_mapping(cast(Mapping[str, Any], value), repo_root=repo_root))
    if isinstance(value, list | tuple | set | frozenset):
        return [
            _normalize_issue_data_value(item, repo_root=repo_root)
            for item in cast(list[object] | tuple[object, ...] | set[object] | frozenset[object], value)
        ]
    return str(value)


def _sanitize_issue_path(value: object, *, repo_root: Path) -> str | None:
    if isinstance(value, Path):
        return sanitize_path_for_report(value, repo_root=repo_root) or value.as_posix()

    raw_value = coerce_optional_str(value)
    if raw_value is None:
        return None
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return sanitize_path_for_report(candidate, repo_root=repo_root) or candidate.as_posix()
    return raw_value


def _coerce_issue_path(
    issue_data: Mapping[str, object],
    *,
    target_display_path: str | None,
    repo_root: Path,
) -> str | None:
    path = _sanitize_issue_path(issue_data.get("path") or issue_data.get("file"), repo_root=repo_root)
    if path:
        return path
    return target_display_path


def _coerce_issue_kind(issue: object) -> str:
    raw_kind = getattr(issue, "kind", None)
    if isinstance(raw_kind, Enum):
        return coerce_optional_str(raw_kind.value) or str(raw_kind)
    return coerce_optional_str(raw_kind) or "unknown"


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _coerce_module_path(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in cast(list[object] | tuple[object, ...], value))
    return (str(value),)


def _is_variable_issue(issue: object) -> bool:
    return isinstance(issue, VariableIssue)


def _describe_variable_issue(issue: object) -> str | None:
    if not _is_variable_issue(issue):
        return None

    return describe_variable_issue(issue)


def _materialize_variable_issue_metadata(issue: object) -> dict[str, str | None]:
    if not _is_variable_issue(issue):
        return {"explanation": None, "suggestion": None}

    metadata = materialize_variable_issue_metadata(issue)
    return {
        "explanation": coerce_optional_str(getattr(metadata, "explanation", None)),
        "suggestion": coerce_optional_str(getattr(metadata, "suggestion", None)),
    }


def _build_semantic_finding_collection(
    report: SattLineSemanticsReport,
    *,
    target_path: Path,
    repo_root: Path,
) -> FindingCollection:
    return _build_semantic_finding_collection_from_issues(
        report.issues,
        target_path=target_path,
        repo_root=repo_root,
        analyzer_key="sattline-semantics",
        owner_surface=None,
    )


def _build_semantic_finding_collection_from_issues(
    issues: Sequence[object],
    *,
    target_path: Path,
    repo_root: Path,
    analyzer_key: str,
    owner_surface: str | None,
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
            analyzer=analyzer_key,
            artifact="findings",
            location=FindingLocation(
                path=target_display_path,
                module_path=tuple(issue.module_path or ()),
            ),
            detail=issue.rule.explanation or issue.rule.description,
            suggestion=issue.rule.suggestion,
            owner_surface=owner_surface,
            data={
                "applies_to": issue.rule.applies_to,
                "source_kind": issue.source_kind,
                **(issue.data or {}),
            },
        )
        for issue in cast(Sequence[Any], issues)
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


if __name__ == "__main__":
    raise SystemExit(main())
