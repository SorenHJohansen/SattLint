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
from ..framework import Issue, ProgramAstBatchLoader, ProgramAstLoader, SimpleReport
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
    unavailable_libraries: frozenset[str] = frozenset()


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
    program_ast_loader: ProgramAstLoader | None,
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
    elif program_ast_loader is None:
        return None, RuntimeError(
            "the batch load did not provide this program and no single-program loader is available"
        )
    else:
        try:
            program_bp, graph = program_ast_loader(config, program_name)
        except (OSError, RuntimeError, ValueError, ProjectLoadError) as exc:
            return None, exc
        loaded = _LoadedProgram(
            base_picture=merge_project_basepicture(program_bp, graph),
            moduletype_index=_moduletype_index_for(graph),
            unavailable_libraries=frozenset(graph.unavailable_libraries),
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
    program_ast_loader: ProgramAstLoader | None,
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
        unavailable_libraries=loaded.unavailable_libraries,
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


def _referenced_program_names(file_entries: list[tuple[Path, list[ICFEntry]]]) -> list[str]:
    """Every program the configured files reference, in first-seen order."""
    seen: set[str] = set()
    names: list[str] = []
    for _icf_file, entries in file_entries:
        for program_name in _entries_by_program(entries):
            key = program_name.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(program_name)
    return names


def _preload_referenced_programs(
    program_names: list[str],
    config: ConfigDict,
    *,
    base_picture: BasePicture | None,
    program_ast_batch_loader: ProgramAstBatchLoader | None,
    program_cache: dict[str, _LoadedProgram],
) -> None:
    """Load all referenced programs in one pass when a batch loader is available.

    A per-program load parses the shared dependency closure again for every
    referenced program, which dominated ICF analysis time. The batch loader
    parses that closure once and returns one graph for every program.
    """
    if program_ast_batch_loader is None:
        return
    pending = [
        name
        for name in program_names
        if name.casefold() not in program_cache
        and (base_picture is None or program_identity(base_picture).casefold() != name.casefold())
    ]
    if not pending:
        return
    try:
        program_pictures, graph = program_ast_batch_loader(config, pending)
    except (OSError, RuntimeError, ValueError, ProjectLoadError):
        # A failed batch falls back to the per-program loader, which reports
        # the failure against the program it concerns.
        return
    moduletype_index = _moduletype_index_for(graph)
    for program_name, program_bp in program_pictures.items():
        program_cache[program_name.casefold()] = _LoadedProgram(
            base_picture=merge_project_basepicture(program_bp, graph),
            moduletype_index=moduletype_index,
        )


def analyze_icf_configuration(
    base_picture: BasePicture | None,
    *,
    config: ConfigDict | None = None,
    debug: bool = False,
    program_ast_loader: ProgramAstLoader | None = None,
    program_ast_batch_loader: ProgramAstBatchLoader | None = None,
) -> SimpleReport:
    """Validate every program referenced by the configured ``.icf`` files.

    ``base_picture`` is optional; when it matches one of the referenced
    programs the already-loaded AST is reused instead of re-loading it.
    ``program_ast_loader`` loads a single referenced program.
    ``program_ast_batch_loader`` loads them all in one parser pass, which is
    what keeps a run with many referenced programs from parsing their shared
    dependency closure once per program; the analyzer layer never imports the
    project package. The analyzer is delivered as a once-per-session whole-run
    check.
    """
    if config is None:
        return SimpleReport(name="ICF configuration", issues=[])

    _, icf_files = configured_icf_files(config)
    if not icf_files:
        return SimpleReport(name="ICF configuration", issues=[])

    if program_ast_loader is None and program_ast_batch_loader is None:
        raise RuntimeError("ICF analysis needs a program loader to load the programs an .icf file references.")

    file_entries = [(icf_file, parse_icf_file(icf_file)) for icf_file in icf_files]
    program_cache: dict[str, _LoadedProgram] = {}
    _preload_referenced_programs(
        _referenced_program_names(file_entries),
        config,
        base_picture=base_picture,
        program_ast_batch_loader=program_ast_batch_loader,
        program_cache=program_cache,
    )

    issues: list[Issue] = []
    for icf_file, entries in file_entries:
        if not entries:
            continue
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
    return SimpleReport(name="ICF configuration", issues=issues)


__all__ = ["analyze_icf_configuration"]
