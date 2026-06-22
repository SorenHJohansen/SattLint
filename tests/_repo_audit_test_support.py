import ast
import json
import os
import subprocess
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import call, patch

import pytest

from sattlint.devtools import coordination_lock_state, doc_gardener
from sattlint.devtools.audit import repo_audit, repo_audit_entrypoints
from sattlint.devtools.shared.pipeline_artifacts import artifact_source_manifest_path, write_json_artifact

from .helpers.artifact_assertions import assert_findings_collection, assert_findings_schema


def _patch_doc_gardener_paths(repo_root: Path):
    return patch.multiple(
        doc_gardener,
        REPO_ROOT=repo_root,
        DOCS_DIR=repo_root / "docs",
        AGENTS_MD=repo_root / "AGENTS.md",
        QUALITY_SCORE=repo_root / "docs" / "quality-score.md",
        TECH_DEBT=repo_root / "docs" / "exec-plans" / "tech-debt-tracker.md",
        CURRENT_WORK=repo_root / ".github" / "coordination" / "current_work_lock.json",
        CURRENT_WORK_TEMPLATE=repo_root / ".github" / "coordination" / "current-work.template.md",
        AI_FIRST_PLAN=repo_root / "docs" / "exec-plans" / "active" / "ai-first-repo-hardening.md",
        AI_FIRST_DEBT=repo_root / "docs" / "exec-plans" / "tech-debt-tracker.md",
    )


__all__ = [
    "UTC",
    "Any",
    "Path",
    "SimpleNamespace",
    "_patch_doc_gardener_paths",
    "artifact_source_manifest_path",
    "assert_findings_collection",
    "assert_findings_schema",
    "ast",
    "call",
    "cast",
    "coordination_lock_state",
    "datetime",
    "doc_gardener",
    "json",
    "nullcontext",
    "os",
    "patch",
    "pytest",
    "repo_audit",
    "repo_audit_entrypoints",
    "subprocess",
    "time",
    "write_json_artifact",
]
