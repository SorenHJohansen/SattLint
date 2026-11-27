"""Terminal text sanitization: control characters and untrusted CLI names.

Project text reaches the terminal through the shared text sink. A target or
module name that contains an escape sequence, a newline, or markup-like text
must render literally, while JSON output keeps the original value.
"""

from __future__ import annotations

import json

import pytest

from sattlint.application.findings import AnalysisFinding
from sattlint.cli.entry import run_cli
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunTargetRecord
from sattlint.utils.terminal_text import sanitize_terminal_label, sanitize_terminal_text

_HOSTILE_TARGET = "Demo\x1b[31m[bold]Target\nInjected"
_HOSTILE_MODULE = "Unit\u202e[bold]Name\x1b[0m\nInjected"
_HOSTILE_MESSAGE = "declared but never read\nInjected"


def test_sanitize_replaces_c0_controls_and_del() -> None:
    text = "\x00a\x01b\x1fc\x7fd"

    assert sanitize_terminal_text(text) == "?a?b?c?d"


def test_sanitize_replaces_c1_controls_and_ansi_escapes() -> None:
    ansi = "\x1b[31mred\x1b[0m"
    c1 = "\x9b31mred"

    sanitized_ansi = sanitize_terminal_text(ansi)
    sanitized_c1 = sanitize_terminal_text(c1)

    assert sanitized_ansi == "?[31mred?[0m"
    assert sanitized_c1 == "?31mred"
    assert "\x1b" not in sanitized_ansi
    assert "\x9b" not in sanitized_c1


def test_sanitize_replaces_unicode_format_characters() -> None:
    text = "before\u202eafter\u200b\u200d\ufeff"

    assert sanitize_terminal_text(text) == "before?after???"


def test_sanitize_keeps_printable_unicode() -> None:
    text = "Straße 日本 ✓ — Module"

    assert sanitize_terminal_text(text) == text


def test_sanitize_newline_and_tab_modes() -> None:
    text = "line one\nline two\tcolumn"

    assert sanitize_terminal_text(text) == "line one?line two?column"
    assert sanitize_terminal_text(text, keep_newlines=True) == "line one\nline two?column"
    assert sanitize_terminal_text(text, keep_tabs=True) == "line one?line two\tcolumn"
    assert sanitize_terminal_text(text, keep_newlines=True, keep_tabs=True) == text


def test_sanitize_label_refuses_newlines_and_tabs() -> None:
    assert sanitize_terminal_label("a\nb\tc") == "a?b?c"


def _install_hostile_run(monkeypatch: pytest.MonkeyPatch) -> None:
    record = RunRecord(
        run_id="hostile",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
        project_path="",
        selected_analyzers=("variables",),
        targets=(
            RunTargetRecord(
                target_name=_HOSTILE_TARGET,
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message=_HOSTILE_MESSAGE,
                                module_path=(_HOSTILE_TARGET, _HOSTILE_MODULE),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    def _resolve_run(_selector: str, **_kwargs: object) -> RunRecord:
        return record

    monkeypatch.setattr("sattlint.cli.commands.resolve_run", _resolve_run)


def test_findings_text_renders_hostile_names_without_terminal_control(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_hostile_run(monkeypatch)

    code = run_cli(["findings", "--run", "hostile"])

    assert code == 0
    output = capsys.readouterr().out
    lines = output.splitlines()
    assert len(lines) == 2
    assert "\x1b" not in output
    assert "\u202e" not in output
    assert "Demo?[31m[bold]Target?Injected.Unit?[bold]Name?[0m?Injected" in output
    assert "declared but never read?Injected" in output


def test_findings_json_keeps_the_original_hostile_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_hostile_run(monkeypatch)

    code = run_cli(["findings", "--run", "hostile", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    finding = payload["findings"][0]
    assert finding["target"] == _HOSTILE_TARGET
    assert finding["module_path"] == [_HOSTILE_TARGET, _HOSTILE_MODULE]
    assert finding["module"] == f"{_HOSTILE_TARGET}.{_HOSTILE_MODULE}"
    assert finding["message"] == _HOSTILE_MESSAGE
