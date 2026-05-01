"""Focused graphics prompt and selector tests for the app."""

from __future__ import annotations

import builtins
from typing import Any

import pytest

from sattlint import app


def make_input(responses):
    it = iter(responses)

    def _input(_prompt=""):
        try:
            return next(it)
        except StopIteration as exc:
            raise AssertionError("No more input responses provided") from exc

    return _input


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
