from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from sattlint.devtools import layer_linter


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_get_layer_for_module_matches_known_prefixes():
    assert layer_linter.get_layer_for_module("sattline_parser") == 0
    assert layer_linter.get_layer_for_module("sattlint.models.ast_model") == 1
    assert layer_linter.get_layer_for_module("sattlint.core.document") == 2
    assert layer_linter.get_layer_for_module("sattlint.resolution.scope") == 3
    assert layer_linter.get_layer_for_module("sattlint.analyzers.unused") == 4
    assert layer_linter.get_layer_for_module("sattlint.engine") == 5
    assert layer_linter.get_layer_for_module("sattlint.reporting.variables_report") == 6
    assert layer_linter.get_layer_for_module("sattlint_lsp.server") == 7
    assert layer_linter.get_layer_for_module("vscode") == 8
    assert layer_linter.get_layer_for_module("sattlint.devtools.layer_linter") == 9
    assert layer_linter.get_layer_for_module("external_package") == -1


def test_resolve_current_module_handles_empty_vscode_and_misc_paths():
    class _FakePath:
        def __init__(self, relative_path: str = ""):
            self._relative_path = Path(relative_path)

        def relative_to(self, _cwd):
            return self._relative_path

    assert layer_linter._resolve_current_module(_FakePath()) == (".", -1)
    assert layer_linter._resolve_current_module(_FakePath("vscode/pkg/__init__.py")) == ("pkg", 8)
    assert layer_linter._resolve_current_module(_FakePath("scripts/tool.txt")) == ("scripts.tool.txt", -1)


def test_find_python_files_recurses_only_existing_roots(tmp_path):
    expected = {
        tmp_path / "src" / "pkg" / "module.py",
        tmp_path / "vscode" / "extension.py",
    }
    for path in expected:
        _write(path, "pass\n")
    _write(tmp_path / "src" / "pkg" / "notes.txt", "ignored\n")

    files = set(layer_linter.find_python_files([tmp_path / "src", tmp_path / "vscode", tmp_path / "missing"]))

    assert files == expected


def test_check_file_for_arch_violations_reports_higher_layer_import(tmp_path, monkeypatch):
    repo_file = tmp_path / "src" / "sattlint" / "core" / "rules.py"
    _write(repo_file, "import sattlint_lsp.server\n")
    monkeypatch.chdir(tmp_path)

    violations = layer_linter.check_file_for_arch_violations(repo_file)

    assert len(violations) == 1
    assert violations[0].file == str(repo_file)
    assert violations[0].line == 1
    assert "sattlint.core.rules" in violations[0].message
    assert "sattlint_lsp.server" in violations[0].message


def test_check_file_for_arch_violations_skips_resolution_value_errors(tmp_path, monkeypatch):
    repo_file = tmp_path / "src" / "sattlint" / "rules.py"
    _write(repo_file, "import sattlint_lsp.server\n")
    monkeypatch.setattr(
        layer_linter,
        "_resolve_current_module",
        lambda _file_path: (_ for _ in ()).throw(ValueError("outside repo")),
    )

    violations = layer_linter.check_file_for_arch_violations(repo_file)

    assert violations == []


def test_check_file_for_arch_violations_skips_external_and_allowed_imports(tmp_path, monkeypatch):
    repo_file = tmp_path / "src" / "sattlint" / "core" / "rules.py"
    _write(
        repo_file,
        "import json\nimport sattline_parser.api\nfrom collections import abc\nfrom sattline_parser import api\n",
    )
    monkeypatch.chdir(tmp_path)

    violations = layer_linter.check_file_for_arch_violations(repo_file)

    assert violations == []


def test_check_file_for_arch_violations_reports_higher_layer_from_import(tmp_path, monkeypatch):
    repo_file = tmp_path / "src" / "sattlint" / "core" / "rules.py"
    _write(repo_file, "from sattlint_lsp import server\n")
    monkeypatch.chdir(tmp_path)

    violations = layer_linter.check_file_for_arch_violations(repo_file)

    assert len(violations) == 1
    assert violations[0].line == 1
    assert "imports from sattlint_lsp" in violations[0].message


def test_check_file_for_arch_violations_skips_relative_imports(tmp_path, monkeypatch):
    repo_file = tmp_path / "src" / "sattlint" / "core" / "rules.py"
    _write(repo_file, "from . import sibling\n")
    monkeypatch.chdir(tmp_path)

    violations = layer_linter.check_file_for_arch_violations(repo_file)

    assert violations == []


def test_check_file_for_arch_violations_reports_unparseable_file(tmp_path, monkeypatch):
    repo_file = tmp_path / "src" / "sattlint" / "broken.py"
    _write(repo_file, "def broken(:\n")
    monkeypatch.chdir(tmp_path)

    violations = layer_linter.check_file_for_arch_violations(repo_file)

    assert len(violations) == 1
    assert violations[0].file == str(repo_file)
    assert violations[0].line == 0
    assert "Failed to parse" in violations[0].message


def test_main_exits_zero_when_no_violations(monkeypatch, capsys):
    monkeypatch.setattr(layer_linter, "find_python_files", lambda _roots: [Path("src/demo.py")])
    monkeypatch.setattr(layer_linter, "check_file_for_arch_violations", lambda _path: [])

    with pytest.raises(SystemExit) as exc_info:
        layer_linter.main()

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "No architecture violations found."


def test_main_exits_one_and_prints_violations(monkeypatch, capsys):
    violation = layer_linter.ArchViolation("src/demo.py", 7, "invalid import")
    monkeypatch.setattr(layer_linter, "find_python_files", lambda _roots: [Path("src/demo.py")])
    monkeypatch.setattr(layer_linter, "check_file_for_arch_violations", lambda _path: [violation])

    with pytest.raises(SystemExit) as exc_info:
        layer_linter.main()

    output = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert "Found 1 architecture violations:" in output
    assert "src/demo.py:7 - invalid import" in output


def test_layer_linter_module_main_guard_executes(monkeypatch):
    original_exists = Path.exists

    def _fake_exists(self):
        if self in {Path("src"), Path("vscode")}:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", _fake_exists)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("sattlint.devtools.layer_linter", run_name="__main__")

    assert exc_info.value.code == 0
