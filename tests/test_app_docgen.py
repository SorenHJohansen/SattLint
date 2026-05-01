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


def test_preview_documentation_candidates_for_target_handles_empty_candidates(monkeypatch, capsys):
    monkeypatch.setattr(app_docs, "classify_documentation_structure", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(app_docs, "discover_documentation_unit_candidates", lambda *_args, **_kwargs: [])

    app_docs.preview_documentation_candidates_for_target(
        "TargetA",
        cast(BasePicture, SimpleNamespace()),
        cast(ProjectGraph, SimpleNamespace(unavailable_libraries=set())),
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
        cast(ProjectGraph, SimpleNamespace(unavailable_libraries={"ControlLib"})),
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
    target_graph = cast(ProjectGraph, SimpleNamespace())
    cfg = {"documentation": {}}
    app_docs.preview_documentation_unit_candidates(
        cfg,
        iter_loaded_projects_fn=lambda _cfg: iter([("TargetA", target_bp, target_graph)]),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert calls == [("TargetA", target_bp, target_graph, cfg)]
    assert pauses == ["pause"]


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
