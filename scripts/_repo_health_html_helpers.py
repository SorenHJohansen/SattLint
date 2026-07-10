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


def render_allow_list_rows(items: list[dict[str, Any]], *, columns: tuple[str, ...], empty_message: str) -> str:
    if not items:
        return f'<tr><td colspan="{len(columns)}">{escape(empty_message)}</td></tr>'
    rendered: list[str] = []
    for item in items:
        rendered.append(
            "<tr>" + "".join(f"<td>{escape(str(item.get(column, 'n/a')))}</td>" for column in columns) + "</tr>"
        )
    return "".join(rendered)


def render_ratcheted_status_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="8">No ratcheted files configured.</td></tr>'
    rendered: list[str] = []
    for item in items:
        current_baseline = item.get("current_baseline")
        target = item.get("target")
        if isinstance(current_baseline, int) and isinstance(target, int):
            gap_sort = (
                max(target - current_baseline, 0)
                if item.get("kind") == "coverage"
                else max(current_baseline - target, 0)
            )
        else:
            gap_sort = 0 if item.get("status") == "tracked" else 1
        filter_text = " ".join(
            str(item.get(key, ""))
            for key in (
                "path",
                "kind",
                "status",
                "current_display",
                "target_display",
                "gap_display",
                "touch_rule",
                "reason",
            )
        ).casefold()
        rendered.append(
            '<tr class="ratchet-row"'
            f' data-path="{escape(str(item.get("path", "n/a")))}"'
            f' data-kind="{escape(str(item.get("kind", "n/a")))}"'
            f' data-status="{escape(str(item.get("status", "n/a")))}"'
            f' data-current-sort="{escape(str(current_baseline if isinstance(current_baseline, int) else -1))}"'
            f' data-target-sort="{escape(str(target if isinstance(target, int) else -1))}"'
            f' data-gap-sort="{escape(str(gap_sort))}"'
            f' data-touch-rule="{escape(str(item.get("touch_rule", "n/a")))}"'
            f' data-filter-text="{escape(filter_text)}"'
            ">"
            f"<td>{escape(str(item.get('path', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('kind', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('status', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('current_display', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('target_display', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('gap_display', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('touch_rule', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('reason', '')))}</td>"
            "</tr>"
        )
    return "".join(rendered)


def render_ratcheted_table_controls() -> str:
    return """
        <div class="table-toolbar" aria-label="Ratcheted file status table controls">
            <label class="table-control search-control" for="ratchet-filter-query">
                <span>Ratcheted file status filter</span>
                <input id="ratchet-filter-query" type="search" placeholder="Filter ratcheted file status by path, reason, or touch rule" />
            </label>
            <label class="table-control" for="ratchet-filter-kind">
                <span>Kind</span>
                <select id="ratchet-filter-kind">
                    <option value="">All</option>
                    <option value="coverage">Coverage</option>
                    <option value="structural">Structural</option>
                    <option value="typing">Typing</option>
                </select>
            </label>
            <label class="table-control" for="ratchet-filter-status">
                <span>Status</span>
                <select id="ratchet-filter-status">
                    <option value="">All</option>
                    <option value="allowlisted">Allowlisted</option>
                    <option value="at_target">At target</option>
                    <option value="below_target">Below target</option>
                    <option value="over_target">Over target</option>
                    <option value="tracked">Tracked</option>
                </select>
            </label>
            <label class="table-control" for="ratchet-sort-by">
                <span>Sort by</span>
                <select id="ratchet-sort-by">
                    <option value="path">Path</option>
                    <option value="kind">Kind</option>
                    <option value="status">Status</option>
                    <option value="current">Current</option>
                    <option value="target">Target</option>
                    <option value="gap">Gap</option>
                </select>
            </label>
            <label class="table-control" for="ratchet-sort-direction">
                <span>Direction</span>
                <select id="ratchet-sort-direction">
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                </select>
            </label>
            <button id="ratchet-reset-filters" class="table-reset" type="button">Reset</button>
            <div id="ratchet-table-summary" class="table-summary" aria-live="polite"></div>
        </div>
    """


def render_ratcheted_table_script() -> str:
    return """
    <script>
        (() => {
            const tbody = document.querySelector('#ratcheted-status-table tbody');
            if (!tbody) {
                return;
            }
            const rows = Array.from(tbody.querySelectorAll('.ratchet-row'));
            if (!rows.length) {
                return;
            }
            const searchInput = document.getElementById('ratchet-filter-query');
            const kindSelect = document.getElementById('ratchet-filter-kind');
            const statusSelect = document.getElementById('ratchet-filter-status');
            const sortBySelect = document.getElementById('ratchet-sort-by');
            const directionSelect = document.getElementById('ratchet-sort-direction');
            const resetButton = document.getElementById('ratchet-reset-filters');
            const summary = document.getElementById('ratchet-table-summary');
            const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

            const numericFields = new Set(['current', 'target', 'gap']);
            const textValue = (row, field) => row.dataset[field] || '';
            const numericValue = (row, field) => {
                const raw = row.dataset[`${field}Sort`];
                const parsed = Number(raw);
                return Number.isFinite(parsed) ? parsed : -1;
            };

            const applyTableState = () => {
                const query = (searchInput?.value || '').trim().toLowerCase();
                const kind = kindSelect?.value || '';
                const status = statusSelect?.value || '';
                const sortBy = sortBySelect?.value || 'path';
                const direction = directionSelect?.value || 'asc';
                const visibleRows = rows.filter((row) => {
                    const matchesQuery = !query || textValue(row, 'filterText').includes(query);
                    const matchesKind = !kind || textValue(row, 'kind') === kind;
                    const matchesStatus = !status || textValue(row, 'status') === status;
                    const visible = matchesQuery && matchesKind && matchesStatus;
                    row.hidden = !visible;
                    return visible;
                });

                visibleRows.sort((left, right) => {
                    let comparison = 0;
                    if (numericFields.has(sortBy)) {
                        comparison = numericValue(left, sortBy) - numericValue(right, sortBy);
                    } else {
                        comparison = collator.compare(textValue(left, sortBy), textValue(right, sortBy));
                    }
                    if (comparison === 0) {
                        comparison = collator.compare(textValue(left, 'path'), textValue(right, 'path'));
                    }
                    return direction === 'desc' ? -comparison : comparison;
                });

                visibleRows.forEach((row) => tbody.appendChild(row));
                if (summary) {
                    summary.textContent = `${visibleRows.length} of ${rows.length} rows shown`;
                }
            };

            for (const element of [searchInput, kindSelect, statusSelect, sortBySelect, directionSelect]) {
                element?.addEventListener('input', applyTableState);
                element?.addEventListener('change', applyTableState);
            }
            resetButton?.addEventListener('click', () => {
                if (searchInput) {
                    searchInput.value = '';
                }
                if (kindSelect) {
                    kindSelect.value = '';
                }
                if (statusSelect) {
                    statusSelect.value = '';
                }
                if (sortBySelect) {
                    sortBySelect.value = 'path';
                }
                if (directionSelect) {
                    directionSelect.value = 'asc';
                }
                applyTableState();
            });

            applyTableState();
        })();
    </script>
    """


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


def page_links(*, main_page_path: str, ratchet_page_path: str, current_page: str) -> str:
    links = [
        (main_page_path, "Repo health", current_page == "main"),
        (ratchet_page_path, "Ratchet details", current_page == "ratchets"),
    ]
    rendered: list[str] = []
    for href, label, is_active in links:
        class_name = "page-link active" if is_active else "page-link"
        rendered.append(f'<a class="{class_name}" href="{escape(href)}">{escape(label)}</a>')
    return '<nav class="page-links">' + "".join(rendered) + "</nav>"
