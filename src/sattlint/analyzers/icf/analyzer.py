"""Registered ``icf`` analyzer: validates every configured ``.icf`` file.

This is the first-class analyzer surface for ICF-configuration validation. It
runs once per analysis session (not per loaded target): it discovers all
``*.icf`` files under the configured ``icf_dir``, loads each referenced program
(either reusing the in-memory program when available, or via the project
loader), and maps every ``ICFValidationIssue`` to an ``Issue`` in the
``icf.*`` kind namespace.

The underlying validation machinery lives in :mod:`sattlint.analyzers.icf`
(:func:`validate_icf_entries_against_program`); this module only wraps it in the
registry ``analyzer_attr`` contract and turns its findings into ``Issue``
objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef

from ...config.types import ConfigDict
from ...models.project_graph import ProjectGraph, merge_project_basepicture
from ...project.loading import load_program_ast
from ...project.support import configured_icf_files
from ...reporting.icf_report import ICFValidationIssue
from ..framework import Issue, SimpleReport
from . import parse_icf_file, validate_icf_entries_against_program

_REASON_TO_KIND: dict[str, str] = {
    "program mismatch": "icf.program_mismatch",
    "unresolved path": "icf.unresolved_path",
    "invalid field path": "icf.invalid_field_path",
    "reference case mismatch": "icf.reference_case_mismatch",
    "unit tag mismatch": "icf.unit_tag_mismatch",
    "group tag mismatch": "icf.group_tag_mismatch",
    "missing journal parameter fields": "icf.missing_journal_field",
    "unit structure drift": "icf.unit_structure_drift",
    "mixed ICF value prefix letters": "icf.value_prefix_inconsistency",
}

_KIND_FOR_LOAD_FAILURE = "icf.program_load_failed"


def _kind_for_reason(reason: str) -> str:
    return _REASON_TO_KIND.get(reason, "icf.issue")


def _issue_message(issue: ICFValidationIssue) -> str:
    location = f"{issue.entry.file_path.name}:{issue.entry.line_no}"
    if not issue.detail:
        return f"{location}: {issue.reason}"
    first_line = issue.detail.strip().splitlines()[0] if issue.detail.strip() else ""
    if not first_line:
        return f"{location}: {issue.reason}"
    return f"{location}: {issue.reason} — {first_line}"


def _issue_data(issue: ICFValidationIssue, program_name: str) -> dict[str, Any]:
    return {
        "program": program_name,
        "file": str(issue.entry.file_path),
        "line": issue.entry.line_no,
        "reason": issue.reason,
        "detail": issue.detail,
        "section": issue.entry.section,
        "key": issue.entry.key,
        "value": issue.entry.value,
        "site": f"{issue.entry.file_path.name}:{issue.entry.line_no}",
        "context": f"{issue.entry.key} = {issue.entry.value}",
    }


def _moduletype_index_for(graph: ProjectGraph) -> dict[str, list[ModuleTypeDef]] | None:
    index: dict[str, list[ModuleTypeDef]] = {}
    for bp in graph.ast_by_name.values():
        for mt in cast(list[ModuleTypeDef] | None, getattr(bp, "moduletype_defs", None)) or []:
            key = mt.name.casefold()
            index.setdefault(key, []).append(mt)
    return index


def _validate_icf_file(
    icf_file: Path,
    program_name: str,
    config: ConfigDict,
    *,
    base_picture: BasePicture | None,
    debug: bool,
) -> list[Issue]:
    entries = parse_icf_file(icf_file)
    if not entries:
        return []

    reuse_in_memory = False
    if base_picture is not None:
        header = getattr(base_picture, "header", None)
        header_name = getattr(header, "name", None)
        if isinstance(header_name, str) and header_name.casefold() == program_name.casefold():
            reuse_in_memory = True

    if reuse_in_memory and base_picture is not None:
        program_bp = base_picture
        graph: ProjectGraph | None = None
    else:
        try:
            program_bp, graph = load_program_ast(config, program_name)
        except (OSError, RuntimeError, ValueError) as exc:
            return [
                Issue(
                    kind=_KIND_FOR_LOAD_FAILURE,
                    message=f"{icf_file.name}: could not load program {program_name!r}: {exc}",
                    module_path=[program_name],
                    data={
                        "program": program_name,
                        "file": str(icf_file),
                        "detail": str(exc),
                        "site": str(icf_file),
                        "context": str(exc),
                    },
                )
            ]

    if graph is not None:
        program_bp = merge_project_basepicture(program_bp, graph)
        moduletype_index = _moduletype_index_for(graph)
    else:
        moduletype_index = None

    report = validate_icf_entries_against_program(
        program_bp,
        entries,
        expected_program=program_name,
        debug=debug,
        moduletype_index=moduletype_index,
    )
    return [
        Issue(
            kind=_kind_for_reason(issue.reason),
            message=_issue_message(issue),
            module_path=[program_name],
            data=_issue_data(issue, program_name),
        )
        for issue in report.issues
    ]


def analyze_icf_configuration(
    base_picture: BasePicture | None,
    *,
    config: ConfigDict | None = None,
    debug: bool = False,
) -> SimpleReport:
    """Validate every configured ``.icf`` file against its referenced program.

    ``base_picture`` is optional; when it matches an ``.icf`` file's program the
    already-loaded AST is reused instead of re-loading it. The analyzer is
    delivered as a once-per-session whole-run check.
    """
    if config is None:
        return SimpleReport(name="ICF configuration", issues=[])

    _, icf_files = configured_icf_files(config)
    issues: list[Issue] = []
    for icf_file in icf_files:
        issues.extend(
            _validate_icf_file(
                icf_file,
                program_name=icf_file.stem,
                config=config,
                base_picture=base_picture,
                debug=debug,
            )
        )
    return SimpleReport(name="ICF configuration", issues=issues)


__all__ = ["analyze_icf_configuration"]
