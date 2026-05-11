from __future__ import annotations

import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path


def _load_ratchet_policy_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_ratchet_policy.py"
    spec = importlib.util.spec_from_file_location("check_ratchet_policy_structural", module_path)
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
    "metrics": {"source_file_max_lines": 2297},
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


def test_evaluate_policy_change_allows_markdown_scope_retirement_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = """
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
    head_structural = """
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

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: retire Markdown ratchet scope and temporary exceptions\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_markdown_scope_in_structural_ratchet():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_structural = '{"metrics": {"source_file_max_lines": 500, "test_file_max_lines": 500}}'
    head_structural = """
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

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.STRUCTURAL_RATCHET_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: head_structural,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted Markdown ratchet reintroduction\n",
        },
        base_text_by_path={
            ratchet_policy.STRUCTURAL_RATCHET_PATH: base_structural,
            approval_path: None,
        },
    )

    assert any("must not track Markdown file metrics" in error for error in errors)
    assert any("must not target Markdown paths" in error for error in errors)


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
