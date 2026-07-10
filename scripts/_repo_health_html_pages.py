from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from scripts import _repo_health_html_helpers as html_helpers
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _repo_health_html_helpers as html_helpers

REPO_HEALTH_STYLE = """
    <style>
        :root {
            color-scheme: light dark;
            --bg: #0f1720;
            --panel: #16212e;
            --panel-alt: #1b2937;
            --border: #2a4156;
            --text: #edf4fb;
            --muted: #9fb3c8;
            --accent: #63d2ff;
            --ok: #4ad295;
            --warn: #f1c75b;
            --error: #ff7676;
            --shadow: 0 18px 45px rgba(0, 0, 0, 0.22);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", sans-serif;
            background: radial-gradient(circle at top left, rgba(99, 210, 255, 0.18), transparent 32%), linear-gradient(180deg, #0c141d 0%, var(--bg) 100%);
            color: var(--text);
        }
        .dashboard-shell { width: min(1280px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 40px; }
        .card { background: linear-gradient(180deg, rgba(22, 33, 46, 0.96), rgba(22, 33, 46, 0.9)); border: 1px solid rgba(159, 179, 200, 0.14); border-radius: 20px; box-shadow: var(--shadow); padding: 22px; }
        .page-links { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
        .page-link { display: inline-flex; align-items: center; justify-content: center; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }
        .page-link.active { border-color: rgba(99, 210, 255, 0.5); color: var(--accent); }
        .dashboard-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; margin-bottom: 18px; }
        .dashboard-action { display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }
        .dashboard-action.primary { border-color: rgba(99, 210, 255, 0.42); color: var(--accent); }
        .dashboard-action-note { color: var(--muted); font-size: 13px; }
        .hero { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(260px, 0.9fr); gap: 24px; align-items: start; margin-bottom: 22px; }
        .eyebrow { margin-bottom: 10px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.12em; font-size: 12px; }
        h1, h2 { margin: 0; font-weight: 700; }
        h1 { font-size: clamp(28px, 4vw, 40px); }
        h2 { font-size: 18px; }
        .hero-copy, .metric-detail, .list-card-meta, .empty-inline, .definitions dt { color: var(--muted); }
        .hero-copy { margin: 12px 0 0; line-height: 1.5; }
        .hero-statuses { display: grid; gap: 12px; min-width: 0; }
        .pill { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px 16px; padding: 12px 14px; border-radius: 14px; background: var(--panel-alt); border: 1px solid rgba(159, 179, 200, 0.12); min-width: 0; }
        .pill.ok { border-color: rgba(74, 210, 149, 0.45); }
        .pill.warn { border-color: rgba(241, 199, 91, 0.45); }
        .pill.error { border-color: rgba(255, 118, 118, 0.45); }
        .pill-copy { display: grid; gap: 4px; min-width: 0; flex: 1 1 180px; }
        .pill-label, .pill-value, .pill-detail { min-width: 0; overflow-wrap: anywhere; word-break: break-word; }
        .pill-detail { color: var(--muted); font-size: 12px; line-height: 1.4; }
        .pill-value { font-weight: 700; text-transform: capitalize; text-align: right; }
        .metrics-grid, .split-grid { display: grid; gap: 16px; margin-bottom: 22px; }
        .metrics-grid { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
        .metric-card { background: rgba(27, 41, 55, 0.9); border-radius: 18px; border: 1px solid rgba(159, 179, 200, 0.12); padding: 18px; }
        .metric-label { color: var(--muted); margin-bottom: 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
        .metric-value { font-size: 26px; font-weight: 700; margin-bottom: 8px; }
        .split-grid { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
        .section-header { margin-bottom: 16px; }
        .definitions { margin: 0; display: grid; gap: 10px; }
        .definition-row { display: grid; grid-template-columns: minmax(110px, 0.8fr) minmax(0, 1.2fr); gap: 12px; }
        .definitions dt, .definitions dd { margin: 0; }
        .definitions dd { text-align: right; }
        .stack-list { display: grid; gap: 12px; }
        .list-card { padding: 14px 16px; border-radius: 16px; background: rgba(27, 41, 55, 0.75); border: 1px solid rgba(159, 179, 200, 0.12); }
        .list-card.compact { padding: 12px 14px; }
        .warning-card { border-color: rgba(241, 199, 91, 0.28); }
        .list-card-title { font-weight: 600; line-height: 1.4; }
        .list-card-meta { margin-top: 6px; font-size: 13px; }
        @media (max-width: 900px) {
            .hero { grid-template-columns: 1fr; }
            .definitions dd { text-align: left; }
            .definition-row { grid-template-columns: 1fr; gap: 4px; }
        }
    </style>
"""

RATCHET_STYLE = """
    <style>
        :root {
            color-scheme: light dark;
            --bg: #0f1720;
            --panel: #16212e;
            --panel-alt: #1b2937;
            --border: #2a4156;
            --text: #edf4fb;
            --muted: #9fb3c8;
            --accent: #63d2ff;
            --shadow: 0 18px 45px rgba(0, 0, 0, 0.22);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", sans-serif;
            background: radial-gradient(circle at top left, rgba(99, 210, 255, 0.16), transparent 30%), linear-gradient(180deg, #0c141d 0%, var(--bg) 100%);
            color: var(--text);
        }
        .dashboard-shell { width: min(1380px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 40px; }
        .card { background: linear-gradient(180deg, rgba(22, 33, 46, 0.96), rgba(22, 33, 46, 0.9)); border: 1px solid rgba(159, 179, 200, 0.14); border-radius: 20px; box-shadow: var(--shadow); padding: 22px; margin-bottom: 18px; }
        .page-links { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
        .page-link { display: inline-flex; align-items: center; justify-content: center; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }
        .page-link.active { border-color: rgba(99, 210, 255, 0.5); color: var(--accent); }
        .dashboard-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; margin-bottom: 18px; }
        .dashboard-action { display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }
        .dashboard-action.primary { border-color: rgba(99, 210, 255, 0.42); color: var(--accent); }
        .dashboard-action-note { color: var(--muted); font-size: 13px; }
        .eyebrow { margin-bottom: 10px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.12em; font-size: 12px; }
        h1, h2 { margin: 0; font-weight: 700; }
        h1 { font-size: clamp(28px, 4vw, 40px); }
        h2 { font-size: 18px; margin-bottom: 14px; }
        .hero-copy, .table-note { color: var(--muted); line-height: 1.5; }
        .summary-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-top: 18px; }
        .metric-card { background: rgba(27, 41, 55, 0.9); border-radius: 18px; border: 1px solid rgba(159, 179, 200, 0.12); padding: 18px; }
        .metric-label { color: var(--muted); margin-bottom: 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
        .metric-value { font-size: 26px; font-weight: 700; margin-bottom: 8px; }
        .split-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
        .table-toolbar { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin-bottom: 16px; align-items: end; }
        .table-control { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
        .table-control span { text-transform: uppercase; letter-spacing: 0.08em; font-size: 11px; }
        .search-control { min-width: 0; grid-column: span 2; }
        .table-control input, .table-control select { min-height: 42px; border-radius: 12px; border: 1px solid rgba(159, 179, 200, 0.18); background: rgba(15, 23, 32, 0.92); color: var(--text); padding: 10px 12px; width: 100%; }
        .table-reset { min-height: 42px; border-radius: 12px; border: 1px solid rgba(159, 179, 200, 0.18); background: rgba(27, 41, 55, 0.82); color: var(--text); padding: 10px 14px; cursor: pointer; }
        .table-summary { color: var(--muted); font-size: 13px; align-self: center; }
        .table-wrap { overflow-x: auto; border-radius: 16px; border: 1px solid rgba(159, 179, 200, 0.12); }
        table { width: 100%; border-collapse: collapse; min-width: 760px; background: rgba(27, 41, 55, 0.5); }
        th, td { padding: 12px 14px; text-align: left; vertical-align: top; border-bottom: 1px solid rgba(159, 179, 200, 0.08); overflow-wrap: anywhere; }
        th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; background: rgba(15, 23, 32, 0.92); position: sticky; top: 0; }
        @media (max-width: 900px) {
            .dashboard-shell { width: min(100vw - 20px, 1380px); }
            .search-control { grid-column: auto; }
        }
    </style>
"""


def ratchet_inventory_path(main_html_path: Path) -> Path:
    return main_html_path.with_name(f"{main_html_path.stem}-ratchets{main_html_path.suffix}")


def render_html(
    report: dict[str, Any],
    *,
    current_page_path: str = "repo-health.html",
    ratchet_page_path: str | None = None,
    refresh_dashboard_task: str,
) -> str:
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    audit_status = report.get("audit_status", {}) if isinstance(report.get("audit_status"), dict) else {}
    context_status = report.get("context_status", {}) if isinstance(report.get("context_status"), dict) else {}
    branch_health = report.get("branch_health", {}) if isinstance(report.get("branch_health"), dict) else {}
    trend = report.get("trend_summary", {}) if isinstance(report.get("trend_summary"), dict) else {}
    handoffs = report.get("handoffs", {}) if isinstance(report.get("handoffs"), dict) else {}
    ratchets = report.get("ratchet_status", {}) if isinstance(report.get("ratchet_status"), dict) else {}
    coverage_ratchet = ratchets.get("coverage", {}) if isinstance(ratchets.get("coverage"), dict) else {}
    structural_ratchet = ratchets.get("structural", {}) if isinstance(ratchets.get("structural"), dict) else {}
    generated_at = str(report.get("generated_at", "n/a"))
    page_links = (
        html_helpers.page_links(main_page_path="#", ratchet_page_path=ratchet_page_path, current_page="main")
        if ratchet_page_path
        else ""
    )
    dashboard_actions = html_helpers.dashboard_actions(refresh_dashboard_task=refresh_dashboard_task)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>SattLint Repo Health</title>
{REPO_HEALTH_STYLE}
</head>
<body>
    <main class=\"dashboard-shell\">
        {page_links}
        {dashboard_actions}
        <section class=\"hero card\">
            <div>
                <div class=\"eyebrow\">Workspace snapshot</div>
                <h1>SattLint Repo Health</h1>
                <p class=\"hero-copy\">Snapshot-backed view of audit, context, branch, and throughput health for this repository.</p>
                <dl class=\"definitions\">
                    {html_helpers.definition_rows([("Generated", generated_at), ("Audit dir", str(report.get("audit_dir", "n/a"))), ("Status", str(report.get("status", "unknown")))])}
                </dl>
            </div>
            <div class=\"hero-statuses\">
                {html_helpers.status_pill("Repo", str(report.get("status", "unknown")))}
                {html_helpers.status_pill("Audit", str(audit_status.get("overall_status", "unknown")))}
                {html_helpers.status_pill("Context", str(context_status.get("status", "unknown")))}
                {html_helpers.status_pill("Coverage Ratchet", str(coverage_ratchet.get("status", "unknown")), detail=f"{html_helpers.format_percent(coverage_ratchet.get('current_line_rate'))} current vs {html_helpers.format_percent(coverage_ratchet.get('minimum_line_rate'))} floor")}
                {html_helpers.status_pill("Structural Ratchet", str(structural_ratchet.get("status", "unknown")), detail=f"{html_helpers.format_number(structural_ratchet.get('function_over_budget_count'))} functions, {html_helpers.format_number(structural_ratchet.get('class_over_budget_count'))} classes, {html_helpers.format_number(structural_ratchet.get('file_exception_count'))} exceptions")}
            </div>
        </section>
        <section class=\"metrics-grid\">
            {html_helpers.metric_card(label="Audit findings", value=html_helpers.format_number(metrics.get("finding_count")), detail=f"Blocking {html_helpers.format_number(metrics.get('blocking_finding_count'))}")}
            {html_helpers.metric_card(label="Coverage", value=html_helpers.format_percent(metrics.get("coverage_total_line_rate")), detail=f"Minimum {html_helpers.format_percent(metrics.get('coverage_min_line_rate'))}")}
            {html_helpers.metric_card(label="Context budget", value=f"{html_helpers.format_number(metrics.get('auto_loaded_context_lines'))}/{html_helpers.format_number(metrics.get('context_auto_loaded_budget'))}", detail=f"{html_helpers.format_number(metrics.get('scoped_context_file_count'))} scoped files")}
            {html_helpers.metric_card(label="Quality checks", value=f"Ruff {html_helpers.format_number(metrics.get('ruff_issue_count'))}", detail=f"Pyright {html_helpers.format_number(metrics.get('pyright_error_count'))} errors / {html_helpers.format_number(metrics.get('pyright_warning_count'))} warnings")}
            {html_helpers.metric_card(label="Pytest runtime", value=(f"{float(metrics.get('test_runtime_seconds', 0.0)):.3f}s" if metrics.get("test_runtime_seconds") is not None else "n/a"), detail="Latest pipeline snapshot")}
            {html_helpers.metric_card(label="AI throughput", value=html_helpers.format_number(metrics.get("ai_task_throughput")), detail=("Merge success n/a" if handoffs.get("merge_success_rate") is None else f"Merge success {html_helpers.format_percent(handoffs.get('merge_success_rate'))}"))}
            {html_helpers.metric_card(label="Branch state", value=html_helpers.format_number(metrics.get("dirty_files")), detail=f"Dirty files on {branch_health.get('branch', 'current branch')}")}
            {html_helpers.metric_card(label="Largest file", value=html_helpers.format_number(metrics.get("largest_file_lines")), detail=str(metrics.get("largest_file_path", "n/a")))}
            {html_helpers.metric_card(label="Ratcheting", value=str(ratchets.get("overall_status", "unknown")), detail=f"Coverage {coverage_ratchet.get('status', 'unknown')} / Structural {structural_ratchet.get('status', 'unknown')}")}
        </section>
        <section class=\"split-grid\">
            <article class=\"card\">
                <div class=\"section-header\"><h2>Branch health</h2></div>
                <dl class=\"definitions\">{html_helpers.definition_rows([("Branch", str(branch_health.get("branch", "n/a"))), ("Dirty files", html_helpers.format_number(branch_health.get("dirty_files"))), ("Ahead by", html_helpers.format_signed(branch_health.get("ahead_by"))), ("Behind by", html_helpers.format_signed(branch_health.get("behind_by"))), ("Tracked worktrees", html_helpers.format_number(branch_health.get("tracked_worktrees")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Trend summary</h2></div>
                <dl class=\"definitions\">{html_helpers.definition_rows([("History snapshots", html_helpers.format_number(trend.get("history_count"))), ("Coverage delta", html_helpers.format_signed(trend.get("coverage_delta"))), ("Finding delta", html_helpers.format_signed(trend.get("finding_delta"))), ("Context delta", html_helpers.format_signed(trend.get("context_delta"))), ("Largest file delta", html_helpers.format_signed(trend.get("largest_file_delta")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Context and audit</h2></div>
                <dl class=\"definitions\">{html_helpers.definition_rows([("Audit severity", str(audit_status.get("max_severity", "n/a"))), ("Context issues", html_helpers.format_number(context_status.get("issue_count"))), ("Root junk files", html_helpers.format_number(metrics.get("root_junk_file_count"))), ("Structural over budget", f"{html_helpers.format_number(metrics.get('function_over_budget_count'))} functions / {html_helpers.format_number(metrics.get('class_over_budget_count'))} classes"), ("Handoffs", html_helpers.format_number(handoffs.get("handoff_count")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Ratchet status</h2></div>
                <dl class=\"definitions\">{html_helpers.definition_rows([("Overall", str(ratchets.get("overall_status", "unknown"))), ("Coverage floor", f"{html_helpers.format_percent(coverage_ratchet.get('current_line_rate'))} against {html_helpers.format_percent(coverage_ratchet.get('minimum_line_rate'))}"), ("Structural budget", f"{html_helpers.format_number(structural_ratchet.get('function_over_budget_count'))} functions / {html_helpers.format_number(structural_ratchet.get('class_over_budget_count'))} classes"), ("Structural regression", "yes" if structural_ratchet.get("structural_budget_regression") else "no"), ("File exceptions", html_helpers.format_number(structural_ratchet.get("file_exception_count")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Top findings</h2></div>
                <div class=\"stack-list\">{html_helpers.render_findings(report.get("top_findings", []))}</div>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Warnings</h2></div>
                <div class=\"stack-list\">{html_helpers.render_warnings(report.get("warnings", []))}</div>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Largest files</h2></div>
                <div class=\"stack-list\">{html_helpers.render_named_list(report.get("largest_files", []), empty_message="No largest-file data in the current snapshot.", title_key="path", primary_value_key="lines", secondary_value_key="kind", primary_suffix=" lines")}</div>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Slowest tests</h2></div>
                <div class=\"stack-list\">{html_helpers.render_named_list(report.get("slowest_tests", []), empty_message="No slow-test data in the current snapshot.", title_key="name", primary_value_key="time_seconds", secondary_value_key="outcome", primary_suffix="s")}</div>
            </article>
        </section>
    </main>
</body>
</html>
"""


def render_ratchet_html(
    report: dict[str, Any],
    *,
    current_page_path: str = "repo-health-ratchets.html",
    main_page_path: str,
    refresh_dashboard_task: str,
) -> str:
    ratchet_inventory = report.get("ratchet_inventory", {}) if isinstance(report.get("ratchet_inventory"), dict) else {}
    allow_lists = (
        ratchet_inventory.get("allow_lists", {}) if isinstance(ratchet_inventory.get("allow_lists"), dict) else {}
    )
    typing_allowlist = (
        allow_lists.get("typing_debt_allowlist", [])
        if isinstance(allow_lists.get("typing_debt_allowlist"), list)
        else []
    )
    structural_exceptions = (
        allow_lists.get("structural_file_exceptions", [])
        if isinstance(allow_lists.get("structural_file_exceptions"), list)
        else []
    )
    ratcheted_statuses = (
        ratchet_inventory.get("ratcheted_file_statuses", [])
        if isinstance(ratchet_inventory.get("ratcheted_file_statuses"), list)
        else []
    )
    ratchet_rows_missing_target = sum(
        1 for item in ratcheted_statuses if item.get("status") in {"below_target", "over_target", "allowlisted"}
    )
    page_links = html_helpers.page_links(main_page_path=main_page_path, ratchet_page_path="#", current_page="ratchets")
    dashboard_actions = html_helpers.dashboard_actions(refresh_dashboard_task=refresh_dashboard_task)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>SattLint Ratchet Details</title>
{RATCHET_STYLE}
</head>
<body>
    <main class=\"dashboard-shell\">
        {page_links}
        {dashboard_actions}
        <section class=\"card\">
            <div class=\"eyebrow\">Ratchets and allow-lists</div>
            <h1>SattLint Ratchet Details</h1>
            <p class=\"hero-copy\">Checked-in debt inventory from the ratchet artifacts and typing allow-list. This page lists allow-listed files and every per-file ratchet entry that still controls touch behavior.</p>
            <section class=\"summary-grid\">
                {html_helpers.metric_card(label="Typing allow-list", value=html_helpers.format_number(len(typing_allowlist)), detail="tool.sattlint.typing_ratchet.debt_allowlist")}
                {html_helpers.metric_card(label="Structural exceptions", value=html_helpers.format_number(len(structural_exceptions)), detail="structural_budget_ratchet.json")}
                {html_helpers.metric_card(label="Ratcheted entries", value=html_helpers.format_number(len(ratcheted_statuses)), detail="coverage, structural, and typing rows")}
                {html_helpers.metric_card(label="Still missing target", value=html_helpers.format_number(ratchet_rows_missing_target), detail="rows not fully cleared")}
            </section>
        </section>
        <section class=\"split-grid\">
            <article class=\"card\">
                <h2>Typing debt allow-list</h2>
                <div class=\"table-wrap\">
                    <table>
                        <thead><tr><th>Path</th></tr></thead>
                        <tbody>{html_helpers.render_allow_list_rows(typing_allowlist, columns=("path",), empty_message="No typing debt allow-list entries.")}</tbody>
                    </table>
                </div>
            </article>
            <article class=\"card\">
                <h2>Structural file exceptions</h2>
                <div class=\"table-wrap\">
                    <table>
                        <thead><tr><th>Path</th><th>Max lines</th><th>Reason</th></tr></thead>
                        <tbody>{html_helpers.render_allow_list_rows(structural_exceptions, columns=("path", "max_lines", "reason"), empty_message="No structural file exceptions.")}</tbody>
                    </table>
                </div>
            </article>
        </section>
        <section class=\"card\">
            <h2>Ratcheted file status</h2>
            {html_helpers.render_ratcheted_table_controls()}
            <p class=\"table-note\">Each row is one per-file ratchet entry from the checked-in debt ledger. These controls apply only to the <strong>Ratcheted file status</strong> table below.</p>
            <div class=\"table-wrap\">
                <table id=\"ratcheted-status-table\">
                    <thead>
                        <tr>
                            <th>Path</th>
                            <th>Kind</th>
                            <th>Status</th>
                            <th>Current</th>
                            <th>Target</th>
                            <th>Gap</th>
                            <th>Touch rule</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>{html_helpers.render_ratcheted_status_rows(ratcheted_statuses)}</tbody>
                </table>
            </div>
        </section>
    </main>
    {html_helpers.render_ratcheted_table_script()}
</body>
</html>
"""
