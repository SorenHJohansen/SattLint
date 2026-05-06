from __future__ import annotations

import importlib.util
import json
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


def _coverage_ratchet_payload(total_line_rate: str) -> str:
    return f"""
{{
    \"kind\": \"sattlint.coverage_ratchet\",
    \"schema_version\": 1,
    \"metrics\": {{
        \"min_line_rate_basis_points\": 8726,
        \"min_changed_line_rate_basis_points\": 10000,
        \"min_touched_file_line_rate_basis_points\": 9000
    }},
    \"summary\": {{
        \"total_line_rate\": {total_line_rate}
    }},
    \"source\": \"coverage.xml\"
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


def test_evaluate_policy_change_allows_initial_typing_ratchet_adoption_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = """
[tool.pytest.ini_options]
addopts = ["--cov-fail-under=87.26"]
""".strip()
    head_pyproject = _pyproject_with_typing_ratchet("87.26")

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: seed explicit typing debt while ratcheting strict coverage\n",
        },
        base_text_by_path={
            ratchet_policy.COVERAGE_RATCHET_PATH: _coverage_ratchet_payload("0.8826"),
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_typing_debt_growth_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_roots=("src/sattlint/core",),
    )
    head_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_roots=("src/sattlint/core",),
        debt_allowlist=("src/sattlint/core/semantic.py", "src/sattlint/core/ast_tools.py"),
    )

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted typing exception growth\n",
        },
        base_text_by_path={
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert any("Typing debt allowlist grew" in error for error in errors)


def test_evaluate_policy_change_allows_typing_scope_expansion_inventory_for_existing_files(tmp_path):
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    (tmp_path / "src" / "sattlint" / "core").mkdir(parents=True)
    (tmp_path / "src" / "sattlint" / "devtools").mkdir(parents=True)
    (tmp_path / "src" / "sattlint").mkdir(parents=True, exist_ok=True)
    for rel_path in (
        "src/sattlint/__init__.py",
        "src/sattlint/app.py",
        "src/sattlint/core/document.py",
        "src/sattlint/core/semantic.py",
        "src/sattlint/devtools/repo_audit.py",
        "src/sattlint/devtools/repo_audit_cli.py",
    ):
        file_path = tmp_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("value = 1\n", encoding="utf-8")

    base_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_paths=("src/sattlint/core/document.py", "src/sattlint/devtools/repo_audit_cli.py"),
        debt_allowlist=("src/sattlint/core/semantic.py", "src/sattlint/devtools/repo_audit.py"),
        strict_roots=("src/sattlint/core", "src/sattlint/devtools"),
    )
    head_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_paths=(
            "src/sattlint/core/document.py",
            "src/sattlint/devtools/repo_audit.py",
            "src/sattlint/devtools/repo_audit_cli.py",
        ),
        debt_allowlist=(
            "src/sattlint/__init__.py",
            "src/sattlint/app.py",
            "src/sattlint/core/semantic.py",
        ),
        strict_roots=("src/sattlint",),
    )

    errors = ratchet_policy.evaluate_policy_change(
        repo_root=tmp_path,
        changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: approved typing scope expansion inventory\n",
        },
        base_text_by_path={
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert errors == []


def test_evaluate_policy_change_rejects_pyright_strict_shrink_even_with_approval():
    approval_path = ".github/approvals/ratchet-rebaseline-2026-05-01.md"
    base_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_paths=("src/sattlint/core/document.py", "src/sattlint/core/diagnostics.py"),
    )
    head_pyproject = _pyproject_with_typing_ratchet("87.26")

    errors = ratchet_policy.evaluate_policy_change(
        changed_files=(ratchet_policy.PYPROJECT_PATH, approval_path),
        current_text_by_path={
            ratchet_policy.PYPROJECT_PATH: head_pyproject,
            approval_path: "Approved-by: Human Reviewer\nReason: attempted strict-list shrink\n",
        },
        base_text_by_path={
            ratchet_policy.PYPROJECT_PATH: base_pyproject,
            approval_path: None,
        },
    )

    assert any("Pyright strict coverage removed" in error for error in errors)


def test_typing_ratchet_state_errors_reject_new_scoped_file_in_debt_allowlist(tmp_path):
    scoped_file = tmp_path / "src" / "sattlint" / "core" / "new_module.py"
    scoped_file.parent.mkdir(parents=True)
    scoped_file.write_text("value = 1\n", encoding="utf-8")

    errors = ratchet_policy._typing_ratchet_state_errors(
        repo_root=tmp_path,
        added_files=("src/sattlint/core/new_module.py",),
        state=ratchet_policy.TypingRatchetState(
            strict_paths=(),
            strict_roots=("src/sattlint/core",),
            debt_allowlist=("src/sattlint/core/new_module.py",),
        ),
    )

    assert any("Typing debt allowlist grew with a new scoped file" in error for error in errors)


def test_typing_ratchet_state_errors_reject_touched_scoped_file_in_debt_allowlist(tmp_path):
    scoped_file = tmp_path / "src" / "sattlint_lsp" / "server.py"
    scoped_file.parent.mkdir(parents=True)
    scoped_file.write_text("value = 1\n", encoding="utf-8")

    errors = ratchet_policy._typing_ratchet_state_errors(
        repo_root=tmp_path,
        added_files=(),
        changed_files=("src/sattlint_lsp/server.py",),
        state=ratchet_policy.TypingRatchetState(
            strict_paths=(),
            strict_roots=("src/sattlint_lsp",),
            debt_allowlist=("src/sattlint_lsp/server.py",),
        ),
    )

    assert any(
        "Touched file under the typing strict scope remains in typing debt allowlist" in error for error in errors
    )


def test_run_policy_check_rejects_touched_scoped_file_still_in_typing_debt(monkeypatch, tmp_path):
    scoped_file = tmp_path / "src" / "sattlint" / "app.py"
    scoped_file.parent.mkdir(parents=True)
    scoped_file.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(
        _pyproject_with_typing_ratchet(
            "87.26",
            strict_paths=(),
            debt_allowlist=("src/sattlint/app.py",),
            strict_roots=("src/sattlint",),
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ratchet_policy,
        "_detect_change_context",
        lambda *_args, **_kwargs: ratchet_policy.ChangeContext(
            changed_files=("src/sattlint/app.py",),
            added_files=(),
            base_ref=None,
            source="worktree",
        ),
    )

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert any(
        "Touched file under the typing strict scope remains in typing debt allowlist" in error for error in errors
    )


def test_run_policy_check_allows_preexisting_touched_debt_during_scope_expansion(monkeypatch, tmp_path):
    scoped_file = tmp_path / "src" / "sattlint" / "devtools" / "repo_audit.py"
    scoped_file.parent.mkdir(parents=True)
    scoped_file.write_text("value = 1\n", encoding="utf-8")
    head_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_paths=("src/sattlint/devtools/repo_audit_cli.py",),
        debt_allowlist=("src/sattlint/devtools/repo_audit.py",),
        strict_roots=("src/sattlint",),
    )
    base_pyproject = _pyproject_with_typing_ratchet(
        "87.26",
        strict_paths=("src/sattlint/devtools/repo_audit_cli.py",),
        debt_allowlist=("src/sattlint/devtools/repo_audit.py",),
        strict_roots=("src/sattlint/devtools",),
    )
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(head_pyproject, encoding="utf-8")

    monkeypatch.setattr(
        ratchet_policy,
        "_detect_change_context",
        lambda *_args, **_kwargs: ratchet_policy.ChangeContext(
            changed_files=("src/sattlint/devtools/repo_audit.py",),
            added_files=(),
            base_ref="HEAD",
            source="staged",
        ),
    )
    monkeypatch.setattr(
        ratchet_policy,
        "_load_base_texts",
        lambda *_args, **_kwargs: {ratchet_policy.PYPROJECT_PATH: base_pyproject},
    )

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert not any(
        "Touched file under the typing strict scope remains in typing debt allowlist" in error for error in errors
    )


def test_run_policy_check_rejects_touched_file_in_per_file_typing_debt(monkeypatch, tmp_path):
    scoped_file = tmp_path / "src" / "sattlint" / "app.py"
    scoped_file.parent.mkdir(parents=True)
    scoped_file.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / ratchet_policy.PYPROJECT_PATH).write_text(
        _pyproject_with_typing_ratchet(
            "87.26",
            strict_paths=(),
            debt_allowlist=("src/sattlint/app.py",),
            strict_roots=("src/sattlint",),
        ),
        encoding="utf-8",
    )
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).parent.mkdir(parents=True)
    (tmp_path / ratchet_policy.FILE_DEBT_RATCHET_PATH).write_text(
        _file_debt_ratchet_payload(
            {
                "src/sattlint/app.py": {
                    "typing": {
                        "touch_rule": "must_exit_on_touch",
                        "reason": "Touched typing debt must leave the allowlist.",
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
            changed_files=("src/sattlint/app.py",),
            added_files=(),
            base_ref=None,
            source="worktree",
        ),
    )

    errors = ratchet_policy.run_policy_check(tmp_path)

    assert any("Touched file in per-file typing debt ratchet remains" in error for error in errors)
