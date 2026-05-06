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


def test_evaluate_policy_change_requires_approval_for_file_debt_ratchet_edits():
    errors = ratchet_policy.evaluate_policy_change(
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


def test_evaluate_policy_change_allows_approved_migration_of_existing_structural_and_typing_debt():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    head_payload = _file_debt_ratchet_payload(
        {
            "docs/exec-plans/feature-roadmap.md": {
                "structural": {
                    "current_baseline": 1453,
                    "target": 500,
                    "touch_rule": "must_shrink",
                    "reason": "Roadmap owner document remains centralized pending breakdown into smaller planning documents.",
                }
            },
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
    "metrics": {"source_file_max_lines": 2297, "markdown_file_max_lines": 1453},
    "file_line_exceptions": {
        "docs/exec-plans/feature-roadmap.md": {
            "max_lines": 1453,
            "reason": "Roadmap owner document remains centralized pending breakdown into smaller planning documents."
        },
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


def test_evaluate_policy_change_rejects_new_structural_debt_entry_without_converging_touch_rule():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    head_payload = _file_debt_ratchet_payload(
        {
            "src/sattlint/app.py": {
                "structural": {
                    "current_baseline": 891,
                    "target": 500,
                    "touch_rule": "must_not_grow",
                    "reason": "Interactive app entry owner still centralizes CLI and menu routing.",
                }
            }
        }
    )
    structural_payload = """
{
    "metrics": {"source_file_max_lines": 2297, "markdown_file_max_lines": 1453},
    "file_line_exceptions": {
        "src/sattlint/app.py": {
            "max_lines": 891,
            "reason": "Interactive app entry owner still centralizes CLI and menu routing."
        }
    }
}
""".strip()

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: structural_payload,
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26"),
            approval_path: "Approved-by: Human Reviewer\nReason: attempted non-converging structural entry\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            approval_path: None,
        },
    )

    assert any("must use must_shrink or must_meet_target" in error for error in errors)


def test_evaluate_policy_change_rejects_unmirrored_typing_debt_entry():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    head_payload = _file_debt_ratchet_payload(
        {
            "src/sattlint/app.py": {
                "typing": {
                    "touch_rule": "must_exit_on_touch",
                    "reason": "Touched app facade typing debt must leave the Pyright debt allowlist.",
                }
            }
        }
    )

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: '{"metrics": {"source_file_max_lines": 500}}',
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26", debt_allowlist=()),
            approval_path: "Approved-by: Human Reviewer\nReason: attempted typing migration without mirrored debt\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            approval_path: None,
        },
    )

    assert any("must mirror tool.sattlint.typing_ratchet.debt_allowlist" in error for error in errors)


def test_evaluate_policy_change_allows_structural_ledger_migration_while_removing_duplicate_exception():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-04.md"
    head_payload = _file_debt_ratchet_payload(
        {
            "src/sattlint/config.py": {
                "structural": {
                    "current_baseline": 565,
                    "target": 500,
                    "touch_rule": "must_shrink",
                    "reason": "Config owner surface still centralizes validation, defaults, and persistence flows.",
                }
            }
        }
    )
    base_structural_payload = """
{
    "metrics": {"source_file_max_lines": 2297},
    "file_line_exceptions": {
        "src/sattlint/config.py": {
            "max_lines": 565,
            "reason": "Config owner surface still centralizes validation, defaults, and persistence flows."
        }
    }
}
""".strip()
    head_structural_payload = '{"metrics": {"source_file_max_lines": 2297}, "file_line_exceptions": {}}'

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.FILE_DEBT_RATCHET_PATH, ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: head_payload,
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural_payload,
            ratchet_policy.PYPROJECT_PATH: _pyproject_with_typing_ratchet("87.26"),
            approval_path: "Approved-by: Human Reviewer\nReason: migrate structural debt into the sparse ledger and remove duplicate exception rows\n",
        },
        base_text_by_path={
            ratchet_policy.FILE_DEBT_RATCHET_PATH: _file_debt_ratchet_payload(),
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural_payload,
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_looser_coverage_ratchet_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826", min_line_rate_basis_points=8700),
            approval_path: "Approved-by: Human Reviewer\nReason: Tried to lower the gate\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            approval_path: None,
        },
    )

    assert any("Coverage ratchet floor must equal" in error for error in errors)


def test_evaluate_policy_change_rejects_looser_pytest_floor_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = _pyproject_with_typing_ratchet("87.26")
    head_pyproject = _pyproject_with_typing_ratchet("87.00")

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: lowering floor\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert any("Pytest coverage floor must equal" in error for error in errors)


def test_evaluate_policy_change_rejects_lowered_coverage_baseline_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8800"),
            approval_path: "Approved-by: Human Reviewer\nReason: tried to lower the baseline\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            approval_path: None,
        },
    )

    assert any("Coverage baseline decreased" in error for error in errors)


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
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8927"),
            approval_path: "Approved-by: Human Reviewer\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            approval_path: None,
        },
    )

    assert errors == [f"Approval record {approval_path} is missing a 'Reason:' line."]


def test_evaluate_policy_change_accepts_stricter_change_with_valid_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = _pyproject_with_typing_ratchet("87.26")
    head_pyproject = _pyproject_with_typing_ratchet("89.50")

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.COVERAGE_RATCHET_PATH, ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.9050"),
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: raised the floor after real fixes\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert errors == []


def test_run_policy_check_rejects_touched_structural_debt_file_that_exceeds_target(monkeypatch, tmp_path):
    target_file = tmp_path / "src" / "pkg" / "legacy.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("\n".join(f"line_{index}" for index in range(6)), encoding="utf-8")
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(
        _pyproject_with_typing_ratchet(
            "87.26",
            strict_paths=("src/pkg/legacy.py",),
            debt_allowlist=(),
            strict_roots=("src/pkg",),
        ),
        encoding="utf-8",
    )
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).parent.mkdir(parents=True)
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).write_text(
        _file_debt_ratchet_payload(
            {
                "src/pkg/legacy.py": {
                    "structural": {
                        "current_baseline": 5,
                        "target": 5,
                        "touch_rule": "must_not_grow",
                        "reason": "Legacy owner module must not grow while still oversized.",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ratchet_policy,
        "_detect_change_context",
        lambda *_args, **_kwargs: ratchet_policy.ChangeContext(
            changed_files=("src/pkg/legacy.py",),
            added_files=(),
            base_ref=None,
            source="worktree",
        ),
    )
    monkeypatch.setattr(
        ratchet_policy,
        "_load_base_texts",
        lambda *_args, **_kwargs: {"src/pkg/legacy.py": "\n".join(f"line_{index}" for index in range(5))},
    )

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert any("Touched structural debt file must meet target" in error for error in errors)
    assert any("target-meeting touch enforcement" in error for error in errors)
    assert any(ratchet_policy.FIRST_STRUCTURAL_DEBT_PROOF_COMMAND in error for error in errors)


def test_run_policy_check_rejects_touched_structural_debt_file_that_does_not_shrink(monkeypatch, tmp_path):
    target_file = tmp_path / "src" / "pkg" / "legacy.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("\n".join(f"line_{index}" for index in range(6)), encoding="utf-8")
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(
        _pyproject_with_typing_ratchet(
            "87.26",
            strict_paths=("src/pkg/legacy.py",),
            debt_allowlist=(),
            strict_roots=("src/pkg",),
        ),
        encoding="utf-8",
    )
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).parent.mkdir(parents=True)
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).write_text(
        _file_debt_ratchet_payload(
            {
                "src/pkg/legacy.py": {
                    "structural": {
                        "current_baseline": 6,
                        "target": 5,
                        "touch_rule": "must_not_grow",
                        "reason": "Legacy owner module must converge toward the target.",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ratchet_policy,
        "_detect_change_context",
        lambda *_args, **_kwargs: ratchet_policy.ChangeContext(
            changed_files=("src/pkg/legacy.py",),
            added_files=(),
            base_ref=None,
            source="worktree",
        ),
    )
    monkeypatch.setattr(
        ratchet_policy,
        "_load_base_texts",
        lambda *_args, **_kwargs: {"src/pkg/legacy.py": "\n".join(f"line_{index}" for index in range(6))},
    )

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert any("Touched structural debt file did not shrink" in error for error in errors)
    assert any("shrink-only touch enforcement" in error for error in errors)
    assert any("Reason: Legacy owner module must converge toward the target." in error for error in errors)


def test_run_policy_check_rejects_touched_coverage_debt_file_below_target(monkeypatch, tmp_path):
    target_file = tmp_path / "src" / "pkg" / "legacy.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("value = 1\n", encoding="utf-8")
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
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(
        _pyproject_with_typing_ratchet(
            "87.26",
            strict_paths=("src/pkg/legacy.py",),
            debt_allowlist=(),
            strict_roots=("src/pkg",),
        ),
        encoding="utf-8",
    )
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).parent.mkdir(parents=True)
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).write_text(
        _file_debt_ratchet_payload(
            {
                "src/pkg/legacy.py": {
                    "coverage": {
                        "current_baseline": 9000,
                        "target": 9500,
                        "touch_rule": "must_reach_target_on_touch",
                        "reason": "Touched coverage debt must clear the recorded target.",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ratchet_policy,
        "_detect_change_context",
        lambda *_args, **_kwargs: ratchet_policy.ChangeContext(
            changed_files=("src/pkg/legacy.py",),
            added_files=(),
            base_ref=None,
            source="worktree",
        ),
    )

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert any("Touched coverage debt file must reach target" in error for error in errors)


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


def test_detect_change_context_prefers_worktree_when_unstaged_changes_exist(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(_repo_root, *args):
        calls.append(args)
        if args == ("diff", "--cached", "--name-only", "--diff-filter=ACMR"):

            class DiffResult:
                returncode = 0
                stdout = ""
                stderr = ""

            return DiffResult()
        if args == ("diff", "--cached", "--name-status", "--diff-filter=A"):

            class AddedResult:
                returncode = 0
                stdout = ""
                stderr = ""

            return AddedResult()
        if args == ("diff", "--name-only", "--diff-filter=ACMR", "HEAD"):

            class WorktreeResult:
                returncode = 0
                stdout = "pyproject.toml\n"
                stderr = ""

            return WorktreeResult()
        if args == ("diff", "--name-status", "--diff-filter=A", "HEAD"):

            class WorktreeAddedResult:
                returncode = 0
                stdout = ""
                stderr = ""

            return WorktreeAddedResult()
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(ratchet_policy, "_git", fake_git)

    context = ratchet_policy._detect_change_context(Path("."), {})

    assert context.changed_files == ("pyproject.toml",)
    assert context.added_files == ()
    assert context.base_ref == "HEAD"
    assert context.source == "worktree"
    assert calls == [
        ("diff", "--cached", "--name-only", "--diff-filter=ACMR"),
        ("diff", "--cached", "--name-status", "--diff-filter=A"),
        ("diff", "--name-only", "--diff-filter=ACMR", "HEAD"),
        ("diff", "--name-status", "--diff-filter=A", "HEAD"),
    ]
