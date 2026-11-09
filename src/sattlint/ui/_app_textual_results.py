from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from ..application.findings import AnalysisFinding, kind_human_label
from ..runs import (
    RunAnalyzerRecord,
    RunModuleRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
    delete_run,
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


@dataclass(frozen=True, slots=True)
class _ModuleSelection:
    target: RunTargetRecord
    path: tuple[str, ...]
    aliases: dict[str, tuple[str, ...]]


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
    timestamp = _format_run_timestamp(summary.finished_at)
    return f"{timestamp[5:16]} ({summary.issue_count})" if len(timestamp) >= 16 else timestamp


_LEADING_MODULE_PATH_RE = re.compile(r"^\[[^\]]+\]\s*")


def _context_label(finding: AnalysisFinding) -> str:
    """The expression/context to show in the findings report.

    Prefers the analyzer-provided ``data["context"]`` (e.g. ``TargetVal =>
    SourceVal``); otherwise falls back to the message with the leading
    ``[Module.Path]`` annotation stripped (the selected module supplies the path).
    """
    message = _LEADING_MODULE_PATH_RE.sub("", finding.message).strip()
    if finding.kind == "unused_datatype_field" and finding.module_path:
        datatype = finding.module_path[-1].removeprefix("DataType:")
        field_prefix = f"datatype '{datatype}'."
        return message.removeprefix(field_prefix)
    data = finding.data
    if finding.kind in {"field_read_only", "field_never_read"}:
        variable = data.get("variable_name")
        field = data.get("field_path")
        return f"{variable}.{field}" if variable and field else message
    context = data.get("context")
    if context:
        return str(context)
    return message


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


def _finding_module_path(finding: AnalysisFinding, analyzer: RunAnalyzerRecord) -> tuple[str, ...]:
    return finding.module_path if finding.module_path else (analyzer.name,)


def _analyzer_label(analyzer: RunAnalyzerRecord) -> str:
    label = f"{analyzer.name} ({analyzer.key})"
    return label if analyzer.status == "completed" else f"{label} — {analyzer.status}"


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


def _module_label(module: RunModuleRecord) -> str:
    if module.moduletype_name:
        return f"{module.name} {module.moduletype_name}"
    return f"{module.name} ({module.kind})" if module.kind else module.name


def _normalized_finding_path(
    target: RunTargetRecord,
    root_name: str,
    finding: AnalysisFinding,
    analyzer: RunAnalyzerRecord,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    path = _finding_module_path(finding, analyzer)
    if path[0].casefold() == target.target_name.casefold():
        normalized = (root_name, *path[1:])
    elif path[0].casefold() == root_name.casefold():
        normalized = path
    else:
        normalized = (root_name, *path)
    if aliases is not None and len(normalized) > 1:
        invoked_path = aliases.get(normalized[1].casefold())
        if invoked_path is not None:
            return (*invoked_path, *normalized[2:])
    return normalized


def _module_path_aliases(target: RunTargetRecord, root_name: str) -> dict[str, tuple[str, ...]]:
    paths = [
        _normalized_finding_path(target, root_name, finding, analyzer)
        for analyzer in target.analyzers
        for finding in analyzer.findings
    ]
    direct_names = {path[1].casefold() for path in paths if len(path) > 1 and ":" not in path[1]}
    candidates: dict[str, dict[tuple[str, ...], tuple[str, ...]]] = {}
    if target.module is not None:
        actual_roots = {child.name.casefold() for child in target.module.children}
        pending = [(child, (root_name, child.name)) for child in target.module.children]
        while pending:
            module, path = pending.pop()
            name = module.name.casefold()
            if len(path) > 2 and module.moduletype_name and name in direct_names and name not in actual_roots:
                candidates.setdefault(name, {})[tuple(part.casefold() for part in path)] = path
            pending.extend((child, (*path, child.name)) for child in module.children)
    else:
        direct_findings = {path[1].casefold() for path in paths if len(path) == 2}
        for path in paths:
            for length in range(3, len(path) + 1):
                name = path[length - 1].casefold()
                if name in direct_names and name not in direct_findings:
                    invoked_path = path[:length]
                    candidates.setdefault(name, {})[tuple(part.casefold() for part in invoked_path)] = invoked_path
    return {name: next(iter(matches.values())) for name, matches in candidates.items() if len(matches) == 1}


def _add_module_children(
    parent: Any,
    children: tuple[RunModuleRecord, ...],
    path: tuple[str, ...],
    target: RunTargetRecord,
    branches: dict[tuple[str, ...], Any],
    finding_paths: set[tuple[str, ...]],
    aliases: dict[str, tuple[str, ...]],
) -> None:
    for child in children:
        child_path = (*path, child.name)
        merged_paths = [child_path]
        final = child
        while len(final.children) == 1 and tuple(part.casefold() for part in child_path) not in finding_paths:
            final = final.children[0]
            child_path = (*child_path, final.name)
            merged_paths.append(child_path)
        label = _module_label(final)
        if len(merged_paths) > 1:
            label = f"{'.'.join(segment[-1] for segment in merged_paths)}{label.removeprefix(final.name)}"
        child_node = parent.add(label, data=_ModuleSelection(target, child_path, aliases))
        for merged_path in merged_paths:
            branches[tuple(part.casefold() for part in merged_path)] = child_node
        _add_module_children(child_node, final.children, child_path, target, branches, finding_paths, aliases)


def _fallback_module_children(
    path: tuple[str, ...], path_children: dict[tuple[str, ...], dict[str, str]]
) -> tuple[RunModuleRecord, ...]:
    key = tuple(part.casefold() for part in path)
    return tuple(
        RunModuleRecord(name=name, children=_fallback_module_children((*path, name), path_children))
        for name in path_children.get(key, {}).values()
    )


def _populate_module_navigation(tree: Any, record: RunRecord) -> _ModuleSelection | None:
    tree.reset("", data=None)
    tree.show_root = False
    first_selection = None
    for target in record.targets:
        module = target.module
        roots = {
            finding.module_path[0]
            for analyzer in target.analyzers
            for finding in analyzer.findings
            if finding.module_path
        }
        root_name = (
            module.name.split(":", 1)[-1]
            if module is not None
            else next(iter(roots))
            if len(roots) == 1
            else target.target_name
        )
        aliases = _module_path_aliases(target, root_name)
        selection = _ModuleSelection(target, (root_name,), aliases)
        if first_selection is None:
            first_selection = selection
        root_label = (
            _module_label(module)
            if module
            else f"{target.target_name}:{root_name}"
            if root_name.casefold() != target.target_name.casefold()
            else target.target_name
        )
        root_node = tree.root.add(root_label, data=selection)
        branches = {(root_name.casefold(),): root_node}
        finding_paths = {
            tuple(part.casefold() for part in _normalized_finding_path(target, root_name, finding, analyzer, aliases))
            for analyzer in target.analyzers
            for finding in analyzer.findings
        }

        if module is not None:
            _add_module_children(root_node, module.children, selection.path, target, branches, finding_paths, aliases)
        else:
            path_children: dict[tuple[str, ...], dict[str, str]] = {}
            for analyzer in target.analyzers:
                for finding in analyzer.findings:
                    path = _normalized_finding_path(target, root_name, finding, analyzer, aliases)
                    for length in range(1, len(path)):
                        parent_key = tuple(part.casefold() for part in path[:length])
                        path_children.setdefault(parent_key, {}).setdefault(path[length].casefold(), path[length])

            _add_module_children(
                root_node,
                _fallback_module_children(selection.path, path_children),
                selection.path,
                target,
                branches,
                finding_paths,
                aliases,
            )
        for analyzer in target.analyzers:
            for finding in analyzer.findings:
                path = _normalized_finding_path(target, root_name, finding, analyzer, aliases)
                for length in range(2, len(path) + 1):
                    prefix = path[:length]
                    key = tuple(part.casefold() for part in prefix)
                    if key not in branches:
                        parent_key = tuple(part.casefold() for part in prefix[:-1])
                        branches[key] = branches[parent_key].add(
                            prefix[-1], data=_ModuleSelection(target, prefix, aliases)
                        )
    _auto_expand_single_child_chains(tree.root)
    tree.root.expand()
    return first_selection


def _module_findings_report(selection: _ModuleSelection, *, show_empty_analyzers: bool) -> str:
    target = selection.target
    path = tuple(part.casefold() for part in selection.path)
    lines: list[str] = []
    for analyzer in target.analyzers:
        matching = tuple(
            finding
            for finding in analyzer.findings
            if tuple(
                part.casefold()
                for part in _normalized_finding_path(target, selection.path[0], finding, analyzer, selection.aliases)
            )
            == path
        )
        if not matching and not (show_empty_analyzers and len(path) == 1 and not analyzer.findings):
            continue
        if lines:
            lines.append("")
        lines.append(_analyzer_label(analyzer))
        if not matching:
            lines.append("  No findings")
            continue
        for kind, items in _finding_groups(
            RunAnalyzerRecord(key=analyzer.key, name=analyzer.name, status=analyzer.status, findings=matching)
        ):
            lines.append(f"  {kind_human_label(kind)} ({sum(count for _, count in items)})")
            for finding, occurrence_count in items:
                lines.append(f"    {_finding_label(finding, occurrence_count=occurrence_count)}")
                site = _site_label(finding)
                if site:
                    lines.append(f"      Site: {site}")
                message = _LEADING_MODULE_PATH_RE.sub("", finding.message).strip()
                if message and message != _context_label(finding):
                    lines.append(f"      {message}")
                if finding.explanation:
                    lines.append(f"      Why it matters: {finding.explanation}")
                if finding.suggestion:
                    lines.append(f"      Suggested fix: {finding.suggestion}")
    return "\n".join(lines) if lines else "No findings for this module"


def on_tree_node_selected(self: Any, event: Any) -> None:
    node = getattr(event, "node", None)
    data = getattr(node, "data", None)
    if isinstance(data, _ModuleSelection):
        _select_results_module(self, data)


def on_tree_node_highlighted(self: Any, event: Any) -> None:
    data = getattr(getattr(event, "node", None), "data", None)
    if isinstance(data, _ModuleSelection):
        _select_results_module(self, data)


def _select_results_module(self: Any, selection: _ModuleSelection) -> None:
    current = getattr(self, "_selected_results_module", None)
    if current is not None and current.target is selection.target and current.path == selection.path:
        return
    self._selected_results_module = selection
    findings_report = getattr(self, "_results_findings_widget", None)
    if findings_report is not None:
        findings_report.update(
            _module_findings_report(selection, show_empty_analyzers=self._results_show_empty_analyzers())
        )


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
    findings_report = getattr(self, "_results_findings_widget", None)
    if findings_report is None:
        findings_report = _TEXTUAL_STATIC("", id="results-findings-report", markup=False)
        _query_required(self, "#results-findings-host", _TEXTUAL_VERTICAL).mount(findings_report)
        self._results_findings_widget = findings_report
    render_key = record.run_id
    if getattr(self, "_results_tree_render_key", None) != render_key:
        selection = _populate_module_navigation(tree, record)
        self._results_tree_render_key = render_key
        self._results_tree_run_id = record.run_id
        self._selected_results_module = None
        if selection is not None:
            _select_results_module(self, selection)
        else:
            findings_report.update("No findings")
    elif self._selected_results_module is not None:
        findings_report.update(
            _module_findings_report(
                self._selected_results_module, show_empty_analyzers=self._results_show_empty_analyzers()
            )
        )
    self._refresh_shell_state()
    self._write_output("Select a module to inspect its findings.")


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
    tree.root.expand()
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
        self._selected_results_module = None
        self._results_tree_run_id = None
        self._results_tree_render_key = None
        tree = getattr(self, "_results_tree_widget", None)
        if tree is not None:
            tree.reset("No matching runs", data=None)
        findings_report = getattr(self, "_results_findings_widget", None)
        if findings_report is not None:
            findings_report.update("No findings")
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
        def on_tree_node_highlighted(self, event: Any) -> None: ...
        def _current_project_tag(self) -> str: ...
        def _refresh_results_runs_list(self) -> None: ...
        def _render_results_tree(self, record: RunRecord) -> None: ...
        def _render_selected_run(self) -> None: ...
        def _expand_all_results(self) -> None: ...
        def _collapse_all_results(self) -> None: ...
        def _results_show_empty_analyzers(self) -> bool: ...
        def _toggle_results_show_empty_analyzers(self) -> None: ...
        def _delete_selected_run(self) -> None: ...
        def _refresh_results_view(self) -> None: ...
else:

    class _TextualResultsMixin:
        """Provides the Results view: run selection and the results tree."""

        on_tree_node_selected = on_tree_node_selected
        on_tree_node_highlighted = on_tree_node_highlighted
        _current_project_tag = _current_project_tag
        _refresh_results_runs_list = _refresh_results_runs_list
        _render_results_tree = _render_results_tree
        _render_selected_run = _render_selected_run
        _expand_all_results = _expand_all_results
        _collapse_all_results = _collapse_all_results
        _results_show_empty_analyzers = _results_show_empty_analyzers
        _toggle_results_show_empty_analyzers = _toggle_results_show_empty_analyzers
        _delete_selected_run = _delete_selected_run
        _refresh_results_view = _refresh_results_view
