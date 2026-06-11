# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
"""Focused documentation preview and generation tests for app docs flows."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import BasePicture
from sattlint import app_docs
from sattlint.models.project_graph import ProjectGraph

from ._app_menus_support import make_input
from .helpers import AnalysisGraphStub


def test_preview_documentation_candidates_for_target_handles_empty_candidates(monkeypatch, capsys):
    monkeypatch.setattr(app_docs, "classify_documentation_structure", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(app_docs, "discover_documentation_unit_candidates", lambda *_args, **_kwargs: [])

    app_docs.preview_documentation_candidates_for_target(
        "TargetA",
        cast(BasePicture, SimpleNamespace()),
        cast(ProjectGraph, AnalysisGraphStub()),
        cfg={"documentation": {}},
    )

    out = capsys.readouterr().out
    assert "=== Target: TargetA ===" in out
    assert "No unit candidates detected." in out


def test_preview_documentation_candidates_for_target_lists_candidates(monkeypatch, capsys):
    classification = object()
    entry = SimpleNamespace(short_path="UnitA", moduletype_label="ApplTank", kind="unit")
    monkeypatch.setattr(app_docs, "classify_documentation_structure", lambda *_args, **_kwargs: classification)
    monkeypatch.setattr(app_docs, "discover_documentation_unit_candidates", lambda *_args, **_kwargs: [entry])
    monkeypatch.setattr(
        app_docs,
        "document_scope_summary",
        lambda _entry, _classification: {"ops": 1, "em": 2, "rp": 3, "ep": 4, "up": 5},
    )

    app_docs.preview_documentation_candidates_for_target(
        "TargetA",
        cast(BasePicture, SimpleNamespace()),
        cast(ProjectGraph, AnalysisGraphStub(unavailable_libraries={"ControlLib"})),
        cfg={"documentation": {}},
    )

    out = capsys.readouterr().out
    assert "1. UnitA | type=ApplTank | ops=1 em=2 rp=3 ep=4 up=5" in out


def test_preview_documentation_unit_candidates_lists_targets_and_pauses(monkeypatch):
    calls: list[tuple[str, object, object, dict[str, object]]] = []
    pauses: list[str] = []

    monkeypatch.setattr(
        app_docs,
        "preview_documentation_candidates_for_target",
        lambda target_name, project_bp, graph, cfg: calls.append((target_name, project_bp, graph, cfg)),
    )

    target_bp = cast(BasePicture, SimpleNamespace())
    target_graph = cast(ProjectGraph, AnalysisGraphStub())
    cfg = {"documentation": {}}
    app_docs.preview_documentation_unit_candidates(
        cfg,
        iter_loaded_projects_fn=lambda _cfg: iter([("TargetA", target_bp, target_graph)]),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls == [("TargetA", target_bp, target_graph, cfg)]
    assert pauses == ["pause"]


def test_preview_documentation_unit_candidates_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(app_docs.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(
        app_docs,
        "preview_documentation_candidates_for_target",
        lambda *_args, **_kwargs: None,
    )

    target_bp = cast(BasePicture, SimpleNamespace())
    target_graph = cast(ProjectGraph, AnalysisGraphStub())
    app_docs.preview_documentation_unit_candidates(
        {"documentation": {}},
        iter_loaded_projects_fn=lambda _cfg: iter([("TargetA", target_bp, target_graph)]),
        pause_fn=lambda: None,
    )

    assert updates == ["Documentation candidates: scanning TargetA"]


def test_run_generate_documentation_skips_unmatched_scoped_target(monkeypatch, capsys):
    class _Scope(SimpleNamespace):
        mode = "instance_paths"
        roots = ()
        unmatched_values = ("Missing.Unit",)

    classification = SimpleNamespace(scope=_Scope())
    monkeypatch.setattr(app_docs, "classify_documentation_structure", lambda *_args, **_kwargs: classification)
    monkeypatch.setattr(
        app_docs, "generate_docx", lambda *_args, **_kwargs: pytest.fail("generate_docx should not run")
    )
    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    target_graph.unavailable_libraries = {"ControlLib"}

    def iter_projects(_cfg: dict[Any, Any]) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
        return iter([("TargetA", target_bp, target_graph)])

    pauses: list[str] = []
    cast(Any, app_docs.run_generate_documentation)(
        cfg={"documentation": {}},
        iter_loaded_projects_fn=cast(Any, iter_projects),
        prompt_fn=lambda _msg, default: default or "out.docx",
        pause_fn=lambda: pauses.append("pause"),
    )

    out = capsys.readouterr().out
    assert "No unit roots matched the configured documentation scope; skipping target." in out
    assert "Unmatched scope filters: Missing.Unit" in out
    assert pauses == ["pause"]


def test_run_generate_documentation_generates_selected_units(monkeypatch, capsys):
    generated: list[tuple[str, set[str], dict[str, object]]] = []
    prompts: list[tuple[str, str | None]] = []
    pauses: list[str] = []

    class _Scope(SimpleNamespace):
        mode = "instance_paths"
        roots = (SimpleNamespace(short_path="UnitA"),)
        unmatched_values = ()

    classification = SimpleNamespace(scope=_Scope())
    monkeypatch.setattr(app_docs, "classify_documentation_structure", lambda *_args, **_kwargs: classification)
    monkeypatch.setattr(
        app_docs,
        "generate_docx",
        lambda _bp, out_name, documentation_config, unavailable_libraries: generated.append(
            (out_name, set(unavailable_libraries), documentation_config["units"])
        ),
    )

    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()
    target_graph.unavailable_libraries = {"ControlLib"}

    app_docs.set_documentation_unit_selection(mode="instance_paths", instance_paths=["UnitA"])
    try:
        app_docs.run_generate_documentation(
            cfg={"documentation": {"classifications": {}}},
            iter_loaded_projects_fn=lambda _cfg: iter([("TargetA", target_bp, target_graph)]),
            prompt_fn=lambda message, default: prompts.append((message, default)) or "chosen.docx",
            pause_fn=lambda: pauses.append("pause"),
        )
    finally:
        app_docs.set_documentation_unit_selection(mode="all")

    out = capsys.readouterr().out
    assert prompts == [("Output DOCX for TargetA", "TargetA_FS.docx")]
    assert "Selected units for TargetA: UnitA" in out
    assert generated == [
        ("chosen.docx", {"ControlLib"}, {"mode": "instance_paths", "instance_paths": ["UnitA"], "moduletype_names": []})
    ]
    assert pauses == ["pause"]


def test_run_generate_documentation_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Scope(SimpleNamespace):
        mode = "all"
        roots = ()
        unmatched_values = ()

    classification = SimpleNamespace(scope=_Scope())
    monkeypatch.setattr(app_docs.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(app_docs, "classify_documentation_structure", lambda *_args, **_kwargs: classification)
    monkeypatch.setattr(app_docs, "generate_docx", lambda *_args, **_kwargs: None)

    target_bp: BasePicture = cast(Any, object())
    target_graph = ProjectGraph()

    app_docs.run_generate_documentation(
        cfg={"documentation": {"classifications": {}}},
        iter_loaded_projects_fn=lambda _cfg: iter([("TargetA", target_bp, target_graph)]),
        prompt_fn=lambda _message, default: default or "out.docx",
        pause_fn=lambda: None,
    )

    assert updates == ["Documentation: classifying TargetA", "Documentation: generating TargetA"]


def test_configure_documentation_scope_by_moduletype_rejects_empty_input(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    pauses: list[str] = []

    changed = app_docs.configure_documentation_scope_by_moduletype(
        split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
        pause_fn=lambda: pauses.append("pause"),
    )

    assert changed is False
    assert pauses == ["pause"]


def test_configure_documentation_scope_by_instance_path_rejects_empty_input(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    pauses: list[str] = []

    changed = app_docs.configure_documentation_scope_by_instance_path(
        split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
        pause_fn=lambda: pauses.append("pause"),
    )

    assert changed is False
    assert pauses == ["pause"]


def test_configure_documentation_scope_by_instance_path_updates_selection(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "UnitA, UnitB")
    pauses: list[str] = []

    try:
        changed = app_docs.configure_documentation_scope_by_instance_path(
            split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
            pause_fn=lambda: pauses.append("pause"),
        )
        selection = app_docs.get_documentation_unit_selection()
    finally:
        app_docs.set_documentation_unit_selection(mode="all")

    assert changed is True
    assert selection == {"mode": "instance_paths", "instance_paths": ["UnitA", "UnitB"], "moduletype_names": []}
    assert pauses == ["pause"]


def test_configure_documentation_scope_by_moduletype_updates_selection(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "ApplTank, XDilute")
    pauses: list[str] = []

    try:
        changed = app_docs.configure_documentation_scope_by_moduletype(
            split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
            pause_fn=lambda: pauses.append("pause"),
        )
        selection = app_docs.get_documentation_unit_selection()
    finally:
        app_docs.set_documentation_unit_selection(mode="all")

    assert changed is True
    assert selection == {"mode": "moduletype_names", "instance_paths": [], "moduletype_names": ["ApplTank", "XDilute"]}
    assert pauses == ["pause"]


def test_reset_documentation_scope_resets_selection():
    pauses: list[str] = []
    app_docs.set_documentation_unit_selection(mode="instance_paths", instance_paths=["UnitA"])

    try:
        changed = app_docs.reset_documentation_scope(pause_fn=lambda: pauses.append("pause"))
        selection = app_docs.get_documentation_unit_selection()
    finally:
        app_docs.set_documentation_unit_selection(mode="all")

    assert changed is True
    assert selection == {"mode": "all", "instance_paths": [], "moduletype_names": []}
    assert pauses == ["pause"]


def test_documentation_menu_routes_actions_tracks_dirty_and_handles_invalid_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actions: list[str] = []
    clears: list[str] = []
    pauses: list[str] = []
    menus: list[tuple[str, int, str | None]] = []

    monkeypatch.setattr(
        app_docs,
        "run_generate_documentation",
        lambda *_args, **_kwargs: actions.append("generate"),
    )
    monkeypatch.setattr(
        app_docs,
        "preview_documentation_unit_candidates",
        lambda *_args, **_kwargs: actions.append("preview"),
    )
    monkeypatch.setattr(
        app_docs,
        "reset_documentation_scope",
        lambda **_kwargs: actions.append("reset") or True,
    )
    monkeypatch.setattr(
        app_docs,
        "configure_documentation_scope_by_moduletype",
        lambda **_kwargs: actions.append("moduletype") or True,
    )
    monkeypatch.setattr(
        app_docs,
        "configure_documentation_scope_by_instance_path",
        lambda **_kwargs: actions.append("instance_path") or False,
    )
    monkeypatch.setattr(builtins, "input", make_input(["1", "2", "3", "4", "5", "x", "b"]))

    app_docs.set_documentation_unit_selection(mode="instance_paths", instance_paths=["UnitA"])
    try:
        dirty = app_docs.documentation_menu(
            {"documentation": {}},
            clear_screen_fn=lambda: clears.append("clear"),
            print_menu_fn=lambda title, options, intro=None, note=None: menus.append((title, len(options), intro)),
            menu_option_factory=lambda key, label, description: {
                "key": key,
                "label": label,
                "description": description,
            },
            quit_app_fn=lambda: pytest.fail("quit_app_fn should not be called"),
            pause_fn=lambda: pauses.append("pause"),
            split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
            iter_loaded_projects_fn=lambda _cfg: iter(()),
            prompt_fn=lambda message, default: default or message,
        )
    finally:
        app_docs.set_documentation_unit_selection(mode="all")

    assert dirty is True
    assert actions == ["generate", "preview", "reset", "moduletype", "instance_path"]
    assert clears == ["clear"] * 7
    assert pauses == ["pause"]
    assert menus and menus[0] == ("Documentation", 7, menus[0][2])


def test_documentation_menu_quit_branch_calls_quit_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    class _QuitSignalError(Exception):
        pass

    monkeypatch.setattr(builtins, "input", make_input(["q"]))

    with pytest.raises(_QuitSignalError):
        app_docs.documentation_menu(
            {"documentation": {}},
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *args, **kwargs: None,
            menu_option_factory=lambda key, label, description: (key, label, description),
            quit_app_fn=lambda: (_ for _ in ()).throw(_QuitSignalError()),
            pause_fn=lambda: None,
            split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
            iter_loaded_projects_fn=lambda _cfg: iter(()),
            prompt_fn=lambda message, default: default or message,
        )


def test_documentation_menu_handles_keyboard_interrupt_and_returns_default_false(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pauses: list[str] = []
    monkeypatch.setattr(builtins, "input", make_input(["4", "b"]))
    monkeypatch.setattr(
        app_docs,
        "configure_documentation_scope_by_moduletype",
        lambda **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    dirty = app_docs.documentation_menu(
        {"documentation": {}},
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *args, **kwargs: None,
        menu_option_factory=lambda key, label, description: (key, label, description),
        quit_app_fn=lambda: pytest.fail("quit_app_fn should not be called"),
        pause_fn=lambda: pauses.append("pause"),
        split_csv_values_fn=lambda raw: [item.strip() for item in raw.split(",") if item.strip()],
        iter_loaded_projects_fn=lambda _cfg: iter(()),
        prompt_fn=lambda message, default: default or message,
    )

    assert dirty is False
    assert pauses == ["pause"]
    assert "Operation canceled. Returning to the menu." in capsys.readouterr().out
