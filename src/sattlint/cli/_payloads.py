"""Typed JSON payload shapes emitted by the headless CLI.

Every command builds one of these envelopes so the serialized contract is
checked by Pyright instead of being assembled from untyped dicts.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from ..analyzers.catalog import AnalyzerMetadataDict
from ..application.findings import Severity
from ..config.string_capacities import StringCapacitiesDict
from ..project.support import LoadFailureKind

type GroupBy = Literal["none", "module", "analyzer", "kind"]

type FailOn = Literal["error", "warning", "any", "none"]

type BaselineEntryStatus = Literal["unchanged", "moved", "changed", "added", "stale"]


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
    analyzers: list[str]
    string_capacities: StringCapacitiesDict
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
    """One selectable analyzer. Selection is per run, so there is no default."""


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
    severity: Severity
    rule_id: str | None
    module_path: list[str]
    module: str
    site: str | None
    context: str | None
    message: str
    explanation: str | None
    suggestion: str | None
    file: str | None
    line: int | None
    column: int | None
    end_line: int | None
    occurrence_count: int
    data: dict[str, object]


class RunPayload(TypedDict):
    run_id: str
    started_at: str
    finished_at: str
    project_tag: str
    project_path: str
    selected_analyzers: list[str]
    cancelled: bool


class FindingSummary(TypedDict):
    findings: int
    occurrences: int
    by_analyzer: dict[str, int]
    by_kind: dict[str, int]
    by_module: dict[str, int]
    by_severity: dict[str, int]


class AnalyzeSummary(FindingSummary, total=False):
    total_findings: int
    targets: int
    analyzers: int
    fail_on: FailOn


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


class TargetLoadFailurePayload(TypedDict):
    """One target the loader could not prepare for analysis."""

    target: str
    kind: LoadFailureKind
    message: str
    path: str | None
    line: int | None
    column: int | None


class BaselineDiffEntryPayload(TypedDict):
    """One non-unchanged entry in a baseline comparison."""

    status: BaselineEntryStatus
    identity: str
    analyzer: str
    kind: str
    severity: Severity
    module: str
    file: str | None
    line: int | None
    message: str
    # A moved entry carries where the matched baseline entry used to be.
    previous_file: NotRequired[str | None]
    previous_line: NotRequired[int | None]
    # A changed entry carries the severity the baseline accepted.
    previous_severity: NotRequired[Severity]


class BaselineBlockPayload(TypedDict):
    """The comparison counts and records added to an analyze document."""

    path: str
    added: int
    moved: int
    changed: int
    stale: int
    unchanged: int
    entries: list[BaselineDiffEntryPayload]


class BaselineUpdatePayload(TypedDict):
    schema_version: int
    command: str
    path: str
    entry_count: int
    generated_by: str
    created: str
    # Present only when a previous baseline existed and was compared.
    added: NotRequired[int]
    pruned: NotRequired[int]


class BaselineDiffPayload(TypedDict):
    schema_version: int
    command: str
    path: str
    run: RunPayload
    baseline: BaselineBlockPayload


class AnalyzePayload(TypedDict):
    schema_version: int
    command: str
    run_id: str | None
    cancelled: bool
    project: AnalyzeProject
    selected_analyzers: list[str]
    summary: AnalyzeSummary
    findings: list[FindingPayload]
    # Present only when some targets loaded and some failed. The run is a
    # partial result, is not stored in run history, and exits 2.
    failures: NotRequired[list[TargetLoadFailurePayload]]
    failed_targets: NotRequired[int]
    # Present only when the run was compared with a baseline.
    baseline: NotRequired[BaselineBlockPayload]


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
    "BaselineBlockPayload",
    "BaselineDiffEntryPayload",
    "BaselineDiffPayload",
    "BaselineEntryStatus",
    "BaselineUpdatePayload",
    "ConfigInfo",
    "ErrorInfo",
    "ErrorPayload",
    "FailOn",
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
    "TargetLoadFailurePayload",
]
