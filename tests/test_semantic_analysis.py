# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportReturnType=false
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint import constants as const
from sattlint import semantic_analysis as semantic_analysis_module
from sattlint.core import semantic as semantic_core_module
from sattlint.core._semantic_snapshot import SemanticAnalysisArtifacts, SymbolDefinition
from sattlint.core.diagnostics import DroppedDiagnosticIssue
from sattlint.reporting.variables_report import IssueKind, VariableIssue, VariablesReport

pytestmark = pytest.mark.unit


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name, "span": SourceSpan(1, 1)}


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
        dropped_issues=(
            DroppedDiagnosticIssue(
                analyzer_key="variables",
                reason="missing-definition",
                module_path=("Root",),
                variable_name="UnusedVar",
                message="drop",
            ),
        ),
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
    assert result.semantic_diagnostic_drops == projection_result.dropped_issues


def test_build_variable_semantic_artifacts_logs_dropped_projection_issues(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    variable_issue = VariableIssue(
        kind=IssueKind.UNUSED,
        module_path=["Root"],
        variable=Variable(name="UnusedVar", datatype=Simple_DataType.INTEGER),
    )
    usage_report = VariablesReport(basepicture_name="Root", issues=[])
    diagnostics_report = VariablesReport(basepicture_name="Root", issues=[variable_issue])
    dropped_issue = DroppedDiagnosticIssue(
        analyzer_key="variables",
        reason="missing-definition",
        module_path=("Root",),
        variable_name="UnusedVar",
        message="missing definition",
    )

    monkeypatch.setattr(semantic_analysis_module, "get_registry_analyzer_spec", lambda key: SimpleNamespace(key=key))
    monkeypatch.setattr(
        semantic_analysis_module,
        "run_registry_analyzer",
        lambda spec, _context, *, overrides=None: usage_report if overrides else diagnostics_report,
    )
    monkeypatch.setattr(semantic_analysis_module, "project_variable_issues", lambda diagnostics, _defs: diagnostics)
    monkeypatch.setattr(
        semantic_analysis_module,
        "_project_lsp_report_diagnostics",
        lambda *_args, **_kwargs: "lsp-projection",
    )
    monkeypatch.setattr(
        semantic_analysis_module,
        "merge_diagnostic_projection_results",
        lambda *reports: SimpleNamespace(
            diagnostics_by_file={"Root.s": ("diagnostic",)},
            dropped_issues=(dropped_issue,),
        ),
    )

    with caplog.at_level(logging.WARNING, logger="SattLint"):
        result = semantic_analysis_module.build_variable_semantic_artifacts(
            BasePicture(header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))),
            SimpleNamespace(unavailable_libraries=set()),
            collect_variable_diagnostics=True,
            debug=False,
            definitions_by_key={},
        )

    assert result.semantic_diagnostic_drops == (dropped_issue,)
    assert "Dropped 1 semantic diagnostic issue(s) during projection." in caplog.messages
    assert any("reason=missing-definition" in message for message in caplog.messages)


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


def test_build_source_snapshot_from_basepicture_exercises_full_semantic_pipeline(tmp_path: Path) -> None:
    entry_file = tmp_path / "Program" / "Main.s"
    base_picture = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[
            ModuleTypeDef(
                name="WorkerType",
                moduleparameters=[
                    Variable(
                        name="MappedInput",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(20, 9),
                    )
                ],
                localvariables=[
                    Variable(
                        name="TypedOutput",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(21, 9),
                    ),
                    Variable(
                        name="TypedStatus",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(22, 9),
                    ),
                ],
                submodules=[],
                moduledef=None,
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="TypedEq",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (
                                    const.KEY_ASSIGN,
                                    _varref("TypedOutput"),
                                    _varref("MappedInput"),
                                ),
                                (
                                    const.KEY_FUNCTION_CALL,
                                    "CopyVariable",
                                    [_varref("MappedInput"), _varref("TypedOutput"), _varref("TypedStatus")],
                                ),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
                origin_file=entry_file.name,
                origin_lib="Program",
            )
        ],
        localvariables=[
            Variable(
                name="SharedInput",
                datatype=Simple_DataType.INTEGER,
                declaration_span=SourceSpan(5, 5),
            ),
            Variable(
                name="Orphan",
                datatype=Simple_DataType.INTEGER,
                declaration_span=SourceSpan(6, 5),
            ),
        ],
        submodules=[
            SingleModule(
                header=_hdr("SingleWorker"),
                moduleparameters=[
                    Variable(
                        name="Input",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(10, 9),
                    )
                ],
                localvariables=[
                    Variable(
                        name="SingleOutput",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(11, 9),
                    ),
                    Variable(
                        name="SingleStatus",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(12, 9),
                    ),
                    Variable(
                        name="SingleUnused",
                        datatype=Simple_DataType.INTEGER,
                        declaration_span=SourceSpan(13, 9),
                    ),
                ],
                submodules=[],
                moduledef=None,
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="SingleEq",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (
                                    const.KEY_ASSIGN,
                                    _varref("SingleOutput"),
                                    _varref("Input"),
                                ),
                                (
                                    const.KEY_FUNCTION_CALL,
                                    "CopyVariable",
                                    [_varref("Input"), _varref("SingleOutput"), _varref("SingleStatus")],
                                ),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            ),
            FrameModule(
                header=_hdr("AreaFrame"),
                moduledef=None,
                modulecode=None,
                submodules=[
                    ModuleTypeInstance(
                        header=_hdr("TypedWorker"),
                        moduletype_name="WorkerType",
                        parametermappings=[
                            ParameterMapping(
                                target=_varref("MappedInput"),
                                source_type=const.TREE_TAG_VARIABLE_NAME,
                                is_duration=False,
                                is_source_global=False,
                                source=_varref("SharedInput"),
                                source_literal=None,
                            )
                        ],
                    )
                ],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    snapshot = semantic_core_module.build_source_snapshot_from_basepicture(
        base_picture,
        entry_file,
        workspace_root=tmp_path,
        collect_variable_diagnostics=True,
        _analysis_provider=semantic_analysis_module.build_variable_semantic_artifacts,
    )
    snapshot_dict = snapshot.to_snapshot_dict()

    canonical_paths = {definition["canonical_path"] for definition in snapshot_dict["definitions"]}
    assert "BasePicture.SharedInput" in canonical_paths
    assert "BasePicture.SingleWorker.SingleOutput" in canonical_paths
    assert "BasePicture.AreaFrame.TypedWorker.TypedOutput" in canonical_paths

    typed_references = snapshot.find_references_to("TypedOutput")
    single_references = snapshot.find_references_to("SingleOutput")
    assert typed_references
    assert single_references
    assert all(reference.source_file == entry_file.name for reference in typed_references)
    assert all(reference.source_file == entry_file.name for reference in single_references)

    call_paths = {tuple(call["module_path"]) for call in snapshot_dict["call_signatures"]}
    assert ("BasePicture", "SingleWorker") in call_paths
    assert ("BasePicture", "AreaFrame", "TypedWorker") in call_paths

    assert any(
        issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name == "SingleUnused"
        for issue in snapshot.diagnostics
    )
    semantic_diagnostics = snapshot.semantic_diagnostics_for_path(entry_file)
    assert any("Unused variable" in diagnostic.message for diagnostic in semantic_diagnostics)
    root_origin = snapshot.project_graph.root_origin_for_name("BasePicture")
    assert root_origin is not None
    assert root_origin.source_path == entry_file.resolve()
    assert root_origin.library_name == "Program"
    assert snapshot_dict["semantic_diagnostic_drop_count"] == len(snapshot.semantic_diagnostic_drops())
    assert snapshot_dict["semantic_diagnostic_drop_count"] > 0
    assert any(
        drop["reason"] in {"missing-module-site", "missing-definition", "missing-variable"}
        for drop in snapshot_dict["semantic_diagnostic_drops"]
    )
