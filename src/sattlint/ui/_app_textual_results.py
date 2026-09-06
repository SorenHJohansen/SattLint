# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..application.findings import AnalysisFinding
from ..runs import (
    RunAnalyzerRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
    list_runs,
    load_run,
)
from ._app_textual_shared import (
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    _TEXTUAL_TREE,
    _TEXTUAL_VERTICAL,
    _query_required,
)


def _format_run_timestamp(iso_text: str) -> str:
    """Format an ISO run timestamp without the 'T'/'Z' separators."""
    if not iso_text:
        return iso_text
    try:
        dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return iso_text
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _run_tree_title(record: RunRecord) -> str:
    label = f"Run {_format_run_timestamp(record.finished_at)}"
    if record.project_tag:
        label += f" — {record.project_tag}"
    label += f" ({record.target_count} targets, {record.issue_count} issues)"
    return label


def _run_summary_label(summary: RunSummary) -> str:
    label = _format_run_timestamp(summary.finished_at)
    if summary.project_tag:
        label += f" — {summary.project_tag}"
    label += f" ({summary.issue_count} issues)"
    return label


def _finding_label(finding: AnalysisFinding, *, default_module: str) -> str:
    location = ".".join(finding.module_path) if finding.module_path else default_module
    label = f"[{location}] {finding.message}"
    if finding.severity:
        label += f" — {finding.severity}"
    if finding.rule_id:
        label += f" ({finding.rule_id})"
    return label


def _hide_leaf_expanders(node: Any) -> None:
    children = list(getattr(node, "children", ()))
    if not children:
        node.allow_expand = False
        return
    for child in children:
        _hide_leaf_expanders(child)


def _populate_run_tree(tree: Any, record: RunRecord) -> None:
    tree.reset(_run_tree_title(record), data=record)
    root = tree.root
    for target in record.targets:
        target_issue_count = sum(len(analyzer.findings) for analyzer in target.analyzers)
        target_node = root.add(
            f"{target.target_name} ({len(target.analyzers)} analyzers, {target_issue_count} issues)",
            data=target,
        )
        for analyzer in target.analyzers:
            analyzer_node = target_node.add(
                f"{analyzer.name} ({analyzer.key}) — {analyzer.status}",
                data=analyzer,
            )
            for finding in analyzer.findings:
                analyzer_node.add(
                    _finding_label(finding, default_module=analyzer.name),
                    data=finding,
                )
    _hide_leaf_expanders(root)
    root.expand()


def _build_run_tree(record: RunRecord) -> Any:
    if _TEXTUAL_TREE is None:
        return None
    tree = _TEXTUAL_TREE(_run_tree_title(record), id="results-tree")
    _populate_run_tree(tree, record)
    return tree


def _run_overview_text(record: RunRecord) -> str:
    return (
        f"Analysis run {record.finished_at}\n"
        f"Configuration: {record.project_tag or '(none)'}\n"
        f"Targets: {record.target_count}\n"
        f"Analyzers: {record.analyzer_count}\n"
        f"Issues: {record.issue_count}"
    )


def _target_overview_text(target: RunTargetRecord) -> str:
    return (
        f"Target: {target.target_name}\n"
        f"Analyzers: {len(target.analyzers)}\n"
        f"Issues: {sum(len(analyzer.findings) for analyzer in target.analyzers)}"
    )


def _write_finding_detail(self: Any, finding: AnalysisFinding) -> None:
    lines = [
        f"Finding: {finding.kind}",
        f"Location: {'.'.join(finding.module_path) if finding.module_path else 'unknown'}",
        f"Message: {finding.message}",
    ]
    if finding.severity:
        lines.append(f"Severity: {finding.severity}")
    if finding.confidence:
        lines.append(f"Confidence: {finding.confidence}")
    if finding.rule_id:
        lines.append(f"Rule: {finding.rule_id}")
    if finding.explanation:
        lines.append(f"Why it matters: {finding.explanation}")
    if finding.suggestion:
        lines.append(f"Suggested fix: {finding.suggestion}")
    self._write_output("\n".join(lines))


def on_tree_node_selected(self: Any, event: Any) -> None:
    node = getattr(event, "node", None)
    data = getattr(node, "data", None)
    if isinstance(data, AnalysisFinding):
        _write_finding_detail(self, data)
    elif isinstance(data, RunAnalyzerRecord):
        self._write_output(data.summary or f"{data.name}: {data.status}")
    elif isinstance(data, RunTargetRecord):
        self._write_output(_target_overview_text(data))
    elif isinstance(data, RunRecord):
        self._write_output(_run_overview_text(data))


def _results_run_summaries(self: Any) -> tuple[RunSummary, ...]:
    return list_runs()


def _refresh_results_runs_list(self: Any) -> None:
    try:
        list_view = self.query_one("#results-runs-list", _TEXTUAL_LIST_VIEW)
    except _TEXTUAL_QUERY_ERRORS:
        return

    summaries = _results_run_summaries(self)
    self._results_run_summaries = list(summaries)
    list_view.clear()
    for summary in summaries:
        list_view.append(_TEXTUAL_LIST_ITEM(_TEXTUAL_STATIC(_run_summary_label(summary))))


def _render_selected_run(self: Any) -> None:
    record = getattr(self, "_selected_run_record", None)
    if record is None:
        return
    self._render_results_tree(record)


def _render_results_tree(self: Any, record: RunRecord) -> None:
    if _TEXTUAL_TREE is None:
        self._write_output("Results tree is unavailable in the current Textual session.")
        return
    self._selected_run_record = record
    tree = getattr(self, "_results_tree_widget", None)
    if tree is None:
        tree = _TEXTUAL_TREE(_run_tree_title(record), id="results-tree")
        tree_host = _query_required(self, "#results-tree-host", _TEXTUAL_VERTICAL)
        tree_host.mount(tree)
        self._results_tree_widget = tree
    _populate_run_tree(tree, record)
    self._refresh_shell_state()
    self._write_output("Analysis results are shown in the tree. Select a node for details.")


def _expand_all_results(self: Any) -> None:
    tree = getattr(self, "_results_tree_widget", None)
    if tree is None:
        self._write_output("No analysis results are available yet.")
        return
    for node in _walk_tree_nodes(tree.root, include_root=True):
        node.expand()
    self._write_output("Expanded all results.")


def _collapse_all_results(self: Any) -> None:
    tree = getattr(self, "_results_tree_widget", None)
    if tree is None:
        self._write_output("No analysis results are available yet.")
        return
    for node in _walk_tree_nodes(tree.root, include_root=True):
        node.collapse()
    self._write_output("Collapsed all results.")


def _walk_tree_nodes(node: Any, *, include_root: bool = False) -> list[Any]:
    nodes: list[Any] = [node] if include_root else []
    for child in getattr(node, "children", ()):
        nodes.append(child)
        nodes.extend(_walk_tree_nodes(child))
    return nodes


def _refresh_results_view(self: Any) -> None:
    self._refresh_results_runs_list()
    summaries = getattr(self, "_results_run_summaries", [])
    if not summaries:
        self._selected_run_record = None
        self._write_output("No previous analysis runs are available yet. Run analyses from the Analyze view.")
        return
    summary = summaries[0]
    record = load_run(summary.run_id)
    if record is None:
        self._write_output("That run could not be loaded.")
        return
    self._selected_run_record = record
    self._render_selected_run()


if TYPE_CHECKING:

    class _TextualResultsMixin:
        def on_tree_node_selected(self, event: Any) -> None: ...
        def _refresh_results_runs_list(self) -> None: ...
        def _render_results_tree(self, record: RunRecord) -> None: ...
        def _render_selected_run(self) -> None: ...
        def _expand_all_results(self) -> None: ...
        def _collapse_all_results(self) -> None: ...
        def _refresh_results_view(self) -> None: ...
else:

    class _TextualResultsMixin:
        """Provides the Results view: run selection and the results tree."""

        on_tree_node_selected = on_tree_node_selected
        _refresh_results_runs_list = _refresh_results_runs_list
        _render_results_tree = _render_results_tree
        _render_selected_run = _render_selected_run
        _expand_all_results = _expand_all_results
        _collapse_all_results = _collapse_all_results
        _refresh_results_view = _refresh_results_view
