"""CLI behavior tests for SattLint."""

from typing import cast

from sattlint import app


def test_build_cli_parser_has_descriptions():
    parser = app.build_cli_parser()

    assert parser.description
    action = next(action for action in parser._actions if getattr(action, "choices", None))
    choices = cast(dict[str, object], action.choices)
    syntax_parser = cast(object, choices["syntax-check"])
    assert getattr(syntax_parser, "description", None)


def test_run_cli_without_command_returns_usage_error():
    assert app.run_cli([]) == 1
