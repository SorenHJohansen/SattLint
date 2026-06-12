from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.cli import entry as cli_entry


class _FakeParser:
    def __init__(self, args: object) -> None:
        self._args = args

    def parse_known_args(self, _argv: list[str]) -> tuple[object, list[str]]:
        return self._args, []

    def print_usage(self, stream: object) -> None:
        del stream


def test_cli_entry_prints_traceback_when_debug_config_load_fails(capsys: pytest.CaptureFixture[str]) -> None:
    parser = _FakeParser(
        SimpleNamespace(
            command="validate-config",
            checks=[],
            config=None,
            no_cache=False,
            quiet=False,
            debug=True,
        )
    )

    exit_code = cli_entry.run_cli(
        ["validate-config", "--debug"],
        config_path=Path("config.toml"),
        build_cli_parser_fn=cast(Any, lambda: parser),
        load_config_fn=lambda _path: (_ for _ in ()).throw(ValueError("bad config")),
        apply_debug_fn=lambda _cfg: None,
    )

    captured = capsys.readouterr()
    assert exit_code == cli_entry.EXIT_USAGE_ERROR
    assert "ERROR [config] bad config" in captured.err
    assert "Traceback (most recent call last)" in captured.err
