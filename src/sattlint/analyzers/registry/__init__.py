"""Analyzer registry for CLI entrypoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
from typing import TypedDict

from .._registry_specs import build_default_analyzers
from ..framework import AnalyzerSpec
from ..plugin import get_plugin_registry_generation, get_registered_plugin_analyzers, register_analyzer
from ._registry_delivery import AnalyzerDeliveryMetadata, build_delivery_metadata

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


#: Analyzer entry points resolved on first attribute access. Building the
#: catalogue needs every one of them, but merely importing the registry must
#: not import every analyzer (and, through them, the project loader).
_LAZY_ANALYZER_EXPORTS: dict[str, tuple[str, str]] = {
    "analyze_alarm_integrity": ("sattlint.analyzers.alarm_integrity", "analyze_alarm_integrity"),
    "analyze_comment_code": ("sattlint.analyzers.comment_code", "analyze_comment_code"),
    "analyze_cyclomatic_complexity": (
        "sattlint.analyzers.cyclomatic_complexity",
        "analyze_cyclomatic_complexity",
    ),
    "analyze_dataflow": ("sattlint.analyzers.dataflow", "analyze_dataflow"),
    "analyze_datatype_fields": ("sattlint.analyzers.datatype_fields", "analyze_datatype_fields"),
    "analyze_icf_configuration": ("sattlint.analyzers.icf.analyzer", "analyze_icf_configuration"),
    "analyze_moduletype_usage": ("sattlint.analyzers.moduletype_usage", "analyze_moduletype_usage"),
    "analyze_picture_display_paths": ("sattlint.analyzers.picture_display_paths", "analyze_picture_display_paths"),
    "analyze_same_cycle": ("sattlint.analyzers.same_cycle", "analyze_same_cycle"),
    "analyze_sfc": ("sattlint.analyzers.sfc", "analyze_sfc"),
    "analyze_spec_compliance": ("sattlint.analyzers.spec_compliance", "analyze_spec_compliance"),
    "analyze_variables": ("sattlint.analyzers.variables", "analyze_variables"),
    "analyze_version_drift": ("sattlint.analyzers.modules", "analyze_version_drift"),
}


def __getattr__(name: str) -> object:
    target = _LAZY_ANALYZER_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


LEGACY_ANALYZER_KEY_ALIASES: dict[str, str] = {
    "same_cycle": "same-cycle",
}


class AnalyzerMetadataDict(TypedDict):
    """Serialized analyzer metadata: the single source for CLI and reports."""

    key: str
    name: str
    description: str
    category: str
    enabled: bool
    summary_output: str
    scope: str
    implementation_bucket: str
    output_artifacts: list[str]
    cli_exposed: bool
    acceptance_tests: list[str]
    depends_on_artifacts: list[str]
    supports_baselines: bool
    supports_incremental: bool
    min_fixture_set: list[str]


class AnalyzerCatalogReport(TypedDict):
    generated_by: str
    analyzers: list[AnalyzerMetadataDict]


@dataclass(frozen=True)
class AnalyzerMetadata:
    spec: AnalyzerSpec
    delivery: AnalyzerDeliveryMetadata = field(
        default_factory=lambda: AnalyzerDeliveryMetadata(
            delivery_scope="workspace",
            implementation_bucket="analyzers",
        )
    )

    @property
    def summary_output(self) -> str:
        return f"{self.spec.key}.summary"

    def to_dict(self) -> AnalyzerMetadataDict:
        delivery = self.delivery
        return AnalyzerMetadataDict(
            key=self.spec.key,
            name=self.spec.name,
            description=self.spec.description,
            category=self.spec.category,
            enabled=self.spec.enabled,
            summary_output=self.summary_output,
            scope=delivery.delivery_scope,
            implementation_bucket=delivery.implementation_bucket,
            output_artifacts=list(delivery.output_artifacts),
            cli_exposed=delivery.cli_exposed,
            acceptance_tests=list(delivery.acceptance_tests),
            depends_on_artifacts=list(delivery.depends_on_artifacts),
            supports_baselines=delivery.supports_baselines,
            supports_incremental=delivery.supports_incremental,
            min_fixture_set=list(delivery.min_fixture_set),
        )


@dataclass(frozen=True)
class AnalyzerCatalog:
    analyzers: tuple[AnalyzerMetadata, ...]

    def enabled_specs(self) -> tuple[AnalyzerSpec, ...]:
        return tuple(analyzer.spec for analyzer in self.analyzers if analyzer.spec.enabled)

    def to_report(self, *, generated_by: str) -> AnalyzerCatalogReport:
        return AnalyzerCatalogReport(
            generated_by=generated_by,
            analyzers=[analyzer.to_dict() for analyzer in self.analyzers],
        )


def canonicalize_analyzer_key(key: str) -> str:
    return LEGACY_ANALYZER_KEY_ALIASES.get(key.casefold(), key.casefold())


def canonicalize_analyzer_keys(keys: tuple[str, ...] | list[str] | set[str]) -> tuple[str, ...]:
    return tuple(canonicalize_analyzer_key(key.strip()) for key in keys if key.strip())


def get_declared_cli_analyzer_keys() -> tuple[str, ...]:
    return tuple(
        sorted(
            analyzer.spec.key for analyzer in get_default_analyzer_catalog().analyzers if analyzer.delivery.cli_exposed
        )
    )


def get_actual_cli_analyzer_keys() -> tuple[str, ...]:
    return tuple(spec.key for spec in get_default_cli_analyzers())


@lru_cache(maxsize=8)
def _build_default_analyzer_catalog(plugin_generation: int) -> AnalyzerCatalog:
    # Building this from the analyzer registry costs tens of ms (delivery-metadata
    # construction for every analyzer), and was previously rebuilt from scratch on every
    # collect_run_checks_result() call. The plugin generation is part of the cache key, so a
    # plugin registered after the first build still reaches the catalogue; the remainder of
    # the inputs is static module-level data. get_default_analyzer_catalog stays the public,
    # monkeypatch-friendly entry point tests already rely on.
    del plugin_generation
    analyzer_specs = tuple(get_default_analyzers())

    analyzers = tuple(
        AnalyzerMetadata(
            spec=spec,
            delivery=build_delivery_metadata(spec),
        )
        for spec in analyzer_specs
    )

    return AnalyzerCatalog(analyzers=analyzers)


def get_default_analyzer_catalog() -> AnalyzerCatalog:
    return _build_default_analyzer_catalog(get_plugin_registry_generation())


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


__all__ = [
    "DEFAULT_CLI_ANALYZER_KEYS",
    "AnalyzerCatalog",
    "AnalyzerCatalogReport",
    "AnalyzerDeliveryMetadata",
    "AnalyzerMetadata",
    "AnalyzerMetadataDict",
    "AnalyzerSpec",
    "build_delivery_metadata",
    "canonicalize_analyzer_key",
    "canonicalize_analyzer_keys",
    "get_actual_cli_analyzer_keys",
    "get_declared_cli_analyzer_keys",
    "get_default_analyzer_catalog",
    "get_default_analyzers",
    "get_default_cli_analyzers",
    "get_enabled_analyzers",
    "get_registered_plugin_analyzers",
    "get_selectable_analyzers",
    "register_analyzer",
]
