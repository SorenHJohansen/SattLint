"""Registry-backed helpers for writing pipeline artifacts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattlint.devtools.artifact_registry import ArtifactDefinition

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIGEST_MANIFEST_KIND = "sattlint.generated_output_sources"
SOURCE_DIGEST_MANIFEST_SCHEMA_VERSION = 1
SOURCE_DIGEST_MANIFEST_SUFFIX = ".sources.json"


@dataclass(frozen=True, slots=True)
class PipelineArtifactContext:
    payloads: Mapping[str, dict[str, Any] | None]


@dataclass(frozen=True, slots=True)
class PipelineArtifactProducer:
    producer_id: str
    build_payload: Callable[[PipelineArtifactContext], dict[str, Any] | None]


def payload_from_context(key: str) -> Callable[[PipelineArtifactContext], dict[str, Any] | None]:
    def _build_payload(context: PipelineArtifactContext) -> dict[str, Any] | None:
        return context.payloads.get(key)

    return _build_payload


def _build_none_payload(_context: PipelineArtifactContext) -> None:
    return None


def artifact_source_manifest_path(path: Path) -> Path:
    suffix = "".join(path.suffixes)
    if suffix:
        stem = path.name[: -len(suffix)]
        return path.with_name(f"{stem}{SOURCE_DIGEST_MANIFEST_SUFFIX}")
    return path.with_name(f"{path.name}{SOURCE_DIGEST_MANIFEST_SUFFIX}")


def _display_path(path: Path, *, repo_root: Path) -> str:
    resolved = path.resolve()
    for candidate_root in (repo_root.resolve(), REPO_ROOT.resolve()):
        try:
            return resolved.relative_to(candidate_root).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def _resolve_generated_by_source_path(generated_by: str | None) -> Path | None:
    if not generated_by:
        return None
    try:
        spec = importlib.util.find_spec(generated_by)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    if spec is None or spec.origin in {None, "built-in", "frozen"}:
        return None
    origin = spec.origin
    if origin is None:
        return None
    return Path(origin)


def _file_sha1(path: Path) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha1:{digest.hexdigest()}"


def build_source_digest_manifest(
    artifact_path: Path,
    payload: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    source_paths: tuple[str | Path, ...] = (),
) -> dict[str, Any] | None:
    ordered_sources: dict[str, Path] = {}
    for raw_source_path in source_paths:
        source_path = Path(raw_source_path)
        resolved_source_path = (
            source_path.resolve() if source_path.is_absolute() else (repo_root / source_path).resolve()
        )
        ordered_sources[_display_path(resolved_source_path, repo_root=repo_root)] = resolved_source_path

    generated_by_source = _resolve_generated_by_source_path(payload.get("generated_by"))
    if generated_by_source is not None:
        ordered_sources.setdefault(
            _display_path(generated_by_source, repo_root=repo_root),
            generated_by_source,
        )

    if not ordered_sources:
        return None

    artifact_content = json.dumps(payload, indent=2, sort_keys=True)
    source_entries: list[dict[str, Any]] = []
    for display_path, resolved_source_path in ordered_sources.items():
        exists = resolved_source_path.exists()
        source_entries.append(
            {
                "path": display_path,
                "exists": exists,
                "digest": _file_sha1(resolved_source_path) if exists and resolved_source_path.is_file() else None,
            }
        )

    return {
        "kind": SOURCE_DIGEST_MANIFEST_KIND,
        "schema_version": SOURCE_DIGEST_MANIFEST_SCHEMA_VERSION,
        "artifact_file": _display_path(artifact_path, repo_root=repo_root),
        "artifact_kind": payload.get("kind"),
        "artifact_schema_version": payload.get("schema_version"),
        "generated_by": payload.get("generated_by"),
        "artifact_digest": f"sha1:{hashlib.sha1(artifact_content.encode('utf-8'), usedforsecurity=False).hexdigest()}",
        "source_count": len(source_entries),
        "sources": source_entries,
    }


def _write_json_content(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: PermissionError | None = None
    for _ in range(5):
        temp_path: str | None = None
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
                temp_path = handle.name
            os.replace(temp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            if temp_path is not None:
                Path(temp_path).unlink(missing_ok=True)
            time.sleep(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to write {path}")


DEFAULT_PIPELINE_ARTIFACT_PRODUCERS: tuple[PipelineArtifactProducer, ...] = (
    PipelineArtifactProducer("progress", payload_from_context("progress")),
    PipelineArtifactProducer("artifact_registry", payload_from_context("artifact_registry")),
    PipelineArtifactProducer("environment", payload_from_context("environment")),
    PipelineArtifactProducer("ruff", payload_from_context("ruff")),
    PipelineArtifactProducer("pyright", payload_from_context("pyright")),
    PipelineArtifactProducer("pytest", payload_from_context("pytest")),
    PipelineArtifactProducer("vulture", payload_from_context("vulture")),
    PipelineArtifactProducer("bandit", payload_from_context("bandit")),
    PipelineArtifactProducer("architecture", payload_from_context("architecture")),
    PipelineArtifactProducer("analyzer_registry", payload_from_context("analyzer_registry")),
    PipelineArtifactProducer("dependency_graph", payload_from_context("dependency_graph")),
    PipelineArtifactProducer("call_graph", payload_from_context("call_graph")),
    PipelineArtifactProducer("graphics_layout", payload_from_context("graphics_layout")),
    PipelineArtifactProducer("impact_analysis", payload_from_context("impact_analysis")),
    PipelineArtifactProducer("trace", payload_from_context("trace")),
    PipelineArtifactProducer("incremental_analysis", payload_from_context("incremental_analysis")),
    PipelineArtifactProducer("findings", payload_from_context("findings")),
    PipelineArtifactProducer("analysis_diff", payload_from_context("analysis_diff")),
    PipelineArtifactProducer("recommendation_drift", payload_from_context("recommendation_drift")),
    PipelineArtifactProducer("corpus_results", payload_from_context("corpus_results")),
    PipelineArtifactProducer("coverage_summary", payload_from_context("coverage_summary")),
    PipelineArtifactProducer("sattline_semantic", payload_from_context("sattline_semantic")),
    PipelineArtifactProducer("rule_metrics", payload_from_context("rule_metrics")),
    PipelineArtifactProducer("profiling_summary", payload_from_context("profiling_summary")),
    PipelineArtifactProducer("performance_budget", payload_from_context("performance_budget")),
    PipelineArtifactProducer("mutation_results", payload_from_context("mutation_results")),
    PipelineArtifactProducer("status", payload_from_context("status")),
    PipelineArtifactProducer("summary", payload_from_context("summary")),
    PipelineArtifactProducer("accuracy_metrics", _build_none_payload),
    PipelineArtifactProducer("ai_templates", _build_none_payload),
    PipelineArtifactProducer("differential", payload_from_context("differential")),
    PipelineArtifactProducer("production_summary", _build_none_payload),
    PipelineArtifactProducer("symbolic_summary", _build_none_payload),
)


def validate_pipeline_artifact_producers(
    artifacts: tuple[ArtifactDefinition, ...],
    *,
    profile: str,
    producers: tuple[PipelineArtifactProducer, ...] = DEFAULT_PIPELINE_ARTIFACT_PRODUCERS,
) -> tuple[str, ...]:
    producer_ids: list[str] = [producer.producer_id for producer in producers]
    duplicate_producer_ids = sorted(
        {producer_id for producer_id in producer_ids if producer_ids.count(producer_id) > 1}
    )
    if duplicate_producer_ids:
        raise ValueError("Duplicate pipeline artifact producers registered: " + ", ".join(duplicate_producer_ids))

    producers_by_id = {producer.producer_id: producer for producer in producers}
    missing_producers = [
        artifact.artifact_id
        for artifact in artifacts
        if profile in artifact.profiles and artifact.producer not in producers_by_id
    ]
    if missing_producers:
        raise ValueError(
            "Pipeline artifact registry entries are missing producers: " + ", ".join(sorted(missing_producers))
        )

    return tuple(artifact.artifact_id for artifact in artifacts if profile in artifact.profiles)


def write_pipeline_artifacts(
    output_dir: Path,
    *,
    artifacts: tuple[ArtifactDefinition, ...],
    profile: str,
    enabled_artifact_ids: set[str],
    context: PipelineArtifactContext,
    write_json: Callable[[Path, dict[str, Any]], None],
    producers: tuple[PipelineArtifactProducer, ...] = DEFAULT_PIPELINE_ARTIFACT_PRODUCERS,
) -> tuple[str, ...]:
    validate_pipeline_artifact_producers(
        artifacts,
        profile=profile,
        producers=producers,
    )
    producers_by_id = {producer.producer_id: producer for producer in producers}

    written_artifacts: list[str] = []
    for artifact in artifacts:
        if profile not in artifact.profiles or artifact.artifact_id not in enabled_artifact_ids:
            continue
        producer = producers_by_id.get(artifact.producer)
        if producer is None:
            raise ValueError(
                "No pipeline artifact producer registered for "
                f"{artifact.artifact_id!r} via producer {artifact.producer!r}"
            )
        payload = producer.build_payload(context)
        if payload is None:
            continue
        write_json(output_dir / artifact.filename, payload)
        written_artifacts.append(artifact.artifact_id)

    return tuple(written_artifacts)


def write_json_artifact(
    path: Path,
    payload: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    source_paths: tuple[str | Path, ...] = (),
) -> None:
    """Write *payload* as indented JSON to *path*, creating parent directories as needed."""
    content = json.dumps(payload, indent=2, sort_keys=True)
    _write_json_content(path, content)

    manifest_payload = build_source_digest_manifest(
        path,
        payload,
        repo_root=repo_root,
        source_paths=source_paths,
    )
    manifest_path = artifact_source_manifest_path(path)
    if manifest_payload is None:
        manifest_path.unlink(missing_ok=True)
        return
    _write_json_content(manifest_path, json.dumps(manifest_payload, indent=2, sort_keys=True))


__all__ = [
    "DEFAULT_PIPELINE_ARTIFACT_PRODUCERS",
    "SOURCE_DIGEST_MANIFEST_KIND",
    "SOURCE_DIGEST_MANIFEST_SCHEMA_VERSION",
    "PipelineArtifactContext",
    "PipelineArtifactProducer",
    "artifact_source_manifest_path",
    "build_source_digest_manifest",
    "payload_from_context",
    "validate_pipeline_artifact_producers",
    "write_json_artifact",
    "write_pipeline_artifacts",
]
