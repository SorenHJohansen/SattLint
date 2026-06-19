# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false
"""Tail parser loader helper tests split from test_engine.py for structural budget control."""

from __future__ import annotations

import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lark import Lark

from sattline_parser.models.ast_model import GraphObject, ModuleDef, ModuleHeader, SingleModule, SourceSpan
from sattlint import _engine_graphics_context_helpers as engine_graphics_context_helpers
from sattlint import _engine_graphics_helpers as engine_graphics_helpers
from sattlint import engine
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import PictureDisplayOccurrence
from tests.parser._parser_validation_test_support import _parse_to_basepicture
from tests.parser.test_engine import _loader_config, _make_basepicture, _make_loader


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


def test_engine_graphics_cache_helpers_cover_defaults_signatures_and_invalid_payloads(tmp_path: Path) -> None:
    bp = _make_basepicture()
    existing_source = tmp_path / "Root.s"
    existing_source.write_text("source", encoding="utf-8")
    missing_source = tmp_path / "Missing.s"
    cached_notice = engine.ValidationNotice(message="cached", line=2, column=3, length=4)
    graph = engine.ProjectGraph()
    graph.source_files = {existing_source, missing_source}
    graph.ast_by_name["Root"] = object()
    graph.ast_by_name["dep"] = object()
    graph.unavailable_libraries = {"ControlLib", "UserLib"}

    assert engine_graphics_context_helpers._normalized_mode_value(None) is None
    assert engine_graphics_context_helpers._normalized_mode_value(SimpleNamespace(value=" Official ")) == "official"
    assert engine_graphics_helpers._graphics_companion_signature(missing_source) is None
    assert engine_graphics_helpers._graphics_companion_signature(existing_source) is not None
    assert engine_graphics_helpers._cached_graphics_companion_signature(bp) is None

    bp.graphics_companion_signature = ("Root.g", 1)
    assert engine_graphics_helpers._cached_graphics_companion_signature(bp) is None
    bp.graphics_companion_signature = ("Root.g", "bad", 1)
    assert engine_graphics_helpers._cached_graphics_companion_signature(bp) is None

    bp.graphics_warning_notices = [cached_notice]
    assert engine_graphics_helpers._cached_graphics_warning_notices(bp) == (cached_notice,)
    bp.graphics_warning_notices = ["bad"]
    assert engine_graphics_helpers._cached_graphics_warning_notices(bp) is None
    bp.graphics_warning_notices = "bad"
    assert engine_graphics_helpers._cached_graphics_warning_notices(bp) is None

    assert engine_graphics_helpers._cached_graphics_warning_context_signature(bp) is None
    bp.graphics_warning_context_signature = ("bad", "shape")
    assert engine_graphics_helpers._cached_graphics_warning_context_signature(bp) is None
    bp.graphics_warning_context_signature = (["bad"], ("dep", "root"), ("controllib",))
    assert engine_graphics_helpers._cached_graphics_warning_context_signature(bp) is None
    bp.graphics_warning_context_signature = ((("Root.s", None, None),), ["dep", "root"], ("controllib",))
    assert engine_graphics_helpers._cached_graphics_warning_context_signature(bp) is None
    bp.graphics_warning_context_signature = ((("Root.s", None, None),), ("dep", "root"), ["controllib"])
    assert engine_graphics_helpers._cached_graphics_warning_context_signature(bp) is None
    bp.graphics_warning_context_signature = ((("Root.s", None, None),), ("dep", "root"), ("controllib",))
    assert engine_graphics_helpers._cached_graphics_warning_context_signature(bp) == (
        (("Root.s", None, None),),
        ("dep", "root"),
        ("controllib",),
    )

    missing_signature = engine_graphics_helpers._graphics_warning_context_file_signature(missing_source)
    existing_signature = engine_graphics_helpers._graphics_warning_context_file_signature(existing_source)
    graph_signature = engine_graphics_helpers._graphics_warning_context_signature(graph)

    assert missing_signature == (str(missing_source), None, None)
    assert existing_signature[0] == str(existing_source)
    assert graph_signature[1] == ("dep", "root")
    assert graph_signature[2] == ("controllib", "userlib")

    assert engine_graphics_helpers._has_attached_graphics_companion(bp) is True
    assert engine_graphics_helpers._clear_attached_graphics_companion(bp) is True
    assert engine_graphics_helpers._has_attached_graphics_companion(bp) is False
    assert engine_graphics_helpers._clear_attached_graphics_companion(bp) is False


def test_graphics_companion_refresh_and_source_context_helpers_cover_cache_and_companion_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_source = tmp_path / "Missing.s"
    source_path = tmp_path / "Panel.s"
    source_path.write_text("source", encoding="utf-8")
    graphics_path = tmp_path / "Panel.g"
    graphics_path.write_text("graphics", encoding="utf-8")
    official_source = tmp_path / "Panel.x"
    official_source.write_text("official", encoding="utf-8")

    bp = _make_basepicture(origin_file=source_path.name)
    assert (
        engine_graphics_helpers.graphics_companion_needs_refresh(
            bp,
            code_path=missing_source,
            mode=engine.CodeMode.DRAFT,
        )
        is False
    )
    assert (
        engine_graphics_helpers.graphics_companion_needs_refresh(
            bp,
            code_path=source_path,
            mode=engine.CodeMode.DRAFT,
        )
        is True
    )

    bp.graphics_file = graphics_path.name
    assert (
        engine_graphics_helpers.graphics_companion_needs_refresh(
            bp,
            code_path=source_path,
            mode=engine.CodeMode.DRAFT,
        )
        is True
    )

    bp.graphics_companion_signature = engine_graphics_helpers._graphics_companion_signature(graphics_path)
    assert (
        engine_graphics_helpers.graphics_companion_needs_refresh(
            bp,
            code_path=source_path,
            mode=engine.CodeMode.DRAFT,
        )
        is False
    )

    bp.graphics_companion_signature = ("wrong", 0, 0)
    assert (
        engine_graphics_helpers.graphics_companion_needs_refresh(
            bp,
            code_path=source_path,
            mode=engine.CodeMode.DRAFT,
        )
        is True
    )

    same_file_bp = _make_basepicture(origin_file=graphics_path.name)
    same_file_bp.graphics_messages = [SimpleNamespace(message="cached")]
    assert (
        engine_graphics_helpers.graphics_companion_needs_refresh(
            same_file_bp,
            code_path=graphics_path,
            mode=engine.CodeMode.DRAFT,
        )
        is True
    )

    assert engine_graphics_context_helpers.graphics_source_context_path(graphics_path) == source_path
    assert engine_graphics_context_helpers.graphics_source_context_path(tmp_path / "Panel.y") == official_source
    assert engine_graphics_context_helpers.graphics_source_context_path(tmp_path / "Missing.g") is None

    loaded = _make_basepicture(origin_file=official_source.name)
    seen: dict[str, object] = {}
    monkeypatch.setattr(engine_graphics_context_helpers, "read_text_with_fallback", lambda _path: "COMPRESSED")
    monkeypatch.setattr(engine_graphics_context_helpers, "is_compressed", lambda text: text == "COMPRESSED")
    monkeypatch.setattr(
        engine_graphics_context_helpers,
        "preprocess_sl_text",
        lambda text: ("decoded", {"compressed": True}),
    )
    monkeypatch.setattr(
        engine_graphics_context_helpers,
        "parser_core_parse_source_text",
        lambda text: seen.update({"text": text}) or loaded,
    )
    monkeypatch.setattr(
        engine_graphics_context_helpers,
        "validate_transformed_basepicture",
        lambda _bp, **kwargs: seen.update(kwargs),
    )

    assert engine_graphics_context_helpers.load_picture_display_source_context(official_source) == loaded
    assert seen == {
        "text": "decoded",
        "allow_old_state_assignment": True,
        "allow_unresolved_external_datatypes": True,
    }

    monkeypatch.setattr(
        engine_graphics_context_helpers,
        "parser_core_parse_source_text",
        lambda _text: (_ for _ in ()).throw(RuntimeError("bad parse")),
    )
    assert engine_graphics_context_helpers.load_picture_display_source_context(official_source) is None

    monkeypatch.setattr(
        engine_graphics_context_helpers,
        "parser_core_parse_source_text",
        lambda _text: (_ for _ in ()).throw(TypeError("bad parser wiring")),
    )
    with pytest.raises(TypeError, match="bad parser wiring"):
        engine_graphics_context_helpers.load_picture_display_source_context(official_source)


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


def test_engine_wrapper_helpers_cover_file_parsing_and_ok_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    basepicture = _make_basepicture()
    parser = cast(Lark, object())
    transformer = cast(engine.SLTransformer, object())
    debug_messages: list[str] = []
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_file",
        lambda code_path, *, parser, transformer, debug: (
            seen.update(
                {
                    "code_path": code_path,
                    "parser": parser,
                    "transformer": transformer,
                    "debug": debug,
                }
            )
            or basepicture
        ),
    )
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda bp: seen.setdefault("validated", bp))

    parsed = engine.parse_source_file(
        tmp_path / "Program.s",
        parser=parser,
        transformer=transformer,
        debug=debug_messages.append,
    )

    assert parsed is basepicture
    assert seen == {
        "code_path": tmp_path / "Program.s",
        "parser": parser,
        "transformer": transformer,
        "debug": debug_messages.append,
        "validated": basepicture,
    }
    assert engine.is_within_directory(tmp_path / "nested" / "Program.s", tmp_path) is True
    assert engine.is_within_directory(tmp_path.parent / "Elsewhere.s", tmp_path) is False
    engine._raise_syntax_validation_failure(
        engine.SyntaxValidationResult(file_path=tmp_path / "Program.s", ok=True, stage="ok")
    )


def test_validate_single_file_syntax_for_graphics_file_loads_source_context(monkeypatch: pytest.MonkeyPatch) -> None:
    basepicture = _make_basepicture()
    warnings = (engine.ValidationNotice(message="picture warning", line=4, column=2, length=6),)
    occurrence = object()

    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda _path: SimpleNamespace(
            messages=(),
            warnings=(),
            errors=[],
            picture_display_records=(object(),),
        ),
    )
    monkeypatch.setattr(engine, "_graphics_source_context_path", lambda _path: Path("Program.s"))
    monkeypatch.setattr(engine, "_load_picture_display_source_context", lambda _path: basepicture)
    monkeypatch.setattr(engine, "correlate_picture_display_records", lambda _bp, _records: (occurrence,))
    monkeypatch.setattr(engine, "_picture_display_path_warnings", lambda _bp, _occurrences: warnings)

    result = engine.validate_single_file_syntax(Path("Program.g"))

    assert result == engine.SyntaxValidationResult(
        file_path=Path("Program.g"),
        ok=True,
        stage="ok",
        warnings=("picture warning",),
        warning_notices=warnings,
    )


def test_attach_graphics_companion_clears_cached_state_when_no_companion_exists(tmp_path: Path) -> None:
    bp = _make_basepicture(origin_file="Root.s")
    bp.graphics_file = "Root.g"
    bp.graphics_messages = [SimpleNamespace(message="cached")]
    bp.graphics_picture_display_records = [object()]
    bp.graphics_warning_notices = (engine.ValidationNotice(message="cached warning"),)

    refreshed = engine._attach_graphics_companion(
        bp,
        code_path=tmp_path / "Root.s",
        mode=engine.CodeMode.DRAFT,
        graph=engine.ProjectGraph(),
        owner_name="Root",
    )

    assert refreshed is True
    assert bp.graphics_file is None
    assert bp.graphics_messages == []
    assert bp.graphics_picture_display_records == []
    assert bp.graphics_warning_notices == ()


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

    loader = engine.SattLineProjectLoader(_loader_config(tmp_path))

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


def test_attach_graphics_companion_records_graphics_subphase_timings(monkeypatch, tmp_path) -> None:
    root_file = tmp_path / "Root.s"
    graphics_file = tmp_path / "Root.g"
    root_file.write_text("source", encoding="utf-8")
    graphics_file.write_text("graphics", encoding="utf-8")

    timings: list[tuple[str, str, float]] = []
    bp = _make_basepicture(origin_file=root_file.name)
    graph = engine.ProjectGraph()

    monkeypatch.setattr(
        engine,
        "validate_graphics_file",
        lambda _path: SimpleNamespace(
            messages=(),
            bindings=(),
            composite_records=(SimpleNamespace(record_index=1, record_start_line=1, record_end_line=1),),
            picture_display_records=(),
        ),
    )
    monkeypatch.setattr(engine_graphics_helpers, "correlate_composite_records", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(engine_graphics_helpers, "correlate_picture_display_records", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(engine_graphics_helpers, "picture_display_path_warnings", lambda *_args, **_kwargs: ())

    engine._attach_graphics_companion(
        bp,
        code_path=root_file,
        mode=engine.CodeMode.DRAFT,
        graph=graph,
        owner_name="Root",
        timing_sink=lambda owner, phase, duration: timings.append((owner, phase, duration)),
    )

    recorded_phases = {phase for _owner, phase, _duration in timings}
    assert {
        "resolve-companion-path",
        "graphics-signature",
        "validate-graphics-file",
        "correlate-composites",
        "correlate-picture-display",
        "picture-display-warnings",
    } <= recorded_phases
    assert all(owner == "Root" for owner, _phase, _duration in timings)
    assert all(duration >= 0.0 for _owner, _phase, duration in timings)


def test_loader_status_and_lookup_wrappers_cover_blank_duplicate_and_forget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    status_messages: list[str] = []
    loader_any = cast(Any, loader)
    loader_any._status_update_fn = status_messages.append

    class _Cache:
        def __init__(self):
            self.forget_calls: list[tuple[str, str, str]] = []

        def get(self, *_args, **_kwargs):
            return {"base_dir": str(tmp_path), "ext": ".x"}

        def forget(self, kind, name, mode):
            self.forget_calls.append((kind, name, mode))

    cache = _Cache()
    loader_any._lookup_cache = cache

    loader._update_status(" Loading Root ")
    loader._update_status("   ")
    loader._update_status("Loading Root")
    loader._update_status("Loading Dep")

    assert loader._find_in_cached_base(kind="code", name="Program", extensions=[".x"]) is None
    monkeypatch.setattr(loader, "_find_code_with_context", lambda _name, requester_dir=None: tmp_path / "Cached.s")
    monkeypatch.setattr(loader, "_find_deps_with_context", lambda _name, requester_dir=None: tmp_path / "Cached.l")

    assert loader._find_code("Program") == tmp_path / "Cached.s"
    assert loader._find_deps_with_context("Program", requester_dir=None) == tmp_path / "Cached.l"
    assert status_messages == ["Loading Root", "Loading Dep"]
    assert cache.forget_calls == [("code", "Program", "draft")]


def test_record_missing_library_covers_unavailable_and_strict_missing_cases() -> None:
    graph = engine.ProjectGraph()

    engine._record_missing_library(
        graph,
        name="ControlLib",
        mode="draft",
        strict=False,
        requester="ControlLib",
    )

    assert graph.warnings == ["ControlLib: unavailable library: expected proprietary dependency"]
    assert graph.unavailable_libraries == {"controllib"}

    with pytest.raises(FileNotFoundError, match=r"Missing code file for 'MissingLib' \(draft\)"):
        engine._record_missing_library(
            graph,
            name="MissingLib",
            mode="draft",
            strict=True,
        )


def test_loader_lookup_returns_cached_code_and_deps_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Cache:
        def get(self, kind, *_args, **_kwargs):
            return {"base_dir": str(tmp_path), "ext": ".s" if kind == "code" else ".l"}

        def set(self, *_args, **_kwargs):
            return None

        def forget(self, *_args, **_kwargs):
            return None

    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    cast(Any, loader)._lookup_cache = _Cache()
    code_path = tmp_path / "Program.s"
    deps_path = tmp_path / "Program.l"
    code_path.write_text("code", encoding="utf-8")
    deps_path.write_text("deps", encoding="utf-8")

    assert loader._find_code_with_context("Program", requester_dir=tmp_path) == code_path
    assert loader._find_deps_with_context("Program", requester_dir=tmp_path) == deps_path


def test_loader_library_name_for_path_falls_back_when_base_resolve_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other_lib = tmp_path.parent / "OtherLib"
    abb_lib = tmp_path.parent / "AbbLib"
    other_lib.mkdir(exist_ok=True)
    abb_lib.mkdir(exist_ok=True)
    loader = engine.SattLineProjectLoader(
        engine.SattLineProjectLoaderConfig(
            program_dir=tmp_path,
            other_lib_dirs=[other_lib],
            abb_lib_dir=abb_lib,
            mode=engine.CodeMode.DRAFT,
            scan_root_only=False,
            debug=False,
        )
    )

    original_resolve = engine.Path.resolve

    def fake_resolve(path: Path, *args, **kwargs):
        if path in {tmp_path, other_lib, abb_lib}:
            raise OSError("resolve failed")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(engine.Path, "resolve", fake_resolve)

    assert loader._library_name_for_path(tmp_path / "Program.s") == tmp_path.name
    assert loader._library_name_for_path(other_lib / "Program.s") == other_lib.name
    assert loader._library_name_for_path(abb_lib / "Program.s") == abb_lib.name


def test_root_only_loader_success_records_warnings_and_indexes_definitions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)
    save_calls: list[tuple[Path, str, object]] = []

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, code_path, mode, bp):
            save_calls.append((code_path, mode, bp))

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path, owner_name=None: basepicture)
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture",
        lambda _bp, warning_sink, **_kwargs: warning_sink("warning-a"),
    )
    monkeypatch.setattr(engine, "_graphics_companion_needs_refresh", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(engine, "_attach_graphics_companion", lambda *_args, **_kwargs: True)

    graph = loader.resolve("Root")

    assert graph.ast_by_name["Root"] is basepicture
    assert graph.warnings == ["Root: warning-a"]
    assert graph.warning_notices == [("Root", engine.ValidationNotice(message="warning-a"))]
    assert save_calls == [(code_path, "draft", basepicture)]


def test_root_only_loader_strict_none_basepicture_reraises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"

    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path, owner_name=None: None)

    with pytest.raises(RuntimeError, match="transformed to no BasePicture"):
        loader.resolve("Root", strict=True)


def test_root_only_loader_full_mode_records_stage_timings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timings: list[tuple[str, str, float]] = []
    loader = _make_loader(monkeypatch, tmp_path)
    cast(Any, loader)._stage_timing_sink = lambda owner, stage, duration: timings.append((owner, stage, duration))
    code_path = tmp_path / "Root.s"
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, *_args, **_kwargs):
            return None

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_parse_one", lambda _path: basepicture)
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(engine, "_graphics_companion_needs_refresh", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(engine, "_attach_graphics_companion", lambda *_args, **_kwargs: False)

    graph = loader.resolve("Root")

    assert graph.ast_by_name["Root"] is basepicture
    assert {stage for _owner, stage, _duration in timings} == {
        "load_or_parse",
        "validate",
        "attach_graphics",
        "index",
        "ast_cache_save",
    }


def test_ensure_local_validation_ignores_incompatible_parameter_mapping() -> None:
    bp = _parse_to_basepicture(
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    ChildType = MODULEDEFINITION DateCode_ 2
    MODULEPARAMETERS
        Value: integer;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ChildType*);
LOCALVARIABLES
    Flag: boolean := False;
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
        Value => Flag
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    )

    assert engine._ensure_local_validation(bp) is True
    assert getattr(bp, engine._LOCAL_VALIDATION_MARKER_ATTR) == engine.LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION


def test_ensure_local_validation_ignores_builtin_arity_mismatch() -> None:
    bp = _parse_to_basepicture(
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: string;
    Name2: string;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Name2);
ENDDEF (*BasePicture*);
"""
    )

    assert engine._ensure_local_validation(bp) is True
    assert getattr(bp, engine._LOCAL_VALIDATION_MARKER_ATTR) == engine.LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION


def test_load_or_parse_marks_local_validation_and_upgrades_cached_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"
    code_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    parsed = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)
    cached = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)
    save_calls: list[tuple[Path, str, object]] = []
    local_validation_calls: list[object] = []

    class _AstCache:
        def __init__(self) -> None:
            self.calls = 0

        def load(self, *_args, **_kwargs):
            self.calls += 1
            return cached if self.calls == 1 else None

        def save(self, path, mode, bp):
            save_calls.append((path, mode, bp))

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_parse_one", lambda _path: parsed)
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture_locally",
        lambda bp, **_kwargs: local_validation_calls.append(bp),
    )

    cached_result = loader._load_or_parse(code_path, owner_name="Root")
    parsed_result = loader._load_or_parse(code_path, owner_name="Root")

    assert cached_result is cached
    assert parsed_result is parsed
    assert local_validation_calls == [cached]
    assert getattr(cached, engine._LOCAL_VALIDATION_MARKER_ATTR) == engine.LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION
    assert getattr(parsed, engine._LOCAL_VALIDATION_MARKER_ATTR, None) is None
    assert save_calls == [
        (code_path, "draft", cached),
        (code_path, "draft", parsed),
    ]


def test_prefetch_dependency_candidates_populates_prefetched_paths_and_asts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    dep_a_path = tmp_path / "DepA.s"
    dep_b_path = tmp_path / "DepB.s"
    dep_a_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    dep_b_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    dep_a_bp = _make_basepicture(origin_file=dep_a_path.name, origin_lib=tmp_path.name)
    dep_b_bp = _make_basepicture(origin_file=dep_b_path.name, origin_lib=tmp_path.name)
    monkeypatch.setattr(
        loader,
        "_prefetch_ast_candidates",
        lambda code_paths: {
            code_path: engine._PrefetchedLoadResult(
                basepicture=dep_a_bp if code_path == dep_a_path else dep_b_bp,
                load_or_parse_duration_s=0.25,
                ast_cache_save_required=False,
            )
            for code_path in code_paths
        },
    )

    loader._prefetch_dependency_candidates(["DepA", "DepB"], requester_dir=tmp_path)

    dep_a_prefetch = loader._prefetched_dependency_candidates[loader._prefetched_dependency_key("DepA", tmp_path)]
    dep_b_prefetch = loader._prefetched_dependency_candidates[loader._prefetched_dependency_key("DepB", tmp_path)]
    assert dep_a_prefetch.code_path == dep_a_path
    assert dep_b_prefetch.code_path == dep_b_path
    assert loader._prefetched_load_results_by_path[dep_a_path].basepicture is dep_a_bp
    assert loader._prefetched_load_results_by_path[dep_b_path].basepicture is dep_b_bp


def test_load_or_parse_uses_prefetched_duration_and_saves_cache_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timings: list[tuple[str, str, float]] = []
    loader = _make_loader(monkeypatch, tmp_path)
    cast(Any, loader)._stage_timing_sink = lambda owner, stage, duration: timings.append((owner, stage, duration))
    code_path = tmp_path / "Root.s"
    code_path.write_text('"a"\n"b"\n"c"\n', encoding="utf-8")
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)
    save_calls: list[tuple[Path, str, object]] = []

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, path, mode, bp):
            save_calls.append((path, mode, bp))

    cast(Any, loader)._ast_cache = _AstCache()
    cast(Any, loader)._prefetched_load_results_by_path[code_path] = engine._PrefetchedLoadResult(
        basepicture=basepicture,
        load_or_parse_duration_s=0.125,
        ast_cache_save_required=True,
    )

    loaded = loader._load_or_parse(code_path, owner_name="Root")

    assert loaded is basepicture
    assert save_calls == [(code_path, "draft", basepicture)]
    assert ("Root", "load_or_parse", 0.125) in timings


def test_root_only_loader_ast_only_refresh_skips_enrichment_but_records_core_stage_timings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timings: list[tuple[str, str, float]] = []
    loader = _make_loader(monkeypatch, tmp_path)
    loader.refresh_mode = "ast-only"
    cast(Any, loader)._stage_timing_sink = lambda owner, stage, duration: timings.append((owner, stage, duration))
    code_path = tmp_path / "Root.s"
    basepicture = _make_basepicture(origin_file=code_path.name, origin_lib=tmp_path.name)

    class _AstCache:
        def load(self, *_args, **_kwargs):
            return None

        def save(self, *_args, **_kwargs):
            return None

    cast(Any, loader)._ast_cache = _AstCache()
    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_parse_one", lambda _path: basepicture)
    monkeypatch.setattr(engine, "validate_transformed_basepicture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        engine,
        "_graphics_companion_needs_refresh",
        lambda *_args, **_kwargs: pytest.fail("graphics companion checks should be skipped during ast-only refresh"),
    )
    monkeypatch.setattr(
        engine,
        "_attach_graphics_companion",
        lambda *_args, **_kwargs: pytest.fail(
            "graphics companion attachment should be skipped during ast-only refresh"
        ),
    )

    graph = loader.resolve("Root")

    assert graph.ast_by_name["Root"] is basepicture
    assert {stage for _owner, stage, _duration in timings} == {
        "load_or_parse",
        "validate",
        "ast_cache_save",
    }


def test_loader_lookup_skips_ignored_base_before_finding_other_matches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Cache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

        def forget(self, *_args, **_kwargs):
            return None

    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    other_lib = tmp_path.parent / "OtherLib"
    other_lib.mkdir(exist_ok=True)
    (other_lib / "Program.s").write_text("code", encoding="utf-8")
    (other_lib / "Program.l").write_text("deps", encoding="utf-8")
    loader.other_lib_dirs = [other_lib]
    loader._ignored_dirs = {tmp_path}
    cast(Any, loader)._lookup_cache = _Cache()

    assert loader._find_code_with_context("Program", requester_dir=tmp_path) == other_lib / "Program.s"
    assert loader._find_deps_with_context("Program", requester_dir=tmp_path) == other_lib / "Program.l"


def test_loader_visit_short_circuits_and_reraises_strict_none_basepicture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    graph = engine.ProjectGraph()
    loader._visited.add("root")
    loader._visit("Root", graph, strict=False, requester_dir=tmp_path)
    assert loader._visit_stack == []

    loader._visited.clear()
    code_path = tmp_path / "Root.s"
    monkeypatch.setattr(loader, "_find_deps_with_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "_find_code_with_context", lambda *_args, **_kwargs: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path, owner_name=None: None)

    with pytest.raises(RuntimeError, match="transform produced no BasePicture"):
        loader._visit("Root", engine.ProjectGraph(), strict=True, requester_dir=tmp_path)


def test_loader_read_and_library_helpers_cover_all_library_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other_lib = tmp_path.parent / "OtherLib"
    abb_lib = tmp_path.parent / "AbbLib"
    other_lib.mkdir(exist_ok=True)
    abb_lib.mkdir(exist_ok=True)
    loader = engine.SattLineProjectLoader(
        engine.SattLineProjectLoaderConfig(
            program_dir=tmp_path,
            other_lib_dirs=[other_lib],
            abb_lib_dir=abb_lib,
            mode=engine.CodeMode.DRAFT,
            scan_root_only=False,
            debug=False,
        )
    )

    monkeypatch.setattr(engine, "read_text_with_fallback", lambda _path: " DepA \n\nDepB\n")
    external_path = tmp_path.parent / "ExternalLib" / "Program.s"

    assert loader._read_deps(tmp_path / "Program.l") == ["DepA", "DepB"]
    assert engine.read_text_with_fallback(tmp_path / "Program.s") == " DepA \n\nDepB\n"
    assert loader._library_name_for_path(tmp_path / "Program.s") == tmp_path.name
    assert loader._library_name_for_path(other_lib / "Program.s") == "OtherLib"
    assert loader._library_name_for_path(abb_lib / "Program.s") == "AbbLib"
    assert loader._library_name_for_path(external_path) == "ExternalLib"
    assert loader._record_library_name("Program", other_lib / "Program.s") == "OtherLib"
    assert loader._lib_by_name["program"] == "OtherLib"


def test_loader_parse_and_cache_helpers_delegate_and_reuse_cached_ast(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path, scan_root_only=False)
    basepicture = _make_basepicture()
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        engine,
        "parser_core_parse_source_file",
        lambda code_path, *, parser, transformer, debug: (
            seen.update({"code_path": code_path, "parser": parser, "transformer": transformer, "debug": debug})
            or basepicture
        ),
    )

    parsed = loader._parse_one(tmp_path / "Program.s")

    class _AstCache:
        def __init__(self, cached):
            self.cached = cached
            self.save_calls: list[tuple[Path, str, object]] = []

        def load(self, code_path, mode):
            return self.cached

        def save(self, code_path, mode, bp):
            self.save_calls.append((code_path, mode, bp))

    cached_cache = _AstCache(basepicture)
    loader_any = cast(Any, loader)
    loader_any._ast_cache = cached_cache
    cached = loader._load_or_parse(tmp_path / "Program.s")

    parsed_cache = _AstCache(None)
    loader_any._ast_cache = parsed_cache
    monkeypatch.setattr(loader, "_parse_one", lambda _path: basepicture)
    uncached = loader._load_or_parse(tmp_path / "Program.s")

    assert parsed is basepicture
    assert seen == {
        "code_path": tmp_path / "Program.s",
        "parser": loader.parser,
        "transformer": loader.transformer,
        "debug": loader.dbg,
    }
    assert cached is basepicture
    assert cached_cache.save_calls == [(tmp_path / "Program.s", "draft", basepicture)]
    assert uncached is basepicture
    assert parsed_cache.save_calls == [(tmp_path / "Program.s", "draft", basepicture)]


def test_root_only_loader_records_missing_root_library(monkeypatch, tmp_path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    monkeypatch.setattr(loader, "_find_code", lambda _name: None)

    graph = loader.resolve("MissingRoot")

    assert graph.missing == ["Missing code file for 'MissingRoot' (mode=draft)"]
    assert graph.unavailable_libraries == {"missingroot"}


def test_root_only_loader_records_none_basepicture_without_raising(monkeypatch, tmp_path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"

    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path, owner_name=None: None)

    graph = loader.resolve("Root")

    assert graph.missing == ["Root transformed to no BasePicture (parse/transform issue?)"]
    assert graph.ast_by_name == {}


def test_root_only_loader_reraises_source_lookup_errors_and_flushes_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    seen: dict[str, bool] = {"flushed": False}

    monkeypatch.setattr(loader, "_find_code", lambda _name: (_ for _ in ()).throw(ValueError("bad lookup")))
    monkeypatch.setattr(loader, "_flush_lookup_cache", lambda: seen.__setitem__("flushed", True))

    with pytest.raises(ValueError, match="bad lookup"):
        loader.resolve("Root")

    assert seen["flushed"] is True


def test_root_only_loader_records_validation_warning_before_failure(monkeypatch, tmp_path) -> None:
    loader = _make_loader(monkeypatch, tmp_path)
    code_path = tmp_path / "Root.s"

    monkeypatch.setattr(loader, "_find_code", lambda _name: code_path)
    monkeypatch.setattr(loader, "_load_or_parse", lambda _path, owner_name=None: object())
    monkeypatch.setattr(loader, "_library_name_for_path", lambda _path: "RootLib")
    monkeypatch.setattr(
        engine,
        "validate_transformed_basepicture",
        lambda _bp, warning_sink, **_kwargs: (
            warning_sink("warning-a") or (_ for _ in ()).throw(engine.StructuralValidationError("bad root"))
        ),
    )

    graph = loader.resolve("Root")

    assert graph.warnings == ["Root: warning-a"]
    assert graph.warning_notices == [("Root", engine.ValidationNotice(message="warning-a"))]
    assert graph.missing == ["Root parse/transform error: bad root"]
    assert graph.failures["root"].line is None
