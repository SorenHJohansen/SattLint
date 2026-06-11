# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportArgumentType=false

"""Focused graphics prompt and selector tests for the app."""

from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import app

from .helpers import make_input


def test_pick_or_prompt_graphics_rule_selector_value_handles_invalid_index_then_manual_entry(monkeypatch):
    outputs: list[str] = []

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(builtins, "input", make_input(["9", "m", "Area.UnitControl"]))

    selected = app.app_graphics_module.pick_or_prompt_graphics_rule_selector_value(
        "unit_structure_path",
        "single",
        cfg=app.DEFAULT_CONFIG.copy(),
        discover_graphics_rule_selector_options_fn=lambda *_args, **_kwargs: [
            {
                "selector_value": "L1.L2.UnitControl",
                "count": 2,
                "target_count": 1,
                "sample_module_path": "TargetA.UnitA.L1.L2.UnitControl",
            }
        ],
    )

    assert selected == "Area.UnitControl"
    assert "? Invalid index" in outputs


def test_prompt_graphics_rule_kind_reprompts_until_valid(monkeypatch):
    outputs: list[str] = []

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(builtins, "input", make_input(["9", "2"]))

    selected = app.app_graphics_module.prompt_graphics_rule_kind()

    assert selected == "single"
    assert "? Choose 1, 2, or 3" in outputs


def test_prompt_graphics_rule_selector_reprompts_for_scope_choice(monkeypatch):
    outputs: list[str] = []
    selector_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_pick(selector_field: str, module_kind: str, *, cfg: dict[str, Any] | None = None) -> str:
        selector_calls.append((selector_field, module_kind, cfg))
        return "Area.UnitControl"

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(builtins, "input", make_input(["9", "2"]))

    selector_field, selector_value = app.app_graphics_module.prompt_graphics_rule_selector(
        "single",
        cfg=app.DEFAULT_CONFIG.copy(),
        pick_or_prompt_graphics_rule_selector_value_fn=fake_pick,
    )

    assert (selector_field, selector_value) == ("unit_structure_path", "Area.UnitControl")
    assert selector_calls == [("unit_structure_path", "single", app.DEFAULT_CONFIG.copy())]
    assert "? Choose 1, 2, or 3" in outputs


def test_prompt_graphics_rule_selector_can_use_interaction_choice_handler():
    selector_calls: list[tuple[str, str, dict[str, Any] | None]] = []
    menu_titles: list[str] = []

    def fake_pick(selector_field: str, module_kind: str, *, cfg: dict[str, Any] | None = None) -> str:
        selector_calls.append((selector_field, module_kind, cfg))
        return "Area.UnitControl"

    interaction = app.app_interaction_module.MenuInteraction(
        choose_menu_option=lambda title, _options, **_kwargs: menu_titles.append(title) or "2",
        prompt=lambda message, default=None: default or message,
        confirm=lambda _message: False,
        pause=lambda: None,
    )

    selector_field, selector_value = app.app_graphics_module.prompt_graphics_rule_selector(
        "single",
        cfg=app.DEFAULT_CONFIG.copy(),
        pick_or_prompt_graphics_rule_selector_value_fn=fake_pick,
        interaction=interaction,
    )

    assert (selector_field, selector_value) == ("unit_structure_path", "Area.UnitControl")
    assert selector_calls == [("unit_structure_path", "single", app.DEFAULT_CONFIG.copy())]
    assert menu_titles == ["Selector Scope"]


def test_optional_prompt_or_none_returns_none_for_skip_and_validation_errors():
    def raise_skip() -> None:
        raise app.app_graphics_module.OptionalPromptSkipped()

    def raise_validation() -> None:
        raise app.app_graphics_module.OptionalPromptValidationError("bad input")

    assert app.app_graphics_module.optional_prompt_or_none(lambda: 42) == 42
    assert app.app_graphics_module.optional_prompt_or_none(raise_skip) is None
    assert app.app_graphics_module.optional_prompt_or_none(raise_validation) is None


def test_prompt_graphics_rule_definition_requires_moduletype_name(monkeypatch):
    outputs: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(app.app_graphics_module, "prompt_graphics_rule_kind", lambda: "moduletype")

    result = app.app_graphics_module.prompt_graphics_rule_definition_with_config(
        None,
        prompt_fn=lambda _label: "",
        pause_fn=lambda: pauses.append("pause"),
        pick_or_prompt_graphics_rule_selector_value_fn=lambda *_args, **_kwargs: pytest.fail(
            "selector prompt should not run"
        ),
    )

    assert result is None
    assert "? ModuleType name is required" in outputs
    assert pauses == ["pause"]


def test_prompt_graphics_rule_definition_rejects_invalid_grid(monkeypatch):
    outputs: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(app.app_graphics_module, "prompt_graphics_rule_kind", lambda: "frame")
    monkeypatch.setattr(
        app.app_graphics_module,
        "prompt_graphics_rule_selector",
        lambda *_args, **_kwargs: ("relative_module_path", "Equipmentmoduler.Stop.L1"),
    )
    monkeypatch.setattr(app.app_graphics_module, "optional_prompt_or_none", lambda _prompt_fn: None)
    monkeypatch.setattr(builtins, "input", make_input(["Stop rule", "", "oops"]))

    result = app.app_graphics_module.prompt_graphics_rule_definition_with_config(
        None,
        prompt_fn=lambda _label: "",
        pause_fn=lambda: pauses.append("pause"),
        pick_or_prompt_graphics_rule_selector_value_fn=lambda *_args, **_kwargs: "unused",
    )

    assert result is None
    assert "? ModuleDef grid must be numeric" in outputs
    assert pauses == ["pause"]


def test_prompt_graphics_rule_definition_requires_expected_fields(monkeypatch):
    outputs: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(app.app_graphics_module, "prompt_graphics_rule_kind", lambda: "frame")
    monkeypatch.setattr(
        app.app_graphics_module,
        "prompt_graphics_rule_selector",
        lambda *_args, **_kwargs: ("relative_module_path", "Equipmentmoduler.Stop.L1"),
    )
    monkeypatch.setattr(app.app_graphics_module, "optional_prompt_or_none", lambda _prompt_fn: None)
    monkeypatch.setattr(builtins, "input", make_input(["", "", ""]))

    result = app.app_graphics_module.prompt_graphics_rule_definition_with_config(
        None,
        prompt_fn=lambda _label: "",
        pause_fn=lambda: pauses.append("pause"),
        pick_or_prompt_graphics_rule_selector_value_fn=lambda *_args, **_kwargs: "unused",
    )

    assert result is None
    assert "? At least one expected graphics field is required" in outputs
    assert pauses == ["pause"]


def test_prompt_graphics_rule_definition_builds_expected_payload(monkeypatch):
    optional_values = iter(
        [
            [1.43, 1.35, 0.0, 0.56, 0.56],
            ["ArgA", "ArgB"],
            [0.5, 1.5],
            True,
            [0.0, 0.0],
            [1.0, 0.21429],
            [0.25, 2.0],
            False,
        ]
    )

    monkeypatch.setattr(app.app_graphics_module, "prompt_graphics_rule_kind", lambda: "single")
    monkeypatch.setattr(
        app.app_graphics_module,
        "prompt_graphics_rule_selector",
        lambda *_args, **_kwargs: ("unit_structure_path", "Area.UnitControl"),
    )
    monkeypatch.setattr(
        app.app_graphics_module,
        "optional_prompt_or_none",
        lambda _prompt_fn: next(optional_values),
    )
    monkeypatch.setattr(builtins, "input", make_input(["House rule", "LayerA", "0.5"]))

    result = app.app_graphics_module.prompt_graphics_rule_definition_with_config(
        None,
        prompt_fn=lambda _label: "",
        pause_fn=lambda: pytest.fail("pause should not run"),
        pick_or_prompt_graphics_rule_selector_value_fn=lambda *_args, **_kwargs: "unused",
    )

    assert result == {
        "module_name": "UnitControl",
        "module_kind": "single",
        "relative_module_path": "",
        "unit_structure_path": "Area.UnitControl",
        "equipment_module_structure_path": "",
        "moduletype_name": "",
        "description": "House rule",
        "expected": {
            "invocation": {
                "coords": [1.43, 1.35, 0.0, 0.56, 0.56],
                "arguments": ["ArgA", "ArgB"],
                "layer": "LayerA",
                "zoom_limits": [0.5, 1.5],
                "zoomable": True,
            },
            "moduledef": {
                "clipping_origin": [0.0, 0.0],
                "clipping_size": [1.0, 0.21429],
                "zoom_limits": [0.25, 2.0],
                "grid": 0.5,
                "zoomable": False,
            },
        },
    }


def test_app_graphics_wrappers_delegate_rule_io_and_reports(monkeypatch, tmp_path):
    outputs: list[str] = []
    cfg = app.DEFAULT_CONFIG.copy()
    config_path = tmp_path / "config.json"
    rules_path = tmp_path / "graphics_rules.json"
    rows = [("alpha", 1)]
    items = ["item"]
    rule = {"selector_value": "Area.UnitControl"}
    captured: dict[str, Any] = {}

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(
        app.app_graphics_module.graphics_rules_module, "get_graphics_rules_path", lambda _path: rules_path
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_rules_module,
        "load_graphics_rules",
        lambda _path: ({"rules": [rule]}, True),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_rules_module,
        "save_graphics_rules",
        lambda path, rules: captured.setdefault("save", (path, rules)),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "format_config_scalar",
        lambda value: f"fmt:{value}",
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "print_config_section",
        lambda title, rows, **kwargs: captured.setdefault("section", (title, rows, kwargs)),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "print_config_list",
        lambda title, items, **kwargs: captured.setdefault("list", (title, items, kwargs)),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "show_config",
        lambda passed_cfg, **kwargs: captured.setdefault("show", (passed_cfg, kwargs)),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "flatten_graphics_expected_fields",
        lambda payload, prefix="": [f"{prefix}field"],
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module, "truncate_table_cell", lambda value, width: "trim"
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "graphics_rule_selector_text",
        lambda passed_rule: f"selector:{passed_rule['selector_value']}",
    )
    monkeypatch.setattr(app.app_graphics_module.graphics_reports_module, "graphics_rule_label", lambda _rule: "label")
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module, "graphics_rule_scope_text", lambda _rule: "scope"
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module, "graphics_rule_config_line", lambda _rule: "config"
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_reports_module,
        "print_graphics_rules_summary",
        lambda path, rules, **kwargs: captured.setdefault("summary", (path, rules, kwargs)),
    )

    assert app.app_graphics_module.get_graphics_rules_path(config_path) == rules_path
    assert app.app_graphics_module.load_graphics_rules(config_path) == ({"rules": [rule]}, True)
    app.app_graphics_module.save_graphics_rules(rules_path, {"rules": [rule]})
    assert captured["save"] == (rules_path, {"rules": [rule]})

    monkeypatch.setattr(
        app.app_graphics_module.graphics_rules_module,
        "load_graphics_rules",
        lambda _path: (_ for _ in ()).throw(ValueError("bad rules")),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_rules_module, "normalize_graphics_rules", lambda _value: {"rules": []}
    )
    assert app.app_graphics_module.load_graphics_rules(config_path) == ({"rules": []}, False)
    assert any("Using defaults" in output for output in outputs)

    assert app.app_graphics_module._format_config_scalar(3) == "fmt:3"
    app.app_graphics_module._print_config_section("Section", rows)
    app.app_graphics_module._print_config_list("List", items)
    app.app_graphics_module.show_config(
        cfg,
        get_graphics_rules_path_fn=lambda: rules_path,
        load_graphics_rules_fn=lambda *_args, **_kwargs: ({"rules": [rule]}, True),
        graphics_rule_config_line_fn=lambda _rule: "rule-config",
    )
    assert app.app_graphics_module.flatten_graphics_expected_fields({"expected": {}}, prefix="pre.") == ["pre.field"]
    assert app.app_graphics_module.truncate_table_cell("demo", 4) == "trim"
    assert app.app_graphics_module.graphics_rule_selector_text(rule) == "selector:Area.UnitControl"
    assert app.app_graphics_module.graphics_rule_label(rule) == "label"
    assert app.app_graphics_module.graphics_rule_scope_text(rule) == "scope"
    assert app.app_graphics_module.graphics_rule_config_line(rule) == "config"
    app.app_graphics_module.print_graphics_rules_summary(rules_path, {"rules": [rule]}, dirty=True)

    assert captured["section"][0] == "Section"
    assert captured["list"][0] == "List"
    assert captured["show"][0] == cfg
    assert captured["summary"][0] == rules_path


def test_app_graphics_optional_prompt_helpers(monkeypatch):
    outputs: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)

    monkeypatch.setattr(builtins, "input", make_input(["1, 2"]))
    assert app.app_graphics_module.prompt_optional_float_list("Coords", 2, pause_fn=lambda: pauses.append("pause")) == [
        1.0,
        2.0,
    ]

    monkeypatch.setattr(builtins, "input", make_input([""]))
    with pytest.raises(app.app_graphics_module.OptionalPromptSkipped):
        app.app_graphics_module.prompt_optional_float_list("Coords", 2, pause_fn=lambda: pauses.append("pause"))

    monkeypatch.setattr(builtins, "input", make_input(["a, b"]))
    with pytest.raises(app.app_graphics_module.OptionalPromptValidationError, match="Must be numeric"):
        app.app_graphics_module.prompt_optional_float_list("Coords", 2, pause_fn=lambda: pauses.append("pause"))

    monkeypatch.setattr(builtins, "input", make_input(["1"]))
    with pytest.raises(app.app_graphics_module.OptionalPromptValidationError, match="Expected 2 values"):
        app.app_graphics_module.prompt_optional_float_list("Coords", 2, pause_fn=lambda: pauses.append("pause"))

    monkeypatch.setattr(builtins, "input", make_input(["Alpha, Beta", "", "yes", "no", "maybe", ""]))
    assert app.app_graphics_module.prompt_optional_text_list("Tags") == ["Alpha", "Beta"]
    with pytest.raises(app.app_graphics_module.OptionalPromptSkipped):
        app.app_graphics_module.prompt_optional_text_list("Tags")
    assert app.app_graphics_module.prompt_optional_bool("Zoomable") is True
    assert app.app_graphics_module.prompt_optional_bool("Zoomable") is False
    with pytest.raises(app.app_graphics_module.OptionalPromptValidationError, match="Enter y or n"):
        app.app_graphics_module.prompt_optional_bool("Zoomable")
    with pytest.raises(app.app_graphics_module.OptionalPromptSkipped):
        app.app_graphics_module.prompt_optional_bool("Zoomable")

    assert outputs.count("? Must be numeric") == 1
    assert outputs.count("? Enter y or n") == 1
    assert any(output == "? Expected 2 values" for output in outputs)
    assert pauses == ["pause", "pause"]


def test_app_graphics_collect_layout_entries_and_menu_wrapper(monkeypatch, tmp_path):
    from sattlint.devtools import structural_reports  # noqa: PLC0415

    cfg = app.DEFAULT_CONFIG.copy()
    project_bp = SimpleNamespace(name="BP")
    graph = SimpleNamespace(name="graph")
    captured: dict[str, Any] = {}

    monkeypatch.chdir(tmp_path)

    def _collect_graphics_layout_report(**kwargs):
        captured["report"] = kwargs
        return {"entries": [{"selector_value": "Area.Unit"}]}

    monkeypatch.setattr(structural_reports, "collect_graphics_layout_report", _collect_graphics_layout_report)

    def _annotate(items, passed_bp, passed_graph):
        captured["annotate"] = (items, passed_bp, passed_graph)
        return items

    entries = app.app_graphics_module.collect_graphics_layout_entries_for_target(
        "TargetA",
        project_bp,
        graph,
        annotate_graphics_entries_with_structure_paths_fn=_annotate,
    )

    assert entries == [{"selector_value": "Area.Unit"}]
    assert captured["annotate"][1:] == (project_bp, graph)

    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "graphics_rules_menu",
        lambda passed_cfg, **kwargs: captured.setdefault("menu", (passed_cfg, kwargs)),
    )
    app.app_graphics_module.graphics_rules_menu(
        cfg,
        get_graphics_rules_path_fn=lambda: tmp_path / "rules.json",
        load_graphics_rules_fn=lambda *_args, **_kwargs: ({"rules": []}, False),
        save_graphics_rules_fn=lambda *_args, **_kwargs: None,
        prompt_graphics_rule_definition_with_config_fn=lambda *_args, **_kwargs: None,
        graphics_rule_label_fn=lambda _rule: "label",
        clear_screen_fn=lambda: None,
        print_menu_fn=lambda *_args, **_kwargs: None,
        menu_option_factory=lambda *_args, **_kwargs: object(),
        confirm_fn=lambda _label: True,
        prompt_fn=lambda *_args, **_kwargs: "1",
        quit_app_fn=lambda: None,
        pause_fn=lambda: None,
    )
    assert captured["menu"][0] == cfg
    assert callable(captured["menu"][1]["print_graphics_rules_summary_fn"])


def test_app_graphics_validation_and_selector_wrappers(monkeypatch):
    outputs: list[str] = []
    pauses: list[str] = []
    status_updates: list[str] = []
    cfg = app.DEFAULT_CONFIG.copy()
    rule = {"selector_value": "Area.UnitControl"}

    class _LiveStatusLine:
        def __enter__(self):
            return status_updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(app.app_graphics_module, "emit_output", outputs.append)
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module, "prompt_graphics_rule_kind", lambda **kwargs: "single"
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module, "selector_prompt_text", lambda field: f"Prompt:{field}"
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "graphics_rule_target_kind_matches",
        lambda kind, entry: kind == entry["kind"],
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "discover_graphics_rule_selector_options",
        lambda *_args, **_kwargs: [rule],
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "pick_or_prompt_graphics_rule_selector_value",
        lambda *_args, **_kwargs: "Area.UnitControl",
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "prompt_graphics_rule_selector",
        lambda *_args, **_kwargs: ("unit_structure_path", "Area.UnitControl"),
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "path_startswith_casefold",
        lambda path, prefix: [part.casefold() for part in path[: len(prefix)]] == [part.casefold() for part in prefix],
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "graphics_entry_canonical_segment",
        lambda entry: entry["segment"],
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module, "looks_like_graphics_unit_root", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "annotate_graphics_entries_with_structure_paths",
        lambda entries, *_args, **_kwargs: [*entries, {"selector_value": "Annotated"}],
    )
    monkeypatch.setattr(
        app.app_graphics_module.graphics_menus_module,
        "prompt_graphics_rule_definition",
        lambda **kwargs: kwargs["prompt_graphics_rule_definition_with_config_fn"](cfg),
    )
    monkeypatch.setattr(app.app_graphics_module.console_module, "live_status_line", _LiveStatusLine)

    assert app.app_graphics_module.prompt_graphics_rule_kind() == "single"
    assert app.app_graphics_module.selector_prompt_text("unit_structure_path") == "Prompt:unit_structure_path"
    assert app.app_graphics_module.graphics_rule_target_kind_matches("single", {"kind": "single"}) is True
    assert app.app_graphics_module.discover_graphics_rule_selector_options(
        cfg,
        selector_field="unit_structure_path",
        module_kind="single",
        has_analyzed_targets_fn=lambda _cfg: True,
        iter_loaded_projects_fn=lambda _cfg: iter(()),
        collect_graphics_layout_entries_for_target_fn=lambda *_args: [],
    ) == [rule]
    assert (
        app.app_graphics_module.pick_or_prompt_graphics_rule_selector_value(
            "unit_structure_path",
            "single",
            cfg=cfg,
            discover_graphics_rule_selector_options_fn=lambda *_args, **_kwargs: [rule],
        )
        == "Area.UnitControl"
    )
    assert app.app_graphics_module.prompt_graphics_rule_selector(
        "single",
        cfg=cfg,
        pick_or_prompt_graphics_rule_selector_value_fn=lambda *_args, **_kwargs: "Area.UnitControl",
    ) == ("unit_structure_path", "Area.UnitControl")
    assert app.app_graphics_module.path_startswith_casefold(["Area", "Unit"], ["area"]) is True
    assert app.app_graphics_module.graphics_entry_canonical_segment({"segment": "Unit"}) == "Unit"
    assert app.app_graphics_module.looks_like_graphics_unit_root(["Area"], [{"selector_value": "Area.Unit"}]) is True
    assert app.app_graphics_module.annotate_graphics_entries_with_structure_paths(
        [], SimpleNamespace(), SimpleNamespace()
    ) == [{"selector_value": "Annotated"}]
    assert app.app_graphics_module.prompt_graphics_rule_definition(
        prompt_graphics_rule_definition_with_config_fn=lambda passed_cfg: {"cfg": passed_cfg}
    ) == {"cfg": cfg}

    app.app_graphics_module.run_graphics_rules_validation(
        cfg,
        get_graphics_rules_path_fn=lambda: Path("graphics_rules.json"),
        load_graphics_rules_fn=lambda _path: ({"rules": []}, False),
        iter_loaded_projects_fn=lambda _cfg: iter(()),
        collect_graphics_layout_entries_for_target_fn=lambda *_args: [],
        pause_fn=lambda: pauses.append("pause"),
    )
    assert any("No graphics rules configured" in output for output in outputs)

    outputs.clear()
    monkeypatch.setattr(app.app_graphics_module.console_module, "live_status_line", _LiveStatusLine)
    monkeypatch.setattr(
        app.app_graphics_module.graphics_rules_module,
        "validate_graphics_layout_entries",
        lambda entries, rules, **kwargs: SimpleNamespace(
            summary=lambda: f"validated:{kwargs['target_name']}:{len(entries)}"
        ),
    )
    app.app_graphics_module.run_graphics_rules_validation(
        cfg,
        get_graphics_rules_path_fn=lambda: Path("graphics_rules.json"),
        load_graphics_rules_fn=lambda _path: ({"rules": [rule]}, False),
        iter_loaded_projects_fn=lambda _cfg: iter(
            [
                ("TargetA", SimpleNamespace(name="bp"), SimpleNamespace(name="graph")),
                ("TargetB", SimpleNamespace(name="bp"), SimpleNamespace(name="graph")),
            ]
        ),
        collect_graphics_layout_entries_for_target_fn=lambda target_name, *_args: (
            (_ for _ in ()).throw(RuntimeError("boom"))
            if target_name == "TargetB"
            else [{"selector_value": "Area.UnitControl"}]
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("validated:TargetA:1" in output for output in outputs)
    assert any("Error during graphics rules validation for TargetB: boom" in output for output in outputs)
    assert pauses == ["pause", "pause"]


def test_graphics_reports_formatting_and_show_config_without_rules(monkeypatch, tmp_path):
    reports = app.app_graphics_module.graphics_reports_module
    outputs: list[str] = []

    def emit(*args):
        outputs.append(args[0] if args else "")

    cfg = {
        "mode": "single",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "telemetry": {"enabled": True},
        "program_dir": tmp_path / "programs",
        "ABB_lib_dir": tmp_path / "abb",
        "icf_dir": tmp_path / "icf",
        "analyzed_programs_and_libraries": ["MainA", "LibB"],
        "other_lib_dirs": [tmp_path / "other"],
    }

    monkeypatch.setattr(reports, "telemetry_output_path", lambda: tmp_path / "telemetry.jsonl")

    reports.print_config_section(
        "Empty Section",
        [],
        emit_output_fn=emit,
        format_config_scalar_fn=reports.format_config_scalar,
    )
    reports.print_config_section(
        "Filled Section",
        [("alpha", True), ("beta", "")],
        emit_output_fn=emit,
        format_config_scalar_fn=reports.format_config_scalar,
    )
    reports.print_config_list(
        "Empty List",
        [],
        emit_output_fn=emit,
        format_config_scalar_fn=reports.format_config_scalar,
    )
    reports.print_config_list(
        "Filled List",
        [1, None],
        emit_output_fn=emit,
        format_config_scalar_fn=reports.format_config_scalar,
    )
    reports.show_config(
        cfg,
        get_documentation_config_fn=lambda _cfg: {
            "classifications": {
                "empty": {},
                "active": {"module_types": ["Frame", "Single"], "paths": []},
            }
        },
        get_graphics_rules_path_fn=lambda: tmp_path / "missing-rules.json",
        load_graphics_rules_fn=lambda *_args, **_kwargs: pytest.fail("rules should not load when path is missing"),
        graphics_rule_config_line_fn=lambda _rule: "unused",
        emit_output_fn=emit,
        print_config_list_fn=lambda title, items: reports.print_config_list(
            title,
            items,
            emit_output_fn=emit,
            format_config_scalar_fn=reports.format_config_scalar,
        ),
        print_config_section_fn=lambda title, rows: reports.print_config_section(
            title,
            rows,
            emit_output_fn=emit,
            format_config_scalar_fn=reports.format_config_scalar,
        ),
    )

    assert reports.format_config_scalar(True) == "yes"
    assert reports.format_config_scalar(False) == "no"
    assert reports.format_config_scalar(None) == "(not set)"
    assert reports.format_config_scalar("") == "(not set)"
    assert reports.format_config_scalar(3.5) == "3.5"
    assert "  (none)" in outputs
    assert "  alpha  yes" in outputs
    assert "  beta   (not set)" in outputs
    assert "  [1] 1" in outputs
    assert "  [2] (not set)" in outputs
    assert "\nCurrent Configuration" in outputs
    assert "Analyzed Programs And Libraries" in outputs
    assert "  graphics_rule_count  0" in outputs
    assert "Documentation Classifications" in outputs
    assert "  empty" in outputs
    assert "    (none)" in outputs
    assert "    module_types  Frame, Single" in outputs


def test_graphics_reports_show_config_covers_invalid_and_configured_rules(tmp_path):
    reports = app.app_graphics_module.graphics_reports_module
    cfg = {
        "mode": "single",
        "scan_root_only": False,
        "fast_cache_validation": True,
        "debug": False,
        "telemetry": {},
        "program_dir": tmp_path / "programs",
        "ABB_lib_dir": tmp_path / "abb",
        "icf_dir": tmp_path / "icf",
        "analyzed_programs_and_libraries": [],
        "other_lib_dirs": [],
    }
    rules_path = tmp_path / "graphics_rules.json"
    rules_path.write_text("{}", encoding="utf-8")
    sections: list[tuple[str, list[tuple[str, object]]]] = []
    emitted: list[str] = []

    def emit(*args):
        emitted.append(args[0] if args else "")

    reports.show_config(
        cfg,
        get_documentation_config_fn=lambda _cfg: {"classifications": {}},
        get_graphics_rules_path_fn=lambda: rules_path,
        load_graphics_rules_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad rules")),
        graphics_rule_config_line_fn=lambda _rule: "unused",
        emit_output_fn=emit,
        print_config_list_fn=lambda _title, _items: None,
        print_config_section_fn=lambda title, rows: sections.append((title, rows)),
    )

    assert (
        "Graphics Rules",
        [("graphics_rules_path", rules_path), ("graphics_rule_count", "invalid (bad rules)")],
    ) in sections

    sections.clear()
    emitted.clear()
    reports.show_config(
        cfg,
        get_documentation_config_fn=lambda _cfg: {"classifications": {}},
        get_graphics_rules_path_fn=lambda: rules_path,
        load_graphics_rules_fn=lambda *_args, **_kwargs: (
            {
                "rules": [
                    {
                        "module_kind": "single",
                        "unit_structure_path": "Area.UnitControl",
                    }
                ]
            },
            False,
        ),
        graphics_rule_config_line_fn=lambda _rule: "single | scope=unit | unit_structure_path=Area.UnitControl",
        emit_output_fn=emit,
        print_config_list_fn=lambda _title, _items: None,
        print_config_section_fn=lambda title, rows: sections.append((title, rows)),
    )

    assert ("Graphics Rules", [("graphics_rules_path", rules_path), ("graphics_rule_count", 1)]) in sections
    assert "Configured Graphics Rule Selectors" in emitted
    assert "  [1] single | scope=unit | unit_structure_path=Area.UnitControl" in emitted


def test_graphics_reports_selector_scope_and_flatten_helpers():
    reports = app.app_graphics_module.graphics_reports_module

    assert reports.flatten_graphics_expected_fields(
        {
            "invocation": {"coords": [1, 2], "flags": {"zoomable": True}},
            "moduledef": {"grid": 0.5},
        }
    ) == ["invocation.coords", "invocation.flags.zoomable", "moduledef.grid"]
    assert reports.truncate_table_cell("abc", 3) == "abc"
    assert reports.truncate_table_cell("abcdef", 3) == "abc"
    assert reports.truncate_table_cell("abcdef", 5) == "ab..."
    assert reports.graphics_rule_selector_text({"unit_structure_path": "Area.Unit"}) == "unit:Area.Unit"
    assert (
        reports.graphics_rule_selector_text({"equipment_module_structure_path": "Equip.Stop"}) == "equipment:Equip.Stop"
    )
    assert (
        reports.graphics_rule_selector_text(
            {
                "module_kind": "moduletype",
                "moduletype_name": "ValveType",
                "relative_module_path": "LineA/Valve1",
            }
        )
        == "ValveType @ path:LineA/Valve1"
    )
    assert reports.graphics_rule_selector_text({"module_kind": "moduletype"}) == "(missing moduletype name)"
    assert reports.graphics_rule_selector_text({"relative_module_path": "A/B/C"}) == "path:A/B/C"
    assert reports.graphics_rule_selector_text({"module_name": "Standalone"}) == "Standalone"
    assert reports.graphics_rule_selector_text({}) == "(missing module name)"
    assert reports.graphics_rule_label({"module_kind": "single", "module_name": "Standalone"}) == "single:Standalone"
    assert reports.graphics_rule_scope_text({"unit_structure_path": "Area.Unit"}) == "unit"
    assert reports.graphics_rule_scope_text({"equipment_module_structure_path": "Equip.Stop"}) == "equipment"
    assert reports.graphics_rule_scope_text({"relative_module_path": "A/B/C"}) == "path"
    assert reports.graphics_rule_scope_text({"moduletype_name": "ValveType"}) == "moduletype"
    assert reports.graphics_rule_scope_text({"module_name": "Standalone"}) == "name"
    assert (
        reports.graphics_rule_config_line(
            {
                "module_kind": "single",
                "unit_structure_path": "Area.Unit",
                "equipment_module_structure_path": "",
                "relative_module_path": "",
                "moduletype_name": "",
                "description": "Shown in reports",
            }
        )
        == "single | scope=unit | unit_structure_path=Area.Unit | description=Shown in reports"
    )
    assert (
        reports.graphics_rule_config_line(
            {
                "module_kind": "moduletype",
                "equipment_module_structure_path": "Equip.Stop",
                "relative_module_path": "LineA/Valve1",
                "moduletype_name": "ValveType",
            }
        )
        == "moduletype | scope=equipment | equipment_module_structure_path=Equip.Stop | relative_module_path=LineA/Valve1 | moduletype_name=ValveType"
    )
    assert reports.graphics_rule_config_line({"module_kind": "frame"}) == "frame | scope=name"


def test_graphics_reports_summary_covers_empty_and_table_rows(tmp_path):
    reports = app.app_graphics_module.graphics_reports_module
    outputs: list[str] = []

    def emit(*args):
        outputs.append(args[0] if args else "")

    rules_path = tmp_path / "graphics_rules.json"

    reports.print_graphics_rules_summary(
        rules_path,
        {"rules": []},
        dirty=True,
        emit_output_fn=emit,
    )

    assert "Graphics Rules" in outputs
    assert f"Path: {rules_path}" in outputs
    assert "Status: unsaved changes" in outputs
    assert "No graphics rules configured yet." in outputs

    outputs.clear()
    reports.print_graphics_rules_summary(
        rules_path,
        {
            "rules": [
                {
                    "module_kind": "single",
                    "unit_structure_path": "Area.Unit.With.An.Extra.Long.Selector.Path.For.Truncation",
                    "description": "Description that is intentionally longer than the table width limit",
                    "expected": {
                        "invocation": {
                            "coords": [1.43, 1.35, 0.0, 0.56, 0.56],
                            "arguments": ["ArgA", "ArgB"],
                        },
                        "moduledef": {
                            "clipping_origin": [0.0, 0.0],
                            "clipping_size": [1.0, 0.21429],
                        },
                    },
                }
            ]
        },
        dirty=False,
        emit_output_fn=emit,
    )

    assert "Status: saved" in outputs
    assert any(line.startswith("#") is False and "Selector" in line and "Description" in line for line in outputs)
    assert any("----" in line for line in outputs)
    assert any(
        "single" in line and "unit" in line and "unit:Area.Unit.With.An.Extra.Long.Selector.Path"[:10] in line
        for line in outputs
    )
    assert any("..." in line for line in outputs if "single" in line)
