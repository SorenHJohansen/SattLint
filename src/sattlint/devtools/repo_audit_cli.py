"""Compatibility wrapper for the moved repo-audit CLI."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import argparse
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .audit import repo_audit_cli as _owner

_OWNER_REPO_AUDIT_MODULE = _owner._repo_audit_module
_OWNER_SELECTED_CHECK_EXIT_CODE = _owner._selected_check_exit_code


def _repo_audit_module() -> Any:
    return _OWNER_REPO_AUDIT_MODULE()


def _selected_check_exit_code(summary: dict[str, Any], fail_on: str) -> tuple[int, dict[str, Any]]:
    return _OWNER_SELECTED_CHECK_EXIT_CODE(summary, fail_on)


@contextmanager
def _patched_owner_test_seams() -> Generator[None]:
    original_repo_audit_module = _owner._repo_audit_module
    original_selected_check_exit_code = _owner._selected_check_exit_code
    _owner._repo_audit_module = _repo_audit_module
    _owner._selected_check_exit_code = _selected_check_exit_code
    try:
        yield
    finally:
        _owner._repo_audit_module = original_repo_audit_module
        _owner._selected_check_exit_code = original_selected_check_exit_code


def build_cli_parser(*, prog: str | None = None, add_help: bool = True) -> argparse.ArgumentParser:
    with _patched_owner_test_seams():
        return _owner.build_cli_parser(prog=prog, add_help=add_help)


def _check_mode_conflicts(args: argparse.Namespace, parser: Any) -> None:
    with _patched_owner_test_seams():
        _owner._check_mode_conflicts(args, parser)


def _latest_report_links(current_output_dir: Path) -> tuple[str | None, str | None]:
    with _patched_owner_test_seams():
        return _owner._latest_report_links(current_output_dir)


def _run_selected_checks(args: argparse.Namespace, fail_on: str) -> tuple[int, dict[str, Any]]:
    with _patched_owner_test_seams():
        return _owner._run_selected_checks(args, fail_on)


def run_parsed_args(args: argparse.Namespace, *, parser: Any | None = None) -> int:
    with _patched_owner_test_seams():
        return _owner.run_parsed_args(args, parser=parser)


def main(argv: list[str] | None = None) -> int:
    with _patched_owner_test_seams():
        return _owner.main(argv)


__all__ = ["build_cli_parser", "main", "run_parsed_args"]
