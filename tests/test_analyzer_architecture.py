# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportAttributeAccessIssue=false
from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

from sattline_parser.models.ast_model import BasePicture, ModuleHeader
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers.dataflow import DataflowAnalyzer
from sattlint.analyzers.framework import (
    AnalysisContext,
    AnalyzerLifecycleMixin,
    BasePictureAnalyzer,
    SimpleReport,
    build_analysis_context,
)
from sattlint.analyzers.registry._registry_delivery_data import default_delivery_templates
from sattlint.analyzers.registry._registry_spec_templates import AnalyzerSpecTemplate, default_spec_templates
from sattlint.analyzers.registry._registry_specs import build_context_kwargs, build_default_analyzers
from sattlint.analyzers.reset_contamination import ResetContaminationAnalyzer
from sattlint.analyzers.shared.variable_utils import VariablesConstMixin
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.analyzers.variables._variable_issue_collection import VariablesIssueCollectionMixin
from sattlint.analyzers.variables._variable_traversal import VariablesTraversalMixin
from sattlint.analyzers.variables._variables_access import VariablesAccessMixin
from sattlint.analyzers.variables._variables_contracts import VariablesContractsMixin
from sattlint.analyzers.variables._variables_execution import VariablesExecutionMixin
from sattlint.analyzers.variables._variables_status import VariablesStatusMixin
from sattlint.analyzers.variables._variables_submodules import VariablesSubmodulesMixin

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
    module_paths = [
        path for path in ANALYZER_DIR.glob("*.py") if path.name != "__init__.py" and not path.name.startswith("_")
    ]
    module_paths.extend(path for path in ANALYZER_DIR.glob("*/__init__.py") if not path.parent.name.startswith("_"))
    return sorted(module_paths)


def _analyzer_module_name(path: Path) -> str:
    return f"{path.parent.name}.py" if path.name == "__init__.py" else path.name


def _public_analyze_defs() -> set[tuple[str, str]]:
    definitions: set[tuple[str, str]] = set()
    for path in _iter_analyzer_modules():
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("analyze_"):
                definitions.add((_analyzer_module_name(path), node.name))
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


def _module_level_private_module_aliases(module: ast.Module) -> list[str]:
    aliases: list[str] = []
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            for alias in node.names:
                if alias.name.startswith("_") and alias.asname and alias.asname.endswith("_module"):
                    aliases.append(alias.name)
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not isinstance(value, ast.Attribute) or not isinstance(value.value, ast.Name):
            continue
        if not value.value.id.endswith("_module"):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.startswith("_"):
                aliases.append(target.id)
    return aliases


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
            mixed_import_modules.append(_analyzer_module_name(path))

    assert mixed_import_modules == []


def test_variables_analyzer_uses_helper_mixins_instead_of_local_method_injection() -> None:
    expected_mixins = (
        VariablesIssueCollectionMixin,
        VariablesTraversalMixin,
        VariablesAccessMixin,
        VariablesContractsMixin,
        VariablesStatusMixin,
        VariablesSubmodulesMixin,
        VariablesExecutionMixin,
        VariablesConstMixin,
    )

    for mixin in expected_mixins:
        assert mixin in VariablesAnalyzer.__mro__

    assert "_add_issue" not in VariablesAnalyzer.__dict__
    assert "_repath_context" not in VariablesAnalyzer.__dict__
    assert "_canonical_path" not in VariablesAnalyzer.__dict__
    assert "_check_param_mapping" not in VariablesAnalyzer.__dict__
    assert "_bind_procedure_status" not in VariablesAnalyzer.__dict__
    assert "_walk_submodules" not in VariablesAnalyzer.__dict__
    assert "run" not in VariablesAnalyzer.__dict__
    assert "_is_const_candidate" not in VariablesAnalyzer.__dict__

    assert VariablesAnalyzer._add_issue.__qualname__.startswith("VariablesIssueCollectionMixin.")
    assert VariablesAnalyzer._repath_context.__qualname__.startswith("VariablesTraversalMixin.")
    assert VariablesAnalyzer._canonical_path.__qualname__.startswith("VariablesAccessMixin.")
    assert VariablesAnalyzer._check_param_mapping.__qualname__.startswith("VariablesContractsMixin.")
    assert VariablesAnalyzer._bind_procedure_status.__qualname__.startswith("VariablesStatusMixin.")
    assert VariablesAnalyzer._walk_submodules.__qualname__.startswith("VariablesSubmodulesMixin.")
    assert VariablesAnalyzer.run.__qualname__.startswith("VariablesExecutionMixin.")
    assert VariablesAnalyzer._is_const_candidate.__qualname__.startswith("VariablesConstMixin.")
    assert not (ANALYZER_DIR / "variables.py").exists()


def test_dataflow_analyzer_uses_shared_lifecycle_mixin() -> None:
    assert AnalyzerLifecycleMixin in DataflowAnalyzer.__mro__


def test_reset_contamination_module_uses_single_class_backed_owner() -> None:
    assert BasePictureAnalyzer in ResetContaminationAnalyzer.__mro__

    module_path = ANALYZER_DIR / "reset_contamination" / "__init__.py"
    module = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    assert _module_level_private_module_aliases(module) == []
    assert not (ANALYZER_DIR / "_reset_contamination.py").exists()


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

    from sattlint.analyzers.registry import _registry_specs as registry_specs_module  # noqa: PLC0415

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
    assert built_specs[0].requires == ()
    assert built_specs[1].context_kwargs == spec.context_kwargs
    assert built_specs[1].requires == ()

    sfc_template = next(template for template in default_spec_templates("semantic-demo") if template.key == "sfc")
    assert sfc_template.requires == ("variables",)


def test_build_analysis_context_normalizes_config_and_shared_artifacts() -> None:
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    config = {"mode": "workspace"}
    context = build_analysis_context(
        base_picture,
        graph=SimpleNamespace(unavailable_libraries={"ControlLib"}),
        selected_issue_kinds={"unused", "shadowing"},
        config=config,
        create_shared_artifacts=True,
    )

    assert context.config == {"mode": "workspace"}
    assert context.config is not config
    assert context.selected_issue_kinds == frozenset({"unused", "shadowing"})
    assert context.shared_artifacts is not None
    assert context.shared_artifacts.counters.shared_artifact_holders_created == 1
    assert context.unavailable_libraries == {"ControlLib"}
