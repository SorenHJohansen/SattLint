from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sattline_parser.grammar import constants as grammar_const
from sattline_parser.models.ast_model import Simple_DataType, Variable

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


def display_location(module_path: list[str]) -> str:
    if len(module_path) <= 2:
        return format_location(module_path)
    return format_location(
        [segment.removeprefix("TypeDef:") if segment.startswith("TypeDef:") else segment for segment in module_path]
    )


def split_moduletype_and_singlemodule_issues(
    issues: list[VariableIssue],
) -> tuple[list[VariableIssue], list[VariableIssue]]:
    moduletype_issues = [
        issue for issue in issues if issue.module_path and issue.module_path[-1].startswith("TypeDef:")
    ]
    singlemodule_issues = [
        issue for issue in issues if not (issue.module_path and issue.module_path[-1].startswith("TypeDef:"))
    ]
    return moduletype_issues, singlemodule_issues


def _uses_typedef_path(module_path: list[str] | tuple[str, ...]) -> bool:
    return any(segment.startswith("TypeDef:") for segment in module_path)


def _build_string_mapping_rows(issues: list[VariableIssue]) -> list[_StringMismatchRow]:
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
                target_name=(issue.target_display_name or issue.variable.name) if issue.variable is not None else "?",
                target_type=issue.variable.datatype_text if issue.variable is not None else "?",
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
    return len(issues)


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


def append_grouped_issue_blocks(
    lines: list[str],
    title: str,
    issues: list[VariableIssue],
    renderer: Callable[[list[str], list[VariableIssue], bool], None],
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
    issues: list[VariableIssue],
    *,
    include_target_type: bool,
) -> None:
    if not issues:
        lines.append("        none")
        return

    location_width = max(len(display_location(issue.module_path)) for issue in issues)
    source_name_width = max(len(issue.source_variable.name) if issue.source_variable else 0 for issue in issues)

    if include_target_type:
        source_type_width = max(
            len(issue.source_variable.datatype_text) if issue.source_variable else 0 for issue in issues
        )
        target_name_width = max(len(issue.variable.name) if issue.variable else 0 for issue in issues)
        target_type_width = max(len(issue.variable.datatype_text) if issue.variable else 0 for issue in issues)
        header = (
            f"        {'Location':<{location_width}}  "
            f"{'Source Var':<{source_name_width}}  {'Type':<{source_type_width}}  =>  "
            f"{'Target Var':<{target_name_width}}  {'Type':<{target_type_width}}"
        )
        lines.append(header)
        lines.append("        " + "-" * len(header.strip()))
        for issue in issues:
            location = display_location(issue.module_path)
            source_name = issue.source_variable.name if issue.source_variable else "?"
            source_type = issue.source_variable.datatype_text if issue.source_variable else "?"
            target_name = issue.variable.name if issue.variable else "?"
            target_type = issue.variable.datatype_text if issue.variable else "?"
            lines.append(
                f"        {location:<{location_width}}  "
                f"{source_name:<{source_name_width}}  {source_type:<{source_type_width}}  =>  "
                f"{target_name:<{target_name_width}}  {target_type:<{target_type_width}}"
            )
        return

    target_name_width = max(len(issue.variable.name) if issue.variable else 0 for issue in issues)
    header = (
        f"        {'Location':<{location_width}}  "
        f"{'Source Var':<{source_name_width}}  =>  {'Target Var':<{target_name_width}}"
    )
    lines.append(header)
    lines.append("        " + "-" * len(header.strip()))
    for issue in issues:
        location = display_location(issue.module_path)
        source_name = issue.source_variable.name if issue.source_variable else "?"
        target_name = issue.variable.name if issue.variable else "?"
        lines.append(
            f"        {location:<{location_width}}  {source_name:<{source_name_width}}  =>  {target_name:<{target_name_width}}"
        )


def variable_datatype_text(variable: Variable) -> str:
    if isinstance(variable.datatype, Simple_DataType):
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


def format_issue(issue: VariableIssue, module_path: list[str] | None = None) -> str:
    location = format_location(issue.module_path if module_path is None else module_path)

    if issue.variable is None and issue.datatype_name is not None:
        field_name = issue.field_path or "?"
        return f"{location} :: {issue.datatype_name}.{field_name}"

    if issue.variable is None and issue.literal_value is not None:
        site = f" [{issue.site}]" if issue.site else ""
        if issue.literal_span is not None:
            span_text = f"line {issue.literal_span.line}, col {issue.literal_span.column}"
        else:
            span_text = "line ?, col ?"
        return f"{location}{site} :: {issue.literal_value} ({span_text})"

    if issue.variable is None:
        return f"{location} :: {issue.role or 'issue'}"

    variable_name = issue.variable.name
    if issue.field_path:
        variable_name = f"{variable_name}.{issue.field_path}"
    variable_text = f"{variable_name} ({variable_datatype_text(issue.variable)})"

    if issue.role in {"localvariable", "moduleparameter"}:
        init_text = variable_init_value_text(issue.variable)
        if init_text is not None:
            variable_text = f"{variable_name} ({variable_datatype_text(issue.variable)}, init={init_text})"

    if issue.role in {"localvariable", "moduleparameter"}:
        detail = f"{issue.role} {variable_text}"
    elif issue.role:
        detail = f"{variable_text} | {issue.role}"
    else:
        detail = variable_text

    extra_parts: list[str] = []
    if issue.sequence_name:
        extra_parts.append(f"sequence={issue.sequence_name}")
    if issue.reset_variable:
        extra_parts.append(f"reset={issue.reset_variable}")
    if extra_parts:
        detail = f"{detail} | {' | '.join(extra_parts)}"

    return f"{location} :: {detail}"


def append_empty_section(lines: list[str], title: str) -> None:
    lines.append(section_header(title, 0))
    lines.append("      none")


def append_variable_issue_list(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(lines, title, issues, render_formatted_issue_rows)


def append_unused_variable_issue_list(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(lines, title, issues, render_formatted_issue_rows)


def append_unused_datatype_fields(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    if not issues:
        append_empty_section(lines, title)
        return

    lines.append(section_header(title, len(issues)))
    lines.append(
        "      Warning: fields that are only consumed outside the analyzed target may still appear unused here."
    )
    for issue in issues:
        location = format_location(issue.module_path)
        datatype_name = issue.datatype_name or "?"
        field_name = issue.field_path or "?"
        lines.append(f"      * {location} :: {datatype_name}.{field_name}")


def append_string_mapping_mismatch(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    rows = _build_string_mapping_rows(issues)
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
    lines: list[str], issues: list[VariableIssue], preserve_typedef_path: bool
) -> None:
    if not issues:
        lines.append("        none")
        return

    for issue in sorted(
        issues,
        key=lambda item: (
            item.variable.datatype_text if item.variable else "?",
            ".".join(item.module_path),
            item.variable.name if item.variable else "?",
        ),
    ):
        location_path = issue.module_path if preserve_typedef_path else singlemodule_display_path(issue.module_path)
        datatype_name = issue.variable.datatype_text if issue.variable else "?"
        location = ".".join(location_path)
        count = issue.duplicate_count or 0
        lines.append(f"        Datatype '{datatype_name}' declared {count} times in {location}:")
        lines.append(f"          - {issue.variable.name if issue.variable else '?'} ({issue.role})")

        if issue.duplicate_locations:
            for duplicate_path, duplicate_role, duplicate_name in issue.duplicate_locations:
                display_path = duplicate_path if preserve_typedef_path else singlemodule_display_path(duplicate_path)
                duplicate_location = ".".join(display_path)
                if duplicate_location == location:
                    lines.append(f"            + {duplicate_name} ({duplicate_role})")
                else:
                    lines.append(f"            + {duplicate_location}: {duplicate_name} ({duplicate_role})")


def append_datatype_duplication(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(lines, title, issues, render_datatype_duplication_rows)


def append_min_max_mapping_mismatch(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(
        lines,
        title,
        issues,
        lambda grouped_lines, grouped_issues, _preserve_typedef_path: render_table_issue_rows(
            grouped_lines,
            grouped_issues,
            include_target_type=False,
        ),
    )


def append_magic_numbers(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(lines, title, issues, render_formatted_issue_rows)


def append_record_component_order_dependence(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    datatype_names = sorted(
        {
            issue.datatype_name
            for issue in issues
            if issue.datatype_name is not None and issue.datatype_name.casefold() != "anytype"
        },
        key=str.casefold,
    )

    if not datatype_names:
        append_empty_section(lines, title)
        return

    lines.append(section_header(title, len(datatype_names)))
    for datatype_name in datatype_names:
        lines.append(f"      * {datatype_name}")
