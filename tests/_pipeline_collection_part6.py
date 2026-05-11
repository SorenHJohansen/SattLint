# ruff: noqa: F403
from ._pipeline_collection_test_support import *


def test_scope_context_resolve_global_name_empty_returns_none():
    from sattlint.resolution.scope import ScopeContext

    ctx = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Main"],
        display_module_path=["Main"],
    )
    var, _, _ = ctx.resolve_global_name("")
    assert var is None


def test_scope_context_resolve_global_name_walks_parent():
    from sattline_parser.models.ast_model import Variable
    from sattlint.resolution.scope import ScopeContext

    parent_var = Variable(name="GlobVar", datatype="Integer")
    parent_ctx = ScopeContext(
        env={"globvar": parent_var},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
    )
    child_ctx = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Root", "Child"],
        display_module_path=["Root", "Child"],
        parent_context=parent_ctx,
    )
    var, _, _ = child_ctx.resolve_global_name("GlobVar")
    assert var is parent_var


# --- contracts/findings.py ---
def test_finding_location_to_dict_and_from_mapping():
    from sattlint.contracts.findings import FindingLocation

    loc = FindingLocation(path="Main.s", line=5, column=3, symbol="Var1", module_path=("Main", "Guard"))
    d = loc.to_dict()
    assert d["path"] == "Main.s"
    assert d["line"] == 5
    assert d["module_path"] == ["Main", "Guard"]

    from_payload = FindingLocation.from_mapping({"path": "Foo.s", "line": "10", "module_path": ["A", "B"]})
    assert from_payload.path == "Foo.s"
    assert from_payload.line == 10
    assert from_payload.module_path == ("A", "B")


def test_finding_location_from_mapping_uses_file_fallback():
    from sattlint.contracts.findings import FindingLocation

    loc = FindingLocation.from_mapping({"file": "Alt.s"})
    assert loc.path == "Alt.s"


def test_finding_record_default_fingerprint_is_set():
    from sattlint.contracts.findings import FindingRecord

    r = FindingRecord(
        id="r1",
        rule_id="var.unused",
        category="variable",
        severity="warning",
        confidence="high",
        message="Unused variable X",
        source="test",
    )
    assert r.fingerprint is not None
    assert "var.unused" in r.fingerprint


def test_finding_record_to_dict_round_trip_via_from_dict():
    from sattlint.contracts.findings import FindingLocation, FindingRecord

    original = FindingRecord(
        id="r2",
        rule_id="scope.leak",
        category="scope",
        severity="info",
        confidence="medium",
        message="Scope issue",
        source="test",
        analyzer="repo-audit",
        location=FindingLocation(path="src/example.py", line=12),
        detail="some detail",
        suggestion="fix it",
    )
    d = original.to_dict()
    restored = FindingRecord.from_dict(d)
    assert restored.rule_id == "scope.leak"
    assert restored.detail == "some detail"
    assert restored.suggestion == "fix it"
    assert restored.file == "src/example.py"
    assert restored.line == 12
    assert restored.owner_surface == "test"
    assert (
        restored.minimal_reproducer
        == "sattlint-repo-audit --profile full --check test --skip-pipeline --output-dir artifacts/audit"
    )
    assert restored.suggested_next_command == restored.minimal_reproducer


def test_finding_record_derives_tool_specific_failure_fields():
    from sattlint.contracts.findings import FindingLocation, FindingRecord

    ruff_finding = FindingRecord(
        id="ruff-f401",
        rule_id="ruff.f401",
        category="style",
        severity="high",
        confidence="high",
        message="Imported but unused",
        source="ruff",
        location=FindingLocation(path="src/sample.py", line=4),
    )
    syntax_finding = FindingRecord(
        id="syntax.parse",
        rule_id="syntax.parse",
        category="syntax",
        severity="high",
        confidence="high",
        message="Parse failed",
        source="corpus-runner",
        analyzer="syntax-check",
        location=FindingLocation(path="Broken.s", line=1),
    )

    assert ruff_finding.owner_surface == "python-style"
    assert ruff_finding.minimal_reproducer == "ruff check src/sample.py"
    assert ruff_finding.suggested_next_command == "ruff check src/sample.py"
    assert syntax_finding.owner_surface == "syntax-check"
    assert syntax_finding.minimal_reproducer == "sattlint syntax-check Broken.s"
    assert syntax_finding.suggested_next_command == "sattlint syntax-check Broken.s"


def test_finding_record_from_mapping_with_explicit_source():
    from sattlint.contracts.findings import FindingRecord

    r = FindingRecord.from_mapping(
        {"rule_id": "x.y", "category": "cat", "severity": "err", "confidence": "low", "message": "msg"},
        source="manual",
        analyzer="myanalyzer",
    )
    assert r.source == "manual"
    assert r.analyzer == "myanalyzer"


def test_finding_collection_to_dict_and_from_dict():
    from sattlint.contracts.findings import FindingCollection, FindingRecord

    rec = FindingRecord(id="f1", rule_id="r1", category="c", severity="s", confidence="c2", message="m", source="s2")
    coll = FindingCollection(findings=(rec,))
    d = coll.to_dict()
    assert d["finding_count"] == 1

    restored = FindingCollection.from_dict(d)
    assert len(restored.findings) == 1
    assert restored.findings[0].rule_id == "r1"


# --- path_sanitizer.py ---
def test_sanitize_path_for_report_returns_relative_for_repo_subpath(tmp_path):
    from sattlint.path_sanitizer import sanitize_path_for_report

    sub = tmp_path / "src" / "main.py"
    result = sanitize_path_for_report(sub, repo_root=tmp_path)
    assert result == "src/main.py"


def test_sanitize_path_for_report_returns_none_for_none():
    from pathlib import Path

    from sattlint.path_sanitizer import sanitize_path_for_report

    result = sanitize_path_for_report(None, repo_root=Path("."))
    assert result is None


def test_sanitize_path_for_report_external_absolute_path(tmp_path):
    import tempfile
    from pathlib import Path

    from sattlint.path_sanitizer import sanitize_path_for_report

    # Create a path outside of tmp_path but absolute
    other = Path(tempfile.gettempdir()) / "some_other" / "file.py"
    result = sanitize_path_for_report(other, repo_root=tmp_path)
    # Should be external/<filename> or external
    assert result is not None
    assert "file.py" in result or result == "<external>"


def test_sanitize_command_for_report_strips_absolute_path_args(tmp_path):
    from sattlint.path_sanitizer import sanitize_command_for_report

    sub = tmp_path / "src" / "main.py"
    sub.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pytest", f"--output-dir={sub}", str(sub)]
    result = sanitize_command_for_report(cmd, repo_root=tmp_path)
    assert result[0] == "pytest"
    assert "src/main.py" in result[1]


def test_path_sanitizer_covers_empty_and_resolve_fallback_branches(tmp_path, monkeypatch):
    from typing import Any, cast

    from sattlint import path_sanitizer

    class _RepoRootFallback:
        def __init__(self, path) -> None:
            self._path = path

        def resolve(self):
            raise OSError("cannot resolve repo root")

        def __fspath__(self) -> str:
            return str(self._path)

    class _CandidatePathFallback:
        def __init__(self, raw_path: str) -> None:
            self._raw_path = raw_path

        def resolve(self, *, strict: bool = False):
            raise OSError(f"cannot resolve candidate with strict={strict}")

        def relative_to(self, _other: object):
            raise ValueError("outside repo")

    assert path_sanitizer._looks_absolute("") is False
    assert path_sanitizer._display_name(r"C:\\temp\\demo.txt") == "demo.txt"
    assert path_sanitizer.sanitize_path_for_report("", repo_root=tmp_path) == ""

    nested = tmp_path / "src" / "main.py"
    assert (
        path_sanitizer.sanitize_path_for_report(nested, repo_root=cast(Any, _RepoRootFallback(tmp_path)))
        == "src/main.py"
    )

    monkeypatch.setattr(path_sanitizer, "Path", _CandidatePathFallback)
    assert path_sanitizer.sanitize_path_for_report(r"C:\\temp\\demo.txt", repo_root=tmp_path) == "<external>/demo.txt"


# --- analyzers/framework.py: SimpleReport.summary() with note, with issues ---
def test_simple_report_summary_with_note():
    from sattlint.analyzers.framework import SimpleReport

    report = SimpleReport(name="TestReport", note="Check this info")
    summary = report.summary()
    assert "Check this info" in summary


def test_simple_report_summary_no_issues_ok():
    from sattlint.analyzers.framework import SimpleReport

    report = SimpleReport(name="TestReport")
    summary = report.summary()
    assert "No issues found" in summary


def test_simple_report_summary_with_issues():
    from sattlint.analyzers.framework import Issue, SimpleReport

    issue = Issue(kind="test.issue", message="Something is wrong", module_path=["Main", "Guard"])
    report = SimpleReport(name="TestReport", issues=[issue])
    summary = report.summary()
    assert "Findings:" in summary
    assert "Something is wrong" in summary


# --- models/usage.py: all branches ---
def test_variable_usage_mark_read_ui_and_non_ui():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    assert u.is_unused is True
    u.mark_read(["Main", "Guard"])
    assert u.read is True
    assert u.non_ui_read is True
    assert u.is_read_only is True
    u.mark_ui_read(["Main", "Display"])
    assert u.ui_read is True
    assert u.is_display_only is False  # has non_ui_read too


def test_variable_usage_mark_field_read_ui():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_field_read("Level.Value", ["Main", "Guard"], ui=True)
    assert u.ui_read is True
    assert "Level.Value" in u.field_reads


def test_variable_usage_mark_field_read_non_ui():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_field_read("Level.Value", ["Main", "Guard"])
    assert u.non_ui_read is True


def test_variable_usage_mark_written_and_mark_field_written():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_written(["Main", "Guard"])
    assert u.written is True
    u.mark_field_written("Level.Value", ["Main", "Guard"])
    assert "Level.Value" in u.field_writes


def test_variable_usage_distinct_reader_writer_counts():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_read(["Main", "Guard"])
    u.mark_read(["Main", "Guard"])
    u.mark_read(["Main", "Observer"])
    u.mark_field_read("Level", ["Main", "Extra"])
    assert u.distinct_reader_count == 3

    u.mark_written(["Main", "Guard"])
    u.mark_field_written("Level", ["Main", "Guard"])
    assert u.distinct_writer_count == 1


def test_variable_usage_is_display_only():
    from sattlint.models.usage import VariableUsage

    u = VariableUsage()
    u.mark_ui_read(["Main", "Display"])
    assert u.is_display_only is True


# --- resolution/type_graph.py: TypeGraph operations ---
def test_type_graph_has_record_and_field():
    from types import SimpleNamespace

    from sattlint.resolution.type_graph import TypeGraph

    dt = SimpleNamespace(
        name="RecordType",
        var_list=[
            SimpleNamespace(name="Value", datatype="Integer", state=False),
            SimpleNamespace(name="Status", datatype="Integer", state=False),
        ],
    )
    graph = TypeGraph.from_datatypes([dt])
    assert graph.has_record("RecordType") is True
    assert graph.has_record("Unknown") is False
    assert graph.record("RecordType") is not None
    assert graph.field("RecordType", "Value") is not None
    assert graph.field("RecordType", "Nonexistent") is None
    assert graph.field("Unknown", "Value") is None
    assert graph.field_type("RecordType", "Value") == "Integer"
    assert graph.field_type("Missing", "x") is None


def test_type_graph_iter_leaf_field_paths_simple_type():
    from sattline_parser.models.ast_model import Simple_DataType
    from sattlint.resolution.type_graph import TypeGraph

    graph = TypeGraph({})
    paths = list(graph.iter_leaf_field_paths(Simple_DataType.INTEGER))
    assert paths == [()]


def test_type_graph_iter_leaf_field_paths_unknown_type():
    from sattlint.resolution.type_graph import TypeGraph

    graph = TypeGraph({})
    paths = list(graph.iter_leaf_field_paths("UnknownType"))
    assert paths == [()]


def test_type_graph_iter_leaf_field_paths_nested_record():
    from types import SimpleNamespace

    from sattline_parser.models.ast_model import Simple_DataType
    from sattlint.resolution.type_graph import TypeGraph

    # RecordA has field "FieldA" of type Integer (Simple_DataType)
    dt = SimpleNamespace(
        name="RecordA",
        var_list=[SimpleNamespace(name="FieldA", datatype=Simple_DataType.INTEGER, state=False)],
    )
    graph = TypeGraph.from_datatypes([dt])
    paths = list(graph.iter_leaf_field_paths("RecordA"))
    assert ("FieldA",) in paths


def test_type_graph_iter_all_addressable_paths():
    from types import SimpleNamespace

    from sattline_parser.models.ast_model import Simple_DataType, Variable
    from sattlint.resolution.type_graph import TypeGraph

    dt = SimpleNamespace(
        name="RootType",
        var_list=[SimpleNamespace(name="Field1", datatype=Simple_DataType.INTEGER, state=False)],
    )
    graph = TypeGraph.from_datatypes([dt])
    root_var = Variable(name="Dv", datatype="RootType")
    paths = list(graph.iter_all_addressable_paths(root_var))
    assert ("Field1",) in paths


# --- console.py: print_output, has_rich, print_status fallback, print_panel fallback,
#     print_table empty rows, print_table with rows, track_items ---
def test_print_output_writes_to_stdout(capsys):
    from sattlint.console import print_output

    print_output("hello", "world", sep="-")
    captured = capsys.readouterr()
    assert "hello-world" in captured.out


def test_has_rich_returns_bool():
    from sattlint.console import has_rich

    assert isinstance(has_rich(), bool)


def test_print_status_fallback_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_status("test message", level="error")
    captured = capsys.readouterr()
    assert "ERROR" in captured.out
    assert "test message" in captured.out


def test_print_panel_fallback_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_panel("My Title", "Panel body text")
    captured = capsys.readouterr()
    assert "My Title" in captured.out
    assert "Panel body text" in captured.out


def test_print_table_empty_rows_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_table("My Table", ["Col1", "Col2"], [])
    captured = capsys.readouterr()
    assert "My Table" in captured.out
    assert "(none)" in captured.out


def test_print_table_with_rows_no_rich(capsys, monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    console_mod.print_table("My Table", ["Name", "Value"], [["alpha", "1"], ["beta", "2"]])
    captured = capsys.readouterr()
    assert "alpha" in captured.out
    assert "beta" in captured.out


def test_track_items_returns_iterable_without_rich(monkeypatch):
    import sattlint.console as console_mod

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", False)
    items = [1, 2, 3]
    result = list(console_mod.track_items(items, description="Loading"))
    assert result == [1, 2, 3]
