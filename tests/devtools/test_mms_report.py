from sattlint.analyzers.framework import Issue
from sattlint.reporting.mms_report import MMSInterfaceHit, MMSInterfaceReport


def test_mms_report_summary_handles_empty_hits_and_issues():
    report = MMSInterfaceReport(basepicture_name="BasePicture", hits=[])

    summary = report.summary()

    assert report.name == "BasePicture"
    assert "Report: MMS interface mappings" in summary
    assert "Target: BasePicture" in summary
    assert "Status: ok" in summary
    assert "No mappings found." in summary


def test_mms_report_summary_ranks_variables_merges_writes_and_preserves_notes():
    report = MMSInterfaceReport(
        basepicture_name="BasePicture",
        hits=[
            MMSInterfaceHit(
                module_path=["Plant", "PumpA"],
                moduletype_name="ValveType",
                parameter_name="OpenCmd",
                source_variable="MMS_Flow",
                write_fields=(
                    ("Open", ((("Plant", "PumpA"), 1), (("Plant", "PumpA"), 3))),
                    ("", ((("Plant", "Shared"), 2),)),
                ),
            ),
            MMSInterfaceHit(
                module_path=["Plant", "PumpB"],
                moduletype_name="ValveType",
                parameter_name="Setpoint",
                source_variable="mms_flow",
                write_fields=(("Open", ((("Plant", "PumpB"), 2),)),),
            ),
            MMSInterfaceHit(
                module_path=["Plant", "PumpC"],
                moduletype_name="ValveType",
                parameter_name="Label",
                source_variable="MMS_Label",
                write_note="indirect mapping",
            ),
        ],
    )

    summary = report.summary()

    assert report.unique_variables == {"mms_flow", "mms_label"}
    assert "Status: data" in summary
    assert "Total mappings: 3" in summary
    assert "Unique variables: 2" in summary
    assert "Most-written MMS variables:" in summary
    assert "MMS_Flow: 7 writes (top fields: open (5x), <whole> (2x))" in summary
    assert "MMS_Label: 0 writes" in summary
    assert "Details by MMS variable:" in summary
    assert "Plant.PumpA | ValveType.OpenCmd" in summary
    assert "Plant.PumpB | ValveType.Setpoint" in summary
    assert "open => Plant.PumpA (3x), Plant.PumpB (2x)" in summary
    assert "<whole> => Plant.Shared (2x)" in summary
    assert "Field writes: indirect mapping" in summary


def test_mms_report_summary_lists_issue_kinds_and_findings():
    report = MMSInterfaceReport(
        basepicture_name="BasePicture",
        hits=[],
        issues=[
            Issue(
                kind="mms.duplicate_tag",
                message="Duplicate outgoing tag",
                module_path=["Plant", "PumpA"],
            ),
            Issue(
                kind="mms.dead_tag",
                message="Dead outgoing tag",
                module_path=None,
            ),
            Issue(
                kind="custom.kind",
                message="Custom finding",
                module_path=["Plant", "PumpB"],
            ),
        ],
    )

    summary = report.summary()

    assert "Status: issues" in summary
    assert "Issues: 3" in summary
    assert "Kinds:" in summary
    assert "Duplicate external tags: 1" in summary
    assert "Dead outgoing tags: 1" in summary
    assert "Findings:" in summary
    assert "[BasePicture] Dead outgoing tag" in summary
    assert "[Plant.PumpA] Duplicate outgoing tag" in summary
    assert "[Plant.PumpB] Custom finding" in summary
