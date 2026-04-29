"""Engine tests for parser setup and project loading."""

import logging
from typing import cast

import pytest

from sattlint import engine


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


def test_loader_resolve_logs_readable_debug_sections(monkeypatch, caplog, tmp_path) -> None:
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

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=True,
    )

    def fake_visit(root_name, graph, strict, requester_dir, syntax_check=False):
        assert root_name == "Root"
        assert strict is False
        assert requester_dir == tmp_path
        assert syntax_check is False
        graph.ast_by_name["iconlib"] = object()
        graph.ast_by_name["configlib"] = object()
        graph.missing.extend(
            [
                "supportlib parse/transform error: BasePicture moduletype 'GetRemoteFile' equation 'Delay' uses OLD on non-STATE variable 'ExecuteLocal'",
                "Missing code file for 'Simulation_PPLib' (draft)",
            ]
        )

    monkeypatch.setattr(loader, "_visit", fake_visit)

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        loader.resolve("Root")

    messages = [record.getMessage() for record in caplog.records]

    assert "[DEBUG] Resolved ASTs (2):" in messages
    assert "[DEBUG]   - iconlib" in messages
    assert "[DEBUG]   - configlib" in messages
    assert "[DEBUG] Missing/failed (2):" in messages
    assert "[DEBUG]   - supportlib" in messages
    assert (
        "[DEBUG]     parse/transform error: BasePicture moduletype 'GetRemoteFile' equation 'Delay' uses OLD on non-STATE variable 'ExecuteLocal'"
        in messages
    )
    assert "[DEBUG]   - Missing code file for 'Simulation_PPLib' (draft)" in messages


def test_loader_can_bypass_file_ast_cache(monkeypatch, tmp_path) -> None:
    class _FakeLookupCache:
        def __init__(self, *_args, **_kwargs):
            pass

    class _FakeAstCache:
        def __init__(self, *_args, **_kwargs):
            self.load_calls = 0
            self.saved = []

        def load(self, *_args, **_kwargs):
            self.load_calls += 1
            return "cached"

        def save(self, *args, **_kwargs):
            self.saved.append(args)

    monkeypatch.setattr(engine, "create_sl_parser", lambda: object())
    monkeypatch.setattr(engine, "SLTransformer", lambda: object())
    monkeypatch.setattr(engine, "FileLookupCache", _FakeLookupCache)
    monkeypatch.setattr(engine, "FileASTCache", _FakeAstCache)
    monkeypatch.setattr(engine, "get_cache_dir", lambda: tmp_path)

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
        use_file_ast_cache=False,
    )

    parsed = object()
    monkeypatch.setattr(loader, "_parse_one", lambda *_args, **_kwargs: parsed)

    result = loader._load_or_parse(tmp_path / "Program.s")
    ast_cache = cast(_FakeAstCache, loader._ast_cache)

    assert result is parsed
    assert ast_cache.load_calls == 0
    assert len(ast_cache.saved) == 1


def test_loader_keeps_dependency_ast_when_validation_warns(monkeypatch, tmp_path) -> None:
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
    root_file.with_suffix(".l").write_text("Dep\n", encoding="utf-8")
    (tmp_path / "Dep.s").write_text(source_text, encoding="utf-8")

    loader = engine.SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=engine.CodeMode.DRAFT,
        scan_root_only=False,
        debug=False,
    )

    call_count = {"value": 0}
    original_validate = engine.validate_transformed_basepicture

    def fake_validate(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise engine.StructuralValidationError("dependency issue")
        return original_validate(*args, **kwargs)

    monkeypatch.setattr(engine, "validate_transformed_basepicture", fake_validate)

    graph = loader.resolve("Root")

    assert "Dep" in graph.ast_by_name
    assert "Root" in graph.ast_by_name
    assert graph.missing == []
    assert any(warning == "Dep: validation warning: dependency issue" for warning in graph.warnings)


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
