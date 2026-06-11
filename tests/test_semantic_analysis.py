from pathlib import Path
from types import SimpleNamespace

import pytest

from sattline_parser.models.ast_model import BasePicture, ModuleHeader, Simple_DataType, Variable
from sattlint import semantic_analysis as semantic_analysis_module
from sattlint.core import semantic as semantic_core_module
from sattlint.core._semantic_snapshot import SemanticAnalysisArtifacts, SymbolDefinition
from sattlint.reporting.variables_report import IssueKind, VariableIssue, VariablesReport

pytestmark = pytest.mark.unit


def test_project_lsp_report_diagnostics_skips_non_list_issue_payloads(monkeypatch):
    monkeypatch.setattr(semantic_analysis_module, "build_module_diagnostic_sites", lambda _base_picture: {})
    monkeypatch.setattr(
        semantic_analysis_module,
        "merge_diagnostic_projection_results",
        lambda *reports: ("merged", reports),
    )
    monkeypatch.setattr("sattlint.analyzers.registry.SEMANTIC_LAYER_ANALYZER_KEY", "semantic-layer")
    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_default_analyzer_catalog",
        lambda: SimpleNamespace(
            analyzers=[
                SimpleNamespace(
                    delivery=SimpleNamespace(lsp_exposed=True),
                    spec=SimpleNamespace(
                        key="custom-analyzer",
                        run=lambda _context: SimpleNamespace(issues=("not-a-list",)),
                    ),
                )
            ]
        ),
    )

    result = semantic_analysis_module._project_lsp_report_diagnostics(
        BasePicture(header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))),
        SimpleNamespace(unavailable_libraries=()),
        debug=False,
    )

    assert result == ("merged", ())


def test_project_lsp_report_diagnostics_builds_context_with_config(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(semantic_analysis_module, "build_module_diagnostic_sites", lambda _base_picture: {})
    monkeypatch.setattr(
        semantic_analysis_module,
        "get_lsp_projection_analyzers",
        lambda: (SimpleNamespace(spec=SimpleNamespace(key="custom-analyzer")),),
    )
    monkeypatch.setattr(
        semantic_analysis_module,
        "merge_diagnostic_projection_results",
        lambda *reports: ("merged", reports),
    )

    def _run_registry_analyzer(spec, context):
        captured["spec"] = spec
        captured["context"] = context
        return SimpleNamespace(issues=[])

    monkeypatch.setattr(semantic_analysis_module, "run_registry_analyzer", _run_registry_analyzer)

    result = semantic_analysis_module._project_lsp_report_diagnostics(
        BasePicture(header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))),
        SimpleNamespace(unavailable_libraries={"MissingLib"}),
        debug=True,
        config={"mode": "workspace"},
        target_is_library=True,
    )

    assert result == ("merged", ())
    context = captured["context"]
    assert context.config == {"mode": "workspace"}
    assert context.target_is_library is True
    assert context.shared_artifacts is not None
    assert context.unavailable_libraries == {"MissingLib"}


def test_build_variable_semantic_artifacts_runs_variables_via_registry(monkeypatch):
    usage_event = object()
    variable_issue = VariableIssue(
        kind=IssueKind.UNUSED,
        module_path=["Root"],
        variable=Variable(name="UnusedVar", datatype=Simple_DataType.INTEGER),
    )
    usage_report = VariablesReport(
        basepicture_name="Root",
        issues=[],
        accesses_by_definition_key={("root", "unusedvar"): (usage_event,)},
        effect_flow_edges={("root", "unusedvar"): (("root", "sink"),)},
        effect_flow_display_names={("root", "unusedvar"): "Root.UnusedVar"},
    )
    diagnostics_report = VariablesReport(basepicture_name="Root", issues=[variable_issue])
    calls: list[dict[str, object]] = []
    projection_calls: list[dict[str, object]] = []

    monkeypatch.setattr(semantic_analysis_module, "get_registry_analyzer_spec", lambda key: SimpleNamespace(key=key))

    def _run_registry_analyzer(spec, context, *, overrides=None):
        calls.append(
            {
                "key": spec.key,
                "context": context,
                "overrides": None if overrides is None else dict(overrides),
            }
        )
        return usage_report if overrides else diagnostics_report

    projection_result = SimpleNamespace(
        diagnostics_by_file={"Root.s": ("diagnostic",)},
        dropped_issues=("drop",),
    )
    monkeypatch.setattr(semantic_analysis_module, "run_registry_analyzer", _run_registry_analyzer)
    monkeypatch.setattr(semantic_analysis_module, "project_variable_issues", lambda diagnostics, _defs: diagnostics)

    def _project_lsp_report_diagnostics(*_args, **kwargs):
        projection_calls.append(dict(kwargs))
        return "lsp-projection"

    monkeypatch.setattr(semantic_analysis_module, "_project_lsp_report_diagnostics", _project_lsp_report_diagnostics)
    monkeypatch.setattr(
        semantic_analysis_module,
        "merge_diagnostic_projection_results",
        lambda *reports: projection_result,
    )

    result = semantic_analysis_module.build_variable_semantic_artifacts(
        BasePicture(header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))),
        SimpleNamespace(unavailable_libraries={"MissingLib"}),
        collect_variable_diagnostics=True,
        debug=True,
        definitions_by_key={},
        config={"mode": "workspace"},
        target_is_library=True,
    )

    assert calls == [
        {
            "key": "variables",
            "context": calls[0]["context"],
            "overrides": {"include_dependency_moduletype_usage": True},
        },
        {
            "key": "variables",
            "context": calls[0]["context"],
            "overrides": None,
        },
    ]
    context = calls[0]["context"]
    assert context.config == {"mode": "workspace"}
    assert context.target_is_library is True
    assert context.shared_artifacts is not None
    assert projection_calls == [
        {
            "config": {"mode": "workspace"},
            "shared_artifacts": context.shared_artifacts,
            "target_is_library": True,
        }
    ]
    assert result.diagnostics == (variable_issue,)
    assert result.accesses_by_definition_key == usage_report.accesses_by_definition_key
    assert result.effect_flow_edges == usage_report.effect_flow_edges
    assert result.effect_flow_display_names == usage_report.effect_flow_display_names
    assert result.semantic_diagnostics_by_file == {"Root.s": ("diagnostic",)}
    assert result.semantic_diagnostic_drops == ("drop",)


def test_build_semantic_snapshot_preserves_builder_tuple_contract(monkeypatch):
    definition = SymbolDefinition(
        canonical_path="Root.Output",
        kind="local",
        datatype="INTEGER",
        declaration_module_path=("Root",),
        display_module_path=("Root<BP>",),
    )
    definitions_by_key = {("root", "output"): definition}
    builder_result = (
        object(),
        object(),
        (definition,),
        definitions_by_key,
        {"worker": []},
        {"Root.s": ()},
        {("root", "output"): ()},
        (object(),),
    )
    captured: dict[str, object] = {}

    class _FakeBuilder:
        def __init__(self, base_picture, unavailable_libraries=None):
            captured["builder_base_picture"] = base_picture
            captured["unavailable_libraries"] = unavailable_libraries

        def build(self):
            return builder_result

    def _analysis_provider(base_picture, project_graph, collect_variable_diagnostics, debug, definitions):
        captured["analysis_args"] = {
            "base_picture": base_picture,
            "project_graph": project_graph,
            "collect_variable_diagnostics": collect_variable_diagnostics,
            "debug": debug,
            "definitions": definitions,
        }
        return SemanticAnalysisArtifacts(
            diagnostics=("diagnostic",),
            accesses_by_definition_key={("root", "output"): ("access",)},
            effect_flow_edges={("root", "output"): (("root", "sink"),)},
            effect_flow_display_names={("root", "output"): "Root.Output"},
            semantic_diagnostics_by_file={"Root.s": ("projection",)},
            semantic_diagnostic_drops=("drop",),
        )

    monkeypatch.setattr(semantic_core_module, "SemanticIndexBuilder", _FakeBuilder)

    base_picture = BasePicture(header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)))
    project_graph = SimpleNamespace(unavailable_libraries={"MissingLib"})

    snapshot = semantic_core_module._build_semantic_snapshot(
        base_picture,
        entry_path=Path("/tmp/Root.s"),
        workspace_root=Path("/tmp"),
        discovery=object(),
        project_graph=project_graph,
        collect_variable_diagnostics=True,
        debug=True,
        analysis_provider=_analysis_provider,
    )

    assert captured["builder_base_picture"] is base_picture
    assert captured["unavailable_libraries"] == {"MissingLib"}
    assert captured["analysis_args"] == {
        "base_picture": base_picture,
        "project_graph": project_graph,
        "collect_variable_diagnostics": True,
        "debug": True,
        "definitions": definitions_by_key,
    }
    assert snapshot.symbol_table is builder_result[0]
    assert snapshot.type_graph is builder_result[1]
    assert snapshot.definitions == builder_result[2]
    assert snapshot.call_signatures == builder_result[7]
    assert snapshot._definitions_by_key is builder_result[3]
    assert snapshot._moduletype_index is builder_result[4]
    assert snapshot._references_by_file is builder_result[5]
    assert snapshot._references_by_definition_key is builder_result[6]
    assert snapshot.diagnostics == ("diagnostic",)
    assert snapshot._accesses_by_definition_key == {("root", "output"): ("access",)}
    assert snapshot._effect_flow_edges == {("root", "output"): (("root", "sink"),)}
    assert snapshot._effect_flow_display_names == {("root", "output"): "Root.Output"}
    assert snapshot._semantic_diagnostics_by_file == {"Root.s": ("projection",)}
    assert snapshot._semantic_diagnostic_drops == ("drop",)
