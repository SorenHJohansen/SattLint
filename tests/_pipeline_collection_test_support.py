# pyright: reportUnusedImport=false
# ruff: noqa: F401
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint.analyzers.registry import (
    get_actual_cli_analyzer_keys,
    get_actual_lsp_analyzer_keys,
    get_declared_cli_analyzer_keys,
    get_declared_lsp_analyzer_keys,
)
from sattlint.analyzers.sattline_semantics import (
    SattLineSemanticsReport,
    SemanticIssue,
    SemanticRule,
)
from sattlint.contracts import FindingCollection, FindingRecord
from sattlint.devtools import corpus, pipeline, structural_reports
from sattlint.devtools.artifact_registry import ArtifactDefinition
from sattlint.devtools.baselines import build_analysis_diff_report
from sattlint.devtools.finding_exports import build_pipeline_finding_collection
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.devtools.shared.pipeline_artifacts import (
    SOURCE_DIGEST_MANIFEST_KIND,
    PipelineArtifactContext,
    PipelineArtifactProducer,
    artifact_source_manifest_path,
    validate_pipeline_artifact_producers,
    write_json_artifact,
    write_pipeline_artifacts,
)
from sattlint.reporting.variables_report import IssueKind

from .helpers.artifact_assertions import (
    assert_analysis_diff_report,
    assert_findings_collection,
)
