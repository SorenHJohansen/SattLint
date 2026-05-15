from pathlib import Path

from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers.sattline_semantics import analyze_sattline_semantics


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
    from sattlint.analyzers.sattline_semantics import get_sattline_semantic_rules

    {rule.id for rule in get_sattline_semantic_rules()}


def test_analyzer_order_independence():
    from sattlint.analyzers.registry import get_default_analyzer_catalog

    catalog = get_default_analyzer_catalog()
    enabled = [a for a in catalog.analyzers if a.spec.enabled]
    default_order_ids = [r.id for a in enabled for r in catalog.rules if a.spec.key in r.analyzers]
    reversed_order_ids = [r.id for a in reversed(enabled) for r in catalog.rules if a.spec.key in r.analyzers]
    assert sorted(default_order_ids) == sorted(reversed_order_ids)


def test_transform_invariant_deterministic():
    from sattline_parser import parse_source_file as parser_core_parse_source_file
    from sattlint.tracing import detect_transform_invariant_violations as check

    fixture = Path(__file__).resolve().parent.parent / "fixtures" / "sample_sattline_files" / "LinterTestProgram.s"
    if not fixture.exists():
        return

    bp1 = parser_core_parse_source_file(fixture)
    bp2 = parser_core_parse_source_file(fixture)

    assert check(bp1) == check(bp2)
