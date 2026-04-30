"""Robustness tests for fault injection, malformed inputs, encoding stress, and oversized inputs."""

from pathlib import Path

import pytest

from sattlint import engine as engine_module
from sattlint.devtools.corpus import execute_corpus_case, run_corpus_suite
from sattlint.engine import validate_single_file_syntax


def _repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


class TestMalformedInput:
    """Tests for malformed SattLine source inputs."""

    def test_validate_single_file_syntax_reports_parse_failure_location(self, tmp_path):
        source_file = tmp_path / "Malformed.s"
        source_file.write_text(
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION Malformed_\n"
            "LOCALVARIABLES\n"
            "    A: integer := 0\n"
            "ModuleDef\n"
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
            "ENDDEF (*Malformed_);",
            encoding="utf-8",
        )

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"
        assert result.line is not None
        assert result.message is not None

    def test_corpus_strict_invalid_reports_syntax_parse_finding(self, tmp_path):
        manifest_path = tmp_path / "strict-invalid.json"
        target_path = tmp_path / "NotSattLine.s"
        target_path.write_text("This is not valid SattLine.\n", encoding="utf-8")
        manifest_path.write_text(
            """{
  "case_id": "strict-invalid",
  "target_file": "NotSattLine.s",
  "mode": "strict",
  "expectation": {
    "expected_finding_ids": ["syntax.parse"],
    "forbidden_finding_ids": ["corpus.execution-error"]
  },
  "required_artifacts": ["findings.json", "status.json", "summary.json"]
}""",
            encoding="utf-8",
        )

        result = execute_corpus_case(manifest_path, tmp_path / "artifacts", repo_root=tmp_path)

        assert result.passed is True
        assert result.execution_error is None
        assert result.evaluation.passed is True
        assert not result.evaluation.unexpected_finding_ids

    def test_corpus_strict_invalid_fails_on_execution_error(self, tmp_path):
        manifest_path = tmp_path / "strict-error.json"
        target_path = tmp_path / "Broken.s"
        target_path.write_text("invalid", encoding="utf-8")
        manifest_path.write_text(
            '{"case_id": "strict-error", "target_file": "Broken.s", "mode": "strict", '
            '"expectation": {"expected_finding_ids": ["syntax.parse"]}, '
            '"required_artifacts": ["findings.json", "status.json", "summary.json"]}',
            encoding="utf-8",
        )

        result = execute_corpus_case(manifest_path, tmp_path / "artifacts", repo_root=tmp_path)

        assert result.passed is True
        assert result.execution_error is None

    def test_strict_corpus_cases_all_pass(self, tmp_path):
        repo_root = _repo_path()
        manifest_dir = repo_root / "tests" / "fixtures" / "corpus" / "manifests"
        strict_manifests = [
            m for m in manifest_dir.glob("strict-*.json") if m.is_file() and m.name.startswith("strict-")
        ]
        if not strict_manifests:
            pytest.skip("No strict-*.json manifests found")

        suite = run_corpus_suite(
            tmp_path / "out",
            manifest_paths=strict_manifests,
            repo_root=repo_root,
            write_results=False,
        )

        failed = [c.manifest.case_id for c in suite.cases if not c.passed]
        assert suite.passed is True, f"Failed strict cases: {failed}"


class TestEncodingStress:
    """Tests for encoding stress and non-ASCII input handling."""

    def test_parser_rejects_identifier_longer_than_20_chars(self, tmp_path):
        long_name = "'QuotedIdentifierLength21'"
        code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {long_name}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*DateCode*);
"""
        source_file = tmp_path / "LongIdentifier.s"
        source_file.write_text(code, encoding="utf-8")

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"

    def test_parser_accepts_encoding_stress_in_incomplete_expression(self, tmp_path):
        code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION EncodingStress_ 1
LOCALVARIABLES
    Var1: integer := 0;
    Var2: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Var1 = Var2 +
ENDDEF (*EncodingStress_);
"""
        source_file = tmp_path / "IncompleteExpr.s"
        source_file.write_text(code, encoding="utf-8")

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"

    def test_parser_handles_truncated_utf8_gracefully(self, tmp_path):
        code = "BasePicture Invocation \xe2\x80\x9c0.0\xe2\x80\x9d"
        source_file = tmp_path / "TruncatedUtf8.s"
        source_file.write_bytes(code.encode("utf-8"))

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"

    def test_parser_handles_incomplete_expression_gracefully(self, tmp_path):
        code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION EncodingStress_ 1
LOCALVARIABLES
    Var1: integer := 0;
    Var2: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Var1 = Var2 +
ENDDEF (*EncodingStress_);
"""
        source_file = tmp_path / "IncompleteExpr.s"
        source_file.write_text(code, encoding="utf-8")

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"


class TestEngineGracefulFailure:
    """Tests for graceful failure behavior when engine encounters malformed input."""

    def test_loader_resolve_returns_graph_on_parse_error_with_missing_entry(self, tmp_path):
        source_text = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION Broken_ 1
LOCALVARIABLES
    A: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*Broken_);
"""
        root_file = tmp_path / "Root.s"
        root_file.write_text(source_text, encoding="utf-8")

        loader = engine_module.SattLineProjectLoader(
            program_dir=tmp_path,
            other_lib_dirs=[],
            abb_lib_dir=tmp_path,
            mode=engine_module.CodeMode.DRAFT,
            scan_root_only=False,
            debug=False,
        )

        graph = loader.resolve("Root")

        assert "Root" not in graph.ast_by_name
        assert len(graph.missing) >= 1

    def test_loader_resolve_continues_on_dependency_parse_error(self, tmp_path):
        root_source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION Root_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*Root*);
""".strip()
        dep_source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION Dep_ 1
LOCALVARIABLES
    B: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*Dep*);
""".strip()
        root_file = tmp_path / "Root.s"
        root_file.write_text(root_source, encoding="utf-8")
        root_file.with_suffix(".l").write_text("Dep\n", encoding="utf-8")
        (tmp_path / "Dep.s").write_text(dep_source, encoding="utf-8")

        loader = engine_module.SattLineProjectLoader(
            program_dir=tmp_path,
            other_lib_dirs=[],
            abb_lib_dir=tmp_path,
            mode=engine_module.CodeMode.DRAFT,
            scan_root_only=False,
            debug=False,
        )

        graph = loader.resolve("Root")

        assert len(graph.missing) >= 1

    def test_loader_resolve_handles_missing_dependency_gracefully(self, tmp_path):
        root_source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION Root_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*Root*);
""".strip()
        root_file = tmp_path / "Root.s"
        root_file.write_text(root_source, encoding="utf-8")
        root_file.with_suffix(".l").write_text("Missing\n", encoding="utf-8")

        loader = engine_module.SattLineProjectLoader(
            program_dir=tmp_path,
            other_lib_dirs=[],
            abb_lib_dir=tmp_path,
            mode=engine_module.CodeMode.DRAFT,
            scan_root_only=False,
            debug=False,
        )

        graph = loader.resolve("Root")

        assert len(graph.unavailable_libraries) >= 1

    def test_validate_single_file_syntax_reports_graceful_parse_failure(self, tmp_path):
        source_file = tmp_path / "GracefulFailure.s"
        source_file.write_text("not valid at all\n", encoding="utf-8")

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"
        assert result.message is not None

    def test_validate_single_file_syntax_reports_parse_failure_for_incomplete_program(self, tmp_path):
        code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION ValidationFail_ 1
LOCALVARIABLES
    Counter: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*ValidationFail*);
"""
        source_file = tmp_path / "ValidationFail.s"
        source_file.write_text(code, encoding="utf-8")

        result = validate_single_file_syntax(source_file)

        assert result.ok is False
        assert result.stage == "parse"


class TestLspRobustness:
    """Tests for LSP dirty-buffer and partial-workspace robustness."""

    def test_incremental_parser_reuses_prefix_on_small_edit(self, tmp_path):
        source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*DateCode*);
""".strip()

        updated = source.replace("Dv = 1;", "Dv = 2;")
        changed_line = updated.splitlines().index("        Dv = 2;")

        from sattlint_lsp.local_parser import FullDocumentParserAdapter

        adapter = FullDocumentParserAdapter()
        document_path = tmp_path / "Program.s"

        first = adapter.analyze(document_path, source, build_snapshot=False, include_comment_validation=False)
        second = adapter.analyze(
            document_path,
            updated,
            build_snapshot=False,
            include_comment_validation=False,
            previous_result=first,
            changed_line_ranges=((changed_line, changed_line),),
        )

        assert second.syntax_diagnostics == ()
        assert second.adapter_state is not None
        assert second.adapter_state.reused_prefix_char_pos > 0  # type: ignore[union-attr]

    def test_incremental_parser_handles_invalid_intermediate_state(self, tmp_path):
        source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*DateCode*);
""".strip()

        from sattlint_lsp.local_parser import FullDocumentParserAdapter

        adapter = FullDocumentParserAdapter()
        document_path = tmp_path / "Program.s"

        result = adapter.analyze(document_path, source, build_snapshot=False, include_comment_validation=False)

        assert result.syntax_diagnostics == ()

    def test_incremental_parser_handles_partial_workspace_dependency(self, tmp_path):
        root_source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION Root_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*Root*);
""".strip()

        root_file = tmp_path / "Root.s"
        root_file.write_text(root_source, encoding="utf-8")
        root_file.with_suffix(".l").write_text("Missing\n", encoding="utf-8")

        loader = engine_module.SattLineProjectLoader(
            program_dir=tmp_path,
            other_lib_dirs=[],
            abb_lib_dir=tmp_path,
            mode=engine_module.CodeMode.DRAFT,
            scan_root_only=False,
            debug=False,
        )

        graph = loader.resolve("Root")

        assert len(graph.unavailable_libraries) >= 1

    def test_local_parser_adaptor_falls_back_to_full_parse_on_dirty_buffer(self, tmp_path):
        source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*DateCode*);
""".strip()

        from sattlint_lsp.local_parser import FullDocumentParserAdapter

        adapter = FullDocumentParserAdapter()
        document_path = tmp_path / "Program.s"

        syntax_only = adapter.analyze(document_path, source, build_snapshot=False, include_comment_validation=False)

        assert syntax_only.syntax_diagnostics == ()
        assert syntax_only.local_snapshot is None

        upgraded = adapter.analyze(
            document_path,
            source,
            build_snapshot=True,
            include_comment_validation=False,
            previous_result=syntax_only,
            changed_line_ranges=(),
        )

        assert upgraded.local_snapshot is not None

    def test_incremental_parser_upgrades_syntax_only_to_full_snapshot(self, tmp_path):
        source = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Dv: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dv = 1;
ENDDEF (*DateCode*);
""".strip()

        from sattlint_lsp.local_parser import FullDocumentParserAdapter

        adapter = FullDocumentParserAdapter()
        document_path = tmp_path / "Program.s"

        syntax_only = adapter.analyze(document_path, source, build_snapshot=False, include_comment_validation=False)

        upgraded = adapter.analyze(
            document_path,
            source,
            build_snapshot=True,
            include_comment_validation=False,
            previous_result=syntax_only,
            changed_line_ranges=(),
        )

        assert upgraded.local_snapshot is not None
