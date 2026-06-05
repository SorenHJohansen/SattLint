from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sattlint import app_base
from sattlint.devtools import audit_core_discovery, repo_audit_cli


def _fake_repo_audit_module(tmp_path: Path, summaries: list[dict[str, object]]) -> SimpleNamespace:
    def _summary_payload(path: Path) -> dict[str, object]:
        return {
            "profile": "full",
            "output_dir": path.resolve().as_posix(),
            "finding_count": 0,
            "findings": [],
            "findings_schema": {"kind": "schema", "schema_version": 1},
            "cli_consistency_status": None,
        }

    return SimpleNamespace(
        DEFAULT_OUTPUT_DIR=tmp_path / "default-audit",
        AUDIT_PROFILE_CHOICES=("quick", "full"),
        REPO_AUDIT_INDIVIDUAL_CHECK_IDS=("cli-consistency", "public-readiness"),
        REPO_ROOT=tmp_path,
        _repo_audit_entrypoints=SimpleNamespace(
            build_check_my_changes_planning_report=lambda **kwargs: {
                "kind": "sattlint.planning_context",
                "planning_context": {"primary_agent": "CLI App Menu"},
            }
        ),
        build_repo_audit_check_catalog=lambda **kwargs: {"kind": "catalog", "checks": []},
        build_repo_audit_check_recommendations=lambda **kwargs: {"kind": "recommendations"},
        apply_ai_gc=lambda **kwargs: {"kind": "sattlint.ai_gc", "summary": {"failure_count": 0}},
        run_check_my_changes=lambda *args, **kwargs: {"kind": "sattlint.check_my_changes", "overall_status": "pass"},
        _run_repo_audit_findings_checks=lambda *args, **kwargs: _summary_payload(tmp_path / "selected-check"),
        _run_repo_audit_cli_consistency_check=lambda *args, **kwargs: _summary_payload(tmp_path / "cli-consistency"),
        run_recommended_repo_audit_slice=lambda *args, **kwargs: _summary_payload(tmp_path / "recommended-slice"),
        run_recommended_repo_audit_finish_gate=lambda *args, **kwargs: {
            **_summary_payload(tmp_path / "recommended-finish-gate"),
            "finish_gate": {"status": "fail"},
        },
        audit_repository=lambda *args, **kwargs: {
            **_summary_payload(tmp_path / "audit"),
            "profile": kwargs["profile"],
        },
        _print_cli_summary=lambda payload: summaries.append(payload),
        _should_fail=lambda findings, fail_on: False,
        _blocking_finding_count=lambda findings, fail_on: 0,
        Finding=lambda **kwargs: SimpleNamespace(**kwargs),
    )


def test_repo_audit_cli_main_machine_readable_branches(monkeypatch, tmp_path, capsys):
    summaries: list[dict[str, object]] = []
    fake_repo_audit = _fake_repo_audit_module(tmp_path, summaries)

    monkeypatch.setattr(repo_audit_cli, "_repo_audit_module", lambda: fake_repo_audit)

    assert repo_audit_cli.main(["--list-checks", "--output-dir", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"kind": "catalog", "checks": []}

    assert (
        repo_audit_cli.main(
            [
                "--recommend-checks",
                "--output-dir",
                str(tmp_path),
                "--changed-file",
                "README.md",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"kind": "recommendations"}

    assert repo_audit_cli.main(["--apply-ai-gc", "--output-dir", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"kind": "sattlint.ai_gc", "summary": {"failure_count": 0}}

    assert repo_audit_cli.main(["--planning-context", "--output-dir", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "kind": "sattlint.planning_context",
        "planning_context": {"primary_agent": "CLI App Menu"},
    }

    assert repo_audit_cli.main(["--check-my-changes", "--output-dir", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"kind": "sattlint.check_my_changes", "overall_status": "pass"}


def test_repo_audit_cli_selected_and_finish_gate_branches(monkeypatch, tmp_path):
    summaries: list[dict[str, object]] = []
    fake_repo_audit = _fake_repo_audit_module(tmp_path, summaries)

    monkeypatch.setattr(repo_audit_cli, "_repo_audit_module", lambda: fake_repo_audit)
    monkeypatch.setattr(
        repo_audit_cli,
        "_selected_check_exit_code",
        lambda summary, fail_on: (0, {"overall_status": "pass", "profile": "full"}),
    )

    assert repo_audit_cli.main(["--check", "public-readiness", "--output-dir", str(tmp_path)]) == 0
    assert repo_audit_cli.main(["--run-recommended-slice", "--output-dir", str(tmp_path)]) == 0
    assert repo_audit_cli.main(["--run-recommended-finish-gate", "--output-dir", str(tmp_path)]) == 1
    assert repo_audit_cli.main(["--output-dir", str(tmp_path)]) == 0

    assert summaries[0] == {"overall_status": "pass", "profile": "full"}
    assert summaries[2] == {"overall_status": "fail", "profile": "full"}


def test_repo_audit_cli_build_parser_supports_alias_parent_usage(monkeypatch, tmp_path):
    fake_repo_audit = _fake_repo_audit_module(tmp_path, [])

    monkeypatch.setattr(repo_audit_cli, "_repo_audit_module", lambda: fake_repo_audit)

    parser = repo_audit_cli.build_cli_parser(prog="sattlint repo-audit", add_help=False)
    option_strings = {
        option for parser_action in parser._actions for option in getattr(parser_action, "option_strings", [])
    }

    assert parser.prog == "sattlint repo-audit"
    assert "-h" not in option_strings
    assert {"--profile", "--fail-on", "--list-checks", "--planning-context"} <= option_strings


def test_collect_cli_metadata_ignores_non_subparser_choices(tmp_path):
    scripts, subcommands = audit_core_discovery.collect_cli_metadata(
        repo_root=tmp_path,
        load_pyproject_fn=lambda _root: {"project": {"scripts": {"sattlint": "sattlint.app:cli"}}},
        build_cli_parser=app_base.build_cli_parser,
    )

    assert scripts == {"sattlint"}
    assert {"syntax-check", "analyze", "repo-audit"} <= subcommands


def test_repo_audit_cli_conflicts_and_latest_links(monkeypatch, tmp_path):
    parser = argparse.ArgumentParser()
    fake_repo_audit = _fake_repo_audit_module(tmp_path, [])

    monkeypatch.setattr(repo_audit_cli, "_repo_audit_module", lambda: fake_repo_audit)

    with pytest.raises(SystemExit):
        repo_audit_cli._check_mode_conflicts(
            argparse.Namespace(
                check=["public-readiness"],
                recommend_checks=True,
                run_recommended_slice=False,
                run_recommended_finish_gate=False,
                check_my_changes=False,
                list_checks=False,
                planning_context=False,
                leaks_only=False,
                apply_ai_gc=False,
            ),
            parser,
        )

    assert repo_audit_cli._latest_report_links(fake_repo_audit.DEFAULT_OUTPUT_DIR.resolve()) == (None, None)
    assert repo_audit_cli._latest_report_links(tmp_path / "other-audit") == (
        "default-audit/status.json",
        "default-audit/summary.json",
    )


@pytest.mark.parametrize(
    ("arg_overrides", "message"),
    [
        (
            {"leaks_only": True, "recommend_checks": True},
            "--leaks-only cannot be combined with --recommend-checks or --run-recommended-slice.",
        ),
        (
            {"check_my_changes": True, "list_checks": True},
            "--check-my-changes must be run on its own.",
        ),
        (
            {"planning_context": True, "apply_ai_gc": True},
            "--planning-context must be run on its own.",
        ),
        (
            {"apply_ai_gc": True, "list_checks": True},
            "--apply-ai-gc must be run on its own.",
        ),
    ],
)
def test_repo_audit_cli_conflict_guards_cover_remaining_exclusive_modes(
    monkeypatch,
    tmp_path,
    arg_overrides,
    message,
):
    fake_repo_audit = _fake_repo_audit_module(tmp_path, [])

    class ParserStub:
        def error(self, error_message: str) -> None:
            raise RuntimeError(error_message)

    monkeypatch.setattr(repo_audit_cli, "_repo_audit_module", lambda: fake_repo_audit)

    args = {
        "check": None,
        "recommend_checks": False,
        "run_recommended_slice": False,
        "run_recommended_finish_gate": False,
        "check_my_changes": False,
        "list_checks": False,
        "planning_context": False,
        "leaks_only": False,
        "apply_ai_gc": False,
    }
    args.update(arg_overrides)

    with pytest.raises(RuntimeError, match=message):
        repo_audit_cli._check_mode_conflicts(argparse.Namespace(**args), ParserStub())


def test_run_selected_checks_rejects_mixed_cli_consistency_selection(monkeypatch, tmp_path):
    fake_repo_audit = _fake_repo_audit_module(tmp_path, [])
    monkeypatch.setattr(repo_audit_cli, "_repo_audit_module", lambda: fake_repo_audit)

    with pytest.raises(ValueError, match="cli-consistency must be run alone"):
        repo_audit_cli._run_selected_checks(
            argparse.Namespace(
                check=["cli-consistency", "public-readiness"],
                output_dir=str(tmp_path),
                profile="full",
                include_generated=False,
                suspicious_identifier=[],
            ),
            "high",
        )
