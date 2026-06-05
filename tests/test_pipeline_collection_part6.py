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


def test_scope_context_resolve_variable_caches_parent_lookup_result():
    from sattline_parser.models.ast_model import Variable
    from sattlint.resolution.scope import ScopeContext

    parent_var = Variable(name="Sig", datatype="Integer")
    parent_ctx = ScopeContext(
        env={"sig": parent_var},
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

    first = child_ctx.resolve_variable("SIG.Field")
    second = child_ctx.resolve_variable("sig.field")

    assert first == second
    assert child_ctx._resolve_cache["sig.field"] == first


def test_scope_context_resolve_variable_prefix_plus_field_and_unresolved_paths():
    from sattline_parser.models.ast_model import Variable
    from sattlint.resolution.scope import ScopeContext

    src_var = Variable(name="Dv", datatype="UserType")
    ctx = ScopeContext(
        env={},
        param_mappings={"sig": (src_var, "I.WT001", ["Lib", "Main"], ["Lib", "Main"])},
        module_path=["Main"],
        display_module_path=["Main"],
    )

    resolved = ctx.resolve_variable("sig.Comp_signal.value")
    unresolved = ctx.resolve_variable("missing.Field")

    assert resolved == (src_var, "I.WT001.Comp_signal.value", ["Lib", "Main"], ["Lib", "Main"])
    assert unresolved == (None, "Field", ["Main"], ["Main"])
    assert ctx._resolve_cache["missing.field"] == unresolved


def test_scope_context_resolve_global_name_unresolved_without_parent_uses_local_paths():
    from sattlint.resolution.scope import ScopeContext

    ctx = ScopeContext(
        env={},
        param_mappings={},
        module_path=["Root", "Child"],
        display_module_path=["Root", "Child"],
    )

    assert ctx.resolve_global_name("Unknown") == (None, ["Root", "Child"], ["Root", "Child"])


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


def test_finding_record_defaults_cover_explicit_and_fallback_paths():
    from sattlint.contracts.findings import FindingCollection, FindingLocation, FindingRecord

    explicit_owner = FindingRecord(
        id="owner",
        rule_id="owner.rule",
        category="unknown",
        severity="low",
        confidence="high",
        message="owner",
        source="manual",
        data={"owner_surface": "custom-surface"},
    )
    unknown_owner = FindingRecord(
        id="unknown",
        rule_id="unknown.rule",
        category="unknown",
        severity="low",
        confidence="high",
        message="unknown",
        source="manual",
    )
    explicit_reproducer = FindingRecord(
        id="explicit-reproducer",
        rule_id="manual.rule",
        category="unknown",
        severity="low",
        confidence="high",
        message="manual",
        source="manual",
        data={"minimal_reproducer": "python -m pytest tests/test_sample.py -q"},
    )
    pyright_default = FindingRecord(
        id="pyright",
        rule_id="pyright.assignment",
        category="types",
        severity="high",
        confidence="high",
        message="Typed mismatch",
        source="manual",
        analyzer="pyright",
    )
    pytest_nodeid = FindingRecord(
        id="pytest-nodeid",
        rule_id="pytest.failures",
        category="correctness",
        severity="high",
        confidence="high",
        message="failed",
        source="pytest",
        data={"nodeid": "tests/test_sample.py::test_failure"},
    )
    pytest_default = FindingRecord(
        id="pytest-default",
        rule_id="pytest.failures",
        category="correctness",
        severity="high",
        confidence="high",
        message="failed",
        source="pytest",
    )
    pytest_path = FindingRecord(
        id="pytest-path",
        rule_id="pytest.failures",
        category="correctness",
        severity="high",
        confidence="high",
        message="failed",
        source="pytest",
        location=FindingLocation(path="tests/test_sample.py"),
    )
    repo_audit_default = FindingRecord(
        id="repo-audit",
        rule_id="repo-audit.sample",
        category="correctness",
        severity="high",
        confidence="high",
        message="audit",
        source="pipeline",
        analyzer="repo-audit",
    )
    explicit_next_command = FindingRecord(
        id="explicit-next",
        rule_id="next.rule",
        category="unknown",
        severity="low",
        confidence="high",
        message="next",
        source="manual",
        data={"suggested_next_command": "pyright src tests"},
    )
    suggested_command = FindingRecord(
        id="suggestion",
        rule_id="suggestion.rule",
        category="unknown",
        severity="low",
        confidence="high",
        message="suggestion",
        source="manual",
        suggestion="  python -m pytest tests/test_sample.py -q",
    )

    assert explicit_owner.owner_surface == "custom-surface"
    assert unknown_owner.owner_surface is None
    assert explicit_reproducer.minimal_reproducer == "python -m pytest tests/test_sample.py -q"
    assert pyright_default.minimal_reproducer == "pyright src tests"
    assert pytest_nodeid.minimal_reproducer == "python -m pytest tests/test_sample.py::test_failure -x -q --tb=short"
    assert pytest_default.minimal_reproducer == "python -m pytest -x -q --tb=short"
    assert pytest_path.minimal_reproducer == "python -m pytest tests/test_sample.py -x -q --tb=short"
    assert repo_audit_default.minimal_reproducer == "sattlint-repo-audit --profile full --output-dir artifacts/audit"
    assert explicit_next_command.suggested_next_command == "pyright src tests"
    assert suggested_command.suggested_next_command == "python -m pytest tests/test_sample.py -q"
    assert FindingCollection(findings=()).schema_metadata == {"kind": "sattlint.findings", "schema_version": 1}


def test_findings_private_coercion_helpers_cover_edge_cases():
    from sattlint.contracts import findings as findings_module

    assert findings_module._coerce_int(True) == 1
    assert findings_module._coerce_int("abc") is None
    assert findings_module._coerce_str(42) == "42"
    assert findings_module._coerce_data_dict([("bad", "input")]) == {}
    assert findings_module._coerce_mapping_sequence("bad") == ()
    assert findings_module._coerce_module_path("Main.Child") == ("Main.Child",)


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


def test_simple_report_summary_formats_metadata_and_analysis_context_fallback():
    from types import SimpleNamespace

    from sattline_parser.models.ast_model import BasePicture, ModuleHeader
    from sattlint.analyzers.framework import AnalysisContext, Issue, SimpleReport

    issue = Issue(
        kind="test.issue",
        message="Something is wrong",
        module_path=["Main", "Guard"],
        severity="high",
        confidence="medium",
        rule_id="TEST-001",
        explanation="Because this path is invalid.",
        suggestion="Fix the configuration.",
    )
    report = SimpleReport(name="TestReport", issues=[issue])
    summary = report.summary()

    assert "[high | medium | TEST-001]" in summary
    assert "Why it matters: Because this path is invalid." in summary
    assert "Suggested fix: Fix the configuration." in summary

    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    with_graph = AnalysisContext(base_picture=bp, graph=SimpleNamespace(unavailable_libraries={"ControlLib"}))
    without_graph = AnalysisContext(base_picture=bp)

    assert with_graph.unavailable_libraries == {"ControlLib"}
    assert without_graph.unavailable_libraries == set()


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


def test_type_graph_from_basepicture_builds_records():
    from types import SimpleNamespace

    from sattlint.resolution.type_graph import TypeGraph

    datatype = SimpleNamespace(
        name="RecordType",
        var_list=[SimpleNamespace(name="Value", datatype="Integer", state=False)],
    )
    base_picture = SimpleNamespace(datatype_defs=[datatype])

    graph = TypeGraph.from_basepicture(base_picture)

    assert graph.has_record("recordtype") is True


def test_type_graph_seeds_builtin_datatypes():
    from sattline_parser.models.ast_model import Simple_DataType
    from sattlint.resolution.type_graph import TypeGraph

    graph = TypeGraph.from_datatypes([])

    assert graph.has_record("ProgStationData") is True
    assert graph.field_type("ProgStationData", "TimeFormats") == "TimeFormatType"
    assert graph.field_type("TimeFormatType", "DateAndTime") == Simple_DataType.STRING
    assert graph.field_type("ColoursType", "WarningColour") == Simple_DataType.INTEGER
    assert graph.field_type("VarGroupType", "RemoteError") == Simple_DataType.BOOLEAN
    assert graph.field_type("AcofType", "Elapsed") == Simple_DataType.DURATION
    assert graph.field_type("AcofType", "AcofTimer") == "AcofTimerType"
    assert graph.field_type("OnOffTimerType", "Hold") == Simple_DataType.BOOLEAN
    assert graph.field_type("OnOffTimerType", "Timer") == "Timer"
    assert graph.field_type("IP4Signal", "Parameters") == "SignalPar"
    assert graph.field_type("IP4Signal", "ControlReadBack") == Simple_DataType.INTEGER
    assert graph.field_type("PidPar", "Gain") == Simple_DataType.REAL
    assert graph.field_type("ManualAutoRealSPar", "Automatic") == Simple_DataType.BOOLEAN
    assert graph.field_type("StaticFunctionRSPar", "x10used") == Simple_DataType.BOOLEAN
    assert graph.field_type("SelectorChain", "Signal") == "RealSignal"
    assert graph.field_type("SelectorChain", "SelectedNb") == Simple_DataType.INTEGER
    assert graph.field_type("SAPar", "Time") == Simple_DataType.DURATION
    assert graph.field_type("AdaptivePidPar", "RampDuration") == Simple_DataType.DURATION
    assert graph.field_type("Alarm4RealSPar", "TimeDelay") == Simple_DataType.INTEGER


def test_type_graph_empty_builtin_handles_expand_as_leaf_paths():
    from sattlint.resolution.type_graph import TypeGraph

    graph = TypeGraph.from_datatypes([])

    assert list(graph.iter_leaf_field_paths("RandomGenerator")) == [()]
    assert list(graph.iter_leaf_field_paths("tObject")) == [()]


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


def test_type_graph_iter_leaf_field_paths_follows_nested_record_fields():
    from types import SimpleNamespace

    from sattline_parser.models.ast_model import Simple_DataType
    from sattlint.resolution.type_graph import TypeGraph

    inner = SimpleNamespace(
        name="RecordB",
        var_list=[SimpleNamespace(name="Leaf", datatype=Simple_DataType.INTEGER, state=False)],
    )
    outer = SimpleNamespace(
        name="RecordA",
        var_list=[SimpleNamespace(name="Child", datatype="RecordB", state=False)],
    )

    graph = TypeGraph.from_datatypes([outer, inner])

    assert list(graph.iter_leaf_field_paths("RecordA")) == [("Child", "Leaf")]


def test_type_graph_iter_leaf_field_paths_stops_on_cycles():
    from types import SimpleNamespace

    from sattlint.resolution.type_graph import TypeGraph

    cyclic = SimpleNamespace(
        name="Loop",
        var_list=[SimpleNamespace(name="Next", datatype="Loop", state=False)],
    )

    graph = TypeGraph.from_datatypes([cyclic])

    assert list(graph.iter_leaf_field_paths("Loop")) == [("Next",)]


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


def test_console_rich_output_paths_and_syntax_excerpt(monkeypatch, tmp_path):
    import sattlint.console as console_mod

    class FakeConsole:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def print(self, value: object, *args: object, **kwargs: object) -> None:
            self.calls.append((value, args, kwargs))

    class FakeTable:
        def __init__(self, *, title: str, show_lines: bool) -> None:
            self.title = title
            self.show_lines = show_lines
            self.columns: list[str] = []
            self.rows: list[tuple[str, ...]] = []

        def add_column(self, column: str) -> None:
            self.columns.append(column)

        def add_row(self, *values: str) -> None:
            self.rows.append(values)

    class FakeSyntax:
        def __init__(self, source: str, lexer: str, *, line_numbers: bool, word_wrap: bool, highlight_lines: set[int]):
            self.source = source
            self.lexer = lexer
            self.line_numbers = line_numbers
            self.word_wrap = word_wrap
            self.highlight_lines = highlight_lines

    stdout_console = FakeConsole()
    stderr_console = FakeConsole()

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", True)
    monkeypatch.setattr(console_mod, "_STDOUT_CONSOLE", stdout_console)
    monkeypatch.setattr(console_mod, "_STDERR_CONSOLE", stderr_console)
    monkeypatch.setattr(console_mod, "Panel", lambda body, title, expand=False: ("panel", title, body, expand))
    monkeypatch.setattr(console_mod, "Table", FakeTable)
    monkeypatch.setattr(console_mod, "Syntax", FakeSyntax)
    monkeypatch.setattr(console_mod, "rich_track", lambda items, description: ((description, item) for item in items))

    console_mod.print_status("done", level="success")
    console_mod.print_status("warn", level="warning", stderr=True)
    console_mod.print_panel("Panel", "Body", stderr=True)
    console_mod.print_table("Grid", ["Name", "Value"], [["alpha", 1], ["beta", 2]])

    assert stdout_console.calls[0][0] == "[bold green]OK[/bold green] done"
    assert stderr_console.calls[0][0] == "[bold yellow]WARNING[/bold yellow] warn"
    assert stderr_console.calls[1][0] == ("panel", "Panel", "Body", False)
    table = stdout_console.calls[1][0]
    assert isinstance(table, FakeTable)
    assert table.columns == ["Name", "Value"]
    assert table.rows == [("alpha", "1"), ("beta", "2")]
    assert list(console_mod.track_items([1, 2], description="Load")) == [("Load", 1), ("Load", 2)]

    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("line1\nline2\n", encoding="utf-8")
    console_mod.print_syntax_excerpt(source_path, 2, 3)
    excerpt_call = stderr_console.calls[-1][0]
    assert excerpt_call[0] == "panel"
    assert excerpt_call[1] == f"{source_path}:2:3"
    assert isinstance(excerpt_call[2], FakeSyntax)
    assert excerpt_call[2].highlight_lines == {2}

    missing_path = tmp_path / "Program" / "Missing.s"
    console_mod.print_syntax_excerpt(missing_path, 1, 1)
    unreadable_path = tmp_path / "Program" / "Unreadable.s"
    unreadable_path.write_bytes(b"\xff")
    console_mod.print_syntax_excerpt(unreadable_path, 1, 1)
    console_mod.print_syntax_excerpt(source_path, None, 1)
    assert len(stderr_console.calls) == 3


def test_live_status_line_handles_tty_and_disabled_output() -> None:
    import sattlint.console as console_mod

    class FakeFile:
        def __init__(self, *, tty: bool) -> None:
            self._tty = tty
            self.writes: list[str] = []
            self.flushes = 0

        def isatty(self) -> bool:
            return self._tty

        def write(self, text: str) -> int:
            self.writes.append(text)
            return len(text)

        def flush(self) -> None:
            self.flushes += 1

    tty_file = FakeFile(tty=True)
    with console_mod.live_status_line(file=tty_file) as update:
        update("loading\nstatus")

    joined = "".join(tty_file.writes)
    assert "loading status" in joined
    assert tty_file.flushes >= 2

    disabled_file = FakeFile(tty=False)
    with console_mod.live_status_line(file=disabled_file) as update:
        update("ignored")

    assert disabled_file.writes == []
    assert disabled_file.flushes == 0


def test_print_syntax_excerpt_returns_when_stderr_console_is_missing(monkeypatch, tmp_path) -> None:
    import sattlint.console as console_mod

    source_path = tmp_path / "Program" / "Main.s"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("line1\nline2\n", encoding="utf-8")

    monkeypatch.setattr(console_mod, "_RICH_AVAILABLE", True)
    monkeypatch.setattr(console_mod, "Syntax", object)
    monkeypatch.setattr(console_mod, "Panel", object)
    monkeypatch.setattr(console_mod, "_STDERR_CONSOLE", None)

    console_mod.print_syntax_excerpt(source_path, 1, 1)
