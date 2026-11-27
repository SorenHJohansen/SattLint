from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sattlint.parser_api import ScalarDatatype, Variable
from sattlint.parser_api import constants as grammar_const

from ..models._variable_issues import (
    DatatypeDuplicationIssue,
    FieldPathVariableIssue,
    ImplicitLatchIssue,
    MagicNumberIssue,
    MinMaxMappingMismatchIssue,
    NestedRecordCandidateIssue,
    ReadBeforeWriteIssue,
    RecordComponentOrderIssue,
    ResetContaminationIssue,
    StringMappingMismatchIssue,
    UnknownParameterTargetIssue,
    UnusedDatatypeFieldIssue,
    UnusedDatatypeIssue,
    VariableIssueBase,
    VariableTargetIssue,
)

if TYPE_CHECKING:
    from .variables_report import VariableIssue


@dataclass(frozen=True)
class _StringMismatchRow:
    location_path: tuple[str, ...]
    source_name: str
    source_role: str
    source_type: str
    validation_source_name: str
    validation_source_type: str
    validation_source_location_path: tuple[str, ...]
    target_name: str
    target_type: str


def section_header(title: str, count: int) -> str:
    return f"  - {title} ({count}):"


def format_location(module_path: list[str]) -> str:
    return ".".join(module_path) if module_path else "?"


def _display_path(module_path: list[str], preserve_typedef_path: bool) -> list[str]:
    return module_path if preserve_typedef_path else singlemodule_display_path(module_path)


def _column_width(label: str, values: list[str]) -> int:
    """Width of a table column, never narrower than its header label."""
    return max(len(label), *(len(value) for value in values))


def split_moduletype_and_singlemodule_issues[T: VariableIssueBase](
    issues: list[T],
) -> tuple[list[T], list[T]]:
    moduletype_issues = [
        issue for issue in issues if issue.module_path and issue.module_path[-1].startswith("TypeDef:")
    ]
    singlemodule_issues = [
        issue for issue in issues if not (issue.module_path and issue.module_path[-1].startswith("TypeDef:"))
    ]
    return moduletype_issues, singlemodule_issues


def _uses_typedef_path(module_path: list[str] | tuple[str, ...]) -> bool:
    return any(segment.startswith("TypeDef:") for segment in module_path)


def _build_string_mapping_rows(issues: list[StringMappingMismatchIssue]) -> list[_StringMismatchRow]:
    rows: list[_StringMismatchRow] = []
    for issue in issues:
        source_name = issue.source_display_name or (
            issue.source_variable.name if issue.source_variable is not None else "?"
        )
        source_type = issue.source_variable.datatype_text if issue.source_variable is not None else "?"
        source_role = issue.source_role or "?"
        rows.append(
            _StringMismatchRow(
                location_path=tuple(issue.module_path),
                source_name=source_name,
                source_role=source_role,
                source_type=source_type,
                validation_source_name=(
                    issue.validation_source_variable.name
                    if issue.validation_source_variable is not None
                    else source_name
                ),
                validation_source_type=(
                    issue.validation_source_variable.datatype_text
                    if issue.validation_source_variable is not None
                    else source_type
                ),
                validation_source_location_path=tuple(
                    issue.validation_source_module_path or issue.source_decl_module_path or issue.module_path
                ),
                target_name=issue.target_display_name or issue.variable.name,
                target_type=issue.variable.datatype_text,
            )
        )
    rows.sort(
        key=lambda row: (
            ".".join(row.location_path).casefold(),
            row.source_name.casefold(),
            row.source_role.casefold(),
            row.source_type.casefold(),
            row.target_name.casefold(),
            row.target_type.casefold(),
        )
    )
    return rows


def count_string_mapping_mismatch_rows(issues: list[VariableIssue]) -> int:
    return sum(1 for issue in issues if isinstance(issue, StringMappingMismatchIssue))


def _is_declaration_destination_mismatch(row: _StringMismatchRow) -> bool:
    return row.target_type.casefold() != row.source_type.casefold()


def _render_string_mapping_group(
    lines: list[str],
    title: str,
    rows: list[_StringMismatchRow],
    preserve_typedef_path: bool,
    *,
    show_direct_source: bool = False,
) -> None:
    lines.append(f"        {title} ({len(rows)}):")
    if show_direct_source and rows:
        lines.append("        Direct source/type show the value seen at the mismatching hop.")
    _render_string_mapping_rows(lines, rows, preserve_typedef_path, show_direct_source=show_direct_source)


def _render_string_mapping_rows(
    lines: list[str],
    rows: list[_StringMismatchRow],
    preserve_typedef_path: bool,
    *,
    show_direct_source: bool = False,
) -> None:
    if not rows:
        lines.append("        none")
        return

    rendered_locations = [
        ".".join(
            row.location_path if preserve_typedef_path else tuple(singlemodule_display_path(list(row.location_path)))
        )
        for row in rows
    ]
    location_width = max(len(location) for location in rendered_locations)
    source_name_width = max(len(row.source_name) for row in rows)
    source_role_width = max(len(row.source_role) for row in rows)
    source_type_width = max(len(row.source_type) for row in rows)
    target_name_width = max(len(row.target_name) for row in rows)
    target_type_width = max(len(row.target_type) for row in rows)

    if show_direct_source:
        rendered_validation_sources = [
            (
                ".".join(
                    row.validation_source_location_path
                    if preserve_typedef_path
                    else tuple(singlemodule_display_path(list(row.validation_source_location_path)))
                )
                + f" :: {row.validation_source_name}"
            )
            for row in rows
        ]
        validation_source_width = max(len(value) for value in rendered_validation_sources)
        validation_type_width = max(len(row.validation_source_type) for row in rows)

        header = (
            f"        {'Location':<{location_width}}  "
            f"{'Source Var':<{source_name_width}}  {'Role':<{source_role_width}}  "
            f"{'Declared Type':<{source_type_width}}  {'Direct Source':<{validation_source_width}}  "
            f"{'Direct Type':<{validation_type_width}}  {'Target Var':<{target_name_width}}  =>  {'Destination Type':<{target_type_width}}"
        )
        lines.append(header)
        lines.append("        " + "-" * len(header.strip()))

        for row, location, validation_source in zip(
            rows, rendered_locations, rendered_validation_sources, strict=False
        ):
            lines.append(
                f"        {location:<{location_width}}  "
                f"{row.source_name:<{source_name_width}}  {row.source_role:<{source_role_width}}  "
                f"{row.source_type:<{source_type_width}}  {validation_source:<{validation_source_width}}  "
                f"{row.validation_source_type:<{validation_type_width}}  {row.target_name:<{target_name_width}}  =>  {row.target_type:<{target_type_width}}"
            )
        return

    header = (
        f"        {'Location':<{location_width}}  "
        f"{'Source Var':<{source_name_width}}  {'Role':<{source_role_width}}  "
        f"{'Declared Type':<{source_type_width}}  {'Target Var':<{target_name_width}}  =>  {'Destination Type':<{target_type_width}}"
    )
    lines.append(header)
    lines.append("        " + "-" * len(header.strip()))

    for row, location in zip(rows, rendered_locations, strict=False):
        lines.append(
            f"        {location:<{location_width}}  "
            f"{row.source_name:<{source_name_width}}  {row.source_role:<{source_role_width}}  "
            f"{row.source_type:<{source_type_width}}  {row.target_name:<{target_name_width}}  =>  {row.target_type:<{target_type_width}}"
        )


def singlemodule_display_path(module_path: list[str]) -> list[str]:
    return [segment.removeprefix("TypeDef:") if segment.startswith("TypeDef:") else segment for segment in module_path]


def append_grouped_issue_blocks[T: VariableIssueBase](
    lines: list[str],
    title: str,
    issues: list[T],
    renderer: Callable[[list[str], list[T], bool], None],
) -> None:
    if not issues:
        append_empty_section(lines, title)
        return

    moduletype_issues, singlemodule_issues = split_moduletype_and_singlemodule_issues(issues)

    lines.append(section_header(title, len(issues)))
    lines.append("      Moduletype:")
    renderer(lines, moduletype_issues, True)
    lines.append("      SingleModule:")
    renderer(lines, singlemodule_issues, False)


def render_formatted_issue_rows(lines: list[str], issues: list[VariableIssue], preserve_typedef_path: bool) -> None:
    if not issues:
        lines.append("        none")
        return

    for issue in issues:
        display_path = issue.module_path if preserve_typedef_path else singlemodule_display_path(issue.module_path)
        lines.append(f"        * {format_issue(issue, display_path)}")


def render_table_issue_rows(
    lines: list[str],
    issues: list[MinMaxMappingMismatchIssue],
    preserve_typedef_path: bool,
    *,
    include_target_type: bool,
) -> None:
    if not issues:
        lines.append("        none")
        return

    locations = [format_location(_display_path(issue.module_path, preserve_typedef_path)) for issue in issues]
    source_names = [issue.source_variable.name if issue.source_variable else "?" for issue in issues]
    target_names = [issue.variable.name if issue.variable else "?" for issue in issues]
    location_width = _column_width("Location", locations)
    source_name_width = _column_width("Source Var", source_names)
    target_name_width = _column_width("Target Var", target_names)

    if include_target_type:
        source_types = [issue.source_variable.datatype_text if issue.source_variable else "?" for issue in issues]
        target_types = [issue.variable.datatype_text if issue.variable else "?" for issue in issues]
        source_type_width = _column_width("Type", source_types)
        target_type_width = _column_width("Type", target_types)
        header = (
            f"        {'Location':<{location_width}}  "
            f"{'Source Var':<{source_name_width}}  {'Type':<{source_type_width}}  =>  "
            f"{'Target Var':<{target_name_width}}  {'Type':<{target_type_width}}"
        )
        lines.append(header)
        lines.append("        " + "-" * len(header.strip()))
        for location, source_name, source_type, target_name, target_type in zip(
            locations,
            source_names,
            source_types,
            target_names,
            target_types,
            strict=True,
        ):
            lines.append(
                f"        {location:<{location_width}}  "
                f"{source_name:<{source_name_width}}  {source_type:<{source_type_width}}  =>  "
                f"{target_name:<{target_name_width}}  {target_type:<{target_type_width}}"
            )
        return

    header = (
        f"        {'Location':<{location_width}}  "
        f"{'Source Var':<{source_name_width}}  =>  {'Target Var':<{target_name_width}}"
    )
    lines.append(header)
    lines.append("        " + "-" * len(header.strip()))
    for location, source_name, target_name in zip(locations, source_names, target_names, strict=True):
        lines.append(
            f"        {location:<{location_width}}  {source_name:<{source_name_width}}  =>  {target_name:<{target_name_width}}"
        )


def variable_datatype_text(variable: Variable) -> str:
    if isinstance(variable.datatype, ScalarDatatype):
        return variable.datatype.value
    return str(variable.datatype)


def variable_init_value_text(variable: Variable) -> str | None:
    if variable.init_value is None:
        return None

    init_value = variable.init_value
    if isinstance(init_value, dict):
        typed_init_value = cast(dict[str, object], init_value)
        literal = typed_init_value.get(grammar_const.GRAMMAR_VALUE_TIME_VALUE)
        if isinstance(literal, str):
            return repr(literal)
        return repr(typed_init_value)

    if isinstance(init_value, str):
        return init_value if variable.init_is_duration else repr(init_value)

    return str(init_value)


def _format_variable_issue(issue: VariableTargetIssue, location: str) -> str:
    variable = issue.variable
    variable_name = variable.name
    if isinstance(issue, FieldPathVariableIssue) and issue.field_path:
        variable_name = f"{variable_name}.{issue.field_path}"
    variable_text = f"{variable_name} ({variable_datatype_text(variable)})"

    if issue.role in {"localvariable", "moduleparameter"}:
        init_text = variable_init_value_text(variable)
        if init_text is not None:
            variable_text = f"{variable_name} ({variable_datatype_text(variable)}, init={init_text})"

    if issue.role in {"localvariable", "moduleparameter"}:
        detail = f"{issue.role} {variable_text}"
    elif issue.role:
        detail = f"{variable_text} | {issue.role}"
    else:
        detail = variable_text

    extra_parts: list[str] = []
    if isinstance(issue, ResetContaminationIssue | ImplicitLatchIssue) and issue.sequence_name:
        extra_parts.append(f"sequence={issue.sequence_name}")
    if isinstance(issue, ResetContaminationIssue) and issue.reset_variable:
        extra_parts.append(f"reset={issue.reset_variable}")
    if extra_parts:
        detail = f"{detail} | {' | '.join(extra_parts)}"

    return f"{location} :: {detail}"


def format_issue(issue: VariableIssue, module_path: list[str] | None = None) -> str:
    location = format_location(issue.module_path if module_path is None else module_path)

    match issue:
        case UnusedDatatypeFieldIssue():
            return f"{location} :: {issue.datatype_name}.{issue.field_path}"
        case UnusedDatatypeIssue():
            return f"{location} :: {issue.datatype_name}.?"
        case MagicNumberIssue():
            site = f" [{issue.site}]" if issue.site else ""
            if issue.literal_span is not None:
                span_text = f"line {issue.literal_span.line}, col {issue.literal_span.column}"
            else:
                span_text = "line ?, col ?"
            return f"{location}{site} :: {issue.literal_value} ({span_text})"
        case ReadBeforeWriteIssue() | UnknownParameterTargetIssue():
            return f"{location} :: {issue.role or 'issue'}"
        case VariableTargetIssue():
            return _format_variable_issue(issue, location)
        case _:
            return f"{location} :: {issue.kind.value}"


def append_empty_section(lines: list[str], title: str) -> None:
    lines.append(section_header(title, 0))
    lines.append("      none")


def append_variable_issue_list(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(lines, title, issues, render_formatted_issue_rows)


def append_unused_datatypes(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    datatype_issues = [issue for issue in issues if isinstance(issue, UnusedDatatypeIssue)]
    if not datatype_issues:
        append_empty_section(lines, title)
        return

    lines.append(section_header(title, len(datatype_issues)))
    for issue in datatype_issues:
        location = format_location(issue.module_path)
        lines.append(f"      * {location} :: {issue.datatype_name}")


def append_unused_datatype_fields(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    field_issues = [issue for issue in issues if isinstance(issue, UnusedDatatypeFieldIssue)]
    if not field_issues:
        append_empty_section(lines, title)
        return

    lines.append(section_header(title, len(field_issues)))
    lines.append(
        "      Warning: fields that are only consumed outside the analyzed target may still appear unused here."
    )
    for issue in field_issues:
        location = format_location(issue.module_path)
        lines.append(f"      * {location} :: {issue.datatype_name}.{issue.field_path}")


def append_string_mapping_mismatch(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    rows = _build_string_mapping_rows([issue for issue in issues if isinstance(issue, StringMappingMismatchIssue)])
    if not rows:
        append_empty_section(lines, title)
        return

    moduletype_rows = [row for row in rows if _uses_typedef_path(row.location_path)]
    singlemodule_rows = [row for row in rows if not _uses_typedef_path(row.location_path)]

    lines.append(section_header(title, len(rows)))
    lines.append("      Moduletype:")
    _render_string_mapping_group(
        lines,
        "Declaration/final destination mismatch",
        [row for row in moduletype_rows if _is_declaration_destination_mismatch(row)],
        True,
    )
    _render_string_mapping_group(
        lines,
        "Intermediate path mismatch only",
        [row for row in moduletype_rows if not _is_declaration_destination_mismatch(row)],
        True,
        show_direct_source=True,
    )
    lines.append("      SingleModule:")
    _render_string_mapping_group(
        lines,
        "Declaration/final destination mismatch",
        [row for row in singlemodule_rows if _is_declaration_destination_mismatch(row)],
        False,
    )
    _render_string_mapping_group(
        lines,
        "Intermediate path mismatch only",
        [row for row in singlemodule_rows if not _is_declaration_destination_mismatch(row)],
        False,
        show_direct_source=True,
    )


def render_datatype_duplication_rows(
    lines: list[str],
    issues: Sequence[DatatypeDuplicationIssue | NestedRecordCandidateIssue],
    preserve_typedef_path: bool,
) -> None:
    if not issues:
        lines.append("        none")
        return

    for issue in sorted(issues, key=_datatype_duplication_sort_key):
        location_path = issue.module_path if preserve_typedef_path else singlemodule_display_path(issue.module_path)
        location = ".".join(location_path)
        if isinstance(issue, NestedRecordCandidateIssue):
            fields = ", ".join(repr(field) for field in issue.field_names)
            records = ", ".join(issue.record_names)
            lines.append(f"        Fields {fields} repeat in {records} ({location}):")
            lines.append("          - Extract the group into a nested RECORD and declare it as one field.")
            continue

        datatype_name = issue.variable.datatype_text
        count = issue.duplicate_count
        lines.append(f"        Datatype '{datatype_name}' declared {count} times in {location}:")
        lines.append(f"          - {issue.variable.name} ({issue.role})")

        if issue.duplicate_locations:
            for duplicate in issue.duplicate_locations:
                display_path = (
                    duplicate.module_path if preserve_typedef_path else singlemodule_display_path(duplicate.module_path)
                )
                duplicate_location = ".".join(display_path)
                if duplicate_location == location:
                    lines.append(f"            + {duplicate.variable_id} ({duplicate.role})")
                else:
                    lines.append(f"            + {duplicate_location}: {duplicate.variable_id} ({duplicate.role})")


def _datatype_duplication_sort_key(
    issue: DatatypeDuplicationIssue | NestedRecordCandidateIssue,
) -> tuple[str, str, str]:
    if isinstance(issue, NestedRecordCandidateIssue):
        return (
            (issue.field_names[0].casefold() if issue.field_names else ""),
            ".".join(issue.module_path).casefold(),
            ",".join(issue.record_names).casefold(),
        )
    return (
        issue.variable.datatype_text.casefold(),
        ".".join(issue.module_path).casefold(),
        issue.variable.name.casefold(),
    )


def append_datatype_duplication(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    duplication_issues = [
        issue for issue in issues if isinstance(issue, DatatypeDuplicationIssue | NestedRecordCandidateIssue)
    ]
    append_grouped_issue_blocks(lines, title, duplication_issues, render_datatype_duplication_rows)


def append_min_max_mapping_mismatch(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    mapping_issues = [issue for issue in issues if isinstance(issue, MinMaxMappingMismatchIssue)]
    append_grouped_issue_blocks(
        lines,
        title,
        mapping_issues,
        lambda grouped_lines, grouped_issues, preserve_typedef_path: render_table_issue_rows(
            grouped_lines,
            grouped_issues,
            preserve_typedef_path,
            include_target_type=False,
        ),
    )


def append_magic_numbers(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(lines, title, issues, render_formatted_issue_rows)


def append_record_component_order_dependence(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    unique_names: dict[str, str] = {}
    for issue in issues:
        if not isinstance(issue, RecordComponentOrderIssue):
            continue
        if issue.datatype_name.casefold() == "anytype":
            continue
        unique_names.setdefault(issue.datatype_name.casefold(), issue.datatype_name)
    datatype_names = sorted(unique_names.values(), key=str.casefold)

    if not datatype_names:
        append_empty_section(lines, title)
        return

    lines.append(section_header(title, len(datatype_names)))
    for datatype_name in datatype_names:
        lines.append(f"      * {datatype_name}")
