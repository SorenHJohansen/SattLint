from __future__ import annotations

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


def render_html(
    report: dict[str, Any],
    *,
    current_page_path: str = "repo-health.html",
    refresh_dashboard_task: str,
) -> str:
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    audit_status = report.get("audit_status", {}) if isinstance(report.get("audit_status"), dict) else {}
    context_status = report.get("context_status", {}) if isinstance(report.get("context_status"), dict) else {}
    branch_health = report.get("branch_health", {}) if isinstance(report.get("branch_health"), dict) else {}
    trend = report.get("trend_summary", {}) if isinstance(report.get("trend_summary"), dict) else {}
    handoffs = report.get("handoffs", {}) if isinstance(report.get("handoffs"), dict) else {}
    generated_at = str(report.get("generated_at", "n/a"))
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
            </div>
        </section>
        <section class=\"metrics-grid\">
            {html_helpers.metric_card(label="Audit findings", value=html_helpers.format_number(metrics.get("finding_count")), detail=f"Blocking {html_helpers.format_number(metrics.get('blocking_finding_count'))}")}
            {html_helpers.metric_card(label="Coverage", value=html_helpers.format_percent(metrics.get("coverage_total_line_rate")), detail="Latest pipeline snapshot")}
            {html_helpers.metric_card(label="Context budget", value=f"{html_helpers.format_number(metrics.get('auto_loaded_context_lines'))}/{html_helpers.format_number(metrics.get('context_auto_loaded_budget'))}", detail=f"{html_helpers.format_number(metrics.get('scoped_context_file_count'))} scoped files")}
            {html_helpers.metric_card(label="Quality checks", value=f"Ruff {html_helpers.format_number(metrics.get('ruff_issue_count'))}", detail=f"Pyright {html_helpers.format_number(metrics.get('pyright_error_count'))} errors / {html_helpers.format_number(metrics.get('pyright_warning_count'))} warnings")}
            {html_helpers.metric_card(label="Pytest runtime", value=(f"{float(metrics.get('test_runtime_seconds', 0.0)):.3f}s" if metrics.get("test_runtime_seconds") is not None else "n/a"), detail="Latest pipeline snapshot")}
            {html_helpers.metric_card(label="AI throughput", value=html_helpers.format_number(metrics.get("ai_task_throughput")), detail=("Merge success n/a" if handoffs.get("merge_success_rate") is None else f"Merge success {html_helpers.format_percent(handoffs.get('merge_success_rate'))}"))}
            {html_helpers.metric_card(label="Branch state", value=html_helpers.format_number(metrics.get("dirty_files")), detail=f"Dirty files on {branch_health.get('branch', 'current branch')}")}
            {html_helpers.metric_card(label="Largest file", value=html_helpers.format_number(metrics.get("largest_file_lines")), detail=str(metrics.get("largest_file_path", "n/a")))}
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
