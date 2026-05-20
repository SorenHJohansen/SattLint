from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from sattline_parser.grammar import constants as grammar_const
from sattline_parser.models.ast_model import Simple_DataType, Variable

if TYPE_CHECKING:
    from .variables_report import VariableIssue


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
    for issue in issues:
        location = format_location(issue.module_path)
        datatype_name = issue.datatype_name or "?"
        field_name = issue.field_path or "?"
        lines.append(f"      * {location} :: {datatype_name}.{field_name}")


def append_string_mapping_mismatch(lines: list[str], title: str, issues: list[VariableIssue]) -> None:
    append_grouped_issue_blocks(
        lines,
        title,
        issues,
        lambda grouped_lines, grouped_issues, _preserve_typedef_path: render_table_issue_rows(
            grouped_lines,
            grouped_issues,
            include_target_type=True,
        ),
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
