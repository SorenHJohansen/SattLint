# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _load_run_markdownlint_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "run_markdownlint.py"
    spec = importlib.util.spec_from_file_location("run_markdownlint", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_markdownlint = _load_run_markdownlint_module()


def test_build_tool_args_adds_no_globs_before_explicit_targets():
    tool_args = ["--config", ".markdownlint-cli2.jsonc", "README.md"]

    built_args = run_markdownlint._build_tool_args(tool_args)

    assert built_args == ["--config", ".markdownlint-cli2.jsonc", "--no-globs", "README.md"]


def test_build_tool_args_leaves_help_only_requests_unchanged():
    tool_args = ["--help"]

    built_args = run_markdownlint._build_tool_args(tool_args)

    assert built_args == ["--help"]


def test_resolve_command_prefers_installed_markdownlint_cli(monkeypatch):
    def fake_which(command: str):
        if command == "markdownlint-cli2":
            return "/usr/bin/markdownlint-cli2"
        if command == "npx":
            return "/usr/bin/npx"
        return None

    monkeypatch.setattr(run_markdownlint.shutil, "which", fake_which)

    command, cwd = run_markdownlint._resolve_command(["README.md"])

    assert command == ["markdownlint-cli2", "README.md"]
    assert cwd == run_markdownlint.REPO_ROOT


def test_main_passes_no_globs_when_explicit_paths_are_supplied(monkeypatch, tmp_path):
    captured_tool_args: list[str] = []

    def fake_resolve_command(tool_args: list[str]):
        captured_tool_args.extend(tool_args)
        return ["markdownlint-cli2"], tmp_path

    monkeypatch.setattr(run_markdownlint, "_resolve_command", fake_resolve_command)
    monkeypatch.setattr(
        run_markdownlint.subprocess,
        "run",
        lambda command, cwd, check=False: subprocess.CompletedProcess(command, 0),
    )

    exit_code = run_markdownlint.main(["--config", ".markdownlint-cli2.jsonc", "README.md"])

    assert exit_code == 0
    assert captured_tool_args == ["--config", ".markdownlint-cli2.jsonc", "--no-globs", "README.md"]
