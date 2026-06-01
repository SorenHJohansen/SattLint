from __future__ import annotations

import importlib.util
import json
import sys
from decimal import Decimal
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


def _coverage_ratchet_payload(
    total_line_rate: str,
    *,
    min_line_rate_basis_points: int | None = None,
) -> str:
    total_basis_points = int((Decimal(total_line_rate) * Decimal("10000")).quantize(Decimal("1")))
    effective_floor = (
        max(total_basis_points - ratchet_policy.COVERAGE_FLOOR_BUFFER_BASIS_POINTS, 0)
        if min_line_rate_basis_points is None
        else min_line_rate_basis_points
    )
    return f"""
{{
    "kind": "sattlint.coverage_ratchet",
    "schema_version": 1,
    "metrics": {{
        "min_line_rate_basis_points": {effective_floor},
        "min_changed_line_rate_basis_points": 10000,
        "min_touched_file_line_rate_basis_points": 9000
    }},
    "summary": {{
        "total_line_rate": {total_line_rate}
    }},
    "source": "coverage.xml"
}}
""".strip()


def _pyproject_with_typing_ratchet(
    cov_fail_under: str,
    *,
    strict_paths: tuple[str, ...] = ("src/sattlint/core/document.py",),
    debt_allowlist: tuple[str, ...] = ("src/sattlint/core/semantic.py",),
    strict_roots: tuple[str, ...] | None = None,
) -> str:
    effective_roots = strict_roots or (*strict_paths, *debt_allowlist)
    strict_lines = "\n".join(f'    "{path}",' for path in strict_paths)
    root_lines = "\n".join(f'    "{path}",' for path in effective_roots)
    debt_lines = "\n".join(f'    "{path}",' for path in debt_allowlist)
    return f"""
[tool.pytest.ini_options]
addopts = ["--cov-fail-under={cov_fail_under}"]

[tool.pyright]
strict = [
{strict_lines}
]

[tool.sattlint.typing_ratchet]
strict_roots = [
{root_lines}
]
debt_allowlist = [
{debt_lines}
]
""".strip()


def _file_debt_ratchet_payload(files: dict[str, object] | None = None) -> str:
    return json.dumps(
        {
            "kind": ratchet_policy.FILE_DEBT_RATCHET_SCHEMA_KIND,
            "schema_version": ratchet_policy.FILE_DEBT_RATCHET_SCHEMA_VERSION,
            "files": files or {},
        },
        indent=4,
        sort_keys=True,
    )


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
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8927"),
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
        },
    )

    assert len(errors) == 1
    assert "Ratchet edits require explicit approval" in errors[0]


def test_evaluate_policy_change_requires_approval_for_file_debt_ratchet_edits(tmp_path):
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes /></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    errors = ratchet_policy.evaluate_policy_change(
        repo_root=tmp_path,
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH,),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            ratchet_policy.STRUCTURAL_RATCHET_PATH: '{"metrics": {"source_file_max_lines": 500}}',
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26"),
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
        },
    )

    assert len(errors) == 1
    assert "Ratchet edits require explicit approval" in errors[0]


def test_file_debt_ratchet_state_rejects_unknown_touch_rule():
    payload = _file_debt_ratchet_payload(
        {
            "src/pkg/legacy.py": {
                "structural": {
                    "current_baseline": 520,
                    "target": 500,
                    "touch_rule": "grow_freely",
                    "reason": "Invalid test payload.",
                }
            }
        }
    )

    try:
        ratchet_policy._file_debt_ratchet_state(payload, ratchet_policy.FILE_DEBT_RATCHET_PATH)
    except ValueError as exc:
        assert "touch_rule must be one of" in str(exc)
    else:
        raise AssertionError("Expected a ValueError for an invalid per-file debt touch_rule")


def test_evaluate_policy_change_rejects_coverage_debt_entry_that_does_not_mirror_coverage_xml(tmp_path):
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"src/pkg/legacy.py\" line-rate=\"0.90\" lines-valid=\"10\" lines-covered=\"9\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )
    base_payload = _file_debt_ratchet_payload(
        {
            "src/pkg/legacy.py": {
                "structural": {
                    "current_baseline": 520,
                    "target": 500,
                    "touch_rule": "must_not_grow",
                    "reason": "Legacy owner module remains centralized pending extraction.",
                }
            }
        }
    )
    head_payload = _file_debt_ratchet_payload(
        {
            "src/pkg/legacy.py": {
                "structural": {
                    "current_baseline": 520,
                    "target": 500,
                    "touch_rule": "must_not_grow",
                    "reason": "Legacy owner module remains centralized pending extraction.",
                },
                "coverage": {
                    "current_baseline": 9100,
                    "target": 9500,
                    "touch_rule": "must_not_drop",
                    "reason": "Touched source coverage debt must mirror coverage.xml and still reach full proof.",
                },
            },
        }
    )

    errors = ratchet_policy.evaluate_policy_change(
        repo_root=tmp_path,
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: '{"metrics": {"source_file_max_lines": 500}}',
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26"),
            approval_path: "Approved-by: Human Reviewer\nReason: attempted debt growth\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: base_payload,
            approval_path: None,
        },
    )

    assert any("must match the current coverage.xml module rate" in error for error in errors)
    assert any("must use must_reach_target_on_touch" in error for error in errors)
    assert any("must be 10000" in error for error in errors)


def test_evaluate_policy_change_allows_approved_migration_of_existing_coverage_debt(tmp_path):
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"src/pkg/legacy.py\" line-rate=\"0.90\" lines-valid=\"10\" lines-covered=\"9\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )
    head_payload = _file_debt_ratchet_payload(
        {
            "src/pkg/legacy.py": {
                "coverage": {
                    "current_baseline": 9000,
                    "target": 10000,
                    "touch_rule": "must_reach_target_on_touch",
                    "reason": "Touched source coverage debt must reach full proof on the next edit.",
                }
            }
        }
    )

    errors = ratchet_policy.evaluate_policy_change(
        repo_root=tmp_path,
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: '{"metrics": {"source_file_max_lines": 500}}',
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26"),
            approval_path: "Approved-by: Human Reviewer\nReason: migrate first approved per-file coverage debt entry into the sparse ledger\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_allows_approved_migration_of_existing_structural_and_typing_debt(tmp_path):
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes /></package></packages>
</coverage>""",
        encoding="utf-8",
    )
    head_payload = _file_debt_ratchet_payload(
        {
            "src/sattlint/app.py": {
                "structural": {
                    "current_baseline": 891,
                    "target": 500,
                    "touch_rule": "must_shrink",
                    "reason": "Interactive app entry owner still centralizes CLI and menu routing.",
                },
                "typing": {
                    "touch_rule": "must_exit_on_touch",
                    "reason": "Touched app facade typing debt must leave the Pyright debt allowlist.",
                },
            },
        }
    )
    structural_payload = """
{
    "metrics": {"source_file_max_lines": 2297},
    "file_line_exceptions": {
        "src/sattlint/app.py": {
            "max_lines": 891,
            "reason": "Interactive app entry owner still centralizes CLI and menu routing."
        }
    }
}
""".strip()
    pyproject_text = _pyproject_with_typing_ratchet(
        "87.26",
        strict_paths=("src/sattlint/core/document.py",),
        debt_allowlist=("src/sattlint/app.py",),
        strict_roots=("src/sattlint",),
    )

    errors = ratchet_policy.evaluate_policy_change(
        repo_root=tmp_path,
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: structural_payload,
            ratchet_policy.PYPROJECT_PATH: pyproject_text,
            approval_path: "Approved-by: Human Reviewer\nReason: migrate first real structural and typing debt entries into the sparse ledger\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_markdown_structural_debt_entry(tmp_path):
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes /></package></packages>
</coverage>""",
        encoding="utf-8",
    )
    head_payload = _file_debt_ratchet_payload(
        {
            "docs/exec-plans/feature-roadmap.md": {
                "structural": {
                    "current_baseline": 1453,
                    "target": 500,
                    "touch_rule": "must_shrink",
                    "reason": "Roadmap owner document remains centralized pending breakdown into smaller planning documents.",
                }
            }
        }
    )

    errors = ratchet_policy.evaluate_policy_change(
        repo_root=tmp_path,
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: '{"metrics": {"source_file_max_lines": 500}}',
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26"),
            approval_path: "Approved-by: Human Reviewer\nReason: attempted markdown structural debt entry\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            approval_path: None,
        },
    )

    assert any("must not target Markdown paths" in error for error in errors)


def test_file_debt_stale_entry_errors_flags_structural_and_coverage_entries(tmp_path):
    stale_structural = tmp_path / "src" / "pkg" / "stale_structural.py"
    stale_structural.parent.mkdir(parents=True)
    stale_structural.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"src/pkg/stale_coverage.py\" line-rate=\"1.0\" lines-valid=\"10\" lines-covered=\"10\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    errors = ratchet_policy._file_debt_stale_entry_errors(
        repo_root=tmp_path,
        file_debt_state={
            "src/pkg/stale_structural.py": {
                "structural": {
                    "current_baseline": 620,
                    "target": 500,
                    "touch_rule": "must_shrink",
                    "reason": "Already shrunk.",
                }
            },
            "src/pkg/stale_coverage.py": {
                "coverage": {
                    "current_baseline": 9000,
                    "target": 10000,
                    "touch_rule": "must_reach_target_on_touch",
                    "reason": "Already at full proof.",
                }
            },
        },
    )

    assert any("stale for src/pkg/stale_structural.py" in error for error in errors)
    assert any("stale for src/pkg/stale_coverage.py" in error for error in errors)


def test_file_debt_runtime_errors_flags_unlisted_touched_files_below_targets(tmp_path):
    undercovered = tmp_path / "src" / "pkg" / "undercovered.py"
    undercovered.parent.mkdir(parents=True)
    undercovered.write_text("value = 1\n", encoding="utf-8")

    oversized = tmp_path / "src" / "pkg" / "oversized.py"
    oversized.write_text("\n".join(f"line_{index} = {index}" for index in range(501)), encoding="utf-8")

    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"src/pkg/undercovered.py\" line-rate=\"0.90\" lines-valid=\"10\" lines-covered=\"9\">
            <lines/>
        </class>
        <class filename=\"src/pkg/oversized.py\" line-rate=\"1.0\" lines-valid=\"10\" lines-covered=\"10\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    errors = ratchet_policy._file_debt_runtime_errors(
        repo_root=tmp_path,
        context=ratchet_policy.ChangeContext(
            changed_files=("src/pkg/undercovered.py", "src/pkg/oversized.py"),
            added_files=(),
            base_ref=None,
            source="test",
        ),
        file_debt_state={},
        structural_exceptions={
            "src/pkg/oversized.py": {
                "max_lines": 700,
                "reason": "Existing structural exception still needs convergence.",
            }
        },
        typing_state=ratchet_policy.TypingRatchetState(strict_paths=(), strict_roots=(), debt_allowlist=()),
    )

    assert any(
        "missing per-file coverage debt entry" in error and "src/pkg/undercovered.py" in error for error in errors
    )
    assert any("missing per-file debt entry" in error and "src/pkg/oversized.py" in error for error in errors)


def test_file_debt_runtime_errors_accepts_unlisted_touched_files_at_targets(tmp_path):
    covered = tmp_path / "src" / "pkg" / "covered.py"
    covered.parent.mkdir(parents=True)
    covered.write_text("value = 1\n", encoding="utf-8")

    within_target = tmp_path / "src" / "pkg" / "within_target.py"
    within_target.write_text("line = 1\n", encoding="utf-8")

    (tmp_path / "coverage.xml").write_text(
        """<?xml version=\"1.0\" ?>
<coverage>
    <packages><package><classes>
        <class filename=\"src/pkg/covered.py\" line-rate=\"1.0\" lines-valid=\"10\" lines-covered=\"10\">
            <lines/>
        </class>
        <class filename=\"src/pkg/within_target.py\" line-rate=\"1.0\" lines-valid=\"10\" lines-covered=\"10\">
            <lines/>
        </class>
    </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )

    errors = ratchet_policy._file_debt_runtime_errors(
        repo_root=tmp_path,
        context=ratchet_policy.ChangeContext(
            changed_files=("src/pkg/covered.py", "src/pkg/within_target.py"),
            added_files=(),
            base_ref=None,
            source="test",
        ),
        file_debt_state={},
        structural_exceptions={
            "src/pkg/within_target.py": {
                "max_lines": 700,
                "reason": "Existing structural exception still needs convergence.",
            }
        },
        typing_state=ratchet_policy.TypingRatchetState(strict_paths=(), strict_roots=(), debt_allowlist=()),
    )

    assert errors == []
