"""Analyzer registry for CLI entrypoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ...utils.repo_paths import repo_root_from
from .._registry_specs import build_default_analyzers
from ..alarm_integrity import analyze_alarm_integrity
from ..comment_code import analyze_comment_code
from ..cyclomatic_complexity import analyze_cyclomatic_complexity
from ..dataflow import analyze_dataflow
from ..datatype_fields import analyze_datatype_fields
from ..framework import AnalyzerSpec
from ..icf.analyzer import analyze_icf_configuration
from ..modules import analyze_version_drift
from ..picture_display_paths import analyze_picture_display_paths
from ..plugin import get_registered_plugin_analyzers, register_analyzer
from ..same_cycle import analyze_same_cycle
from ..sfc import analyze_sfc
from ..spec_compliance import analyze_spec_compliance
from ..variables import analyze_variables
from ._registry_delivery import AnalyzerDeliveryMetadata, build_delivery_metadata, summary_output_for_analyzer

# Policy (analyzer execution refactor B4.9): every registered analyzer is
# selectable, and is either in the default CLI set below or deliberately opt-in
# (datatype-fields, cyclomatic-complexity, version-drift).
DEFAULT_CLI_ANALYZER_KEYS: tuple[str, ...] = (
    "variables",
    "picture-display-paths",
    "sfc",
    "comment-code",
    "spec-compliance",
    "alarm-integrity",
    "same-cycle",
    "dataflow",
    "icf",
)


def _registry_repo_root() -> Path:
    try:
        return repo_root_from(Path(__file__))
    except RuntimeError:
        return Path(__file__).resolve().parent


REPO_ROOT = _registry_repo_root()
DEFAULT_CORPUS_MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "manifests"

LEGACY_ANALYZER_KEY_ALIASES: dict[str, str] = {
    "same_cycle": "same-cycle",
}


@dataclass(frozen=True)
class AnalyzerMetadata:
    spec: AnalyzerSpec
    rule_ids: tuple[str, ...] = ()
    delivery: AnalyzerDeliveryMetadata = field(
        default_factory=lambda: AnalyzerDeliveryMetadata(
            scope="workspace",
            implementation_bucket="analyzers",
        )
    )

    @property
    def summary_output(self) -> str:
        return f"{self.spec.key}.summary"

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "key": self.spec.key,
            "name": self.spec.name,
            "description": self.spec.description,
            "category": self.spec.category,
            "enabled": self.spec.enabled,
            "summary_output": self.summary_output,
            "rule_ids": list(self.rule_ids),
        }
        data.update(self.delivery.to_dict())
        return data


@dataclass(frozen=True)
class AnalyzerCatalog:
    analyzers: tuple[AnalyzerMetadata, ...]

    def enabled_specs(self) -> tuple[AnalyzerSpec, ...]:
        return tuple(analyzer.spec for analyzer in self.analyzers if analyzer.spec.enabled)

    def to_report(self, *, generated_by: str) -> dict[str, object]:
        return {
            "generated_by": generated_by,
            "analyzers": [analyzer.to_dict() for analyzer in self.analyzers],
        }


def canonicalize_analyzer_key(key: str) -> str:
    return LEGACY_ANALYZER_KEY_ALIASES.get(key.casefold(), key.casefold())


def canonicalize_analyzer_keys(keys: tuple[str, ...] | list[str] | set[str]) -> tuple[str, ...]:
    return tuple(canonicalize_analyzer_key(key) for key in keys if key.strip())


def get_declared_cli_analyzer_keys() -> tuple[str, ...]:
    return tuple(
        sorted(
            analyzer.spec.key for analyzer in get_default_analyzer_catalog().analyzers if analyzer.delivery.cli_exposed
        )
    )


def get_actual_cli_analyzer_keys() -> tuple[str, ...]:
    return tuple(spec.key for spec in get_default_cli_analyzers())


@lru_cache(maxsize=1)
def _build_default_analyzer_catalog() -> AnalyzerCatalog:
    # Building this from the static rule/analyzer registry costs tens of ms (delivery-metadata
    # construction for every analyzer), and was previously rebuilt from scratch on every
    # collect_run_checks_result() call. All inputs are static module-level data, so caching it for
    # the process lifetime is safe; get_default_analyzer_catalog stays the public, monkeypatch-friendly
    # entry point tests already rely on.
    analyzer_specs = tuple(get_default_analyzers())

    analyzers = tuple(
        AnalyzerMetadata(
            spec=spec,
            rule_ids=(),
            delivery=build_delivery_metadata(spec, ()),
        )
        for spec in analyzer_specs
    )

    return AnalyzerCatalog(analyzers=analyzers)


def get_default_analyzer_catalog() -> AnalyzerCatalog:
    return _build_default_analyzer_catalog()


def get_enabled_analyzers() -> list[AnalyzerSpec]:
    return list(get_default_analyzer_catalog().enabled_specs())


def get_selectable_analyzers() -> list[AnalyzerSpec]:
    return list(get_default_analyzers())


def get_default_cli_analyzers() -> list[AnalyzerSpec]:
    enabled_by_key = {canonicalize_analyzer_key(spec.key): spec for spec in get_enabled_analyzers()}
    return [
        enabled_by_key[key] for key in canonicalize_analyzer_keys(DEFAULT_CLI_ANALYZER_KEYS) if key in enabled_by_key
    ]


def get_default_analyzers() -> list[AnalyzerSpec]:
    return [
        *build_default_analyzers(),
        *get_registered_plugin_analyzers(),
    ]


def get_correctness_analyzer_keys() -> tuple[str, ...]:
    return tuple(
        sorted(
            analyzer.spec.key
            for analyzer in get_default_analyzer_catalog().analyzers
            if analyzer.spec.enabled and analyzer.spec.category == "correctness"
        )
    )


__all__ = [
    "DEFAULT_CLI_ANALYZER_KEYS",
    "DEFAULT_CORPUS_MANIFEST_DIR",
    "LEGACY_ANALYZER_KEY_ALIASES",
    "REPO_ROOT",
    "AnalyzerCatalog",
    "AnalyzerDeliveryMetadata",
    "AnalyzerMetadata",
    "AnalyzerSpec",
    "analyze_alarm_integrity",
    "analyze_comment_code",
    "analyze_cyclomatic_complexity",
    "analyze_dataflow",
    "analyze_datatype_fields",
    "analyze_icf_configuration",
    "analyze_picture_display_paths",
    "analyze_same_cycle",
    "analyze_sfc",
    "analyze_spec_compliance",
    "analyze_variables",
    "analyze_version_drift",
    "build_default_analyzers",
    "build_delivery_metadata",
    "canonicalize_analyzer_key",
    "canonicalize_analyzer_keys",
    "get_actual_cli_analyzer_keys",
    "get_correctness_analyzer_keys",
    "get_declared_cli_analyzer_keys",
    "get_default_analyzer_catalog",
    "get_default_analyzers",
    "get_default_cli_analyzers",
    "get_enabled_analyzers",
    "get_registered_plugin_analyzers",
    "get_selectable_analyzers",
    "register_analyzer",
    "summary_output_for_analyzer",
]
