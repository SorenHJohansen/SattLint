"""Registered ``icf`` analyzer: validates every configured ``.icf`` file.

This is the first-class analyzer surface for ICF-configuration validation. It
runs once per analysis session (not per loaded target): it discovers all
``*.icf`` files under the configured ``icf_dir``, derives the referenced
programs from the parsed entries, and validates each program against the
entries that reference it. A file name is configuration, not program identity:
a channel configuration such as ``KaHCBSolvent.icf`` may reference several
programs and share its name with none of them.

Each referenced program is loaded once per session (reusing the in-memory
program when available, or via the project loader) and every
``ICFValidationIssue`` is mapped to an ``Issue`` in the ``icf.*`` kind
namespace.

The underlying validation machinery lives in :mod:`sattlint.analyzers.icf`
(:func:`validate_icf_entries_against_program`); this module only wraps it in the
registry ``analyzer_attr`` contract and turns its findings into ``Issue``
objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattlint.parser_api import BasePicture, ModuleTypeDef, ProjectLoadError

from ...config.types import ConfigDict
from ...models.project_graph import ProjectGraph, merge_project_basepicture, program_identity
from ...project.support import configured_icf_files
from ...reporting.icf_report import ICFEntry, ICFValidationIssue
from ..framework import Issue, ProgramAstLoader, SimpleReport
from . import parse_icf_file, validate_icf_entries_against_program
from ._icf_file_io import extract_icf_sattline_ref, is_placeholder_icf_value

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
    return f"{location}: {issue.reason}: {first_line}"


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


@dataclass(frozen=True)
class _LoadedProgram:
    """One referenced program, loaded once per analysis session."""

    base_picture: BasePicture
    moduletype_index: dict[str, list[ModuleTypeDef]] | None


def _entries_by_program(entries: list[ICFEntry]) -> dict[str, list[ICFEntry]]:
    """Group parsed entries by the program each one references.

    The program a file validates against comes from the entry values, never
    from the file name. Entries with no parseable ``Program:Path`` reference
    validate nothing, so they belong to no group and produce no finding.
    """
    grouped: dict[str, list[ICFEntry]] = {}
    display_names: dict[str, str] = {}
    for entry in entries:
        if is_placeholder_icf_value(entry.value):
            continue
        program, path = extract_icf_sattline_ref(entry.value)
        if program is None or path is None:
            continue
        key = program.casefold()
        display_names.setdefault(key, program)
        grouped.setdefault(key, []).append(entry)
    return {display_names[key]: program_entries for key, program_entries in grouped.items()}


def _load_referenced_program(
    program_name: str,
    config: ConfigDict,
    *,
    base_picture: BasePicture | None,
    program_ast_loader: ProgramAstLoader,
    program_cache: dict[str, _LoadedProgram],
) -> tuple[_LoadedProgram | None, Exception | None]:
    key = program_name.casefold()
    cached = program_cache.get(key)
    if cached is not None:
        return cached, None

    # ``header.name`` is the literal ``BasePicture`` keyword, so the loaded
    # program's own name is the only usable identity here.
    if base_picture is not None and program_identity(base_picture).casefold() == key:
        loaded = _LoadedProgram(base_picture=base_picture, moduletype_index=None)
    else:
        try:
            program_bp, graph = program_ast_loader(config, program_name)
        except (OSError, RuntimeError, ValueError, ProjectLoadError) as exc:
            return None, exc
        loaded = _LoadedProgram(
            base_picture=merge_project_basepicture(program_bp, graph),
            moduletype_index=_moduletype_index_for(graph),
        )

    program_cache[key] = loaded
    return loaded, None


def _validate_icf_program(
    icf_file: Path,
    program_name: str,
    entries: list[ICFEntry],
    config: ConfigDict,
    *,
    base_picture: BasePicture | None,
    debug: bool,
    program_ast_loader: ProgramAstLoader,
    program_cache: dict[str, _LoadedProgram],
) -> list[Issue]:
    loaded, load_error = _load_referenced_program(
        program_name,
        config,
        base_picture=base_picture,
        program_ast_loader=program_ast_loader,
        program_cache=program_cache,
    )
    if loaded is None:
        detail = str(load_error)
        return [
            Issue(
                kind=_KIND_FOR_LOAD_FAILURE,
                message=f"{icf_file.name}: could not load program {program_name!r}: {detail}",
                module_path=[program_name],
                data={
                    "program": program_name,
                    "file": str(icf_file),
                    "detail": detail,
                    "site": str(icf_file),
                    "context": detail,
                },
            )
        ]

    report = validate_icf_entries_against_program(
        loaded.base_picture,
        entries,
        expected_program=program_name,
        debug=debug,
        moduletype_index=loaded.moduletype_index,
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


def _validate_icf_file(
    icf_file: Path,
    config: ConfigDict,
    *,
    base_picture: BasePicture | None,
    debug: bool,
    program_ast_loader: ProgramAstLoader,
    program_cache: dict[str, _LoadedProgram],
) -> list[Issue]:
    entries = parse_icf_file(icf_file)
    if not entries:
        return []

    issues: list[Issue] = []
    for program_name, program_entries in _entries_by_program(entries).items():
        issues.extend(
            _validate_icf_program(
                icf_file,
                program_name,
                program_entries,
                config,
                base_picture=base_picture,
                debug=debug,
                program_ast_loader=program_ast_loader,
                program_cache=program_cache,
            )
        )
    return issues


def analyze_icf_configuration(
    base_picture: BasePicture | None,
    *,
    config: ConfigDict | None = None,
    debug: bool = False,
    program_ast_loader: ProgramAstLoader | None = None,
) -> SimpleReport:
    """Validate every program referenced by the configured ``.icf`` files.

    ``base_picture`` is optional; when it matches one of the referenced
    programs the already-loaded AST is reused instead of re-loading it.
    ``program_ast_loader`` is the caller-supplied project loader contract used
    for the remaining programs; the analyzer layer never imports the project
    package. The analyzer is delivered as a once-per-session whole-run check.
    """
    if config is None:
        return SimpleReport(name="ICF configuration", issues=[])

    _, icf_files = configured_icf_files(config)
    if not icf_files:
        return SimpleReport(name="ICF configuration", issues=[])

    if program_ast_loader is None:
        raise RuntimeError("ICF analysis needs a program loader to load the programs an .icf file references.")

    issues: list[Issue] = []
    program_cache: dict[str, _LoadedProgram] = {}
    for icf_file in icf_files:
        issues.extend(
            _validate_icf_file(
                icf_file,
                config=config,
                base_picture=base_picture,
                debug=debug,
                program_ast_loader=program_ast_loader,
                program_cache=program_cache,
            )
        )
    return SimpleReport(name="ICF configuration", issues=issues)


__all__ = ["analyze_icf_configuration"]
