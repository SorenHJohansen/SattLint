"""Registry-backed helpers for writing pipeline artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattlint.devtools.artifact_registry import ArtifactDefinition


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
    PipelineArtifactProducer("impact_analysis", payload_from_context("impact_analysis")),
    PipelineArtifactProducer("trace", payload_from_context("trace")),
    PipelineArtifactProducer("findings", payload_from_context("findings")),
    PipelineArtifactProducer("analysis_diff", payload_from_context("analysis_diff")),
    PipelineArtifactProducer("corpus_results", payload_from_context("corpus_results")),
    PipelineArtifactProducer("status", payload_from_context("status")),
    PipelineArtifactProducer("summary", payload_from_context("summary")),
)


def validate_pipeline_artifact_producers(
    artifacts: tuple[ArtifactDefinition, ...],
    *,
    profile: str,
    producers: tuple[PipelineArtifactProducer, ...] = DEFAULT_PIPELINE_ARTIFACT_PRODUCERS,
) -> tuple[str, ...]:
    producer_ids: list[str] = [producer.producer_id for producer in producers]
    duplicate_producer_ids = sorted(
        {
            producer_id
            for producer_id in producer_ids
            if producer_ids.count(producer_id) > 1
        }
    )
    if duplicate_producer_ids:
        raise ValueError(
            "Duplicate pipeline artifact producers registered: "
            + ", ".join(duplicate_producer_ids)
        )

    producers_by_id = {producer.producer_id: producer for producer in producers}
    missing_producers = [
        artifact.artifact_id
        for artifact in artifacts
        if profile in artifact.profiles and artifact.producer not in producers_by_id
    ]
    if missing_producers:
        raise ValueError(
            "Pipeline artifact registry entries are missing producers: "
            + ", ".join(sorted(missing_producers))
        )

    return tuple(
        artifact.artifact_id
        for artifact in artifacts
        if profile in artifact.profiles
    )


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
    producers_by_id = {
        producer.producer_id: producer
        for producer in producers
    }

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


__all__ = [
    "DEFAULT_PIPELINE_ARTIFACT_PRODUCERS",
    "PipelineArtifactContext",
    "PipelineArtifactProducer",
    "payload_from_context",
    "validate_pipeline_artifact_producers",
    "write_pipeline_artifacts",
]
