from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from ..application.findings import AnalysisFinding, kind_human_label
from ..runs import (
    RunAnalyzerRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
    delete_run,
    list_runs,
    load_run,
)
from ._app_textual_shared import (
    _TEXTUAL_BUTTON,
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    _TEXTUAL_TREE,
    _TEXTUAL_VERTICAL,
    _query_required,
)

ResultsGroupBy = Literal["analyzer", "module"]

if _TEXTUAL_TREE is not None:
    from rich.cells import cell_len as _cell_len  # type: ignore[import-untyped]

    _TREE_TOGGLE_WIDTH = _cell_len(str(_TEXTUAL_TREE.ICON_NODE))

    class _ResultsTree(_TEXTUAL_TREE):  # pyright: ignore[reportUntypedBaseClass]
        """Results tree with cheap label measurement.

        Textual's ``Tree._build`` re-measures every expanded label on each
        expand/collapse through ``render_label`` (Rich ``Text`` copy/stylize/
        assemble). Overriding ``get_label_width`` to measure the plain label
        avoids that work; the width is memoized per node and invalidated when
        the node's label or expand affordance changes.
        """

        def get_label_width(self, node: Any) -> int:
            cached = getattr(node, "_sattlint_label_width", None)
            updates = getattr(node, "_updates", 0)
            if cached is not None and cached[0] == updates:
                return int(cached[1])
            width = _cell_len(str(node._label.plain))
            if getattr(node, "_allow_expand", False):
                width += _TREE_TOGGLE_WIDTH
            node._sattlint_label_width = (updates, width)
            return width

else:  # pragma: no cover - optional dependency path
    _ResultsTree: Any = None


def _new_results_tree() -> Any:
    return _ResultsTree("", id="results-tree")


def _format_run_timestamp(iso_text: str) -> str:
    """Format an ISO run timestamp without the 'T'/'Z' separators."""
    if not iso_text:
        return iso_text
    try:
        dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return iso_text
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _run_summary_label(summary: RunSummary) -> str:
    return f"{_format_run_timestamp(summary.finished_at)} ({summary.issue_count} issues)"


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
    if finding.rule_id:
        label += f" ({finding.rule_id})"
    if occurrence_count > 1:
        label += f" ({occurrence_count} occurrences)"
    return label


def _finding_groups(
    analyzer: RunAnalyzerRecord,
) -> list[tuple[str, list[tuple[AnalysisFinding, int]]]]:
    """Group findings by issue kind, message, and site.

    Identical findings repeated at the same site across instance paths are
    represented once with an occurrence count.
    """
    counts: dict[tuple[str, str, str | None], int] = {}
    representatives: dict[tuple[str, str, str | None], AnalysisFinding] = {}
    order: list[tuple[str, str, str | None]] = []
    for finding in analyzer.findings:
        key = (finding.kind, finding.message, _site_label(finding))
        if key not in representatives:
            representatives[key] = finding
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    groups: list[tuple[str, list[tuple[AnalysisFinding, int]]]] = []
    kind_index: dict[str, int] = {}
    for key in order:
        kind, _message, _site = key
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


def _module_display_paths(paths: Iterable[tuple[str, ...]]) -> dict[tuple[str, ...], tuple[str, ...]]:
    """Map module paths to display paths with single-child chains merged.

    A module node is collapsed into its parent when it carries no findings of
    its own and has exactly one child path. The resulting node label is the
    dotted chain (``RootProgram.StartMaster.Charge``) instead of one node per
    path segment. Branch points and module nodes with findings stay separate so
    navigation is preserved.
    """
    terminals = set(paths)
    trie: dict[str, dict[str, Any]] = {}
    for path in terminals:
        node = trie
        for segment in path:
            node = node.setdefault(segment, {})

    display_paths: dict[tuple[str, ...], tuple[str, ...]] = {}
    pending: list[tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]] = [(trie, (), ())]
    while pending:
        node, origin_prefix, display_prefix = pending.pop()
        for segment, children in node.items():
            origin = (*origin_prefix, segment)
            display = (*display_prefix, segment)
            remaining = children
            while origin not in terminals and len(remaining) == 1:
                ((child_segment, grandchildren),) = remaining.items()
                origin = (*origin, child_segment)
                display = (*display[:-1], f"{display[-1]}.{child_segment}")
                remaining = grandchildren
            if origin in terminals:
                display_paths[origin] = display
            if remaining:
                pending.append((remaining, origin, display))
    return display_paths


def _finding_module_path(finding: AnalysisFinding, analyzer: RunAnalyzerRecord) -> tuple[str, ...]:
    return finding.module_path if finding.module_path else (analyzer.name,)


def _add_finding_leaves(parent: Any, findings: Iterable[tuple[AnalysisFinding, int]]) -> None:
    site_nodes: dict[tuple[int, str], Any] = {}
    for finding, occurrence_count in findings:
        leaf_parent = parent
        site = _site_label(finding)
        if site:
            site_key = (id(parent), site)
            site_node = site_nodes.get(site_key)
            if site_node is None:
                site_node = parent.add(site, data=None)
                site_nodes[site_key] = site_node
            leaf_parent = site_node
        finding_node = leaf_parent.add(_finding_label(finding, occurrence_count=occurrence_count), data=finding)
        finding_node.allow_expand = False


def _populate_findings_by_analyzer(analyzer_node: Any, analyzer: RunAnalyzerRecord) -> None:
    builder = _ModuleTreeBuilder()
    for kind, items in _finding_groups(analyzer):
        total = sum(count for _finding, count in items)
        display_paths = _module_display_paths(_finding_module_path(finding, analyzer) for finding, _count in items)
        kind_node = analyzer_node.add(f"{kind_human_label(kind)} ({total})", data=None)
        by_module: dict[tuple[str, ...], list[tuple[AnalysisFinding, int]]] = {}
        for finding, occurrence_count in items:
            by_module.setdefault(display_paths[_finding_module_path(finding, analyzer)], []).append(
                (finding, occurrence_count)
            )
        for display_segments, module_items in by_module.items():
            module_node = builder.add(kind_node, display_segments)
            _add_finding_leaves(module_node, module_items)


def _populate_findings_by_module(
    target_node: Any,
    target: RunTargetRecord,
    *,
    show_empty_analyzers: bool,
) -> None:
    analyzers = [analyzer for analyzer in target.analyzers if analyzer.findings]
    display_paths = _module_display_paths(
        _finding_module_path(finding, analyzer) for analyzer in analyzers for finding in analyzer.findings
    )
    module_branches: dict[
        tuple[str, ...],
        list[tuple[RunAnalyzerRecord, dict[str, list[tuple[AnalysisFinding, int]]]]],
    ] = {}
    for analyzer in analyzers:
        modules: dict[tuple[str, ...], dict[str, list[tuple[AnalysisFinding, int]]]] = {}
        for kind, items in _finding_groups(analyzer):
            for finding, occurrence_count in items:
                modules.setdefault(_finding_module_path(finding, analyzer), {}).setdefault(kind, []).append(
                    (finding, occurrence_count)
                )
        for segments, kinds in modules.items():
            module_branches.setdefault(segments, []).append((analyzer, kinds))
    builder = _ModuleTreeBuilder()
    for segments, branches in module_branches.items():
        module_node = builder.add(target_node, display_paths[segments])
        for analyzer, kinds in branches:
            analyzer_node = module_node.add(
                f"{analyzer.name} ({analyzer.key}) — {analyzer.status}",
                data=analyzer,
            )
            for kind, items in kinds.items():
                total = sum(count for _finding, count in items)
                kind_node = analyzer_node.add(f"{kind_human_label(kind)} ({total})", data=None)
                _add_finding_leaves(kind_node, items)
    if show_empty_analyzers:
        empty_analyzers = [analyzer for analyzer in target.analyzers if not analyzer.findings]
        if empty_analyzers:
            no_findings_node = target_node.add(f"No findings ({len(empty_analyzers)})", data=None)
            for analyzer in empty_analyzers:
                analyzer_node = no_findings_node.add(
                    f"{analyzer.name} ({analyzer.key}) — {analyzer.status}",
                    data=analyzer,
                )
                analyzer_node.allow_expand = False


def _auto_expand_single_child_chains(root: Any) -> None:
    """Expand every descendant that has exactly one child.

    Chains of single-child branch nodes (common for nested module paths and
    sites) carry no navigation choice, so opening them up front saves the user
    from clicking through each level. The root is left untouched so the hidden
    top level is not implicitly expanded.
    """
    stack = list(root._children)
    while stack:
        node = stack.pop()
        if len(node._children) == 1:
            node._expanded = True
        stack.extend(node._children)


def _populate_run_tree(
    tree: Any,
    record: RunRecord,
    *,
    show_empty_analyzers: bool = False,
    group_by: ResultsGroupBy = "analyzer",
) -> None:
    tree.reset("", data=record)
    tree.show_root = False
    root = tree.root
    for target in record.targets:
        shown_analyzers = [analyzer for analyzer in target.analyzers if show_empty_analyzers or analyzer.findings]
        target_issue_count = sum(len(analyzer.findings) for analyzer in shown_analyzers)
        target_node = root.add(
            f"{target.target_name} ({len(shown_analyzers)} analyzers, {target_issue_count} issues)",
            data=target,
        )
        if group_by == "module":
            _populate_findings_by_module(target_node, target, show_empty_analyzers=show_empty_analyzers)
            continue
        for analyzer in shown_analyzers:
            analyzer_node = target_node.add(
                f"{analyzer.name} ({analyzer.key}) — {analyzer.status}",
                data=analyzer,
            )
            _populate_findings_by_analyzer(analyzer_node, analyzer)
    _auto_expand_single_child_chains(root)
    root.expand()


def _build_run_tree(
    record: RunRecord,
    *,
    show_empty_analyzers: bool = False,
    group_by: ResultsGroupBy = "analyzer",
) -> Any:
    if _TEXTUAL_TREE is None:
        return None
    tree = _new_results_tree()
    _populate_run_tree(tree, record, show_empty_analyzers=show_empty_analyzers, group_by=group_by)
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


def _apply_results_list_index(list_view: Any, index: int) -> None:
    """Sync the ListView index once the rebuilt items are mounted.

    ``ListView.append`` mounts items asynchronously, so assigning ``index``
    during the rebuild can target a still-empty list. This runs after a refresh
    (when the items are present) so arrow-key navigation starts from the
    highlighted run; the ``-highlight`` class is applied at creation in
    ``_refresh_results_runs_list`` and is not affected by this.
    """
    if 0 <= index < len(list_view.children):
        list_view.index = index


def _refresh_results_runs_list(self: Any) -> None:
    try:
        list_view = self.query_one("#results-runs-list", _TEXTUAL_LIST_VIEW)
    except _TEXTUAL_QUERY_ERRORS:
        return

    summaries = _results_run_summaries(self)
    self._results_run_summaries = list(summaries)
    selected_id = getattr(self._selected_run_record, "run_id", None) if self._selected_run_record is not None else None
    highlight_index = None
    if selected_id is not None:
        for index, summary in enumerate(summaries):
            if summary.run_id == selected_id:
                highlight_index = index
                break
    if highlight_index is None and summaries:
        highlight_index = 0

    # Keep the already-mounted items when the content is unchanged so the
    # selected run stays highlighted; only rebuild when the labels differ.
    existing_labels = [
        str(getattr(next(iter(child.children), _TEXTUAL_STATIC("")), "renderable", "")) for child in list_view.children
    ]
    new_labels = [_run_summary_label(summary) for summary in summaries]
    if existing_labels != new_labels:
        # ``ListView.append`` mounts items asynchronously, so ``index`` alone
        # cannot highlight the freshly appended run reliably. Applying the
        # ``-highlight`` class at creation keeps the selected run visible even
        # when the index assignment runs before the items are mounted.
        list_view.clear()
        for index, summary in enumerate(summaries):
            item = _TEXTUAL_LIST_ITEM(_TEXTUAL_STATIC(_run_summary_label(summary)))
            if index == highlight_index:
                item.set_class(True, "-highlight")
            list_view.append(item)
        if highlight_index is not None:
            list_view.call_after_refresh(_apply_results_list_index, list_view, highlight_index)
    elif highlight_index is not None:
        list_view.index = highlight_index


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
        tree = _new_results_tree()
        tree_host = _query_required(self, "#results-tree-host", _TEXTUAL_VERTICAL)
        tree_host.mount(tree)
        self._results_tree_widget = tree
        self._results_tree_render_key = None
    group_by = self._results_group_by()
    show_empty_analyzers = self._results_show_empty_analyzers()
    render_key = (record.run_id, show_empty_analyzers, group_by)
    if getattr(self, "_results_tree_render_key", None) != render_key:
        _populate_run_tree(
            tree,
            record,
            show_empty_analyzers=show_empty_analyzers,
            group_by=group_by,
        )
        self._results_tree_render_key = render_key
        self._results_tree_run_id = record.run_id
    self._update_results_group_button()
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


def _results_group_by(self: Any) -> ResultsGroupBy:
    value = getattr(self, "_results_group_by_flag", "analyzer")
    return "module" if value == "module" else "analyzer"


def _results_group_label(group_by: ResultsGroupBy) -> str:
    return "Group: Module" if group_by == "module" else "Group: Analyzer"


def _update_results_group_button(self: Any) -> None:
    try:
        button = self.query_one("#results-toggle-group", _TEXTUAL_BUTTON)
    except _TEXTUAL_QUERY_ERRORS:
        return
    button.label = _results_group_label(self._results_group_by())


def _toggle_results_group_by(self: Any) -> None:
    group_by: ResultsGroupBy = "module" if self._results_group_by() == "analyzer" else "analyzer"
    self._results_group_by_flag = group_by
    self._write_output("Results are grouped by module." if group_by == "module" else "Results are grouped by analyzer.")
    self._render_selected_run()
    self._refresh_shell_state()


def _expand_all_results(self: Any) -> None:
    tree = getattr(self, "_results_tree_widget", None)
    if tree is None:
        self._write_output("No analysis results are available yet.")
        return
    for node in _walk_tree_nodes(tree.root, include_root=True):
        node._expanded = True
    tree._invalidate()
    self._write_output("Expanded all results.")


def _collapse_all_results(self: Any) -> None:
    tree = getattr(self, "_results_tree_widget", None)
    if tree is None:
        self._write_output("No analysis results are available yet.")
        return
    for node in _walk_tree_nodes(tree.root, include_root=True):
        node._expanded = False
    _auto_expand_single_child_chains(tree.root)
    tree._invalidate()
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
        self._results_tree_run_id = None
        self._results_tree_render_key = None
        tree = getattr(self, "_results_tree_widget", None)
        if tree is not None:
            tree.reset("No matching runs", data=None)
        self._write_output("No previous analysis runs are available yet. Run analyses from the Analyze view.")
        return
    current_id = getattr(self._selected_run_record, "run_id", None)
    if current_id is None or not any(summary.run_id == current_id for summary in summaries):
        summary = summaries[0]
        record = load_run(summary.run_id)
        if record is None:
            self._report_error("Could not load run", "That run could not be loaded.")
            return
        self._selected_run_record = record
    self._render_selected_run()


def _delete_selected_run(self: Any) -> None:
    record = getattr(self, "_selected_run_record", None)
    if record is None:
        self._write_output("No run is selected.")
        return
    if not delete_run(record.run_id):
        self._write_output("That run could not be deleted.")
        return
    self._write_output(f"Deleted run {_format_run_timestamp(record.finished_at)}.")
    self._selected_run_record = None
    self._refresh_results_view()
    self._refresh_shell_state()


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
        def _results_group_by(self) -> ResultsGroupBy: ...
        def _update_results_group_button(self) -> None: ...
        def _toggle_results_group_by(self) -> None: ...
        def _delete_selected_run(self) -> None: ...
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
        _results_group_by = _results_group_by
        _update_results_group_button = _update_results_group_button
        _toggle_results_group_by = _toggle_results_group_by
        _delete_selected_run = _delete_selected_run
        _refresh_results_view = _refresh_results_view
