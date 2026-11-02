"""Typed JSON payload shapes emitted by the headless CLI.

Every command builds one of these envelopes so the serialized contract is
checked by Pyright instead of being assembled from untyped dicts.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from ..analyzers.catalog import AnalyzerMetadataDict

type GroupBy = Literal["none", "module", "analyzer", "kind"]


class ErrorInfo(TypedDict):
    code: str
    message: str
    details: dict[str, object]


class ErrorPayload(TypedDict):
    schema_version: int
    command: str
    error: ErrorInfo


class ConfigInfo(TypedDict):
    path: str
    exists: bool


class ProjectPaths(TypedDict):
    program_dir: str
    ABB_lib_dir: str
    icf_dir: str
    other_lib_dirs: list[str]


class ProjectInfo(TypedDict):
    path: str
    root: str
    slproj_version: int
    mode: str
    targets: list[str]
    analysis: dict[str, object]
    paths: ProjectPaths
    config: ConfigInfo
    cache_dir: str
    runs_dir: str
    review_output_dir: str


class ProjectShowPayload(TypedDict):
    schema_version: int
    command: str
    project: ProjectInfo


class AnalyzerInfo(AnalyzerMetadataDict):
    default: bool


class AnalyzersListPayload(TypedDict):
    schema_version: int
    command: str
    analyzers: list[AnalyzerInfo]


class FindingPayload(TypedDict):
    id: str
    target: str
    analyzer: str
    analyzer_name: str
    kind: str
    rule_id: str | None
    module_path: list[str]
    module: str
    site: str | None
    context: str | None
    message: str
    explanation: str | None
    suggestion: str | None
    occurrence_count: int
    data: dict[str, object]


class RunPayload(TypedDict):
    run_id: str
    started_at: str
    finished_at: str
    project_tag: str
    selected_analyzers: list[str]
    cancelled: bool


class FindingSummary(TypedDict):
    findings: int
    occurrences: int
    by_analyzer: dict[str, int]
    by_kind: dict[str, int]
    by_module: dict[str, int]


class AnalyzeSummary(FindingSummary, total=False):
    total_findings: int
    targets: int
    analyzers: int


class FindingsSummary(FindingSummary, total=False):
    matched: int


class FindingGroup(TypedDict):
    key: str
    group_by: str
    count: int
    finding_ids: list[str]


class AnalyzeProject(TypedDict):
    path: str
    targets: list[str]


class AnalyzePayload(TypedDict):
    schema_version: int
    command: str
    run_id: str | None
    cancelled: bool
    project: AnalyzeProject
    selected_analyzers: list[str]
    summary: AnalyzeSummary
    findings: list[FindingPayload]


class FindingsFilters(TypedDict):
    target: list[str]
    analyzer: list[str]
    module: list[str]
    exact_module: bool
    kind: list[str]
    rule: list[str]
    group_by: GroupBy
    limit: int | None


class FindingsPayload(TypedDict):
    schema_version: int
    command: str
    run: RunPayload
    filters: FindingsFilters
    summary: FindingsSummary
    groups: list[FindingGroup]
    findings: list[FindingPayload]


class ShowPayload(TypedDict):
    schema_version: int
    command: str
    run: RunPayload
    finding: FindingPayload


__all__ = [
    "AnalyzePayload",
    "AnalyzeProject",
    "AnalyzeSummary",
    "AnalyzerInfo",
    "AnalyzersListPayload",
    "ConfigInfo",
    "ErrorInfo",
    "ErrorPayload",
    "FindingGroup",
    "FindingPayload",
    "FindingSummary",
    "FindingsFilters",
    "FindingsPayload",
    "FindingsSummary",
    "GroupBy",
    "ProjectInfo",
    "ProjectPaths",
    "ProjectShowPayload",
    "RunPayload",
    "ShowPayload",
]
