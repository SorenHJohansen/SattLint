from __future__ import annotations

from typing import Any, cast

from sattlint import _app_analysis_menus
from sattlint.app_interaction import MenuInteraction


def test_variable_usage_submenu_supplies_textual_menu_options() -> None:
    seen: dict[str, object] = {}

    def _choose_menu_option(title: str, options: list[Any], **kwargs: Any) -> str:
        seen.update({"title": title, "options": options, "kwargs": kwargs})
        return "b"

    def _prompt(message: str, default: str | None = None) -> str:
        del message
        return default or ""

    interaction = MenuInteraction(
        choose_menu_option=_choose_menu_option,
        prompt=_prompt,
        confirm=lambda _message: False,
        pause=lambda: None,
    )

    _app_analysis_menus.variable_usage_submenu(
        {},
        clear_screen_fn=lambda: None,
        quit_app_fn=lambda: None,
        run_variable_analysis_fn=lambda _cfg, _kinds: None,
        run_datatype_usage_analysis_fn=lambda _cfg: None,
        run_debug_variable_usage_fn=lambda _cfg: None,
        run_module_localvar_analysis_fn=lambda _cfg: None,
        pause_fn=lambda: None,
        emit_output_fn=lambda *_args: None,
        interaction=interaction,
    )

    options_object = seen["options"]
    assert isinstance(options_object, list)
    options = cast(list[Any], options_object)
    option_keys = [getattr(option, "key", "") for option in options]

    assert seen["title"] == "Variable issues"
    assert option_keys[:3] == ["1", "2", "3"]
    assert option_keys[-5:] == ["23", "24", "25", "b", "q"]
