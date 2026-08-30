from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.parse import quote


def format_percent(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "n/a"


def format_number(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "n/a"


def format_signed(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if number.is_integer():
        whole = int(number)
        return f"+{whole}" if whole > 0 else str(whole)
    return f"{number:+.4f}"


def metric_card(*, label: str, value: str, detail: str) -> str:
    return (
        '<article class="metric-card">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        f'<div class="metric-detail">{escape(detail)}</div>'
        "</article>"
    )


def definition_rows(entries: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="definition-row"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in entries
    )


def status_tone(status: str | None) -> str:
    if status == "pass":
        return "ok"
    if status in {"pass_with_findings", "pass_with_notes"}:
        return "warn"
    if status == "fail":
        return "error"
    return "neutral"


def status_pill(label: str, status: str | None, *, detail: str | None = None) -> str:
    detail_markup = "" if not detail else f'<div class="pill-detail">{escape(detail)}</div>'
    return (
        f'<div class="pill {status_tone(status)}">'
        '<div class="pill-copy">'
        f'<span class="pill-label">{escape(label)}</span>'
        f"{detail_markup}"
        "</div>"
        f'<span class="pill-value">{escape(status or "unknown")}</span>'
        "</div>"
    )


def render_named_list(
    items: list[dict[str, Any]],
    *,
    empty_message: str,
    title_key: str,
    primary_value_key: str,
    secondary_value_key: str,
    primary_suffix: str = "",
) -> str:
    if not items:
        return f'<div class="empty-inline">{escape(empty_message)}</div>'
    rendered: list[str] = []
    for item in items:
        title = str(item.get(title_key, "Unknown item"))
        primary_raw = item.get(primary_value_key)
        if isinstance(primary_raw, float):
            primary = f"{primary_raw:.3f}{primary_suffix}"
        elif isinstance(primary_raw, int):
            primary = f"{primary_raw:,}{primary_suffix}"
        else:
            primary = str(primary_raw) if primary_raw is not None else "n/a"
        secondary_raw = item.get(secondary_value_key)
        secondary = "" if secondary_raw in {None, ""} else f" | {secondary_raw}"
        rendered.append(
            '<article class="list-card compact">'
            f'<div class="list-card-title">{escape(title)}</div>'
            f'<div class="list-card-meta">{escape(primary)}{escape(secondary)}</div>'
            "</article>"
        )
    return "".join(rendered)


def render_findings(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return '<div class="empty-inline">No top findings in the current snapshot.</div>'
    rendered: list[str] = []
    for finding in findings:
        message = str(finding.get("message", "Unnamed finding"))
        severity = str(finding.get("severity", "unknown"))
        category = str(finding.get("category", "uncategorized"))
        path_text = str(finding.get("path", "workspace"))
        rendered.append(
            '<article class="list-card">'
            f'<div class="list-card-title">{escape(message)}</div>'
            f'<div class="list-card-meta">{escape(severity)} | {escape(category)} | {escape(path_text)}</div>'
            "</article>"
        )
    return "".join(rendered)


def render_warnings(warnings: list[dict[str, Any]]) -> str:
    if not warnings:
        return '<div class="empty-inline">No local hygiene warnings in the current snapshot.</div>'
    rendered: list[str] = []
    for warning in warnings:
        message = str(warning.get("message", "Warning"))
        paths = warning.get("paths", [])
        path_text = ", ".join(str(path) for path in paths[:5]) if isinstance(paths, list) else "No paths attached"
        rendered.append(
            '<article class="list-card warning-card">'
            f'<div class="list-card-title">{escape(message)}</div>'
            f'<div class="list-card-meta">{escape(path_text or "No paths attached")}</div>'
            "</article>"
        )
    return "".join(rendered)


def vscode_task_command_uri(task_label: str) -> str:
    return f"command:workbench.action.tasks.runTask?{quote(json.dumps([task_label]))}"


def dashboard_actions(*, refresh_dashboard_task: str) -> str:
    refresh_href = vscode_task_command_uri(refresh_dashboard_task)
    return (
        '<div class="dashboard-actions">'
        f'<a class="dashboard-action primary" href="{escape(refresh_href)}">Refresh dashboard</a>'
        '<span class="dashboard-action-note">Runs the existing VS Code task to regenerate the dashboard artifacts.</span>'
        "</div>"
    )
