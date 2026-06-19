# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from lark.exceptions import VisitError
from lsprotocol.types import DiagnosticSeverity

import sattlint_lsp.local_parser as lsp_local_parser
from sattline_parser.models.ast_model import (
    FrameModule,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    SingleModule,
    SourceSpan,
)
from sattlint_lsp.local_parser import DocumentParseResult, FullDocumentParserAdapter, IncrementalParseState


def _make_visit_error(message: str = "boom", *, line: int = 7, column: int = 9) -> VisitError:
    class NestedError(Exception):
        pass

    nested = NestedError(message)
    nested.line = line
    nested.column = column
    return VisitError("rule", object(), nested)


def test_local_parser_private_helpers_cover_edge_branches():
    class CastableText(str):
        @classmethod
        def cast_from(cls, value: str) -> "CastableText":
            return cls(f"cast:{value}")

    plain_error = ValueError("plain")
    plain_error.line = 3
    plain_error.column = 4

    assert lsp_local_parser._coerce_lexer_text(CastableText("before"), "after") == "cast:after"
    assert lsp_local_parser._coerce_lexer_text(object(), "after") == "after"
    assert lsp_local_parser._extract_error_position(plain_error) == (3, 4)
    assert lsp_local_parser._extract_error_position(_make_visit_error()) == (7, 9)
    assert lsp_local_parser._split_dotted_name("") == ("", ())

    diagnostics = []
    seen: set[tuple[int, int, str]] = set()
    diagnostic = lsp_local_parser._diagnostic_from_message("msg", None, None)
    assert lsp_local_parser._append_unique_diagnostic(diagnostics, seen, diagnostic) is True
    assert lsp_local_parser._append_unique_diagnostic(diagnostics, seen, diagnostic) is False

    merged = lsp_local_parser._merge_env(
        {"root": SimpleNamespace(name="Root")},
        [SimpleNamespace(name="Child")],
    )
    assert set(merged) == {"root", "child"}


def test_local_parser_sequence_and_module_helpers_cover_recursive_branches():
    step = cast(Any, SFCStep.__new__(SFCStep))
    step.name = "StepA"

    alternative = cast(Any, SFCAlternative.__new__(SFCAlternative))
    alternative.branches = [[step]]

    parallel = cast(Any, SFCParallel.__new__(SFCParallel))
    parallel.branches = [[step]]

    subsequence = cast(Any, SFCSubsequence.__new__(SFCSubsequence))
    subsequence.body = [step]

    transition_sub = cast(Any, SFCTransitionSub.__new__(SFCTransitionSub))
    transition_sub.body = [step]

    known_steps: dict[str, str] = {}
    available_features: dict[str, set[str]] = {}
    lsp_local_parser._collect_sequence_step_features(
        [alternative, parallel, subsequence, transition_sub],
        seqcontrol=True,
        seqtimer=True,
        known_steps=known_steps,
        available_features=available_features,
    )
    assert known_steps == {"stepa": "StepA"}
    assert available_features["stepa"] == {"hold", "reset", "t", "x"}

    diagnostics: list[object] = []
    seen: set[tuple[int, int, str]] = set()
    typedef = cast(
        Any,
        SimpleNamespace(
            moduleparameters=[SimpleNamespace(name="Param")],
            localvariables=[SimpleNamespace(name="Local")],
            modulecode=None,
            submodules=[cast(Any, object())],
        ),
    )
    single_module = cast(Any, SingleModule.__new__(SingleModule))
    single_module.moduleparameters = [SimpleNamespace(name="SingleParam")]
    single_module.localvariables = [SimpleNamespace(name="SingleLocal")]
    single_module.modulecode = None
    frame_module = cast(Any, FrameModule.__new__(FrameModule))
    frame_module.modulecode = None
    frame_module.submodules = [cast(Any, object())]
    single_module.submodules = [frame_module]

    lsp_local_parser._collect_step_auto_variable_diagnostics_for_typedef(typedef, {}, diagnostics, seen)
    lsp_local_parser._collect_step_auto_variable_diagnostics_for_module(single_module, {}, diagnostics, seen)
    lsp_local_parser._collect_step_auto_variable_diagnostics_for_module(frame_module, {}, diagnostics, seen)

    base_picture = cast(
        Any,
        SimpleNamespace(
            localvariables=[SimpleNamespace(name="RootVar")],
            modulecode=None,
            moduletype_defs=[typedef],
            submodules=[single_module, frame_module],
        ),
    )
    assert lsp_local_parser._collect_step_auto_variable_diagnostics(base_picture) == ()


def test_local_parser_step_auto_variable_diagnostics_cover_modulecode_paths(monkeypatch):
    step_a = cast(Any, SFCStep.__new__(SFCStep))
    step_a.name = "StepA"
    step_b = cast(Any, SFCStep.__new__(SFCStep))
    step_b.name = "StepB"

    modulecode = cast(
        Any,
        SimpleNamespace(
            sequences=[
                SimpleNamespace(name="SeqA", seqcontrol=False, seqtimer=False, code=[step_a]),
                SimpleNamespace(name="SeqB", seqcontrol=True, seqtimer=True, code=[step_b]),
            ]
        ),
    )
    span = SourceSpan(12, 4)
    references = [
        "not-a-mapping",
        {"var_name": 1, "span": span},
        {"var_name": "", "span": span},
        {"var_name": "StepA.bad", "span": span},
        {"var_name": "Env.x", "span": span},
        {"var_name": "SeqA.hold", "span": span},
        {"var_name": "SeqA.reset", "span": span},
        {"var_name": "SeqB.hold", "span": span},
        {"var_name": "Missing.hold", "span": span},
        {"var_name": "StepA.hold", "span": span},
        {"var_name": "StepA.reset", "span": span},
        {"var_name": "StepA.t", "span": span},
        {"var_name": "StepA.x", "span": span},
        {"var_name": "StepB.hold", "span": span},
        {"var_name": "StepB.t", "span": span},
    ]

    monkeypatch.setattr(lsp_local_parser, "iter_variable_refs", lambda current_modulecode: references)

    diagnostics: list[Any] = []
    seen: set[tuple[int, int, str]] = set()
    lsp_local_parser._collect_step_auto_variable_diagnostics_for_modulecode(
        modulecode,
        {"env": SimpleNamespace(name="Env")},
        diagnostics,
        seen,
    )

    messages = [diagnostic.message for diagnostic in diagnostics]
    assert any("sequence 'SeqA' only exposes .Hold" in message for message in messages)
    assert any("sequence 'SeqA' only exposes .Reset" in message for message in messages)
    assert any("no sequence step named 'Missing'" in message for message in messages)
    assert any("step 'StepA' only exposes .Hold" in message for message in messages)
    assert any("step 'StepA' only exposes .Reset" in message for message in messages)
    assert any("step 'StepA' only exposes .T" in message for message in messages)


def test_local_parser_analyze_appends_step_auto_diagnostics(monkeypatch, tmp_path: Path):
    adapter = FullDocumentParserAdapter()
    fake_state = cast(
        Any,
        SimpleNamespace(
            cleaned_text="clean",
            base_picture=SimpleNamespace(localvariables=(), modulecode=None, moduletype_defs=(), submodules=()),
        ),
    )
    appended_diagnostic = lsp_local_parser._diagnostic_from_message("auto diagnostic", 2, 3)

    monkeypatch.setattr(lsp_local_parser, "find_disallowed_comments", lambda text: [])
    monkeypatch.setattr(adapter, "_parse_incrementally", lambda *args, **kwargs: fake_state)
    monkeypatch.setattr(
        lsp_local_parser,
        "_collect_step_auto_variable_diagnostics",
        lambda base_picture: (appended_diagnostic,),
    )

    result = adapter.analyze(
        tmp_path / "Program" / "Auto.s",
        "x",
        build_snapshot=False,
        include_comment_validation=False,
    )

    assert [diagnostic.message for diagnostic in result.syntax_diagnostics] == ["auto diagnostic"]


def test_incremental_parser_private_methods_cover_checkpoint_edges():
    adapter = FullDocumentParserAdapter()

    mutable_cursor = cast(
        Any,
        SimpleNamespace(
            lexer_thread=None,
            lexer_state=SimpleNamespace(
                state=SimpleNamespace(line_ctr=SimpleNamespace(char_pos=5, line=3, column=2), text="old")
            ),
            parser_state=object(),
        ),
    )
    immutable_cursor = cast(Any, SimpleNamespace(as_mutable=lambda: mutable_cursor))
    mutable_cursor.as_immutable = lambda: immutable_cursor

    checkpoint = lsp_local_parser._ParseCheckpoint(char_pos=5, line=3, column=2, cursor=immutable_cursor)
    state = IncrementalParseState(cleaned_text="one\ntwo", checkpoints=(checkpoint,), base_picture=cast(Any, object()))

    assert adapter._cursor_lexer(mutable_cursor) is mutable_cursor.lexer_state
    assert adapter._state_from_result(DocumentParseResult(syntax_diagnostics=(), adapter_state=None)) is None
    assert adapter._select_resume_checkpoint(state, "one\ntwo", ()) is None

    checkpoints = [checkpoint]
    adapter._append_checkpoint_if_advanced(checkpoints, mutable_cursor)
    assert checkpoints == [checkpoint]


def test_local_parser_analyze_covers_graphics_comment_and_error_paths(monkeypatch, tmp_path: Path):
    adapter = FullDocumentParserAdapter()

    monkeypatch.setattr(
        lsp_local_parser,
        "validate_graphics_text",
        lambda text, path: SimpleNamespace(
            messages=[
                SimpleNamespace(message="warning", line=1, column=2, length=3, severity="warning"),
                SimpleNamespace(message="error", line=4, column=5, length=1, severity="error"),
            ]
        ),
    )
    graphics_result = adapter.analyze(tmp_path / "Diagram.g", "graphics")
    assert [diagnostic.message for diagnostic in graphics_result.syntax_diagnostics] == ["warning", "error"]
    assert graphics_result.syntax_diagnostics[0].severity == DiagnosticSeverity.Warning
    assert graphics_result.local_snapshot is None

    parse_called = False

    def fail_parse(*args: object, **kwargs: object) -> object:
        nonlocal parse_called
        parse_called = True
        raise AssertionError("comment validation should return before parsing")

    monkeypatch.setattr(adapter, "_parse_incrementally", fail_parse)
    monkeypatch.setattr(
        lsp_local_parser,
        "find_disallowed_comments",
        lambda text: [SimpleNamespace(start_line=2, start_col=4), SimpleNamespace(start_line=2, start_col=4)],
    )
    comment_result = adapter.analyze(
        tmp_path / "Program" / "Main.s",
        "bad comment",
        build_snapshot=False,
        include_comment_validation=True,
    )
    assert parse_called is False
    assert len(comment_result.syntax_diagnostics) == 1

    invalid_result = FullDocumentParserAdapter().analyze(
        tmp_path / "Program" / "Broken.s",
        "not valid sattline",
        build_snapshot=False,
        include_comment_validation=False,
    )
    assert invalid_result.syntax_diagnostics

    monkeypatch.setattr(lsp_local_parser, "find_disallowed_comments", lambda text: [])

    def raise_visit(*args: object, **kwargs: object) -> object:
        raise _make_visit_error("visit boom")

    monkeypatch.setattr(adapter, "_parse_incrementally", raise_visit)
    visit_result = adapter.analyze(
        tmp_path / "Program" / "Visit.s",
        "x",
        build_snapshot=False,
        include_comment_validation=False,
    )
    assert visit_result.syntax_diagnostics[0].message == "visit boom"

    def raise_generic(*args: object, **kwargs: object) -> object:
        raise RuntimeError("generic boom")

    monkeypatch.setattr(adapter, "_parse_incrementally", raise_generic)
    generic_result = adapter.analyze(
        tmp_path / "Program" / "Generic.s",
        "x",
        build_snapshot=False,
        include_comment_validation=False,
    )
    assert generic_result.syntax_diagnostics[0].message == "generic boom"


def test_local_parser_analyze_covers_snapshot_exception_paths(monkeypatch, tmp_path: Path):
    adapter = FullDocumentParserAdapter()
    fake_state = cast(
        Any,
        SimpleNamespace(
            cleaned_text="clean",
            base_picture=SimpleNamespace(localvariables=(), modulecode=None, moduletype_defs=(), submodules=()),
        ),
    )

    monkeypatch.setattr(lsp_local_parser, "find_disallowed_comments", lambda text: [])
    monkeypatch.setattr(adapter, "_parse_incrementally", lambda *args, **kwargs: fake_state)

    monkeypatch.setattr(
        lsp_local_parser,
        "build_source_snapshot_from_basepicture",
        lambda *args, **kwargs: (_ for _ in ()).throw(_make_visit_error("snapshot visit")),
    )
    visit_result = adapter.analyze(
        tmp_path / "Program" / "SnapshotVisit.s",
        "x",
        build_snapshot=True,
        include_comment_validation=False,
    )
    assert visit_result.syntax_diagnostics[0].message == "snapshot visit"

    monkeypatch.setattr(
        lsp_local_parser,
        "build_source_snapshot_from_basepicture",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("snapshot generic")),
    )
    generic_result = adapter.analyze(
        tmp_path / "Program" / "SnapshotGeneric.s",
        "x",
        build_snapshot=True,
        include_comment_validation=False,
    )
    assert generic_result.syntax_diagnostics[0].message == "snapshot generic"


def test_local_parser_fatal_exceptions_propagate(monkeypatch, tmp_path: Path):
    adapter = FullDocumentParserAdapter()
    fake_state = cast(
        Any,
        SimpleNamespace(
            cleaned_text="clean",
            base_picture=SimpleNamespace(localvariables=(), modulecode=None, moduletype_defs=(), submodules=()),
        ),
    )

    monkeypatch.setattr(lsp_local_parser, "find_disallowed_comments", lambda text: [])

    monkeypatch.setattr(
        adapter,
        "_parse_incrementally",
        lambda *args, **kwargs: (_ for _ in ()).throw(MemoryError("parse fatal")),
    )
    with pytest.raises(MemoryError, match="parse fatal"):
        adapter.analyze(
            tmp_path / "Program" / "ParseFatal.s",
            "x",
            build_snapshot=False,
            include_comment_validation=False,
        )

    monkeypatch.setattr(adapter, "_parse_incrementally", lambda *args, **kwargs: fake_state)
    monkeypatch.setattr(
        lsp_local_parser,
        "build_source_snapshot_from_basepicture",
        lambda *args, **kwargs: (_ for _ in ()).throw(MemoryError("snapshot fatal")),
    )
    with pytest.raises(MemoryError, match="snapshot fatal"):
        adapter.analyze(
            tmp_path / "Program" / "SnapshotFatal.s",
            "x",
            build_snapshot=True,
            include_comment_validation=False,
        )
