from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_ratchet_policy_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_ratchet_policy.py"
    spec = importlib.util.spec_from_file_location("check_ratchet_policy", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ratchet_policy = _load_ratchet_policy_module()


def test_evaluate_policy_change_allows_non_protected_edits():
    errors = ratchet_policy.evaluate_policy_change(
        changed_files=("README.md",),
        current_text_by_path={"README.md": "docs"},
        base_text_by_path={"README.md": "docs"},
    )

    assert errors == []


def test_new_file_size_errors_rejects_added_python_files_over_500_lines(tmp_path):
    oversized = tmp_path / "src" / "pkg" / "new_module.py"
    oversized.parent.mkdir(parents=True)
    oversized.write_text("\n".join(f"value_{index} = {index}" for index in range(501)), encoding="utf-8")

    errors = ratchet_policy._new_file_size_errors(tmp_path, ("src/pkg/new_module.py",))

    assert errors == ["New Python file src/pkg/new_module.py is 501 lines; new files must stay at or under 500 lines."]


def test_new_file_size_errors_rejects_added_markdown_files_over_500_lines(tmp_path):
    oversized = tmp_path / "docs" / "guide.md"
    oversized.parent.mkdir(parents=True)
    oversized.write_text("\n".join(f"- item {index}" for index in range(501)), encoding="utf-8")

    errors = ratchet_policy._new_file_size_errors(tmp_path, ("docs/guide.md",))

    assert errors == ["New Markdown file docs/guide.md is 501 lines; new files must stay at or under 500 lines."]


def test_new_file_coverage_errors_rejects_added_source_files_below_100_percent(tmp_path):
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"src/pkg/new_module.py\" line-rate=\"0.99\" lines-valid=\"100\" lines-covered=\"99\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    errors = ratchet_policy._new_file_coverage_errors(tmp_path, ("src/pkg/new_module.py",))

    assert errors == [
        "New source file src/pkg/new_module.py is covered at 99.00%; new source files must start at 100.00% coverage."
    ]


def test_new_file_coverage_errors_accepts_added_source_files_at_100_percent(tmp_path):
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"pkg/new_module.py\" line-rate=\"1.0\" lines-valid=\"10\" lines-covered=\"10\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    errors = ratchet_policy._new_file_coverage_errors(tmp_path, ("src/pkg/new_module.py",))

    assert errors == []


def test_evaluate_policy_change_requires_explicit_approval_record():
    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH,),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8827}}',
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8826}}',
        },
    )

    assert len(errors) == 1
    assert "Ratchet edits require explicit approval" in errors[0]


def test_evaluate_policy_change_rejects_looser_coverage_ratchet_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8700}}',
            approval_path: "Approved-by: Human Reviewer\nReason: Tried to lower the gate\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8826}}',
            approval_path: None,
        },
    )

    assert any("Coverage ratchet loosened" in error for error in errors)


def test_evaluate_policy_change_rejects_looser_pytest_floor_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = """
[tool.pytest.ini_options]
addopts = ["--cov-fail-under=88.26"]
""".strip()
    head_pyproject = """
[tool.pytest.ini_options]
addopts = ["--cov-fail-under=87.50"]
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: lowering floor\n",
        },
        base_text_by_path={
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert any("Pytest coverage floor loosened" in error for error in errors)


def test_evaluate_policy_change_rejects_looser_structural_metric_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = '{"metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858}}'
    head_structural = '{"metrics": {"source_file_max_lines": 2000, "test_file_max_lines": 2858}}'

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted rebaseline\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert any("Structural ratchet loosened" in error for error in errors)


def test_structural_file_line_exception_mapping_requires_reason():
    payload = {
        "metrics": {},
        "file_line_exceptions": {"src/pkg/legacy.py": {"max_lines": 520, "reason": ""}},
    }

    try:
        ratchet_policy._structural_file_line_exception_mapping(payload, ratchet_policy.STRUCTURAL_RATCHET_PATH)
    except ValueError as exc:
        assert "file_line_exceptions['src/pkg/legacy.py'].reason" in str(exc)
    else:
        raise AssertionError("Expected a ValueError for a missing structural exception reason")


def test_evaluate_policy_change_allows_structural_file_exception_schema_migration_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = '{"metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858}}'
    head_structural = """
{
    "metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858},
    "file_line_exceptions": {
        "src/pkg/legacy.py": {
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction."
        }
    }
}
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: add justified structural file exceptions\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_wider_structural_file_exception_after_schema_migration():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = """
{
    "metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858},
    "file_line_exceptions": {
        "src/pkg/legacy.py": {
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction."
        }
    }
}
""".strip()
    head_structural = """
{
    "metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858},
    "file_line_exceptions": {
        "src/pkg/legacy.py": {
            "max_lines": 530,
            "reason": "Legacy owner module remains centralized pending extraction."
        }
    }
}
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted exception growth\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert any("Structural file-line exception loosened" in error for error in errors)


def test_evaluate_policy_change_rejects_new_structural_file_exception_after_schema_migration():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = """
{
    "metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858},
    "file_line_exceptions": {
        "src/pkg/legacy.py": {
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction."
        }
    }
}
""".strip()
    head_structural = """
{
    "metrics": {"source_file_max_lines": 1974, "test_file_max_lines": 2858},
    "file_line_exceptions": {
        "src/pkg/legacy.py": {
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction."
        },
        "tests/test_legacy.py": {
            "max_lines": 540,
            "reason": "Legacy owner regression suite remains aggregated pending extraction."
        }
    }
}
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted new exception\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert any("Structural file-line exception added" in error for error in errors)


def test_evaluate_policy_change_allows_markdown_scope_exception_migration_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = """
{
    "metrics": {"source_file_max_lines": 500, "test_file_max_lines": 500},
    "file_line_exceptions": {
        "src/pkg/legacy.py": {
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction."
        }
    }
}
""".strip()
    head_structural = """
{
    "metrics": {"source_file_max_lines": 500, "test_file_max_lines": 500, "markdown_file_max_lines": 1453},
    "file_line_exceptions": {
        "docs/roadmap.md": {
            "max_lines": 530,
            "reason": "Roadmap owner document remains centralized pending breakdown into smaller plans."
        },
        "src/pkg/legacy.py": {
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction."
        }
    }
}
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: add Markdown ratchet scope and temporary exceptions\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_new_markdown_exception_after_markdown_scope_migration():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = """
{
    "metrics": {"source_file_max_lines": 500, "test_file_max_lines": 500, "markdown_file_max_lines": 1453},
    "file_line_exceptions": {
        "docs/roadmap.md": {
            "max_lines": 530,
            "reason": "Roadmap owner document remains centralized pending breakdown into smaller plans."
        }
    }
}
""".strip()
    head_structural = """
{
    "metrics": {"source_file_max_lines": 500, "test_file_max_lines": 500, "markdown_file_max_lines": 1453},
    "file_line_exceptions": {
        "docs/roadmap.md": {
            "max_lines": 530,
            "reason": "Roadmap owner document remains centralized pending breakdown into smaller plans."
        },
        "docs/tech-debt.md": {
            "max_lines": 510,
            "reason": "Tech debt tracker remains centralized pending decomposition."
        }
    }
}
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted Markdown exception growth\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert any("Structural file-line exception added" in error for error in errors)


def test_evaluate_policy_change_rejects_invalid_approval_record():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8827}}',
            approval_path: "Approved-by: Human Reviewer\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8826}}',
            approval_path: None,
        },
    )

    assert errors == [f"Approval record {approval_path} is missing a 'Reason:' line."]


def test_evaluate_policy_change_accepts_stricter_change_with_valid_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = """
[tool.pytest.ini_options]
addopts = ["--cov-fail-under=88.26"]
""".strip()
    head_pyproject = """
[tool.pytest.ini_options]
addopts = ["--cov-fail-under=88.50"]
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH, ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8850}}',
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: raised the floor after real fixes\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: '{"metrics": {"min_line_rate_basis_points": 8826}}',
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert errors == []


def test_detect_change_context_prefers_base_ref_when_present(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(_repo_root, *args):
        calls.append(args)
        if args == ("diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"):

            class DiffResult:
                returncode = 0
                stdout = "pyproject.toml\n"
                stderr = ""

            return DiffResult()
        if args == ("diff", "--name-status", "--diff-filter=A", "origin/main...HEAD"):

            class AddedResult:
                returncode = 0
                stdout = "A\tsrc/pkg/new_module.py\n"
                stderr = ""

            return AddedResult()
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(ratchet_policy, "_git", fake_git)

    context = ratchet_policy._detect_change_context(Path("."), {"GITHUB_BASE_REF": "main"})

    assert context.changed_files == ("pyproject.toml",)
    assert context.added_files == ("src/pkg/new_module.py",)
    assert context.base_ref == "origin/main"
    assert context.source == "base-ref"
    assert calls == [
        ("diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"),
        ("diff", "--name-status", "--diff-filter=A", "origin/main...HEAD"),
    ]
