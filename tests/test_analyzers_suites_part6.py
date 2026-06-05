# ruff: noqa: F403, F405
from ._analyzers_suites_test_support import *


def test_module_localvar_field_report_includes_filtered_summary_sections():
    record_type = DataType(
        name="UsageRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Target", datatype=Simple_DataType.INTEGER),
        ],
    )
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Input", datatype="UsageRecord")],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ChildEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Input.Target"), IntLiteral(2)),
                    ],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("Dv"),
                source_literal=None,
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[
                    Variable(name="Dv", datatype="UsageRecord"),
                    Variable(name="Mirror", datatype="UsageRecord"),
                    Variable(name="Sink", datatype=Simple_DataType.INTEGER),
                ],
                submodules=[child],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="Usage",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("Sink"), _varref("Dv.Source")),
                                (const.KEY_ASSIGN, _varref("Dv.Target"), IntLiteral(1)),
                                (const.KEY_ASSIGN, _varref("Mirror"), _varref("Dv")),
                                (const.KEY_ASSIGN, _varref("Dv"), _varref("Mirror")),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    report = report_module_localvar_fields(bp, "Unit", "Dv")

    assert "Field usage analysis for local variable 'Dv' in module path 'Root.Unit'" in report
    assert "FIELD-LEVEL ACCESSES:" in report
    assert "dv.source [read]" in report.lower()
    assert "dv.target [write]" in report.lower()
    assert "WHOLE VARIABLE ACCESSES:" in report
    assert "Reads (1 total, 1 unique location(s))" in report
    assert "SUMMARY:" in report
    assert "Aliased parameters: 2" in report
    assert "Fields accessed: 2" in report
    assert "Total field reads: 1" in report
    assert "Total field writes: 3" in report
    assert "Whole variable reads: 1" in report
    assert "Whole variable writes: 2" in report


def test_find_module_instances_includes_direct_and_typedef_expansions():
    parent_typedef = ModuleTypeDef(
        name="ParentType",
        moduleparameters=[],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("WantedAlias"),
                moduletype_name="WantedType",
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[parent_typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("DirectWanted"),
                moduletype_name="WantedType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("ParentInstance"),
                moduletype_name="ParentType",
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    results = _find_module_instances(bp, "WantedType")
    paths = {tuple(path) for _module, path in results}

    assert ("Root", "DirectWanted") in paths
    assert ("Root", "ParentInstance", "WantedAlias") in paths


def test_module_diff_helpers_detect_modified_and_variant_only_names():
    variant_items = [
        {
            "alpha": ("Alpha", ("int", 1)),
            "beta": ("Beta", ("int", 2)),
        },
        {
            "alpha": ("Alpha", ("int", 3)),
            "gamma": ("Gamma", ("int", 4)),
        },
    ]

    common, only_in_variant, modified = _collect_named_item_diffs(variant_items)

    assert common == ["Alpha"]
    assert only_in_variant == {1: ["Beta"], 2: ["Gamma"]}
    assert "Alpha" in modified


def test_module_ast_normalizer_casefolds_names_and_ignores_position_fields():
    normalized_dict = _normalize_ast_value(
        {
            "var_name": "MiXeD",
            "state": "NeW",
            "position": (1.0, 2.0),
        }
    )
    normalized_var = _normalize_ast_value(Variable(name="FlowRate", datatype=Simple_DataType.INTEGER))

    assert "position" not in repr(normalized_dict)
    assert "mixed" in repr(normalized_dict)
    assert "new" in repr(normalized_dict)
    assert "flowrate" in repr(normalized_var)


def test_module_diff_helpers_report_nested_variant_details_and_missing_items():
    variants = {
        1: _normalize_ast_value({"Config": [{"Mode": "Auto"}]}),
        2: _normalize_ast_value({"Config": [{"Mode": "Manual"}, {"Enabled": True}]}),
    }

    details = _diff_normalized_variants(variants)

    paths = {detail.path for detail in details}
    assert "Config[0].Mode" in paths
    assert "Config[1]" in paths
    detail_map = {detail.path: detail.variants for detail in details}
    assert detail_map["Config[1]"][1] == "<missing>"


def test_module_comparison_summary_covers_empty_and_single_variant_reports():
    empty_summary = ComparisonResult(module_name="Pump", total_found=0, unique_variants=0).summary()

    module = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    fingerprint = create_fingerprint(module, ["Root", "Pump"])
    single_summary = ComparisonResult(
        module_name="Pump",
        total_found=1,
        unique_variants=1,
        fingerprints=[fingerprint],
        all_instances=[(["Root", "Pump"], fingerprint)],
    ).summary()

    assert "No modules found with this name" in empty_summary
    assert "All instances are structurally identical" in single_summary
    assert "DateCode: None - Root" in single_summary


def test_module_comparison_summary_lists_variant_differences():
    variant_a = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[Variable(name="CommonParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="OnlyA", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("OnlyA"), IntLiteral(1))],
                )
            ]
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[Variable(name="CommonParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="OnlyB", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="OtherEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("OnlyB"), IntLiteral(2))],
                )
            ]
        ),
        parametermappings=[],
    )
    fingerprint_a = create_fingerprint(variant_a, ["Root", "PumpA"])
    fingerprint_b = create_fingerprint(variant_b, ["Root", "PumpB"])

    summary = ComparisonResult(
        module_name="Pump",
        total_found=2,
        unique_variants=2,
        fingerprints=[fingerprint_a, fingerprint_b],
        all_instances=[(["Root", "PumpA"], fingerprint_a), (["Root", "PumpB"], fingerprint_b)],
        parameter_diff=VariableDiff(common=["CommonParam"], only_in_variant={1: [], 2: []}),
        localvar_diff=VariableDiff(common=[], only_in_variant={1: ["OnlyA"], 2: ["OnlyB"]}),
        submodule_diff=SubmoduleDiff(common=[(0, "SharedChild", "Single")], only_in_variant={1: [], 2: []}),
        code_diff=CodeDiff(
            sequences_common=[],
            sequences_only_in_variant={1: [], 2: []},
            equations_common=[],
            equations_only_in_variant={1: ["MainEq"], 2: ["OtherEq"]},
        ),
    ).summary()

    assert "Found 2 different structural variants" in summary
    assert "Module Parameters Differences" in summary
    assert "Local Variables Differences" in summary
    assert "Submodules Differences (Recursive Tree)" in summary
    assert "Equations Only in Variant 1 (1): ['MainEq']" in summary


def test_module_diff_compaction_and_upgrade_notes_cover_modified_buckets():
    parameter_diff = VariableDiff(
        common=["SharedParam"],
        only_in_variant={1: ["OnlyParam"], 2: []},
        modified={
            "SharedParam": [
                AstDiffDetail(path="datatype", variants={1: "'INTEGER'", 2: "'REAL'"}),
            ]
        },
    )
    localvar_diff = VariableDiff(
        common=[],
        only_in_variant={1: [], 2: ["OnlyLocal"]},
        modified={
            "SharedLocal": [
                AstDiffDetail(path="init_value", variants={1: "1", 2: "2"}),
            ]
        },
    )
    submodule_diff = SubmoduleDiff(
        common=[(0, "SharedChild", "Single")],
        only_in_variant={1: [(1, "OnlyChild", "Frame")], 2: []},
    )
    code_diff = CodeDiff(
        sequences_common=["SharedSeq"],
        sequences_only_in_variant={1: ["OnlySeq"], 2: []},
        equations_common=["SharedEq"],
        equations_only_in_variant={1: [], 2: ["OnlyEq"]},
        modified_sequences={
            "SharedSeq": [
                AstDiffDetail(path="code[0]", variants={1: "'Auto'", 2: "'Manual'"}),
            ]
        },
        modified_equations={
            "SharedEq": [
                AstDiffDetail(path="code[1]", variants={1: "1", 2: "2"}),
            ]
        },
    )

    compact_parameter = _compact_diff(parameter_diff)
    compact_localvar = _compact_diff(localvar_diff)
    compact_submodule = _compact_diff(submodule_diff)
    compact_code = _compact_diff(code_diff)
    notes = _build_upgrade_notes(
        {
            "moduleparameters": compact_parameter,
            "localvariables": compact_localvar,
            "submodules": compact_submodule,
            "code": compact_code,
        }
    )

    assert compact_parameter is not None
    assert compact_parameter["modified"]["SharedParam"][0]["path"] == "datatype"
    assert compact_localvar is not None
    assert compact_localvar["only_in_variant"] == {2: ["OnlyLocal"]}
    assert compact_submodule is not None
    assert compact_submodule["only_in_variant"] == {1: [[1, "OnlyChild", "Frame"]]}
    assert compact_code is not None
    assert compact_code["modified_sequences"]["SharedSeq"][0]["path"] == "code[0]"
    assert _compact_diff(SubmoduleDiff(common=[], only_in_variant={1: [], 2: []})) is None
    assert any(note == "Module parameters only in variant 1: OnlyParam." for note in notes)
    assert any(note == "Module parameter 'SharedParam' changed across variants 1, 2 at datatype." for note in notes)
    assert any(note == "Local variables only in variant 2: OnlyLocal." for note in notes)
    assert any(note == "Sequence 'SharedSeq' changed across variants 1, 2 at code[0]." for note in notes)
    assert any(note == "Equations only in variant 2: OnlyEq." for note in notes)
    assert any(note == "Submodule structure differs in variant 1: 1 unique node(s)." for note in notes)


def test_module_variant_grouping_collapses_identical_structures_and_common_prefix():
    shared_a = SingleModule(
        header=_hdr("Pump"),
        datecode=100,
        moduledef=None,
        moduleparameters=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    shared_b = SingleModule(
        header=_hdr("Pump"),
        datecode=200,
        moduledef=None,
        moduleparameters=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    drifted = SingleModule(
        header=_hdr("Pump"),
        datecode=300,
        moduledef=None,
        moduleparameters=[Variable(name="Shared", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="OnlyHere", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    comparison = compare_modules(
        [
            (["Root", "Area", "PumpA"], shared_a),
            (["root", "area", "PumpB"], shared_b),
            (["Root", "Other", "PumpC"], drifted),
        ]
    )
    grouped = _group_instances_by_variant(comparison)

    assert comparison.unique_variants == 2
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1
    assert _common_module_prefix(
        [["Root", "Area", "PumpA"], ["root", "area", "PumpB"], ["Root", "Other", "PumpC"]]
    ) == ["Root"]


def test_sfc_guard_signature_collapses_contradictory_and_expression_to_false():
    signature = _normalize_guard_signature(
        (
            const.GRAMMAR_VALUE_AND,
            [
                _varref("Permit"),
                (const.GRAMMAR_VALUE_NOT, _varref("Permit")),
            ],
        )
    )

    assert signature == ("bool", False)
