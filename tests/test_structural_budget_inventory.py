# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownLambdaType=false
from __future__ import annotations

import subprocess
from pathlib import Path

from sattlint.devtools import _structural_budget_inventory as inventory


def test_count_structural_lines_skips_blank_and_hash_prefixed_lines() -> None:
    text = """
value = 1

    # indented comment
# heading-like line
value = 2
"""

    assert inventory.count_structural_lines(text) == 2


def test_iter_structural_python_files_yields_src_then_scripts_then_tests(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "pkg" / "module.py"
    script_file = tmp_path / "scripts" / "tool.py"
    test_file = tmp_path / "tests" / "test_module.py"
    ignored_test_helper = tmp_path / "tests" / "helper.py"
    for path in (src_file, script_file, test_file, ignored_test_helper):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n", encoding="utf-8")

    assert list(inventory.iter_structural_python_files(tmp_path)) == [
        ("src", src_file),
        ("src", script_file),
        ("tests", test_file),
    ]


def test_tracked_markdown_paths_handles_missing_git_and_failures(monkeypatch) -> None:
    monkeypatch.setattr(inventory.shutil, "which", lambda _name: None)
    assert inventory._tracked_markdown_paths(Path(".")) == ()

    monkeypatch.setattr(inventory.shutil, "which", lambda _name: "git")

    monkeypatch.setattr(
        inventory.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["git", "ls-files", "*.md"],
            returncode=1,
            stdout="",
            stderr="fatal",
        ),
    )
    assert inventory._tracked_markdown_paths(Path(".")) == ()

    def raise_oserror(*_args, **_kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr(inventory.subprocess, "run", raise_oserror)
    assert inventory._tracked_markdown_paths(Path(".")) == ()


def test_tracked_markdown_paths_normalizes_git_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(inventory.shutil, "which", lambda _name: "git")
    monkeypatch.setattr(
        inventory.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["git", "ls-files", "*.md"],
            returncode=0,
            stdout="docs\\guide.md\nREADME.md\n\n",
            stderr="",
        ),
    )

    assert inventory._tracked_markdown_paths(tmp_path) == ("docs/guide.md", "README.md")


def test_iter_structural_markdown_files_prefers_tracked_paths(monkeypatch, tmp_path: Path) -> None:
    tracked_doc = tmp_path / "docs" / "guide.md"
    tracked_doc.parent.mkdir(parents=True, exist_ok=True)
    tracked_doc.write_text("guide\n", encoding="utf-8")
    monkeypatch.setattr(inventory, "_tracked_markdown_paths", lambda _root: ("docs/guide.md", "docs/missing.md"))

    assert list(inventory.iter_structural_markdown_files(tmp_path)) == [("markdown", tracked_doc)]


def test_iter_structural_markdown_files_falls_back_to_rglob(monkeypatch, tmp_path: Path) -> None:
    doc = tmp_path / "docs" / "guide.md"
    git_doc = tmp_path / ".git" / "ignored.md"
    for path in (doc, git_doc):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content\n", encoding="utf-8")
    monkeypatch.setattr(inventory, "_tracked_markdown_paths", lambda _root: ())

    assert list(inventory.iter_structural_markdown_files(tmp_path)) == [("markdown", doc)]


def test_read_structural_text_counts_python_structural_lines_and_markdown_physical_lines(tmp_path: Path) -> None:
    python_file = tmp_path / "module.py"
    markdown_file = tmp_path / "guide.md"
    python_file.write_text("# comment\nvalue = 1\n\nvalue = 2\n", encoding="utf-8")
    markdown_file.write_text("# heading\n# heading two\n", encoding="utf-8")

    assert inventory.read_structural_text(python_file) == (python_file.read_text(encoding="utf-8"), 2, None)
    assert inventory.read_structural_text(markdown_file) == (markdown_file.read_text(encoding="utf-8"), 2, None)


def test_read_structural_text_handles_unicode_decode_with_byte_fallback(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"

    def fake_read_text(self: Path, *, encoding: str) -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "boom")

    def fake_read_bytes(self: Path) -> bytes:
        return b"first\nsecond\n"

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    assert inventory.read_structural_text(path) == (
        None,
        2,
        {"error": "'utf-8' codec can't decode byte 0xff in position 0: boom", "error_type": "UnicodeDecodeError"},
    )


def test_read_structural_text_handles_oserror_paths(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"

    def fake_read_text(self: Path, *, encoding: str) -> str:
        raise OSError("missing")

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    assert inventory.read_structural_text(path) == (None, None, {"error": "missing", "error_type": "OSError"})


def test_read_structural_text_handles_byte_fallback_oserror(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"

    def fake_read_text(self: Path, *, encoding: str) -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "boom")

    def fake_read_bytes(self: Path) -> bytes:
        raise OSError("still broken")

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    assert inventory.read_structural_text(path) == (
        None,
        None,
        {"error": "still broken", "error_type": "OSError"},
    )


def test_summarize_structural_budget_metrics_reads_report_fields() -> None:
    report = {
        "source_files_over_budget": [{"path": "src/demo.py", "line_count": 10}],
        "test_files_over_budget": [],
        "functions_over_budget": [{"line_span": 7}, {"line_span": 9}],
        "classes_over_budget": [{"method_count": 4}],
        "repeated_private_names": [{"file_count": 3}],
        "facade_private_entrypoints": [{"path": "src/sattlint/app.py"}],
        "summary": {
            "source_file_max_lines": 10,
            "test_file_max_lines": 0,
            "import_max_count": 4,
            "dependency_max_count": 2,
            "public_symbol_max_count": 5,
            "nesting_max_depth": 3,
        },
    }

    assert inventory.summarize_structural_budget_metrics(report) == {
        "source_file_over_budget_count": 1,
        "source_file_max_lines": 10,
        "test_file_over_budget_count": 0,
        "test_file_max_lines": 0,
        "function_over_budget_count": 2,
        "function_max_lines": 9,
        "class_over_budget_count": 1,
        "class_max_methods": 4,
        "repeated_private_name_count": 1,
        "repeated_private_name_max_files": 3,
        "import_max_count": 4,
        "dependency_max_count": 2,
        "public_symbol_max_count": 5,
        "nesting_max_depth": 3,
        "facade_private_entrypoint_count": 1,
    }
