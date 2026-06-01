from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

from sattline_parser.models.ast_model import BasePicture, ModuleHeader
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers._registry_delivery_data import default_delivery_templates
from sattlint.analyzers._registry_spec_templates import AnalyzerSpecTemplate, default_spec_templates
from sattlint.analyzers._registry_specs import build_context_kwargs, build_default_analyzers
from sattlint.analyzers.framework import AnalysisContext, SimpleReport

ANALYZER_DIR = Path(__file__).resolve().parents[1] / "src" / "sattlint" / "analyzers"
KEBAB_CASE_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LEGACY_UNDERSCORE_ANALYZER_KEYS = frozenset()
EXPLICIT_NON_REGISTRY_ANALYZE_FUNCTIONS = frozenset(
    {
        ("comment_code.py", "analyze_comment_code_files"),
        ("modules.py", "analyze_module_duplicates"),
    }
)


def _iter_analyzer_modules() -> list[Path]:
    return sorted(path for path in ANALYZER_DIR.glob("*.py") if path.name != "__init__.py")


def _public_analyze_defs() -> set[tuple[str, str]]:
    definitions: set[tuple[str, str]] = set()
    for path in _iter_analyzer_modules():
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("analyze_"):
                definitions.add((path.name, node.name))
    return definitions


def _uses_absolute_analyzer_import(module: ast.Module) -> bool:
    for node in ast.walk(module):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (node.module == "sattlint.analyzers" or node.module.startswith("sattlint.analyzers."))
        ):
            return True
    return False


def _uses_relative_analyzer_import(module: ast.Module) -> bool:
    return any(isinstance(node, ast.ImportFrom) and node.level == 1 for node in ast.walk(module))


def test_registry_keys_are_kebab_case_or_explicit_legacy_allowlist() -> None:
    templates = default_spec_templates(registry_module.SEMANTIC_LAYER_ANALYZER_KEY)
    underscore_keys = {template.key for template in templates if "_" in template.key}
    assert underscore_keys == LEGACY_UNDERSCORE_ANALYZER_KEYS

    invalid_kebab_keys = sorted(
        template.key
        for template in templates
        if template.key not in LEGACY_UNDERSCORE_ANALYZER_KEYS and not KEBAB_CASE_KEY.fullmatch(template.key)
    )
    assert invalid_kebab_keys == []


def test_public_analyze_functions_are_registry_backed_or_explicit_exceptions() -> None:
    registry_backed_functions = {
        template.analyzer_attr
        for template in default_spec_templates(registry_module.SEMANTIC_LAYER_ANALYZER_KEY)
        if template.analyzer_attr.startswith("analyze_")
    }

    public_analyze_defs = _public_analyze_defs()
    explicit_non_registry_defs = {
        definition for definition in public_analyze_defs if definition[1] not in registry_backed_functions
    }

    assert explicit_non_registry_defs == EXPLICIT_NON_REGISTRY_ANALYZE_FUNCTIONS


def test_analyzer_modules_do_not_mix_absolute_and_relative_package_imports() -> None:
    mixed_import_modules: list[str] = []
    for path in _iter_analyzer_modules():
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _uses_absolute_analyzer_import(module) and _uses_relative_analyzer_import(module):
            mixed_import_modules.append(path.name)

    assert mixed_import_modules == []


def test_registry_helper_templates_and_runners_cover_remaining_paths(monkeypatch) -> None:
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    context = AnalysisContext(
        base_picture=base_picture,
        graph=SimpleNamespace(unavailable_libraries={"ControlLib"}),
        debug=True,
        target_is_library=True,
        config={"mode": "test"},
    )
    registry_stub = SimpleNamespace(
        get_configured_mutually_exclusive_step_sets=lambda config: ("step-set", config["mode"]),
        get_configured_naming_rules=lambda config: {"mode": config["mode"]},
        get_configured_step_contracts=lambda config: ("contract", config["mode"]),
        analyze_direct=lambda analysis_context: SimpleReport(name=analysis_context.base_picture.header.name),
        analyze_picture=lambda base_picture, **kwargs: SimpleReport(name=base_picture.header.name, note=str(kwargs)),
    )

    spec = AnalyzerSpecTemplate(
        key="demo",
        name="Demo",
        description="demo",
        analyzer_attr="analyze_picture",
        context_kwargs=(
            "analysis_context",
            "analyzed_target_is_library",
            "config",
            "debug",
            "graph",
            "mutually_exclusive_steps",
            "rules",
            "sfc_mutually_exclusive_steps",
            "sfc_step_contracts",
            "step_contracts",
            "unavailable_libraries",
        ),
    )
    kwargs = build_context_kwargs(spec, registry_stub, context, overrides={"debug": False})
    assert kwargs["analysis_context"] is context
    assert kwargs["analyzed_target_is_library"] is True
    assert kwargs["config"] == {"mode": "test"}
    assert kwargs["debug"] is False
    assert kwargs["graph"] is context.graph
    assert kwargs["mutually_exclusive_steps"] == ("step-set", "test")
    assert kwargs["rules"] == {"mode": "test"}
    assert kwargs["sfc_mutually_exclusive_steps"] == ("step-set", "test")
    assert kwargs["sfc_step_contracts"] == ("contract", "test")
    assert kwargs["step_contracts"] == ("contract", "test")
    assert kwargs["unavailable_libraries"] == {"ControlLib"}

    direct_template = AnalyzerSpecTemplate(
        key="direct",
        name="Direct",
        description="direct",
        analyzer_attr="analyze_direct",
        direct_context=True,
    )
    direct_runner = build_default_analyzers(semantic_layer_analyzer_key=registry_module.SEMANTIC_LAYER_ANALYZER_KEY)
    assert any(spec.key == "variables" for spec in direct_runner)

    from sattlint.analyzers import _registry_specs as registry_specs_module

    direct_report = registry_specs_module._build_runner(direct_template, registry_stub)(context)
    assert direct_report.name == "Root"

    standard_report = registry_specs_module._build_runner(spec, registry_stub)(context)
    assert "ControlLib" in (standard_report.note or "")

    deliveries = default_delivery_templates(
        registry_module.SEMANTIC_LAYER_ANALYZER_KEY,
        shared_fixtures=("fixture-a", "fixture-b"),
    )
    assert deliveries[0].key == registry_module.SEMANTIC_LAYER_ANALYZER_KEY
    assert deliveries[0].min_fixture_set == ("fixture-a", "fixture-b")

    monkeypatch.setattr(
        registry_specs_module,
        "default_spec_templates",
        lambda _key: (direct_template, spec),
    )
    monkeypatch.setitem(registry_specs_module.__dict__, "registry", registry_stub)
    built_specs = registry_specs_module.build_default_analyzers(semantic_layer_analyzer_key="semantic-demo")
    assert [built.key for built in built_specs] == ["direct", "demo"]
    assert built_specs[0].direct_context is True
    assert built_specs[1].context_kwargs == spec.context_kwargs
