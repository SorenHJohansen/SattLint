# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false
from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from ..application.findings import AnalysisFinding, kind_human_label
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


_LEADING_MODULE_PATH_RE = re.compile(r"^\[[^\]]+\]\s*")


def _context_label(finding: AnalysisFinding) -> str:
    """The expression/context to show on the finding leaf.

    Prefers the analyzer-provided ``data["context"]`` (e.g. ``TargetVal =>
    SourceVal``); otherwise falls back to the message with the leading
    ``[Module.Path]`` annotation stripped (the path is already shown as tree
    branch nodes).
    """
    data = finding.data
    context = data.get("context")
    if context:
        return str(context)
    return _LEADING_MODULE_PATH_RE.sub("", finding.message).strip()


def _site_label(finding: AnalysisFinding) -> str | None:
    """The containing EquationBlock / Sequence / step for a finding, if known."""
    site = finding.data.get("site")
    if site:
        return str(site)
    return None


def _finding_label(finding: AnalysisFinding, *, occurrence_count: int = 1) -> str:
    label = _context_label(finding)
    if finding.severity:
        label += f" — {finding.severity}"
    if finding.rule_id:
        label += f" ({finding.rule_id})"
    if occurrence_count > 1:
        label += f" ({occurrence_count} occurrences)"
    return label


def _add_finding_detail_leafs(node: Any, finding: AnalysisFinding) -> None:
    """Attach the standard Context / Why / Fix leafs to a finding node.

    Each leaf is added only when the corresponding text exists, so a finding
    with no explanation stays a plain leaf node.
    """
    context = _context_label(finding)
    if context:
        node.add(f"Context: {context}", data=None)
    if finding.explanation:
        node.add(f"Why: {finding.explanation}", data=None)
    if finding.suggestion:
        node.add(f"Fix: {finding.suggestion}", data=None)


def _hide_leaf_expanders(node: Any) -> None:
    children = list(getattr(node, "children", ()))
    if not children:
        node.allow_expand = False
        return
    for child in children:
        _hide_leaf_expanders(child)


def _finding_groups(
    analyzer: RunAnalyzerRecord,
) -> list[tuple[str, list[tuple[AnalysisFinding, int]]]]:
    """Group findings by issue kind, collapsing identical (kind, message) pairs.

    Identical findings that repeat at multiple sites (e.g. a moduletype body
    analyzed at several instance paths) are represented once, with their
    occurrence count, so a moduletype issue is shown at a single instance path.
    """
    counts: dict[tuple[str, str], int] = {}
    representatives: dict[tuple[str, str], AnalysisFinding] = {}
    order: list[tuple[str, str]] = []
    for finding in analyzer.findings:
        key = (finding.kind, finding.message)
        if key not in representatives:
            representatives[key] = finding
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    groups: list[tuple[str, list[tuple[AnalysisFinding, int]]]] = []
    kind_index: dict[str, int] = {}
    for key in order:
        kind, _message = key
        if kind not in kind_index:
            kind_index[kind] = len(groups)
            groups.append((kind, []))
        groups[kind_index[kind]][1].append((representatives[key], counts[key]))
    return groups


class _ModuleTreeBuilder:
    """Builds module-path branch nodes, reusing a branch for identical segments."""

    def __init__(self) -> None:
        self._branches: dict[tuple[int, str], Any] = {}

    def add(self, parent: Any, segments: tuple[str, ...]) -> Any:
        current = parent
        for index, segment in enumerate(segments):
            key = (id(current), segment)
            node = self._branches.get(key)
            if node is None:
                node = current.add(segment, data=".".join(segments[: index + 1]))
                self._branches[key] = node
            current = node
        return current


def _populate_analyzer_findings(analyzer_node: Any, analyzer: RunAnalyzerRecord) -> None:
    builder = _ModuleTreeBuilder()
    for kind, groups in _finding_groups(analyzer):
        total = sum(count for _finding, count in groups)
        kind_node = analyzer_node.add(f"{kind_human_label(kind)} ({total})", data=None)
        site_nodes: dict[tuple[int, str], Any] = {}
        for finding, occurrence_count in groups:
            segments = finding.module_path if finding.module_path else (analyzer.name,)
            leaf_parent = builder.add(kind_node, segments)
            site = _site_label(finding)
            if site:
                site_key = (id(leaf_parent), site)
                site_node = site_nodes.get(site_key)
                if site_node is None:
                    site_node = leaf_parent.add(site, data=None)
                    site_nodes[site_key] = site_node
                leaf_parent = site_node
            finding_node = leaf_parent.add(_finding_label(finding, occurrence_count=occurrence_count), data=finding)
            _add_finding_detail_leafs(finding_node, finding)


def _populate_run_tree(tree: Any, record: RunRecord, *, show_empty_analyzers: bool = False) -> None:
    tree.reset(_run_tree_title(record), data=record)
    root = tree.root
    for target in record.targets:
        shown_analyzers = [analyzer for analyzer in target.analyzers if show_empty_analyzers or analyzer.findings]
        target_issue_count = sum(len(analyzer.findings) for analyzer in shown_analyzers)
        target_node = root.add(
            f"{target.target_name} ({len(shown_analyzers)} analyzers, {target_issue_count} issues)",
            data=target,
        )
        for analyzer in shown_analyzers:
            analyzer_node = target_node.add(
                f"{analyzer.name} ({analyzer.key}) — {analyzer.status}",
                data=analyzer,
            )
            _populate_analyzer_findings(analyzer_node, analyzer)
    _hide_leaf_expanders(root)
    root.expand()
    for target_node in root.children:
        target_node.expand()
        for analyzer_node in target_node.children:
            analyzer_node.expand()


def _build_run_tree(record: RunRecord, *, show_empty_analyzers: bool = False) -> Any:
    if _TEXTUAL_TREE is None:
        return None
    tree = _TEXTUAL_TREE(_run_tree_title(record), id="results-tree")
    _populate_run_tree(tree, record, show_empty_analyzers=show_empty_analyzers)
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
        f"Finding: {kind_human_label(finding.kind)}",
        f"Location: {'.'.join(finding.module_path) if finding.module_path else 'unknown'}",
        f"Message: {_LEADING_MODULE_PATH_RE.sub('', finding.message).strip()}",
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
    elif isinstance(data, str):
        self._write_output(f"Module: {data}")
    elif isinstance(data, RunAnalyzerRecord):
        self._write_output(data.summary or f"{data.name}: {data.status}")
    elif isinstance(data, RunTargetRecord):
        self._write_output(_target_overview_text(data))
    elif isinstance(data, RunRecord):
        self._write_output(_run_overview_text(data))


def _current_project_tag(self: Any) -> str:
    program_targets = self._cfg.get("analyzed_programs_and_libraries", [])
    if isinstance(program_targets, list):
        values = cast(list[object], program_targets)
        return ", ".join(str(target) for target in values if str(target).strip())
    return ""


def _results_run_summaries(self: Any) -> tuple[RunSummary, ...]:
    summaries = list_runs()
    project_tag = self._current_project_tag()
    if not project_tag:
        return ()
    return tuple(summary for summary in summaries if summary.project_tag == project_tag)


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
    _populate_run_tree(tree, record, show_empty_analyzers=self._results_show_empty_analyzers())
    self._refresh_shell_state()
    self._write_output("Analysis results are shown in the tree. Select a node for details.")


def _results_show_empty_analyzers(self: Any) -> bool:
    return bool(getattr(self, "_results_show_empty_analyzers_flag", False))


def _toggle_results_show_empty_analyzers(self: Any) -> None:
    self._results_show_empty_analyzers_flag = not self._results_show_empty_analyzers()
    self._write_output(
        "Now showing analyzers with no findings."
        if self._results_show_empty_analyzers()
        else "Hiding analyzers with no findings."
    )
    self._render_selected_run()


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
        tree = getattr(self, "_results_tree_widget", None)
        if tree is not None:
            tree.reset("No matching runs", data=None)
        self._write_output("No previous analysis runs are available yet. Run analyses from the Analyze view.")
        return
    summary = summaries[0]
    record = load_run(summary.run_id)
    if record is None:
        self._report_error("Could not load run", "That run could not be loaded.")
        return
    self._selected_run_record = record
    self._render_selected_run()


if TYPE_CHECKING:

    class _TextualResultsMixin:
        def on_tree_node_selected(self, event: Any) -> None: ...
        def _current_project_tag(self) -> str: ...
        def _refresh_results_runs_list(self) -> None: ...
        def _render_results_tree(self, record: RunRecord) -> None: ...
        def _render_selected_run(self) -> None: ...
        def _expand_all_results(self) -> None: ...
        def _collapse_all_results(self) -> None: ...
        def _results_show_empty_analyzers(self) -> bool: ...
        def _toggle_results_show_empty_analyzers(self) -> None: ...
        def _refresh_results_view(self) -> None: ...
else:

    class _TextualResultsMixin:
        """Provides the Results view: run selection and the results tree."""

        on_tree_node_selected = on_tree_node_selected
        _current_project_tag = _current_project_tag
        _refresh_results_runs_list = _refresh_results_runs_list
        _render_results_tree = _render_results_tree
        _render_selected_run = _render_selected_run
        _expand_all_results = _expand_all_results
        _collapse_all_results = _collapse_all_results
        _results_show_empty_analyzers = _results_show_empty_analyzers
        _toggle_results_show_empty_analyzers = _toggle_results_show_empty_analyzers
        _refresh_results_view = _refresh_results_view
