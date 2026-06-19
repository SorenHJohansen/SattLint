# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportMissingTypeArgument=false
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
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import alarm_integrity as alarm_integrity_module
from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.framework import Issue
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _event_detector_typedef(*, with_default_priority: bool) -> ModuleTypeDef:
    severity = Variable(name="Severity", datatype=Simple_DataType.INTEGER)
    if with_default_priority:
        severity = Variable(name="Severity", datatype=Simple_DataType.INTEGER, init_value=2)
    return ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            severity,
            Variable(name="Condition", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )


def test_alarm_integrity_detects_duplicate_tags_across_instances() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="CondA", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CondB", datatype=Simple_DataType.BOOLEAN),
        ],
        moduletype_defs=[_event_detector_typedef(with_default_priority=True)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondA"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondB"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    duplicate_tag_issues = [issue for issue in report.issues if issue.kind == "alarm.duplicate_tag"]
    assert len(duplicate_tag_issues) == 2
    assert all("Unit.Temp.High" in issue.message for issue in duplicate_tag_issues)


def test_alarm_integrity_detects_duplicate_conditions_across_instances() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedCondition", datatype=Simple_DataType.BOOLEAN)],
        moduletype_defs=[_event_detector_typedef(with_default_priority=True)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedCondition"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.Low",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedCondition"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    duplicate_condition_issues = [issue for issue in report.issues if issue.kind == "alarm.duplicate_condition"]
    assert len(duplicate_condition_issues) == 2
    assert all("SharedCondition" in issue.message for issue in duplicate_condition_issues)


def test_alarm_integrity_detects_conflicting_priorities_for_same_tag() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="CondA", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CondB", datatype=Simple_DataType.BOOLEAN),
        ],
        moduletype_defs=[_event_detector_typedef(with_default_priority=False)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Severity"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=1,
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondA"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Severity"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=3,
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondB"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    conflicting_priority_issues = [issue for issue in report.issues if issue.kind == "alarm.conflicting_priority"]
    assert len(conflicting_priority_issues) == 2
    assert all("1" in issue.message and "3" in issue.message for issue in conflicting_priority_issues)


def test_alarm_integrity_detects_never_cleared_alarm_variable() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="AlarmTrip", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("AlarmTrip"), True])],
                )
            ]
        ),
    )

    report = analyze_alarm_integrity(bp)

    never_cleared_issues = [issue for issue in report.issues if issue.kind == "alarm.never_cleared"]
    assert len(never_cleared_issues) == 1
    assert "AlarmTrip" in never_cleared_issues[0].message


def test_alarm_integrity_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "alarm-integrity" in specs
    assert specs["alarm-integrity"].enabled is True


def test_alarm_integrity_report_summary_covers_empty_and_populated_reports() -> None:
    empty_report = alarm_integrity_module.AlarmIntegrityReport(basepicture_name="Root", issues=[])

    assert empty_report.name == "Root"
    empty_summary = empty_report.summary()
    assert "No alarm integrity issues found." in empty_summary

    populated_report = alarm_integrity_module.AlarmIntegrityReport(
        basepicture_name="Root",
        issues=[
            Issue(kind="alarm.never_cleared", message="later", module_path=None),
            Issue(kind="alarm.duplicate_tag", message="first", module_path=["Root", "B"]),
            Issue(kind="alarm.duplicate_tag", message="second", module_path=["Root", "A"]),
        ],
    )

    summary = populated_report.summary()
    assert "Duplicate alarm tags: 2" in summary
    assert "Never-cleared alarm writes: 1" in summary
    assert summary.index("[Root.A] second") < summary.index("[Root.B] first")
    assert "[Root] later" in summary


def test_alarm_integrity_helper_methods_cover_origins_mappings_and_value_formatting(monkeypatch) -> None:  # noqa: PLR0915
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        localvariables=[Variable(name="AlarmFlag", datatype=Simple_DataType.BOOLEAN, init_value=True)],
    )
    analyzer = alarm_integrity_module.AlarmIntegrityAnalyzer(bp)

    assert analyzer._is_from_root_origin(None) is True
    assert analyzer._is_from_root_origin("Root.x") is True
    assert analyzer._is_from_root_origin("Other.s") is False
    bp.origin_file = None
    assert analyzer._is_from_root_origin("Root.s") is False
    bp.origin_file = "Root.s"

    merged_env = analyzer._merge_env(
        {"existing": Variable(name="Existing", datatype=Simple_DataType.INTEGER)}, bp.localvariables
    )
    assert set(merged_env) == {"existing", "alarmflag"}

    typedef = _event_detector_typedef(with_default_priority=True)
    instance = ModuleTypeInstance(
        header=_hdr("AlarmA"),
        moduletype_name="EventDetector1",
        parametermappings=[
            ParameterMapping(
                target=_varref("Tag"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal=" Area.Alarm ",
            ),
            ParameterMapping(
                target=_varref("Condition"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=True,
                source=_varref("GlobalCondition"),
                source_literal=None,
            ),
        ],
    )

    assert analyzer._parameter_names(instance, typedef) == {"tag", "severity", "condition"}
    assert analyzer._pick_parameter_name({"tag", "condition"}, ("priority", "condition")) == "condition"
    assert analyzer._pick_parameter_name({"tag"}, ("priority",)) is None

    literal_value = analyzer._resolve_mapping_value(instance.parametermappings[0], merged_env)
    assert literal_value == alarm_integrity_module._ParameterValue(
        status="resolved",
        value=" Area.Alarm ",
        source="literal parameter mapping",
        signature="literal:area.alarm",
    )
    reference_value = analyzer._resolve_mapping_value(instance.parametermappings[1], merged_env)
    assert reference_value == alarm_integrity_module._ParameterValue(
        status="reference",
        source="GLOBAL GlobalCondition",
        signature="globalcondition",
    )
    init_mapping = ParameterMapping(
        target=_varref("Condition"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("AlarmFlag"),
        source_literal=None,
    )
    assert analyzer._resolve_mapping_value(init_mapping, merged_env) == alarm_integrity_module._ParameterValue(
        status="resolved",
        value=True,
        source="init value of variable AlarmFlag",
        signature="alarmflag",
    )
    dotted_mapping = ParameterMapping(
        target=_varref("Condition"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("Alarm.Flag"),
        source_literal=None,
    )
    assert analyzer._resolve_mapping_value(dotted_mapping, merged_env) == alarm_integrity_module._ParameterValue(
        status="reference",
        source="mapped variable reference Alarm.Flag",
        signature="alarm.flag",
    )
    assert (
        analyzer._resolve_mapping_value(
            ParameterMapping(
                target=_varref("Condition"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=None,
            ),
            merged_env,
        )
        is None
    )

    assert analyzer._find_parameter_mapping(instance.parametermappings, "TAG") is instance.parametermappings[0]
    assert analyzer._find_parameter_mapping(instance.parametermappings, "missing") is None
    assert analyzer._find_variable(typedef.moduleparameters, "severity") is not None
    assert analyzer._find_variable(typedef.moduleparameters, "missing") is None
    assert analyzer._get_parameter_value(instance, typedef, merged_env, "tag") == literal_value
    unresolved_value = analyzer._get_parameter_value(
        ModuleTypeInstance(
            header=_hdr("AlarmB"),
            moduletype_name="EventDetector1",
            parametermappings=[
                ParameterMapping(
                    target=_varref("Condition"),
                    source_type=const.TREE_TAG_VARIABLE_NAME,
                    is_duration=False,
                    is_source_global=False,
                    source=None,
                    source_literal=None,
                )
            ],
        ),
        typedef,
        merged_env,
        "condition",
    )
    assert unresolved_value.status == "unresolved_mapping"
    assert analyzer._get_parameter_value(instance, None, merged_env, "tag").status == "resolved"
    assert analyzer._get_parameter_value(instance, None, merged_env, "severity").status == "unknown"
    assert analyzer._get_parameter_value(
        ModuleTypeInstance(header=_hdr("AlarmC"), moduletype_name="EventDetector1", parametermappings=[]),
        typedef,
        merged_env,
        "severity",
    ).source == ("default parameter value on EventDetector1")
    not_configured_typedef = _event_detector_typedef(with_default_priority=False)
    assert (
        analyzer._get_parameter_value(
            ModuleTypeInstance(header=_hdr("AlarmD"), moduletype_name="EventDetector1", parametermappings=[]),
            not_configured_typedef,
            merged_env,
            "severity",
        ).status
        == "not_configured"
    )

    assert (
        analyzer._tag_key(alarm_integrity_module._ParameterValue(status="resolved", value="  Alarm.Tag  "))
        == "tag:alarm.tag"
    )
    assert analyzer._tag_key(alarm_integrity_module._ParameterValue(status="reference", signature="sig")) == "ref:sig"
    assert analyzer._tag_key(alarm_integrity_module._ParameterValue(status="unknown")) is None
    assert (
        analyzer._tag_display(alarm_integrity_module._ParameterValue(status="resolved", value="  Alarm.Tag  "))
        == "Alarm.Tag"
    )
    assert (
        analyzer._tag_display(
            alarm_integrity_module._ParameterValue(status="reference", source="mapped variable reference A")
        )
        == "mapped variable reference A"
    )
    assert analyzer._tag_display(alarm_integrity_module._ParameterValue(status="reference", signature="sig")) == "sig"
    assert analyzer._priority_key(alarm_integrity_module._ParameterValue(status="resolved", value=2)) == "literal:2"
    assert analyzer._priority_key(alarm_integrity_module._ParameterValue(status="unknown")) is None
    assert (
        analyzer._condition_key(alarm_integrity_module._ParameterValue(status="reference", signature="literal:true"))
        is None
    )
    assert (
        analyzer._condition_key(alarm_integrity_module._ParameterValue(status="reference", signature="cond.ref"))
        == "cond.ref"
    )
    assert (
        analyzer._condition_display(
            alarm_integrity_module._ParameterValue(status="reference", source="mapped variable reference A")
        )
        == "mapped variable reference A"
    )
    assert (
        analyzer._condition_display(alarm_integrity_module._ParameterValue(status="reference", signature="cond.ref"))
        == "cond.ref"
    )
    assert analyzer._value_display(alarm_integrity_module._ParameterValue(status="resolved", value=2)) == "2"
    assert analyzer._value_display(alarm_integrity_module._ParameterValue(status="reference", source="src")) == "src"
    assert analyzer._literal_signature("  Alarm.Tag  ") == "literal:alarm.tag"
    assert analyzer._literal_signature(None) == "literal:None"

    monkeypatch.setattr(
        alarm_integrity_module,
        "resolve_moduletype_def_strict",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("missing")),
    )
    assert analyzer._resolve_moduletype(instance, None) is None


def test_alarm_integrity_candidate_and_issue_emitters_cover_suppression_and_deduping(monkeypatch) -> None:
    bp = BasePicture(header=_hdr("Root"), origin_file="Root.s")
    analyzer = alarm_integrity_module.AlarmIntegrityAnalyzer(bp)
    env = {"conda": Variable(name="CondA", datatype=Simple_DataType.BOOLEAN, init_value=True)}
    typedef = _event_detector_typedef(with_default_priority=True)

    no_tag_instance = ModuleTypeInstance(
        header=_hdr("NoTag"),
        moduletype_name="EventDetector1",
        parametermappings=[
            ParameterMapping(
                target=_varref("Condition"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("CondA"),
                source_literal=None,
            )
        ],
    )
    assert analyzer._collect_alarm_candidate(no_tag_instance, ["Root", "NoTag"], env, None) is None

    no_signal_instance = ModuleTypeInstance(
        header=_hdr("NoSignal"),
        moduletype_name="EventDetector1",
        parametermappings=[
            ParameterMapping(
                target=_varref("Tag"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal="Alarm.Tag",
            )
        ],
    )
    assert analyzer._collect_alarm_candidate(no_signal_instance, ["Root", "NoSignal"], env, None) is None

    instance = ModuleTypeInstance(
        header=_hdr("AlarmA"),
        moduletype_name="EventDetector1",
        parametermappings=[
            ParameterMapping(
                target=_varref("Tag"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal="Alarm.Tag",
            ),
            ParameterMapping(
                target=_varref("Condition"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("CondA"),
                source_literal=None,
            ),
        ],
    )
    monkeypatch.setattr(analyzer, "_resolve_moduletype", lambda *_args, **_kwargs: typedef)
    candidate = analyzer._collect_alarm_candidate(instance, ["Root", "AlarmA"], env, None)
    assert candidate is not None
    assert candidate.moduletype_label == "EventDetector1"
    assert candidate.tag_key == "tag:alarm.tag"
    assert candidate.priority_display == "2"
    assert candidate.condition_display == "init value of variable CondA"
    unknown_type_instance = ModuleTypeInstance(
        header=_hdr("AlarmUnknown"),
        moduletype_name="MissingType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Tag"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source_literal="Alarm.Unknown",
            ),
            ParameterMapping(
                target=_varref("Condition"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("CondA"),
                source_literal=None,
            ),
        ],
    )
    monkeypatch.setattr(analyzer, "_resolve_moduletype", lambda *_args, **_kwargs: None)
    unknown_candidate = analyzer._collect_alarm_candidate(unknown_type_instance, ["Root", "AlarmUnknown"], env, None)
    assert unknown_candidate is not None
    assert unknown_candidate.moduletype_label == "MissingType"
    suppressed_candidate = analyzer._collect_alarm_candidate(
        ModuleTypeInstance(
            header=_hdr("Suppressed"),
            moduletype_name="MissingType",
            parametermappings=[
                ParameterMapping(
                    target=_varref("Tag"),
                    source_type=const.TREE_TAG_VARIABLE_NAME,
                    is_duration=False,
                    is_source_global=False,
                    source=None,
                    source_literal=None,
                ),
                ParameterMapping(
                    target=_varref("Condition"),
                    source_type=const.TREE_TAG_VARIABLE_NAME,
                    is_duration=False,
                    is_source_global=False,
                    source=None,
                    source_literal=None,
                ),
            ],
        ),
        ["Root", "Suppressed"],
        env,
        None,
    )
    assert suppressed_candidate is None
    assert analyzer._get_parameter_value(instance, typedef, env, "missing").status == "unknown"
    assert analyzer._condition_key(alarm_integrity_module._ParameterValue(status="unknown")) is None
    assert (
        analyzer._condition_key(alarm_integrity_module._ParameterValue(status="reference", signature="literal:none"))
        is None
    )

    analyzer._candidates = [
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "Ignored"],
            instance_name="Ignored",
            moduletype_label="EventDetector1",
            tag_key="tag:ignored",
            tag_display="Ignored",
            priority_key=None,
            priority_display=None,
            condition_key="ref:ignored",
            condition_display="IgnoredCond",
        ),
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "AlarmA"],
            instance_name="AlarmA",
            moduletype_label="EventDetector1",
            tag_key="tag:alarm.tag",
            tag_display="Alarm.Tag",
            priority_key="literal:1",
            priority_display="1",
            condition_key="ref:conda",
            condition_display="CondA",
        ),
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "AlarmB"],
            instance_name="AlarmB",
            moduletype_label="EventDetector1",
            tag_key="tag:alarm.tag",
            tag_display=None,
            priority_key="literal:2",
            priority_display=None,
            condition_key="ref:conda",
            condition_display=None,
        ),
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "AlarmC"],
            instance_name="AlarmC",
            moduletype_label="EventDetector1",
            tag_key=None,
            tag_display=None,
            priority_key="literal:3",
            priority_display="3",
            condition_key="ref:missingdisplay",
            condition_display=None,
        ),
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "AlarmD"],
            instance_name="AlarmD",
            moduletype_label="EventDetector1",
            tag_key=None,
            tag_display=None,
            priority_key="literal:4",
            priority_display="4",
            condition_key="ref:missingdisplay",
            condition_display=None,
        ),
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "AlarmA"],
            instance_name="AlarmAClone",
            moduletype_label="EventDetector1",
            tag_key="tag:alarm.alt",
            tag_display="Alarm.Alt",
            priority_key="literal:5",
            priority_display="5",
            condition_key=None,
            condition_display=None,
        ),
        alarm_integrity_module._AlarmCandidate(
            module_path=["Root", "AlarmB"],
            instance_name="AlarmBClone",
            moduletype_label="EventDetector1",
            tag_key="tag:alarm.alt",
            tag_display="Alarm.Alt",
            priority_key="literal:6",
            priority_display="6",
            condition_key=None,
            condition_display=None,
        ),
    ]
    analyzer._emit_duplicate_tag_issues()
    analyzer._emit_duplicate_condition_issues()
    analyzer._emit_conflicting_priority_issues()
    conflict_issues = [issue for issue in analyzer.issues if issue.kind == "alarm.conflicting_priority"]
    assert len(conflict_issues) == 6
    assert any("Alarm condition 'ref:missingdisplay'" in issue.message for issue in conflict_issues)
    assert analyzer._location_list(analyzer._candidates) == [
        "Root.AlarmA",
        "Root.AlarmB",
        "Root.AlarmC",
        "Root.AlarmD",
        "Root.Ignored",
    ]


def test_alarm_integrity_run_walks_supported_nodes_and_module_code_filters_clear_writes(monkeypatch) -> None:
    typedef = ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            Variable(name="Severity", datatype=Simple_DataType.INTEGER, init_value=2),
            Variable(name="Condition", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[Variable(name="TypeFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[]),
        parametermappings=[],
        origin_file="Root.s",
    )
    foreign_typedef = ModuleTypeDef(
        name="ForeignDetector",
        moduleparameters=[Variable(name="Tag", datatype=Simple_DataType.TAGSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[]),
        parametermappings=[],
        origin_file="Other.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        localvariables=[Variable(name="RootFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[
            SingleModule(
                header=_hdr("Single"),
                moduledef=None,
                moduleparameters=[Variable(name="SingleParam", datatype=Simple_DataType.INTEGER)],
                localvariables=[Variable(name="SingleLocal", datatype=Simple_DataType.BOOLEAN)],
                submodules=[],
                modulecode=ModuleCode(equations=[]),
                parametermappings=[],
            ),
            FrameModule(header=_hdr("Frame"), modulecode=ModuleCode(equations=[]), submodules=[]),
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Alarm.Tag",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("RootFlag"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        moduletype_defs=[typedef, foreign_typedef],
        modulecode=ModuleCode(equations=[]),
    )
    analyzer = alarm_integrity_module.AlarmIntegrityAnalyzer(bp)
    visited_paths: list[tuple[str, ...]] = []

    def _record_module_code(_modulecode, module_path, _env):
        visited_paths.append(tuple(module_path))

    monkeypatch.setattr(analyzer, "_check_module_code", _record_module_code)
    monkeypatch.setattr(
        analyzer,
        "_collect_alarm_candidate",
        lambda inst, module_path, *_args, **_kwargs: alarm_integrity_module._AlarmCandidate(
            module_path=module_path.copy(),
            instance_name=inst.header.name,
            moduletype_label=inst.moduletype_name,
            tag_key="tag:alarm.tag",
            tag_display="Alarm.Tag",
            priority_key="literal:1",
            priority_display="1",
            condition_key="ref:rootflag",
            condition_display="RootFlag",
        ),
    )
    monkeypatch.setattr(
        analyzer,
        "_emit_duplicate_tag_issues",
        lambda: analyzer._issues.append(Issue(kind="alarm.duplicate_tag", message="tag")),
    )
    monkeypatch.setattr(
        analyzer,
        "_emit_duplicate_condition_issues",
        lambda: analyzer._issues.append(Issue(kind="alarm.duplicate_condition", message="cond")),
    )
    monkeypatch.setattr(
        analyzer,
        "_emit_conflicting_priority_issues",
        lambda: analyzer._issues.append(Issue(kind="alarm.conflicting_priority", message="prio")),
    )

    issues = analyzer.run()

    assert [tuple(path) for path in visited_paths] == [
        ("Root",),
        ("Root", "Single"),
        ("Root", "Frame"),
        ("Root", "TypeDef:EventDetector1"),
    ]
    assert {issue.kind for issue in issues} == {
        "alarm.duplicate_tag",
        "alarm.duplicate_condition",
        "alarm.conflicting_priority",
    }
    assert len(analyzer._candidates) == 1

    real_analyzer = alarm_integrity_module.AlarmIntegrityAnalyzer(bp)
    monkeypatch.setattr(
        alarm_integrity_module,
        "_collect_alarm_boolean_writes",
        lambda *_args, **_kwargs: {
            "trip": type("Entry", (), {"values": {True}, "display": "AlarmTrip"})(),
            "cleared": type("Entry", (), {"values": {True, False}, "display": "AlarmCleared"})(),
            "false_only": type("Entry", (), {"values": {False}, "display": "AlarmFalse"})(),
        },
    )
    real_analyzer._check_module_code(None, ["Root"], {})
    real_analyzer._check_module_code(ModuleCode(equations=[]), ["Root"], {})
    assert [issue.kind for issue in real_analyzer.issues] == ["alarm.never_cleared"]
