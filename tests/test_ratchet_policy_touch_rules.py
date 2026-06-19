# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path


def _load_ratchet_policy_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_ratchet_policy.py"
    spec = importlib.util.spec_from_file_location("check_ratchet_policy_touch", module_path)
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
    coverage_report_path = tmp_path / ".".join(("coverage", "xml"))
    target_file.parent.mkdir(parents=True)
    target_file.write_text("value = 1\n", encoding="utf-8")
    coverage_report_path.write_text(
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
        if args == ("ls-files", "--others", "--exclude-standard", ".github/approvals"):

            class UntrackedApprovalsResult:
                returncode = 0
                stdout = ""
                stderr = ""

            return UntrackedApprovalsResult()
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
        ("ls-files", "--others", "--exclude-standard", ".github/approvals"),
        ("diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"),
        ("diff", "--name-status", "--diff-filter=A", "origin/main...HEAD"),
    ]


def test_detect_change_context_prefers_worktree_when_unstaged_changes_exist(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(_repo_root, *args):
        calls.append(args)
        if args == ("ls-files", "--others", "--exclude-standard", ".github/approvals"):

            class UntrackedApprovalsResult:
                returncode = 0
                stdout = ""
                stderr = ""

            return UntrackedApprovalsResult()
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
        ("ls-files", "--others", "--exclude-standard", ".github/approvals"),
        ("diff", "--cached", "--name-only", "--diff-filter=ACMR"),
        ("diff", "--cached", "--name-status", "--diff-filter=A"),
        ("diff", "--name-only", "--diff-filter=ACMR", "HEAD"),
        ("diff", "--name-status", "--diff-filter=A", "HEAD"),
    ]


def test_detect_change_context_includes_untracked_approval_record(monkeypatch):
    calls: list[tuple[str, ...]] = []
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-07.md"

    def fake_git(_repo_root, *args):
        calls.append(args)
        if args == ("ls-files", "--others", "--exclude-standard", ".github/approvals"):

            class UntrackedApprovalsResult:
                returncode = 0
                stdout = f"{approval_path}\n"
                stderr = ""

            return UntrackedApprovalsResult()
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

    assert context.changed_files == ("pyproject.toml", approval_path)
    assert context.added_files == (approval_path,)
    assert context.base_ref == "HEAD"
    assert context.source == "worktree"
    assert calls == [
        ("ls-files", "--others", "--exclude-standard", ".github/approvals"),
        ("diff", "--cached", "--name-only", "--diff-filter=ACMR"),
        ("diff", "--cached", "--name-status", "--diff-filter=A"),
        ("diff", "--name-only", "--diff-filter=ACMR", "HEAD"),
        ("diff", "--name-status", "--diff-filter=A", "HEAD"),
    ]


def test_run_policy_check_accepts_untracked_approval_record_for_protected_pyproject_edit(monkeypatch, tmp_path):
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-07.md"
    approval_file = tmp_path / approval_path
    approval_file.parent.mkdir(parents=True)
    approval_file.write_text(
        "Approved-by: Human Reviewer\nReason: allow protected pyproject repair from worktree\n",
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "analysis").mkdir(parents=True)
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(
        _pyproject_with_typing_ratchet("87.26"),
        encoding="utf-8",
    )
    (tmp_path / ratchet_policy.COVERAGE_RATCHET_PATH).write_text(_coverage_ratchet_payload("0.8826"), encoding="utf-8")
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).write_text(_file_debt_ratchet_payload(), encoding="utf-8")
    (tmp_path / ratchet_policy.STRUCTURAL_RATCHET_PATH).write_text(
        '{"metrics": {"source_file_max_lines": 500}}', encoding="utf-8"
    )

    monkeypatch.setattr(
        ratchet_policy,
        "_detect_change_context",
        lambda *_args, **_kwargs: ratchet_policy.ChangeContext(
            changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
            added_files=(approval_path,),
            base_ref="HEAD",
            source="worktree",
        ),
    )
    monkeypatch.setattr(ratchet_policy, "_typing_ratchet_state_errors", lambda **_kwargs: [])
    monkeypatch.setattr(ratchet_policy, "_file_debt_runtime_errors", lambda **_kwargs: [])

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert errors == []
