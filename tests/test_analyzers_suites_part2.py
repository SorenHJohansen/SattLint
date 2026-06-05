# ruff: noqa: F403, F405
from ._analyzers_suites_test_support import *


def test_dataflow_flags_contradictory_branch_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (
                                        const.GRAMMAR_VALUE_AND,
                                        [
                                            _varref("Flag"),
                                            (const.GRAMMAR_VALUE_NOT, _varref("Flag")),
                                        ],
                                    ),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("Output"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [
                                (
                                    const.KEY_ASSIGN,
                                    _varref("Output"),
                                    False,
                                )
                            ],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert "dataflow.condition_always_false" in _issue_kinds(report)
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_dataflow_flags_impossible_inferred_compare_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (
                                        const.GRAMMAR_VALUE_AND,
                                        [
                                            (
                                                const.KEY_COMPARE,
                                                _varref("Counter"),
                                                [("==", 1)],
                                            ),
                                            (
                                                const.KEY_COMPARE,
                                                _varref("Counter"),
                                                [("==", 2)],
                                            ),
                                        ],
                                    ),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("Output"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    impossible_conditions = [
        issue
        for issue in report.issues
        if issue.kind == "dataflow.condition_always_false"
        and issue.data is not None
        and "Counter == 1" in str(issue.data.get("condition"))
        and "Counter == 2" in str(issue.data.get("condition"))
    ]

    assert impossible_conditions
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_sfc_parallel_write_race_detected_for_record_field_overlap():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCParallel(
                branches=[
                    [
                        SFCStep(
                            kind="step",
                            name="Left",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Rec"), 1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Rec.Field"), 2)]),
                        )
                    ],
                ]
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[
            DataType(
                name="RecType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Field", datatype=Simple_DataType.INTEGER)],
            )
        ],
        localvariables=[Variable(name="Rec", datatype="RecType")],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
        moduledef=None,
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == ["Root.Rec"]


def test_sfc_transition_logic_detects_always_true_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="AlwaysOpen",
                condition=(
                    const.GRAMMAR_VALUE_OR,
                    [_varref("Permit"), (const.GRAMMAR_VALUE_NOT, _varref("Permit"))],
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_transition_always_true"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_name"] == "AlwaysOpen"


def test_sfc_transition_logic_detects_always_false_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="NeverOpen",
                condition=(
                    const.GRAMMAR_VALUE_AND,
                    [_varref("Permit"), (const.GRAMMAR_VALUE_NOT, _varref("Permit"))],
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_transition_always_false"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_name"] == "NeverOpen"


def test_sfc_transition_logic_detects_duplicate_guards_after_normalization():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="OpenPrimary",
                condition=(const.GRAMMAR_VALUE_AND, [_varref("Permit"), _varref("Ready")]),
            ),
            SFCTransition(
                name="OpenBackup",
                condition=(const.GRAMMAR_VALUE_AND, [_varref("Ready"), _varref("Permit")]),
            ),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Permit", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Ready", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_duplicate_transition_guard"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_names"] == ["OpenPrimary", "OpenBackup"]


def test_version_drift_detects_small_code_delta_between_same_named_modules():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 2)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["module_name"] == "Mixer"
    assert issues[0].data["unique_variants"] == 2
    assert "code" in issues[0].data["material_differences"]
    assert "modified_equations" in issues[0].data["material_differences"]["code"]
    assert "Logic" in issues[0].data["material_differences"]["code"]["modified_equations"]
    assert issues[0].data["material_differences"]["code"]["modified_equations"]["Logic"]
    assert any("Equation 'Logic' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_records_modified_variable_shape_diffs():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.REAL)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert "localvariables" in issues[0].data["material_differences"]
    assert "Output" in issues[0].data["material_differences"]["localvariables"]["modified"]
    assert any(
        detail["path"] == "datatype"
        for detail in issues[0].data["material_differences"]["localvariables"]["modified"]["Output"]
    )
    assert any("Local variable 'Output' changed" in note for note in issues[0].data["upgrade_notes"])
