"""Engine tests for parser setup and project loading."""

import logging
import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lark.exceptions import VisitError

from sattline_parser.models.ast_model import GraphObject, ModuleDef, ModuleHeader, SingleModule, SourceSpan
from sattlint import _engine_graphics_helpers as engine_graphics_helpers
from sattlint import engine
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import PictureDisplayOccurrence


def _make_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    scan_root_only: bool = True,
    debug: bool = False,
    use_file_ast_cache: bool = True,
) -> engine.SattLineProjectLoader:
    class _FakeLookupCache:
        def __init__(self, *_args, **_kwargs):
            pass

    class _FakeAstCache:
        def __init__(self, *_args, **_kwargs):
            pass

        def load(self, *_args, **_kwargs):
            return None

        def save(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(engine, "create_sl_parser", lambda: object())
    monkeypatch.setattr(engine, "SLTransformer", lambda: object())
    monkeypatch.setattr(engine, "FileLookupCache", _FakeLookupCache)
    monkeypatch.setattr(engine, "FileASTCache", _FakeAstCache)
    monkeypatch.setattr(engine, "get_cache_dir", lambda: tmp_path)

    return engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=scan_root_only,
        debug=debug,
        use_file_ast_cache=use_file_ast_cache,
    )


def _make_basepicture(
    name: str = "Root",
    *,
    origin_file: str = "Root.s",
    origin_lib: str = "rootlib",
    parse_tree: object | None = None,
) -> engine.BasePicture:
    return engine.BasePicture(
        header=ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name=name,
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=ModuleDef(),
        origin_file=origin_file,
        origin_lib=origin_lib,
        parse_tree=parse_tree,
    )


def test_format_debug_list_renders_multiline_bullets() -> None:
    formatted = engine._format_debug_list("Resolved ASTs", ["iconlib", "configlib"])

    assert formatted == ("Resolved ASTs (2):\n  - iconlib\n  - configlib")


def test_format_debug_missing_entries_splits_parse_failures() -> None:
    formatted = engine._format_debug_missing_entries(
        [
            "supportlib parse/transform error: BasePicture moduletype 'GetRemoteFile' equation 'Delay' uses OLD on non-STATE variable 'ExecuteLocal'",
            "Missing code file for 'Simulation_PPLib' (draft)",
        ]
    )

    assert formatted == (
        "Missing/failed (2):\n"
        "  - supportlib\n"
        "    parse/transform error: BasePicture moduletype 'GetRemoteFile' equation 'Delay' uses OLD on non-STATE variable 'ExecuteLocal'\n"
        "  - Missing code file for 'Simulation_PPLib' (draft)"
    )


def test_format_debug_missing_entries_handles_empty_input() -> None:
    assert engine._format_debug_missing_entries([]) == "Missing/failed: none"


def test_expected_unavailable_library_helpers_are_case_insensitive() -> None:
    assert engine.is_expected_unavailable_library("ControlLib") is True
    assert engine.is_expected_unavailable_library("OtherLib") is False
    assert engine.expected_unavailable_library_reason("CONTROLLIB") == "expected proprietary dependency"
    assert engine.expected_unavailable_library_reason("OtherLib") is None


def test_code_mode_extension_helpers_cover_both_modes() -> None:
    assert engine.code_ext(engine.CodeMode.OFFICIAL) == ".x"
    assert engine.code_ext(engine.CodeMode.DRAFT) == ".s"
    assert engine.deps_ext(engine.CodeMode.OFFICIAL) == ".z"
    assert engine.deps_ext(engine.CodeMode.DRAFT) == ".l"
    assert engine.graphics_ext(engine.CodeMode.OFFICIAL) == ".y"
    assert engine.graphics_ext(engine.CodeMode.DRAFT) == ".g"
    assert engine.graphics_ext_candidates(engine.CodeMode.OFFICIAL) == (".y",)
    assert engine.graphics_ext_candidates(engine.CodeMode.DRAFT) == (".g", ".y")


def test_normalize_code_mode_accepts_enum_and_string() -> None:
    assert engine._normalize_code_mode(engine.CodeMode.DRAFT) is engine.CodeMode.DRAFT
    assert engine._normalize_code_mode(" official ") is engine.CodeMode.OFFICIAL
    assert engine._normalize_code_mode("") is None
    assert engine._normalize_code_mode(None) is None


def test_resolve_graphics_companion_path_prefers_existing_candidates(tmp_path: Path) -> None:
    draft_source = tmp_path / "Program.s"
    draft_source.write_text("code", encoding="utf-8")
    draft_graphics = draft_source.with_suffix(".g")
    draft_graphics.write_text("graphics", encoding="utf-8")

    official_source = tmp_path / "Program.x"
    official_source.write_text("code", encoding="utf-8")
    official_graphics = official_source.with_suffix(".y")
    official_graphics.write_text("graphics", encoding="utf-8")

    assert engine.resolve_graphics_companion_path(draft_source) == draft_graphics
    assert engine.resolve_graphics_companion_path(official_source) == official_graphics
    assert engine.resolve_graphics_companion_path(draft_graphics) == draft_graphics
    assert engine.resolve_graphics_companion_path(tmp_path / "Missing.s") is None


def test_graphics_validation_to_syntax_result_merges_warnings_and_errors() -> None:
    result = SimpleNamespace(
        warnings=[SimpleNamespace(message="graphics warning")],
        errors=[SimpleNamespace(message="graphics error", line=4, column=7)],
    )

    syntax = engine._graphics_validation_to_syntax_result(
        Path("Program.g"),
        result,
        warnings=("parse warning",),
    )

    assert syntax == engine.SyntaxValidationResult(
        file_path=Path("Program.g"),
        ok=False,
        stage="graphics",
        message="graphics error",
        line=4,
        column=7,
        warnings=("parse warning", "graphics warning"),
        warning_notices=(
            engine.ValidationNotice(message="parse warning"),
            engine.ValidationNotice(message="graphics warning"),
        ),
    )


def test_graphics_validation_to_syntax_result_returns_ok_without_errors() -> None:
    result = SimpleNamespace(warnings=[SimpleNamespace(message="graphics warning")], errors=[])

    syntax = engine._graphics_validation_to_syntax_result(Path("Program.g"), result)

    assert syntax == engine.SyntaxValidationResult(
        file_path=Path("Program.g"),
        ok=True,
        stage="ok",
        warnings=("graphics warning",),
        warning_notices=(engine.ValidationNotice(message="graphics warning"),),
    )


def test_picture_display_path_warnings_include_declaring_module() -> None:
    child = SingleModule(
        header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
    )
    base_picture = engine.BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        position=(0.0, 0.0, 0.0, 1.0, 1.0),
        moduledef=ModuleDef(),
        submodules=[child],
    )
    occurrences = (
        PictureDisplayOccurrence(
            program_name="Root",
            declaring_module_path=("Root", "L1"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token="<token>",
                        index_value=0,
                        kind="literal",
                        raw_text="AbsentPanel",
                        span=SourceSpan(line=3, column=9),
                    ),
                ),
            ),
        ),
    )

    warnings = engine._picture_display_path_warnings(base_picture, occurrences)

    assert warnings == (
        engine.ValidationNotice(
            message=(
                "PictureDisplay in module 'Root.L1' path 'AbsentPanel' could not be resolved: "
                "module 'AbsentPanel' was not found under 'Root.L1'"
            ),
            line=3,
            column=9,
            length=len("AbsentPanel"),
        ),
    )


def test_record_project_failure_uses_nested_visit_error_position() -> None:
    graph = engine.ProjectGraph()
    nested = engine.StructuralValidationError("bad dependency")
    nested.line = 9
    nested.column = 3
    nested.length = 2
    visit_error = VisitError("node", None, nested)

    engine._record_project_failure(graph, "Dep", visit_error)

    failure = graph.failures["dep"]
    assert graph.missing == [f"Dep parse/transform error: {visit_error}"]
    assert failure.name == "Dep"
    assert failure.line == 9
    assert failure.column == 3
    assert failure.length == 2


def test_load_source_text_decodes_compressed_sources(monkeypatch) -> None:
    debug_lines: list[str] = []

    monkeypatch.setattr(engine, "read_text_with_fallback", lambda _path: "COMPRESSED")
    monkeypatch.setattr(engine, "is_compressed", lambda text: text == "COMPRESSED")
    monkeypatch.setattr(engine, "preprocess_sl_text", lambda text: ("decoded", {"compressed": True}))

    source = engine._load_source_text(Path("Program.s"), debug=debug_lines.append)

    assert source == "decoded"
    assert debug_lines == [
        "Parsing file: Program.s",
        "Compressed format detected; decoding before parsing",
    ]


def test_parse_source_text_delegates_and_validates(monkeypatch) -> None:
    basepic = object()
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_text",
        lambda src, parser=None, transformer=None, debug=None: (
            seen.update({"src": src, "parser": parser, "transformer": transformer, "debug": debug}) or basepic
        ),
    )
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda parsed: seen.update({"validated": parsed}))

    parser = cast(Any, object())
    transformer = cast(Any, object())

    def debug(message):
        return None

    result = engine.parse_source_text("SOURCE", parser=parser, transformer=transformer, debug=debug)

    assert result is basepic
    assert seen == {
        "src": "SOURCE",
        "parser": parser,
        "transformer": transformer,
        "debug": debug,
        "validated": basepic,
    }


def test_validate_single_file_syntax_reports_disallowed_comment_location(monkeypatch) -> None:
    monkeypatch.setattr(engine, "_load_source_text", lambda _path: "source")
    monkeypatch.setattr(
        engine,
        "find_disallowed_comments",
        lambda _src: [SimpleNamespace(start_line=6, start_col=9)],
    )
    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_text",
        lambda _src: pytest.fail("parser should not run when raw-source validation fails"),
    )

    result = engine.validate_single_file_syntax(Path("Program.s"))

    assert result == engine.SyntaxValidationResult(
        file_path=Path("Program.s"),
        ok=False,
        stage="validation",
        message="comment is only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks",
        line=6,
        column=9,
    )


def test_validate_single_file_syntax_reports_transform_errors_from_visit_error(monkeypatch) -> None:
    nested = engine.StructuralValidationError("bad transform")
    nested.line = 11
    nested.column = 4

    monkeypatch.setattr(engine, "_load_source_text", lambda _path: "source")
    monkeypatch.setattr(engine, "find_disallowed_comments", lambda _src: [])
    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_text",
        lambda _src, **_kwargs: (_ for _ in ()).throw(VisitError("node", None, nested)),
    )

    result = engine.validate_single_file_syntax(Path("Program.s"))

    assert result == engine.SyntaxValidationResult(
        file_path=Path("Program.s"),
        ok=False,
        stage="transform",
        message="bad transform",
        line=11,
        column=4,
    )


def test_validate_single_file_syntax_suppresses_expected_parse_failure_logs(monkeypatch, caplog) -> None:
    monkeypatch.setattr(engine, "_load_source_text", lambda _path: "IF X THEN")
    monkeypatch.setattr(engine, "find_disallowed_comments", lambda _src: [])

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        result = engine.validate_single_file_syntax(Path("Program.s"))

    assert result.file_path == Path("Program.s")
    assert result.ok is False
    assert result.stage == "parse"
    assert not caplog.records


def test_validate_single_file_syntax_uses_parse_stage_for_generic_line_errors(monkeypatch) -> None:
    class _LoadFailureError(Exception):
        def __init__(self) -> None:
            super().__init__("bad read")
            self.line = 7
            self.column = 2

    monkeypatch.setattr(
        engine,
        "_load_source_text",
        lambda _path: (_ for _ in ()).throw(_LoadFailureError()),
    )

    result = engine.validate_single_file_syntax(Path("Program.s"))

    assert result == engine.SyntaxValidationResult(
        file_path=Path("Program.s"),
        ok=False,
        stage="parse",
        message="bad read",
        line=7,
        column=2,
    )


def test_validate_single_file_syntax_passes_official_file_flags_to_validation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(engine, "_load_source_text", lambda _path: "source")
    monkeypatch.setattr(engine, "find_disallowed_comments", lambda _src: [])
    monkeypatch.setattr(engine, "parser_core_parse_source_text", lambda _src, **_kwargs: object())
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture",
        lambda _bp, **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(engine, "resolve_graphics_companion_path", lambda *_args, **_kwargs: None)

    result = engine.validate_single_file_syntax(Path("Program.x"))

    assert result == engine.SyntaxValidationResult(file_path=Path("Program.x"), ok=True, stage="ok")
    assert captured["allow_old_state_assignment"] is True
    assert captured["allow_unresolved_external_datatypes"] is True


def test_validate_single_file_syntax_validates_graphics_companion_after_parser_warnings(monkeypatch) -> None:
    warnings: list[str] = []

    monkeypatch.setattr(engine, "_load_source_text", lambda _path: "source")
    monkeypatch.setattr(engine, "find_disallowed_comments", lambda _src: [])
    monkeypatch.setattr(engine, "parser_core_parse_source_text", lambda _src, **_kwargs: object())
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture",
        lambda _bp, warning_sink, **_kwargs: warning_sink("parser warning"),
    )
    monkeypatch.setattr(
        engine,
        "resolve_graphics_companion_path",
        lambda *_args, **_kwargs: Path("Program.g"),
    )
    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda _path: SimpleNamespace(warnings=[SimpleNamespace(message="graphics warning")], errors=[]),
    )

    result = engine.validate_single_file_syntax(Path("Program.s"))

    assert warnings == []
    assert result == engine.SyntaxValidationResult(
        file_path=Path("Program.g"),
        ok=True,
        stage="ok",
        warnings=("parser warning", "graphics warning"),
        warning_notices=(
            engine.ValidationNotice(message="parser warning"),
            engine.ValidationNotice(message="graphics warning"),
        ),
    )


def test_validate_single_file_syntax_preserves_structured_validation_notices(monkeypatch) -> None:
    monkeypatch.setattr(engine, "_load_source_text", lambda _path: "source")
    monkeypatch.setattr(engine, "find_disallowed_comments", lambda _src: [])
    monkeypatch.setattr(engine, "parser_core_parse_source_text", lambda _src, **_kwargs: object())

    def _warn_with_notice(_bp, warning_sink, **_kwargs):
        warning_sink(engine.ValidationNotice("parser warning", line=12, column=9, length=7))

    monkeypatch.setattr(engine, "validate_transformed_basepicture", _warn_with_notice)
    monkeypatch.setattr(engine, "resolve_graphics_companion_path", lambda *_args, **_kwargs: None)

    result = engine.validate_single_file_syntax(Path("Program.s"))

    assert result.ok is True
    assert result.warnings == ("parser warning",)
    assert result.warning_notices == (engine.ValidationNotice("parser warning", line=12, column=9, length=7),)


def test_loader_attaches_graphics_companion_metadata_to_basepicture(monkeypatch, tmp_path) -> None:
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    graphics_file = tmp_path / "Root.g"
    root_file.write_text(source_text, encoding="utf-8")
    graphics_file.write_text("graphics", encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda _path: SimpleNamespace(
            messages=(
                SimpleNamespace(
                    severity="warning",
                    message="asset missing",
                    line=4,
                    column=2,
                    length=5,
                ),
            )
        ),
    )

    graph = loader.resolve("Root")

    bp = graph.ast_by_name["Root"]
    assert bp.graphics_file == "Root.g"
    assert [message.message for message in bp.graphics_messages] == ["asset missing"]
    assert graph.warnings == ["Root: graphics validation warning: asset missing"]
    assert graph.warning_notices == [
        (
            "Root",
            engine.ValidationNotice(
                message="graphics validation warning: asset missing",
                line=4,
                column=2,
                length=5,
            ),
        )
    ]
    assert root_file in graph.source_files
    assert graphics_file not in graph.source_files


def test_attach_graphics_companion_correlates_picturedisplay_records_by_composite_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root_file = tmp_path / "Root.s"
    graphics_file = tmp_path / "Root.g"
    root_file.write_text("source", encoding="utf-8")
    graphics_file.write_text("graphics", encoding="utf-8")

    child = SingleModule(
        header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
    )
    bp = _make_basepicture()
    bp.submodules = [child]
    bp.moduledef = ModuleDef(graph_objects=[GraphObject("CompositeObject")])

    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda _path: SimpleNamespace(
            messages=(),
            bindings=(),
            picture_display_records=(PictureDisplayRecord(record_index=2, record_start_line=3, record_end_line=8),),
        ),
    )

    graph = engine.ProjectGraph()

    engine._attach_graphics_companion(
        bp,
        code_path=root_file,
        mode=engine.CodeMode.DRAFT,
        graph=graph,
        owner_name="Root",
    )

    assert bp.graphics_file == "Root.g"
    assert [record.record_index for record in bp.graphics_picture_display_records] == [2]
    assert len(bp.graphics_picture_display_occurrences) == 1
    assert bp.graphics_picture_display_occurrences[0].declaring_module_path == ("Root",)


def test_attach_graphics_companion_reuses_cached_signature_after_pickle_roundtrip(monkeypatch, tmp_path) -> None:
    root_file = tmp_path / "Root.s"
    graphics_file = tmp_path / "Root.g"
    root_file.write_text("source", encoding="utf-8")
    graphics_file.write_text("graphics", encoding="utf-8")

    graphics_calls: list[Path] = []
    warning_calls: list[str] = []
    warning_notice = engine.ValidationNotice(message="picture warning", line=4, column=2, length=7)

    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda path: (
            graphics_calls.append(path) or SimpleNamespace(messages=(), bindings=(), picture_display_records=())
        ),
    )

    def fake_picture_display_path_warnings(*_args, **_kwargs):
        warning_calls.append("called")
        return (warning_notice,)

    monkeypatch.setattr(
        engine_graphics_helpers,
        "picture_display_path_warnings",
        fake_picture_display_path_warnings,
    )

    first_bp = _make_basepicture(origin_file=root_file.name)
    first_graph = engine.ProjectGraph()
    second_graph = engine.ProjectGraph()

    first_refreshed = engine._attach_graphics_companion(
        first_bp,
        code_path=root_file,
        mode=engine.CodeMode.DRAFT,
        graph=first_graph,
        owner_name="Root",
    )
    cached_bp = pickle.loads(pickle.dumps(first_bp))
    second_refreshed = engine._attach_graphics_companion(
        cached_bp,
        code_path=root_file,
        mode=engine.CodeMode.DRAFT,
        graph=second_graph,
        owner_name="Root",
    )

    assert first_refreshed is True
    assert second_refreshed is False
    assert graphics_calls == [graphics_file]
    assert warning_calls == ["called"]
    assert first_bp.graphics_file == "Root.g"
    assert cached_bp.graphics_file == "Root.g"
    assert getattr(cached_bp, "graphics_warning_notices", ()) == (warning_notice,)
    assert getattr(cached_bp, "graphics_companion_signature", None) is not None
    assert first_graph.warnings == ["Root: picture warning"]
    assert second_graph.warnings == ["Root: picture warning"]


def test_loader_strict_syntax_check_validates_root_before_reading_dependencies(monkeypatch, tmp_path) -> None:
    invalid_root = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "LOCALVARIABLES",
            "    A: integer := 0;",
            "    A: integer := 1;",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    root_file.write_text(invalid_root, encoding="utf-8")
    root_file.with_suffix(".l").write_text("Dep\n", encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    def fail_if_read(*_args, **_kwargs):
        raise AssertionError("dependency list should not be read before strict root validation")

    monkeypatch.setattr(loader, "_read_deps", fail_if_read)

    with pytest.raises(engine.StructuralValidationError, match="duplicate variable names"):
        loader.resolve("Root", strict=True, syntax_check=True)


def test_loader_rejects_circular_dependencies(monkeypatch, tmp_path) -> None:
    """Test that circular dependencies are detected and rejected with clear error."""
    # Create a circular dependency: A -> B -> A
    base_code = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION {}_ 1",
            "LOCALVARIABLES",
            '    Tag: string := "{}";',
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )

    # Create files for circular dependency
    a_file = tmp_path / "LibA.s"
    a_file.write_text(base_code.format("LibA", "299A"), encoding="utf-8")
    a_file.with_suffix(".l").write_text("LibB\n", encoding="utf-8")

    b_file = tmp_path / "LibB.s"
    b_file.write_text(base_code.format("LibB", "299B"), encoding="utf-8")
    b_file.with_suffix(".l").write_text("LibA\n", encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    # Should raise CircularDependencyError with formatted cycle path
    with pytest.raises(engine.CircularDependencyError, match=r"Circular dependency detected:.*->.*") as exc_info:
        loader.resolve("LibA")

    # Verify error contains the cycle information
    assert exc_info.value.cycle_path == ["liba", "libb"]
    assert "LibA" in str(exc_info.value) or "liba" in str(exc_info.value)
    assert "LibB" in str(exc_info.value) or "libb" in str(exc_info.value)


def test_loader_rejects_self_circular_dependency(monkeypatch, tmp_path) -> None:
    """Test that self-referencing circular dependencies (A -> A) are detected."""
    base_code = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION SelfRef_ 1",
            "LOCALVARIABLES",
            '    Tag: string := "299";',
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )

    # Create a file that depends on itself
    self_file = tmp_path / "SelfRef.s"
    self_file.write_text(base_code, encoding="utf-8")
    self_file.with_suffix(".l").write_text("SelfRef\n", encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    # Should raise CircularDependencyError for self-reference
    with pytest.raises(engine.CircularDependencyError, match=r"Circular dependency detected"):
        loader.resolve("SelfRef")


def test_loader_records_expected_unavailable_dependency_with_reason(tmp_path) -> None:
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    root_file.write_text(source_text, encoding="utf-8")
    root_file.with_suffix(".l").write_text("ControlLib\n", encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    graph = loader.resolve("Root")

    assert "controllib" in graph.unavailable_libraries
    assert graph.missing == []
    assert any("expected proprietary dependency" in warning for warning in graph.warnings)


def test_loader_records_missing_dependency_with_requester_context(tmp_path) -> None:
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    root_file.write_text(source_text, encoding="utf-8")
    root_file.with_suffix(".l").write_text("UserLib\n", encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    graph = loader.resolve("Root")

    assert "userlib" in graph.unavailable_libraries
    assert any("dependency 'UserLib' referenced by 'root'" in message for message in graph.missing)


def test_loader_rejects_dependency_version_datecode_conflicts_in_strict_mode(tmp_path) -> None:
    root_source = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    lib_a_source = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "TYPEDEFINITIONS",
            "    SharedType = RECORD DateCode_ 1",
            "        Value: integer;",
            "    ENDDEF (*SharedType*);",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    lib_b_source = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "TYPEDEFINITIONS",
            "    SharedType = RECORD DateCode_ 2",
            "        Value: integer;",
            "    ENDDEF (*SharedType*);",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )

    root_file = tmp_path / "Root.s"
    root_file.write_text(root_source, encoding="utf-8")
    root_file.with_suffix(".l").write_text("LibA\nLibB\n", encoding="utf-8")
    (tmp_path / "LibA.s").write_text(lib_a_source, encoding="utf-8")
    (tmp_path / "LibB.s").write_text(lib_b_source, encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    with pytest.raises(engine.DependencyVersionCompatibilityError, match="SharedType"):
        loader.resolve("Root", strict=True)


def test_loader_rejects_unresolved_external_datatypes_in_strict_mode(tmp_path) -> None:
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "LOCALVARIABLES",
            "    ExternalRef: DI_IOType;",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    root_file.write_text(source_text, encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    with pytest.raises(engine.StructuralValidationError, match="unknown datatype"):
        loader.resolve("Root", strict=True)


def test_loader_allows_unresolved_external_datatypes_in_non_strict_mode(tmp_path) -> None:
    source_text = "\n".join(
        [
            '"SyntaxVersion"',
            '"OriginalFileDate"',
            '"ProgramDate"',
            "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1",
            "LOCALVARIABLES",
            "    ExternalRef: DI_IOType;",
            "ModuleDef",
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "ENDDEF (*BasePicture*);",
        ]
    )
    root_file = tmp_path / "Root.s"
    root_file.write_text(source_text, encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    graph = loader.resolve("Root", strict=False)

    assert "Root" in graph.ast_by_name
    assert graph.missing == []


def test_merge_project_basepicture_merges_dependency_defs_and_sorts_library_deps() -> None:
    root_bp = _make_basepicture()
    datatype = engine.DataType(
        name="SharedType", description=None, datecode=1, origin_file="DepType.s", origin_lib="deplib"
    )
    moduletype = engine.ModuleTypeDef(name="SharedModule", datecode=2, origin_file="DepModule.s", origin_lib="deplib")
    graph = cast(
        Any,
        SimpleNamespace(
            datatype_defs={"sharedtype": datatype},
            moduletype_defs={("deplib", "sharedmodule", "depmodule.s"): moduletype},
            library_dependencies={"rootlib": {"zzlib", "aalib"}},
        ),
    )

    merged = engine.merge_project_basepicture(root_bp, graph)

    assert merged is not root_bp
    assert merged.header == root_bp.header
    assert merged.datatype_defs == [datatype]
    assert merged.moduletype_defs == [moduletype]
    assert merged.library_dependencies == {"rootlib": ["aalib", "zzlib"]}


def test_get_dump_dir_uses_home_scoped_sattlint_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(engine.Path, "home", lambda: tmp_path)

    dump_dir = engine._get_dump_dir()

    assert dump_dir == tmp_path / ".sattlint" / "dumps"
    assert dump_dir.is_dir()


def test_dump_parse_tree_reports_missing_parse_tree(capsys: pytest.CaptureFixture[str]) -> None:
    engine.dump_parse_tree(cast(Any, (_make_basepicture(parse_tree=None), SimpleNamespace())))

    assert "No parse tree available" in capsys.readouterr().out


def test_basepicture_pickle_roundtrip_omits_parse_tree() -> None:
    class _FakeParseTree:
        def pretty(self) -> str:
            return "TREE"

    basepicture = _make_basepicture(parse_tree=_FakeParseTree())

    restored = cast(engine.BasePicture, pickle.loads(pickle.dumps(basepicture)))

    assert restored.header == basepicture.header
    assert restored.origin_file == basepicture.origin_file
    assert restored.origin_lib == basepicture.origin_lib
    assert restored.parse_tree is None


def test_dump_parse_tree_and_ast_write_dump_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FakeParseTree:
        def pretty(self) -> str:
            return "TREE"

    monkeypatch.setattr(engine, "_get_dump_dir", lambda: tmp_path)
    basepicture = _make_basepicture(parse_tree=_FakeParseTree())

    project = cast(Any, (basepicture, SimpleNamespace()))

    engine.dump_parse_tree(project)
    engine.dump_ast(project)

    output = capsys.readouterr().out
    parse_dump = next(tmp_path.glob("parse_tree_Root_*.txt"))
    ast_dump = next(tmp_path.glob("ast_Root_*.txt"))

    assert parse_dump.read_text(encoding="utf-8") == "TREE"
    assert ast_dump.read_text(encoding="utf-8") == str(basepicture)
    assert "saved to:" in output


def test_dump_dependency_graph_writes_all_available_sections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(engine, "_get_dump_dir", lambda: tmp_path)
    basepicture = _make_basepicture()
    datatype = engine.DataType(
        name="SharedType", description=None, datecode=1, origin_file="DepType.s", origin_lib="deplib"
    )
    moduletype = engine.ModuleTypeDef(name="SharedModule", datecode=2, origin_file="DepModule.s", origin_lib="deplib")
    graph = cast(
        Any,
        SimpleNamespace(
            ast_by_name={
                "Dep": SimpleNamespace(origin_lib="deplib", origin_file="Dep.s"),
                "Root": SimpleNamespace(origin_lib="rootlib", origin_file="Root.s"),
            },
            datatype_defs={"sharedtype": datatype},
            moduletype_defs={("deplib", "sharedmodule", "depmodule.s"): moduletype},
            library_dependencies={"rootlib": {"deplib"}},
            missing=["Missing code file for 'OtherLib' (draft)"],
            warnings=["Root: version compatibility warning"],
            ignored_vendor=["VendorLib (vendor: vendor/VendorLib.s)"],
        ),
    )

    engine.dump_dependency_graph(cast(Any, (basepicture, graph)))

    dump_file = next(tmp_path.glob("dependency_graph_Root_*.txt"))
    text = dump_file.read_text(encoding="utf-8")
    output = capsys.readouterr().out

    assert "Programs/Libraries parsed: 2" in text
    assert "Dep (from deplib/Dep.s)" in text
    assert "Root (from rootlib/Root.s)" in text
    assert "DataType Definitions: 1" in text
    assert "sharedtype (from deplib/DepType.s)" in text
    assert "deplib:SharedModule (from deplib/DepModule.s)" in text
    assert "rootlib -> deplib" in text
    assert "Missing code file for 'OtherLib' (draft)" in text
    assert "Root: version compatibility warning" in text
    assert "VendorLib (vendor: vendor/VendorLib.s)" in text
    assert "saved to:" in output


def test_loader_visit_uses_cached_dependency_library_and_warns_on_non_strict_conflicts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    code_path = tmp_path / "Root.s"
    dep_code_path = tmp_path / "Dep.s"
    deps_path = tmp_path / "Root.l"
    basepicture = _make_basepicture()
    dep_basepicture = _make_basepicture("Dep", origin_file="Dep.s", origin_lib="")
    added_dependencies: list[tuple[str, list[str]]] = []
    indexed: list[tuple[object, Path, str]] = []
    graph = cast(
        Any,
        SimpleNamespace(
            ast_by_name={},
            datatype_defs={},
            moduletype_defs={},
            missing=[],
            warnings=[],
            warning_notices=[],
            ignored_vendor=[],
            unavailable_libraries=set(),
            failures={},
            add_library_dependencies=lambda lib, deps: added_dependencies.append((lib, deps)),
            index_from_basepic=lambda bp, *, source_path, library_name: indexed.append((bp, source_path, library_name)),
        ),
    )

    loader._lib_by_name["dep"] = "deplib"
    monkeypatch.setattr(
        loader,
        "_find_deps_with_context",
        lambda name, **_kwargs: deps_path if name == "Root" else None,
    )
    monkeypatch.setattr(loader, "_read_deps", lambda _path: ["Dep"])
    monkeypatch.setattr(
        loader,
        "_find_code_with_context",
        lambda name, **_kwargs: code_path if name == "Root" else dep_code_path if name == "Dep" else None,
    )
    monkeypatch.setattr(loader, "_load_or_parse", lambda path: basepicture if path == code_path else dep_basepicture)
    monkeypatch.setattr(
        loader,
        "_record_library_name",
        lambda name, *_args, **_kwargs: "rootlib" if name == "Root" else "deplib",
    )
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        engine,
        "_collect_dependency_version_conflicts",
        lambda _graph, bp, **_kwargs: ["conflict-a"] if bp is basepicture else [],
    )

    loader._visit("Root", graph, strict=False, requester_dir=tmp_path)

    assert graph.ast_by_name == {"Dep": dep_basepicture, "Root": basepicture}
    assert graph.warnings == ["Root: version compatibility warning: conflict-a"]
    assert added_dependencies[-1] == ("rootlib", ["deplib"])
    assert indexed[-1] == (basepicture, code_path, "rootlib")


def test_loader_visit_records_missing_when_transform_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    graph = cast(
        Any,
        SimpleNamespace(
            ast_by_name={},
            datatype_defs={},
            moduletype_defs={},
            missing=[],
            warnings=[],
            ignored_vendor=[],
            unavailable_libraries=set(),
            failures={},
            add_library_dependencies=lambda *_args, **_kwargs: None,
            index_from_basepic=lambda *_args, **_kwargs: None,
        ),
    )

    monkeypatch.setattr(loader, "_find_deps_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_code_with_context", lambda *_args, **_kwargs: tmp_path / "Root.s")
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: None)

    loader._visit("Root", graph, strict=False, requester_dir=tmp_path)

    assert graph.missing == ["Root transform produced no BasePicture (skipped)"]
    assert "root" in loader._visited


def test_loader_visit_records_validation_warning_before_non_strict_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    basepicture = _make_basepicture()
    graph = cast(
        Any,
        SimpleNamespace(
            ast_by_name={},
            datatype_defs={},
            moduletype_defs={},
            missing=[],
            warnings=[],
            warning_notices=[],
            ignored_vendor=[],
            unavailable_libraries=set(),
            failures={},
            add_library_dependencies=lambda *_args, **_kwargs: None,
            index_from_basepic=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index failed")),
        ),
    )

    monkeypatch.setattr(loader, "_find_deps_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_code_with_context", lambda *_args, **_kwargs: tmp_path / "Root.s")
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path: basepicture)
    monkeypatch.setattr(loader, "_record_library_name", lambda *_args, **_kwargs: "rootlib")
    monkeypatch.setattr(engine, "_collect_dependency_version_conflicts", lambda *_args, **_kwargs: [])

    def _warn_then_continue(_bp, *, warning_sink, **_kwargs):
        warning_sink("warning-a")

    monkeypatch.setattr(engine, "validate_transformed_basepicture", _warn_then_continue)

    loader._visit("Root", graph, strict=False, requester_dir=tmp_path)

    assert graph.warnings == ["Root: warning-a", "Root: warning-a"]
    assert graph.warning_notices == [
        ("Root", engine.ValidationNotice(message="warning-a")),
        ("Root", engine.ValidationNotice(message="warning-a")),
    ]
    assert graph.missing == ["Root parse/transform error: index failed"]
    assert "root" in graph.failures


def test_loader_visit_marks_vendor_only_dependency_as_ignored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    vendor_code = tmp_path / "vendor" / "VendorOnly.s"
    graph = cast(
        Any,
        SimpleNamespace(
            ast_by_name={},
            datatype_defs={},
            moduletype_defs={},
            missing=[],
            warnings=[],
            ignored_vendor=[],
            unavailable_libraries=set(),
            failures={},
            add_library_dependencies=lambda *_args, **_kwargs: None,
            index_from_basepic=lambda *_args, **_kwargs: None,
        ),
    )

    monkeypatch.setattr(loader, "_find_deps_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_code_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_vendor_code", lambda _name: vendor_code)
    monkeypatch.setattr(loader, "_find_vendor_deps", lambda _name: None)

    loader._visit("VendorOnly", graph, strict=False, requester_dir=tmp_path)

    assert graph.ignored_vendor == [f"VendorOnly (vendor: {vendor_code})"]
    assert graph.unavailable_libraries == {"vendoronly"}


def test_loader_visit_records_missing_dependency_with_requester_from_visit_stack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    graph = cast(
        Any,
        SimpleNamespace(
            ast_by_name={},
            datatype_defs={},
            moduletype_defs={},
            missing=[],
            warnings=[],
            ignored_vendor=[],
            unavailable_libraries=set(),
            failures={},
            add_library_dependencies=lambda *_args, **_kwargs: None,
            index_from_basepic=lambda *_args, **_kwargs: None,
        ),
    )

    loader._visit_stack = ["root"]
    monkeypatch.setattr(loader, "_find_deps_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_code_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_vendor_code", lambda _name: None)
    monkeypatch.setattr(loader, "_find_vendor_deps", lambda _name: None)

    loader._visit("MissingDep", graph, strict=False, requester_dir=tmp_path)

    assert graph.missing == ["Missing code file for dependency 'MissingDep' referenced by 'root' (draft)"]
    assert graph.unavailable_libraries == {"missingdep"}
