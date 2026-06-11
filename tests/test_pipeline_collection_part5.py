# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
# ruff: noqa: F403, F405
from ._pipeline_collection_test_support import *


def test_build_coverage_summary_report_flags_high_severity(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report  # noqa: PLC0415

    xml_content = """<?xml version="1.0" ?>
<coverage>
  <packages><package><classes>
    <class filename="src/sattlint/bad_module.py" line-rate="0.05" lines-valid="100" lines-covered="5">
      <lines/>
    </class>
  </classes></package></packages>
</coverage>"""
    (tmp_path / "coverage.xml").write_text(xml_content, encoding="utf-8")
    result = build_coverage_summary_report(tmp_path)
    findings = result["findings"]
    assert any(f["severity"] == "high" for f in findings)


def test_build_coverage_summary_report_normalizes_src_paths_and_tracks_totals(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report  # noqa: PLC0415

    (tmp_path / "artifacts" / "analysis").mkdir(parents=True)
    (tmp_path / "artifacts" / "analysis" / "coverage_ratchet.json").write_text(
        '{"kind": "sattlint.coverage_ratchet", "schema_version": 1, "metrics": {"min_line_rate_basis_points": 8700}}',
        encoding="utf-8",
    )
    (tmp_path / "coverage.xml").write_text(
        """<?xml version="1.0" ?>
<coverage lines-valid="100" lines-covered="88" line-rate="0.88">
    <packages><package><classes>
        <class filename="sattlint/bad_module.py" line-rate="0.88" lines-valid="100" lines-covered="88">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    result = build_coverage_summary_report(tmp_path)

    assert result["modules"][0]["path"] == "src/sattlint/bad_module.py"
    assert result["summary"]["total_line_rate"] == 0.88
    assert result["summary"]["total_lines_missing"] == 12
    assert result["ratchet"]["status"] == "pass"
    assert result["change_scoped"]["status"] == "skipped"
    assert result["ratchet"]["setpoint_metrics"] == {
        "min_line_rate_basis_points": 10000,
        "min_changed_line_rate_basis_points": 10000,
        "min_touched_file_line_rate_basis_points": 9000,
    }
    assert result["ratchet"]["current_metrics"]["line_rate_basis_points"] == 8800


def test_build_coverage_summary_report_flags_ratchet_regression(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report  # noqa: PLC0415

    (tmp_path / "artifacts" / "analysis").mkdir(parents=True)
    (tmp_path / "artifacts" / "analysis" / "coverage_ratchet.json").write_text(
        '{"kind": "sattlint.coverage_ratchet", "schema_version": 1, "metrics": {"min_line_rate_basis_points": 9000}}',
        encoding="utf-8",
    )
    (tmp_path / "coverage.xml").write_text(
        """<?xml version="1.0" ?>
<coverage lines-valid="100" lines-covered="88" line-rate="0.88">
    <packages><package><classes>
        <class filename="sattlint/good_module.py" line-rate="0.88" lines-valid="100" lines-covered="88">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    result = build_coverage_summary_report(tmp_path)

    assert result["ratchet"]["status"] == "fail"
    assert result["ratchet"]["regressions"] == [
        {"metric": "line_rate_basis_points", "expected_min": 9000, "actual": 8800}
    ]
    assert any(f.get("id") == "coverage-ratchet-regression" for f in result["findings"])


def test_build_coverage_summary_report_prefers_changed_line_proof(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report  # noqa: PLC0415

    (tmp_path / "artifacts" / "analysis").mkdir(parents=True)
    (tmp_path / "artifacts" / "analysis" / "coverage_ratchet.json").write_text(
        (
            '{"kind": "sattlint.coverage_ratchet", "schema_version": 1, "metrics": '
            '{"min_line_rate_basis_points": 8700, "min_changed_line_rate_basis_points": 10000, '
            '"min_touched_file_line_rate_basis_points": 9000}}'
        ),
        encoding="utf-8",
    )
    (tmp_path / "coverage.xml").write_text(
        """<?xml version="1.0" ?>
<coverage lines-valid="10" lines-covered="9" line-rate="0.9">
    <packages><package><classes>
        <class filename="src/sattlint/good_module.py" line-rate="0.9" lines-valid="10" lines-covered="9">
            <lines>
                <line number="10" hits="1"/>
                <line number="11" hits="1"/>
                <line number="12" hits="0"/>
            </lines>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    result = build_coverage_summary_report(
        tmp_path,
        changed_files=["src/sattlint/good_module.py"],
        changed_line_map={"src/sattlint/good_module.py": [10, 11]},
    )

    assert result["change_scoped"]["status"] == "pass"
    assert result["change_scoped"]["mode"] == "changed-lines"
    assert result["change_scoped"]["summary"]["changed_line_count"] == 2
    assert result["change_scoped"]["summary"]["changed_lines_covered"] == 2
    assert result["change_scoped"]["summary"]["changed_line_rate"] == 1.0
    assert result["change_scoped"]["ratchet"]["metric"] == "changed_line_rate_basis_points"
    assert result["change_scoped"]["ratchet"]["actual"] == 10000


def test_build_coverage_summary_report_falls_back_to_touched_file_proof(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report  # noqa: PLC0415

    (tmp_path / "artifacts" / "analysis").mkdir(parents=True)
    (tmp_path / "artifacts" / "analysis" / "coverage_ratchet.json").write_text(
        (
            '{"kind": "sattlint.coverage_ratchet", "schema_version": 1, "metrics": '
            '{"min_line_rate_basis_points": 8700, "min_changed_line_rate_basis_points": 10000, '
            '"min_touched_file_line_rate_basis_points": 9000}}'
        ),
        encoding="utf-8",
    )
    (tmp_path / "coverage.xml").write_text(
        """<?xml version="1.0" ?>
<coverage lines-valid="20" lines-covered="17" line-rate="0.85">
    <packages><package><classes>
        <class filename="src/sattlint/good_module.py" line-rate="0.85" lines-valid="20" lines-covered="17">
            <lines>
                <line number="30" hits="0"/>
            </lines>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    result = build_coverage_summary_report(
        tmp_path,
        changed_files=["src/sattlint/good_module.py"],
        changed_line_map={"src/sattlint/good_module.py": [99]},
    )

    assert result["change_scoped"]["status"] == "fail"
    assert result["change_scoped"]["mode"] == "touched-files"
    assert result["change_scoped"]["summary"]["changed_line_count"] == 0
    assert result["change_scoped"]["summary"]["touched_line_rate"] == 0.85
    assert result["change_scoped"]["ratchet"]["metric"] == "touched_file_line_rate_basis_points"
    assert result["change_scoped"]["ratchet"]["regressions"] == [
        {"metric": "touched_file_line_rate_basis_points", "expected_min": 9000, "actual": 8500}
    ]
    assert any(f.get("id") == "change-scoped-coverage-ratchet-regression" for f in result["findings"])


def test_build_current_debt_snapshot_report_marks_live_and_stale_entries(tmp_path):
    from sattlint.devtools.current_debt_snapshot import build_current_debt_snapshot_report  # noqa: PLC0415

    (tmp_path / "artifacts" / "analysis").mkdir(parents=True)
    (tmp_path / "artifacts" / "analysis" / "file_debt_ratchet.json").write_text(
        json.dumps(
            {
                "kind": "sattlint.file_debt_ratchet",
                "schema_version": 1,
                "files": {
                    "src/pkg/stale_structural.py": {
                        "structural": {
                            "current_baseline": 620,
                            "target": 500,
                            "touch_rule": "must_shrink",
                            "reason": "Still needs to shrink.",
                        }
                    },
                    "src/pkg/active_coverage.py": {
                        "coverage": {
                            "current_baseline": 8700,
                            "target": 10000,
                            "touch_rule": "must_reach_target_on_touch",
                            "reason": "Still needs full proof.",
                        }
                    },
                    "src/pkg/stale_coverage.py": {
                        "coverage": {
                            "current_baseline": 9100,
                            "target": 10000,
                            "touch_rule": "must_reach_target_on_touch",
                            "reason": "Reached full proof.",
                        }
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report = build_current_debt_snapshot_report(
        tmp_path,
        structural_budget_report={
            "current_file_line_counts": {
                "src/pkg/stale_structural.py": 480,
            }
        },
        coverage_summary_report={
            "skipped": False,
            "modules": [
                {"path": "src/pkg/active_coverage.py", "line_rate": 0.91},
                {"path": "src/pkg/stale_coverage.py", "line_rate": 1.0},
            ],
        },
    )

    assert report["summary"]["stale_count"] == 2
    assert report["summary"]["active_count"] == 1
    assert report["files"]["src/pkg/stale_structural.py"]["structural"]["status"] == "stale"
    assert report["files"]["src/pkg/active_coverage.py"]["coverage"]["status"] == "active"
    assert report["files"]["src/pkg/stale_coverage.py"]["coverage"]["status"] == "stale"


def test_coverage_report_normalizers_cover_empty_absolute_and_duplicate_inputs():
    from sattlint.devtools import coverage_reports  # noqa: PLC0415

    absolute_windows_path = "C:" + "/tmp/demo.py"

    assert coverage_reports._normalize_coverage_filename("./") == ""
    assert coverage_reports._normalize_coverage_filename(absolute_windows_path) == absolute_windows_path
    assert coverage_reports._normalize_coverage_filename("module.py") == "src/module.py"
    assert coverage_reports._normalize_changed_files([" src\\demo.py ", "", "src/demo.py", "tests/test_demo.py"]) == [
        "src/demo.py",
        "tests/test_demo.py",
    ]
    assert coverage_reports._changed_source_files(["src/demo.py", "tests/test_demo.py", "src/demo.txt"]) == [
        "src/demo.py"
    ]


def test_coverage_report_git_diff_helpers_cover_edge_cases(tmp_path, monkeypatch):
    from sattlint.devtools import coverage_reports  # noqa: PLC0415

    diff_text = "\n".join(
        [
            "+++ /dev/null",
            "@@ -0,0 +1,1 @@",
            "+++ b/src/demo.py",
            "not-a-hunk-line",
            "@@ -1,0 +10,2 @@",
            "@@ -5,1 +20,0 @@",
            "+++ b/docs/ignored.md",
            "@@ -1 +1 @@",
        ]
    )
    assert coverage_reports._parse_git_changed_line_map(diff_text, allowed_paths={"src/demo.py"}) == {
        "src/demo.py": {10, 11}
    }

    assert coverage_reports._discover_changed_line_map(tmp_path, ["README.md"]) == {}

    monkeypatch.setattr(coverage_reports.shutil, "which", lambda _name: None)
    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {}

    monkeypatch.setattr(coverage_reports.shutil, "which", lambda _name: "git")
    monkeypatch.setattr(
        coverage_reports.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {}

    call_count = {"value": 0}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        call_count["value"] += 1
        if call_count["value"] == 1:
            return subprocess.CompletedProcess(command, 1, "", "")
        return subprocess.CompletedProcess(command, 0, diff_text, "")

    monkeypatch.setattr(coverage_reports.subprocess, "run", fake_run)
    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {"src/demo.py": [10, 11]}


def test_coverage_report_ratchet_and_module_helpers_cover_invalid_inputs(tmp_path):
    from sattlint.devtools import coverage_reports  # noqa: PLC0415

    ratchet_path = tmp_path / coverage_reports.COVERAGE_RATCHET_PATH
    ratchet_path.parent.mkdir(parents=True)
    ratchet_path.write_text("{not json", encoding="utf-8")
    invalid_json = coverage_reports._load_coverage_ratchet(tmp_path)
    assert invalid_json["status"] == "invalid"

    ratchet_path.write_text(
        '{"kind": "sattlint.coverage_ratchet", "schema_version": 1, "metrics": {"min_line_rate_basis_points": "9000"}}',
        encoding="utf-8",
    )
    invalid_metrics = coverage_reports._load_coverage_ratchet(tmp_path)
    assert invalid_metrics["status"] == "invalid"
    assert invalid_metrics["error_type"] == "ValueError"

    root_xml = coverage_reports.ElementTree.fromstring(
        """<?xml version=\"1.0\" ?>
<coverage>
  <packages><package><classes>
    <class filename=\"demo.py\" line-rate=\"0.5\" lines-valid=\"2\" lines-covered=\"1\">
      <lines>
        <line number=\"0\" hits=\"1\"/>
        <line number=\"4\" hits=\"1\"/>
      </lines>
    </class>
  </classes></package></packages>
</coverage>"""
    )

    modules, module_lookup, _line_rates = coverage_reports._collect_modules(root_xml)
    summary = coverage_reports._summarize_change_scoped_coverage(
        changed_files=["src/demo.py"],
        changed_line_map={"src/demo.py": []},
        module_lookup=module_lookup,
        ratchet_state={"metrics": {}},
    )

    assert modules[0]["path"] == "src/demo.py"
    assert modules[0]["line_hits"] == {4: 1}
    assert summary["mode"] == "touched-files"
    assert summary["summary"]["changed_line_count"] == 0


def test_build_coverage_summary_report_discovers_changed_lines_and_flags_low_severity(tmp_path, monkeypatch):
    from sattlint.devtools import coverage_reports  # noqa: PLC0415

    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
  <packages><package><classes>
    <class filename=\"demo.py\" line-rate=\"0.5\" lines-valid=\"4\" lines-covered=\"2\">
      <lines>
        <line number=\"5\" hits=\"1\"/>
        <line number=\"6\" hits=\"0\"/>
      </lines>
    </class>
  </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    observed: dict[str, Any] = {}

    def fake_discover(root: Path, changed_files: list[str]) -> dict[str, list[int]]:
        observed["root"] = root
        observed["changed_files"] = changed_files
        return {"src/demo.py": [5, 6]}

    monkeypatch.setattr(coverage_reports, "_discover_changed_line_map", fake_discover)

    result = coverage_reports.build_coverage_summary_report(tmp_path, changed_files=["src/demo.py"])

    assert observed == {"root": tmp_path, "changed_files": ["src/demo.py"]}
    assert any(finding["severity"] == "low" for finding in result["findings"])
    assert result["summary"]["total_lines_valid"] == 4
    assert result["summary"]["total_lines_covered"] == 2
    assert result["summary"]["total_line_rate"] == 0.5


# --- resolution/paths.py: CanonicalPath.join() no-arg, ModuleSegment.display() branches ---
def test_canonical_path_join_no_args_returns_self():
    from sattlint.resolution.paths import CanonicalPath  # noqa: PLC0415

    cp = CanonicalPath(("Main", "Guard"))
    assert cp.join() is cp


def test_module_segment_display_variants():
    from sattlint.resolution.paths import ModuleSegment  # noqa: PLC0415

    assert ModuleSegment("Guard", "SM").display() == "Guard<SM>"
    assert ModuleSegment("Loop", "FM").display() == "Loop<FM>"
    assert ModuleSegment("T1", "TD").display() == "T1<TD>"
    assert ModuleSegment("Root", "BP").display() == "Root<BP>"
    assert ModuleSegment("UTI", "MT", "MyType").display() == "UTI<MT:MyType>"


# --- resolution/scope.py: param mapping prefix-only and no-prefix branches, resolve_global_name ---
def test_scope_context_resolve_variable_prefix_only_mapping():
    from sattline_parser.models.ast_model import Variable  # noqa: PLC0415
    from sattlint.resolution.scope import ScopeContext  # noqa: PLC0415

    src_var = Variable(name="Dv", datatype="UserType")
    ctx = ScopeContext(
        env={"dv": src_var},
        param_mappings={"sig": (src_var, "I.WT001", ["Lib", "Main"], ["Lib", "Main"])},
        module_path=["Main"],
        display_module_path=["Main"],
    )
    var, full_field_path, _, _ = ctx.resolve_variable("sig")
    assert var is src_var
    assert full_field_path == "I.WT001"


def test_scope_context_resolve_variable_no_prefix_mapping():
    from sattline_parser.models.ast_model import Variable  # noqa: PLC0415
    from sattlint.resolution.scope import ScopeContext  # noqa: PLC0415

    src_var = Variable(name="Dv", datatype="UserType")
    ctx = ScopeContext(
        env={},
        param_mappings={"sig": (src_var, "", ["Lib"], ["Lib"])},
        module_path=["Main"],
        display_module_path=["Main"],
    )
    var, full_field_path, _, _ = ctx.resolve_variable("sig")
    assert var is src_var
    assert full_field_path == ""
