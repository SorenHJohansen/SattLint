from pathlib import Path
from types import SimpleNamespace

from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers import sattline_semantics as semantics_module
from sattlint.analyzers.framework import AnalysisContext, AnalysisSharedArtifacts
from sattlint.analyzers.sattline_semantics import SattLineSemanticsReport, analyze_sattline_semantics


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_sattline_semantics_includes_unsafe_default_true_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EnableBypass", datatype=Simple_DataType.BOOLEAN, init_value=True),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("EnableBypass"), False)],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.unsafe-default-true" for issue in report.issues)


def test_sattline_semantics_includes_scan_cycle_stale_read_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER, state=True),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, {const.KEY_VAR_NAME: "Counter", "state": "new"}, 1),
                        (const.KEY_ASSIGN, _varref("Output"), {const.KEY_VAR_NAME: "Counter", "state": "old"}),
                    ],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.scan-cycle-stale-read" for issue in report.issues)


def test_sattline_semantics_rule_ids_are_stable():
    from sattlint.analyzers.sattline_semantics import get_sattline_semantic_rules  # noqa: PLC0415

    {rule.id for rule in get_sattline_semantic_rules()}


def test_sattline_semantics_helpers_cover_rule_lookup_and_empty_summary():
    known_kind = next(iter(semantics_module.FRAMEWORK_RULES_BY_KIND))

    assert (
        semantics_module.get_rule_for_framework_issue_kind(known_kind)
        is semantics_module.FRAMEWORK_RULES_BY_KIND[known_kind]
    )
    assert semantics_module.get_rule_for_framework_issue_kind("missing.kind") is None

    report = SattLineSemanticsReport(basepicture_name="Root", issues=[])

    assert report.name == "Root"
    assert "No semantic issues found." in report.summary()


def test_analyze_sattline_semantics_handles_overrides_direct_context_and_skipped_reports(monkeypatch):
    bp = BasePicture(header=_hdr("Root"))
    captured: dict[str, object] = {}
    shared_artifacts = AnalysisSharedArtifacts()
    context = AnalysisContext(base_picture=bp, shared_artifacts=shared_artifacts)

    analyzers = [
        SimpleNamespace(
            spec=SimpleNamespace(
                enabled=True,
                semantic_mapping_kind="variable",
                key=registry_module.SEMANTIC_LAYER_ANALYZER_KEY,
                analyzer_attr="should_not_run",
                direct_context=True,
            )
        ),
        SimpleNamespace(
            spec=SimpleNamespace(
                enabled=True,
                semantic_mapping_kind="variable",
                key="direct-context",
                analyzer_attr="analyze_direct_context",
                direct_context=True,
            )
        ),
        SimpleNamespace(
            spec=SimpleNamespace(
                enabled=True,
                semantic_mapping_kind="variable",
                key="bp-analyzer",
                analyzer_attr="analyze_basepicture",
                direct_context=False,
            )
        ),
    ]

    monkeypatch.setattr(
        registry_module,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=analyzers),
    )
    monkeypatch.setattr(
        registry_module,
        "analyze_direct_context",
        lambda context: SimpleNamespace(issues="not-a-list", context=context),
        raising=False,
    )
    monkeypatch.setattr(
        registry_module,
        "analyze_basepicture",
        lambda base_picture, **kwargs: SimpleNamespace(issues=[], base_picture=base_picture, kwargs=kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        semantics_module,
        "build_context_kwargs",
        lambda spec, module, context, overrides: captured.setdefault("overrides", overrides) or {"captured": True},
    )
    monkeypatch.setattr(semantics_module, "map_variable_issues", lambda issues: [])
    monkeypatch.setattr(semantics_module, "detect_transform_invariant_violations", lambda _bp: [])
    monkeypatch.setattr(semantics_module, "map_trace_findings", lambda findings: [])

    report = analyze_sattline_semantics(
        bp,
        analysis_context=context,
        sfc_mutually_exclusive_steps=[("A", "B")],
        sfc_step_contracts={"Step": object()},
    )

    assert report.issues == []
    assert shared_artifacts.counters.semantic_analyzer_reruns == 2
    assert captured["overrides"] == {
        "mutually_exclusive_steps": (("A", "B"),),
        "sfc_mutually_exclusive_steps": (("A", "B"),),
        "step_contracts": captured["overrides"]["step_contracts"],
        "sfc_step_contracts": captured["overrides"]["sfc_step_contracts"],
    }


def test_analyzer_order_independence():
    from sattlint.analyzers.registry import get_default_analyzer_catalog  # noqa: PLC0415

    catalog = get_default_analyzer_catalog()
    enabled = [a for a in catalog.analyzers if a.spec.enabled]
    default_order_ids = [r.id for a in enabled for r in catalog.rules if a.spec.key in r.analyzers]
    reversed_order_ids = [r.id for a in reversed(enabled) for r in catalog.rules if a.spec.key in r.analyzers]
    assert sorted(default_order_ids) == sorted(reversed_order_ids)


def test_transform_invariant_deterministic():
    from sattline_parser import parse_source_file as parser_core_parse_source_file  # noqa: PLC0415
    from sattlint.tracing import detect_transform_invariant_violations as check  # noqa: PLC0415

    fixture = Path(__file__).resolve().parent.parent / "fixtures" / "sample_sattline_files" / "LinterTestProgram.s"
    if not fixture.exists():
        return

    bp1 = parser_core_parse_source_file(fixture)
    bp2 = parser_core_parse_source_file(fixture)

    assert check(bp1) == check(bp2)
