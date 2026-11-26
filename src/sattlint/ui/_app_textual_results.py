from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.style import Style
from rich.text import Text

from ..application.findings import AnalysisFinding, finding_data_key, kind_human_label
from ..models._variable_issues import (
    DECLARATION_ROLE_LOCAL_VARIABLE,
    DECLARATION_ROLE_MODULE_PARAMETER,
    IssueKind,
)
from ..runs import (
    RunAnalyzerRecord,
    RunModuleRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
    delete_run,
    finding_acknowledgement_key,
    list_runs,
    load_run,
    load_run_acknowledgements,
    save_run_acknowledgements,
)
from ._app_textual_shared import (
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_QUERY_ERRORS,
    _TEXTUAL_STATIC,
    _TEXTUAL_TREE,
    _TEXTUAL_VERTICAL,
    InteractionRequest,
    _query_required,
)

if _TEXTUAL_TREE is not None:
    from rich.cells import cell_len as _cell_len  # type: ignore[import-untyped]

    _TREE_TOGGLE_WIDTH = _cell_len(str(_TEXTUAL_TREE.ICON_NODE))
    _TREE_LEAF_ICON = "\u2022 "
    _TREE_LEAF_WIDTH = _cell_len(_TREE_LEAF_ICON)

    class _ResultsTree(_TEXTUAL_TREE):  # pyright: ignore[reportUntypedBaseClass]
        """Results tree that marks leaves and measures labels cheaply.

        A leaf node carries a dot instead of the expand triangle, so it is
        clear it has nothing to open. Textual's ``Tree._build`` re-measures
        every expanded label on each expand/collapse through ``render_label``
        (Rich ``Text`` copy/stylize/assemble). Overriding ``get_label_width``
        to measure the plain label avoids that work; the width is memoized per
        node and invalidated when the node's label or expand affordance
        changes.
        """

        def render_label(self, node: Any, base_style: Style, style: Style) -> Text:
            rendered = super().render_label(node, base_style, style)
            if node.allow_expand:
                return rendered
            return Text.assemble((_TREE_LEAF_ICON, base_style), rendered)

        def get_label_width(self, node: Any) -> int:
            label = node.label
            text = label.plain if isinstance(label, Text) else str(label)
            allow_expand = bool(node.allow_expand)
            cache_key = (text, allow_expand)
            cached = getattr(node, "_sattlint_label_width", None)
            if cached is not None and cached[0] == cache_key:
                return int(cached[1])
            width = _cell_len(text) + (_TREE_TOGGLE_WIDTH if allow_expand else _TREE_LEAF_WIDTH)
            node._sattlint_label_width = (cache_key, width)
            return width

else:  # pragma: no cover - optional dependency path
    _ResultsTree: Any = None


_DECLARATION_ROLE_LABELS: dict[str, str] = {
    DECLARATION_ROLE_MODULE_PARAMETER: "module parameter",
    DECLARATION_ROLE_LOCAL_VARIABLE: "local variable",
}
_DECLARATION_ROLE_ORDER: tuple[str, ...] = (
    DECLARATION_ROLE_MODULE_PARAMETER,
    DECLARATION_ROLE_LOCAL_VARIABLE,
)
_LEGACY_DECLARATION_ROLE_RE = re.compile(r"^\[[^\]]+\]\s+(localvariable|moduleparameter)\s+'")


def _new_results_tree() -> Any:
    tree = _ResultsTree("", id="results-tree")
    # Selecting a node reveals its findings; only the expand affordance (or
    # space) changes the tree shape. Textual's default also toggles on select.
    tree.auto_expand = False
    return tree


@dataclass(frozen=True, slots=True)
class _ModuleSelection:
    target: RunTargetRecord
    path: tuple[str, ...]
    aliases: dict[str, tuple[str, ...]]


@dataclass(slots=True)
class _ModuleNavigation:
    """The module tree nodes and the state needed to recolor them."""

    first_selection: _ModuleSelection | None = None
    nodes: dict[tuple[str, ...], Any] = field(default_factory=dict)
    labels: dict[tuple[str, ...], str] = field(default_factory=dict)
    finding_paths: set[tuple[str, ...]] = field(default_factory=set)


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
    if finding.kind == "unused_datatype" and finding.module_path:
        return finding.module_path[-1].removeprefix("DataType:")
    if finding.kind == "unused_datatype_field" and finding.module_path:
        datatype = finding.module_path[-1].removeprefix("DataType:")
        field_prefix = f"datatype '{datatype}'."
        return message.removeprefix(field_prefix)
    data = finding.data
    if finding.kind in {"field_read_only", "field_never_read"}:
        variable = data.get("variable_name")
        field = data.get("field_path")
        return f"{variable}.{field}" if variable and field else message
    context = data.get("relation", data.get("context"))
    if context:
        return str(context)
    return message


def _site_label(finding: AnalysisFinding) -> str | None:
    """The containing EquationBlock / Sequence / step for a finding, if known."""
    site = finding.data.get("site")
    if site:
        return str(site)
    return None


def _finding_declaration_role(finding: AnalysisFinding) -> str | None:
    """The declaration kind a finding belongs to, when the run recorded it.

    Runs stored before the field existed carry the role only in the message
    produced by the variable issue text helper, so fall back to that shape.
    """
    role = finding.data.get("declaration_role")
    if isinstance(role, str) and role in _DECLARATION_ROLE_LABELS:
        return role
    match = _LEGACY_DECLARATION_ROLE_RE.match(finding.message)
    return match.group(1) if match is not None else None


def _declaration_role_sort_key(role: str | None) -> int:
    if role in _DECLARATION_ROLE_ORDER:
        return _DECLARATION_ROLE_ORDER.index(role)
    return len(_DECLARATION_ROLE_ORDER)


def _finding_group_label(kind: str, role: str | None) -> str:
    if role is None:
        return kind_human_label(kind)
    role_label = _DECLARATION_ROLE_LABELS[role]
    if kind == IssueKind.UNUSED.value:
        return f"Unused {role_label}"
    return f"{kind_human_label(kind)} — {role_label}"


def _module_node_label(label: str, *, has_findings: bool, fully_acknowledged: bool = False) -> str | Text:
    if fully_acknowledged:
        return Text(label, style="bold #1b7f3a")
    return Text(label, style="bold #674600") if has_findings else label


def _finding_label(finding: AnalysisFinding, *, occurrence_count: int = 1) -> str:
    label = _context_label(finding)
    if label.casefold() == kind_human_label(finding.kind).casefold():
        label = _LEADING_MODULE_PATH_RE.sub("", finding.message).strip()
    if occurrence_count > 1:
        label += f" \u00d7{occurrence_count}"
    return label


def _readable_site(site: str) -> str:
    parts: list[str] = []
    for segment in site.split(" > "):
        tokens = segment.split(":")
        if tokens[0] in {"SQ", "SUBSEQ"} and len(tokens) == 2:
            parts.append(tokens[1])
        elif tokens[0] == "STEP" and len(tokens) == 3:
            parts.extend((tokens[1], tokens[2].capitalize()))
        elif tokens[0] in {"EQ", "TRANS", "TRANS-SUB"} and len(tokens) == 2:
            label = "Equation" if tokens[0] == "EQ" else "Transition"
            parts.append(f"{label} {tokens[1]}")
        elif tokens[0] in {"ALT", "PAR"} and len(tokens) == 3 and tokens[2].isdigit():
            label = "Alternative" if tokens[0] == "ALT" else "Parallel branch"
            parts.append(f"{label} {int(tokens[2]) + 1}")
        else:
            parts.append(segment)
    return " \u203a ".join(parts)


def _finding_details(finding: AnalysisFinding) -> list[str]:
    details: list[str] = []
    message = _LEADING_MODULE_PATH_RE.sub("", finding.message).strip()
    context = _finding_label(finding)
    if message and context.casefold() not in message.casefold():
        details.append(message)
    previous_sites = finding.data.get("previous_sites")
    if isinstance(previous_sites, (list, tuple)):
        details.extend(f"Previous write: {_readable_site(str(site))}" for site in previous_sites)
    for key, label in (("target_display_name", "Target"), ("source_display_name", "Source")):
        value = finding.data.get(key)
        if value:
            details.append(f"{label}: {value}")
    return details


def _finding_groups(
    analyzer: RunAnalyzerRecord,
) -> list[tuple[str, str | None, list[tuple[AnalysisFinding, int]]]]:
    """Group findings by issue kind, declaration role, message, and site.

    Identical findings repeated at the same site across instance paths are
    represented once with an occurrence count. Kinds keep their first-seen
    order; within a kind, module parameters come before local variables, and
    findings with no declaration kind come last.
    """
    counts: dict[tuple[str, str | None, str, str | None, str], int] = {}
    representatives: dict[tuple[str, str | None, str, str | None, str], AnalysisFinding] = {}
    order: list[tuple[str, str | None, str, str | None, str]] = []
    for finding in analyzer.findings:
        key = (
            finding.kind,
            _finding_declaration_role(finding),
            finding.message,
            _site_label(finding),
            finding_data_key(finding),
        )
        if key not in representatives:
            representatives[key] = finding
            counts[key] = 0
            order.append(key)
        counts[key] += 1

    kind_order: list[str] = []
    role_order: dict[str, list[str | None]] = {}
    for kind, role, _message, _site, _data in order:
        if kind not in role_order:
            kind_order.append(kind)
            role_order[kind] = []
        if role not in role_order[kind]:
            role_order[kind].append(role)

    groups: list[tuple[str, str | None, list[tuple[AnalysisFinding, int]]]] = []
    for kind in kind_order:
        roles = sorted(role_order[kind], key=_declaration_role_sort_key)
        for role in roles:
            items = [(representatives[key], counts[key]) for key in order if key[0] == kind and key[1] == role]
            if items:
                groups.append((kind, role, items))
    return groups


def _finding_module_path(finding: AnalysisFinding, analyzer: RunAnalyzerRecord) -> tuple[str, ...]:
    return finding.module_path if finding.module_path else (analyzer.name,)


def _analyzer_label(analyzer: RunAnalyzerRecord) -> str:
    label = analyzer.name
    return label if analyzer.status == "completed" else f"{label} — {analyzer.status}"


def _mark_leaf_nodes(root: Any) -> None:
    """Disallow expansion on nodes without children after the tree is built.

    Nodes are created before their children are attached, so the final child
    count decides which nodes are leaves.
    """
    for node in _walk_tree_nodes(root):
        node.allow_expand = bool(node.children)


def _auto_expand_single_child_chains(root: Any) -> None:
    """Expand every descendant that has exactly one child.

    Chains of single-child branch nodes (common for nested module paths and
    sites) carry no navigation choice, so opening them up front saves the user
    from clicking through each level. The root is left untouched so the hidden
    top level is not implicitly expanded.
    """
    stack = list(root.children)
    while stack:
        node = stack.pop()
        if len(node.children) == 1:
            node.expand()
        stack.extend(node.children)


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
    finding_prefixes: set[tuple[str, ...]],
    aliases: dict[str, tuple[str, ...]],
    fully_acknowledged: set[tuple[str, ...]],
    navigation: _ModuleNavigation,
) -> None:
    for child in children:
        child_path = (*path, child.name)
        if tuple(part.casefold() for part in child_path) not in finding_prefixes:
            continue
        merged_paths = [child_path]
        final = child
        retained_children = tuple(
            descendant
            for descendant in final.children
            if tuple(part.casefold() for part in (*child_path, descendant.name)) in finding_prefixes
        )
        while len(retained_children) == 1 and tuple(part.casefold() for part in child_path) not in finding_paths:
            final = retained_children[0]
            child_path = (*child_path, final.name)
            merged_paths.append(child_path)
            retained_children = tuple(
                descendant
                for descendant in final.children
                if tuple(part.casefold() for part in (*child_path, descendant.name)) in finding_prefixes
            )
        label = _module_label(final)
        if len(merged_paths) > 1:
            label = f"{'.'.join(segment[-1] for segment in merged_paths)}{label.removeprefix(final.name)}"
        child_key = tuple(part.casefold() for part in child_path)
        child_node = parent.add(
            _module_node_label(
                label,
                has_findings=child_key in finding_paths,
                fully_acknowledged=child_key in fully_acknowledged,
            ),
            data=_ModuleSelection(target, child_path, aliases),
        )
        _record_navigation_node(navigation, child_key, label, child_node)
        for merged_path in merged_paths:
            branches[tuple(part.casefold() for part in merged_path)] = child_node
        _add_module_children(
            child_node,
            retained_children,
            child_path,
            target,
            branches,
            finding_paths,
            finding_prefixes,
            aliases,
            fully_acknowledged,
            navigation,
        )


def _fallback_module_children(
    path: tuple[str, ...], path_children: dict[tuple[str, ...], dict[str, str]]
) -> tuple[RunModuleRecord, ...]:
    key = tuple(part.casefold() for part in path)
    return tuple(
        RunModuleRecord(name=name, children=_fallback_module_children((*path, name), path_children))
        for name in path_children.get(key, {}).values()
    )


def _results_targets(record: RunRecord) -> list[RunTargetRecord]:
    targets = list(record.targets)
    if any(analyzer.findings for analyzer in record.project_analyzers):
        targets.append(
            RunTargetRecord(
                target_name="Project",
                analyzers=record.project_analyzers,
            )
        )
    return targets


def _target_root_name(target: RunTargetRecord) -> str:
    module = target.module
    roots = {
        finding.module_path[0] for analyzer in target.analyzers for finding in analyzer.findings if finding.module_path
    }
    return (
        module.name.split(":", 1)[-1]
        if module is not None
        else next(iter(roots))
        if len(roots) == 1
        else target.target_name
    )


def _fully_acknowledged_paths(record: RunRecord, acknowledged: frozenset[str]) -> set[tuple[str, ...]]:
    """Normalized module paths whose displayed findings are all acknowledged."""
    fully_acknowledged: set[tuple[str, ...]] = set()
    for target in _results_targets(record):
        if not any(analyzer.findings for analyzer in target.analyzers):
            continue
        root_name = _target_root_name(target)
        aliases = _module_path_aliases(target, root_name)
        keys_by_path: dict[tuple[str, ...], list[str]] = {}
        for analyzer in target.analyzers:
            findings_by_path: dict[tuple[str, ...], list[AnalysisFinding]] = {}
            for finding in analyzer.findings:
                path = _normalized_finding_path(target, root_name, finding, analyzer, aliases)
                findings_by_path.setdefault(path, []).append(finding)
            for path, findings in findings_by_path.items():
                groups = _finding_groups(
                    RunAnalyzerRecord(
                        key=analyzer.key,
                        name=analyzer.name,
                        status=analyzer.status,
                        findings=findings,
                    )
                )
                for _kind, declaration_role, items in groups:
                    for finding, _occurrence_count in items:
                        key = finding_acknowledgement_key(
                            target_name=target.target_name,
                            analyzer_key=analyzer.key,
                            finding=finding,
                            declaration_role=declaration_role,
                        )
                        keys_by_path.setdefault(path, []).append(key)
        for path, keys in keys_by_path.items():
            if keys and all(key in acknowledged for key in keys):
                fully_acknowledged.add(tuple(part.casefold() for part in path))
    return fully_acknowledged


def _populate_module_navigation(
    tree: Any,
    record: RunRecord,
    *,
    acknowledged: frozenset[str] = frozenset(),
) -> _ModuleNavigation:
    tree.reset("", data=None)
    tree.show_root = False
    navigation = _ModuleNavigation()
    fully_acknowledged = _fully_acknowledged_paths(record, acknowledged)
    for target in _results_targets(record):
        if not any(analyzer.findings for analyzer in target.analyzers):
            continue
        module = target.module
        root_name = _target_root_name(target)
        aliases = _module_path_aliases(target, root_name)
        selection = _ModuleSelection(target, (root_name,), aliases)
        if navigation.first_selection is None:
            navigation.first_selection = selection
        root_label = (
            _module_label(module)
            if module
            else f"{target.target_name}:{root_name}"
            if root_name.casefold() != target.target_name.casefold()
            else target.target_name
        )
        finding_paths = {
            tuple(part.casefold() for part in _normalized_finding_path(target, root_name, finding, analyzer, aliases))
            for analyzer in target.analyzers
            for finding in analyzer.findings
        }
        navigation.finding_paths.update(finding_paths)
        finding_prefixes = {path[:length] for path in finding_paths for length in range(1, len(path) + 1)}
        root_key = (root_name.casefold(),)
        root_node = tree.root.add(
            _module_node_label(
                root_label,
                has_findings=root_key in finding_paths,
                fully_acknowledged=root_key in fully_acknowledged,
            ),
            data=selection,
        )
        _record_navigation_node(navigation, root_key, root_label, root_node)
        branches = {root_key: root_node}

        if module is not None:
            _add_module_children(
                root_node,
                module.children,
                selection.path,
                target,
                branches,
                finding_paths,
                finding_prefixes,
                aliases,
                fully_acknowledged,
                navigation,
            )
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
                finding_prefixes,
                aliases,
                fully_acknowledged,
                navigation,
            )
        for analyzer in target.analyzers:
            for finding in analyzer.findings:
                path = _normalized_finding_path(target, root_name, finding, analyzer, aliases)
                for length in range(2, len(path) + 1):
                    prefix = path[:length]
                    key = tuple(part.casefold() for part in prefix)
                    if key not in branches:
                        parent_key = tuple(part.casefold() for part in prefix[:-1])
                        node = branches[parent_key].add(
                            _module_node_label(
                                prefix[-1],
                                has_findings=key in finding_paths,
                                fully_acknowledged=key in fully_acknowledged,
                            ),
                            data=_ModuleSelection(target, prefix, aliases),
                        )
                        branches[key] = node
                        _record_navigation_node(navigation, key, prefix[-1], node)
    _mark_leaf_nodes(tree.root)
    _auto_expand_single_child_chains(tree.root)
    tree.root.expand()
    return navigation


def _record_navigation_node(
    navigation: _ModuleNavigation,
    key: tuple[str, ...],
    label: str,
    node: Any,
) -> None:
    navigation.nodes[key] = node
    navigation.labels[key] = label


def _refresh_results_module_colors(self: Any, acknowledged: frozenset[str]) -> None:
    """Recolor module nodes after an acknowledgement toggle."""
    navigation = getattr(self, "_results_navigation", None)
    record = getattr(self, "_selected_run_record", None)
    if navigation is None or record is None:
        return
    fully_acknowledged = _fully_acknowledged_paths(record, acknowledged)
    for key, node in navigation.nodes.items():
        node.label = _module_node_label(
            navigation.labels[key],
            has_findings=key in navigation.finding_paths,
            fully_acknowledged=key in fully_acknowledged,
        )
        refresh = getattr(node, "refresh", None)
        if callable(refresh):
            refresh()


def _build_module_findings_report(
    selection: _ModuleSelection,
    *,
    show_empty_analyzers: bool,
    expanded_details: frozenset[int] = frozenset(),
    acknowledged: frozenset[str] = frozenset(),
) -> tuple[Text, tuple[str, ...]]:
    target = selection.target
    path = tuple(part.casefold() for part in selection.path)
    lines: list[Text] = []
    detail_index = 0
    acknowledgement_keys: list[str] = []
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
            lines.append(Text(""))
        lines.append(Text(_analyzer_label(analyzer), style="bold #001ba3"))
        if not matching:
            lines.append(Text("  No findings", style="dim"))
            continue
        for kind, declaration_role, items in _finding_groups(
            RunAnalyzerRecord(key=analyzer.key, name=analyzer.name, status=analyzer.status, findings=matching)
        ):
            lines.append(
                Text(
                    f"{_finding_group_label(kind, declaration_role)} ({sum(count for _, count in items)})",
                    style="bold #674600",
                )
            )
            for finding_index, (finding, occurrence_count) in enumerate(items):
                if finding_index:
                    lines.append(Text(""))
                key = finding_acknowledgement_key(
                    target_name=target.target_name,
                    analyzer_key=analyzer.key,
                    finding=finding,
                    declaration_role=declaration_role,
                )
                acknowledgement_keys.append(key)
                is_acknowledged = key in acknowledged
                marker = "\u2713 " if is_acknowledged else ""
                label_style = "dim bold" if is_acknowledged else "bold"
                lines.append(
                    Text(
                        f"  {marker}{_finding_label(finding, occurrence_count=occurrence_count)}",
                        style=label_style,
                    )
                )
                site = _site_label(finding)
                if site:
                    lines.append(Text(f"  {_readable_site(site)}", style="#38545a"))
                controls = Text("  ")
                acknowledge_control = Text(
                    "Unacknowledge" if is_acknowledged else "Acknowledge",
                    style="dim underline #58787e" if is_acknowledged else "underline #001ba3",
                )
                acknowledge_control.stylize(Style(meta={"@click": f"toggle_ack({len(acknowledgement_keys) - 1})"}))
                controls.append_text(acknowledge_control)
                details = _finding_details(finding)
                if details:
                    controls.append_text(Text("  \u00b7  ", style="dim"))
                    expanded = detail_index in expanded_details
                    details_control = Text(
                        "Hide details" if expanded else "Details",
                        style="underline #001ba3",
                    )
                    details_control.stylize(Style(meta={"@click": f"toggle_details({detail_index})"}))
                    controls.append_text(details_control)
                lines.append(controls)
                if details and detail_index in expanded_details:
                    lines.extend(Text(f"  {detail}") for detail in details)
                detail_index += 1
    report = Text("\n").join(lines) if lines else Text("No findings for this module", style="dim")
    return report, tuple(acknowledgement_keys)


def _module_findings_report(
    selection: _ModuleSelection,
    *,
    show_empty_analyzers: bool,
    expanded_details: frozenset[int] = frozenset(),
    acknowledged: frozenset[str] = frozenset(),
) -> Text:
    report, _acknowledgement_keys = _build_module_findings_report(
        selection,
        show_empty_analyzers=show_empty_analyzers,
        expanded_details=expanded_details,
        acknowledged=acknowledged,
    )
    return report


if _TEXTUAL_STATIC is not None:

    class _FindingsReport(_TEXTUAL_STATIC):
        def __init__(
            self,
            content: str = "",
            *,
            on_toggle_ack: Callable[[str, str], None],
            id: str | None = None,
            markup: bool = True,
        ) -> None:
            super().__init__(content, id=id, markup=markup)
            self._on_toggle_ack = on_toggle_ack
            self._run_id = ""
            self._acknowledged: frozenset[str] = frozenset()
            self._acknowledgement_keys: tuple[str, ...] = ()

        def set_selection(
            self,
            selection: _ModuleSelection,
            *,
            show_empty_analyzers: bool,
            run_id: str,
            acknowledged: frozenset[str],
        ) -> None:
            self._selection = selection
            self._show_empty = show_empty_analyzers
            self._run_id = run_id
            self._acknowledged = acknowledged
            self._expanded_details: set[int] = set()
            self._refresh_report()

        def set_acknowledged(self, acknowledged: frozenset[str], *, run_id: str) -> None:
            self._run_id = run_id
            self._acknowledged = acknowledged
            self._refresh_report()

        def _refresh_report(self) -> None:
            report, acknowledgement_keys = _build_module_findings_report(
                self._selection,
                show_empty_analyzers=self._show_empty,
                expanded_details=frozenset(self._expanded_details),
                acknowledged=self._acknowledged,
            )
            self._acknowledgement_keys = acknowledgement_keys
            self.update(report)

        def action_toggle_details(self, index: int) -> None:
            if index in self._expanded_details:
                self._expanded_details.remove(index)
            else:
                self._expanded_details.add(index)
            self._refresh_report()

        def action_toggle_ack(self, index: int) -> None:
            if 0 <= index < len(self._acknowledgement_keys):
                self._on_toggle_ack(self._run_id, self._acknowledgement_keys[index])

else:
    _FindingsReport = None


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
        findings_report.set_selection(
            selection,
            show_empty_analyzers=self._results_show_empty_analyzers(),
            run_id=getattr(self, "_results_tree_run_id", "") or "",
            acknowledged=getattr(self, "_results_acknowledged", frozenset()),
        )


def _current_project_path(self: Any) -> str:
    """The open project file, or an empty string when no project is open.

    Only the project path can identify a stored run. The user config file is
    never a run's project, so runs started before a project is opened are not
    attributed to it.
    """
    raw_path = getattr(self, "_project_path", None)
    return "" if raw_path is None else str(raw_path)


def _results_run_summaries(self: Any) -> tuple[RunSummary, ...]:
    """Stored runs that belong to the open project file.

    A run stored before the project path was recorded cannot be attributed to a
    project, so it is not listed. Its record stays on disk until it ages out.
    Paths are compared case-insensitively because a stored run may come from a
    case-insensitive filesystem that reported a different spelling.
    """
    project_path = self._current_project_path()
    if not project_path:
        return ()
    project_key = project_path.casefold()
    return tuple(summary for summary in list_runs() if summary.project_path.casefold() == project_key)


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
    previous_run_id = getattr(self, "_results_tree_run_id", None)
    self._selected_run_record = record
    tree = getattr(self, "_results_tree_widget", None)
    if tree is None:
        tree = _new_results_tree()
        tree_host = _query_required(self, "#results-tree-host", _TEXTUAL_VERTICAL)
        tree_host.mount(tree)
        self._results_tree_widget = tree
        self._results_tree_render_key = None
        self._results_tree_run_id = None
    findings_report = getattr(self, "_results_findings_widget", None)
    if findings_report is None:
        findings_report = _FindingsReport(
            "",
            id="results-findings-report",
            markup=False,
            on_toggle_ack=self._toggle_results_acknowledgement,
        )
        _query_required(self, "#results-findings-host", _TEXTUAL_VERTICAL).mount(findings_report)
        self._results_findings_widget = findings_report
    render_key = record.run_id
    if getattr(self, "_results_tree_render_key", None) != render_key:
        acknowledged = load_run_acknowledgements(record.run_id)
        navigation = _populate_module_navigation(tree, record, acknowledged=acknowledged)
        self._results_navigation = navigation
        self._results_tree_render_key = render_key
        self._results_tree_run_id = record.run_id
        self._results_acknowledged = acknowledged
        self._selected_results_module = None
        if navigation.first_selection is not None:
            _select_results_module(self, navigation.first_selection)
        else:
            findings_report.update("No findings")
    elif self._selected_results_module is not None:
        findings_report.set_selection(
            self._selected_results_module,
            show_empty_analyzers=self._results_show_empty_analyzers(),
            run_id=record.run_id,
            acknowledged=getattr(self, "_results_acknowledged", frozenset()),
        )
    self._refresh_shell_state()
    if record.run_id != previous_run_id:
        self._write_output("Select a module to inspect its findings.")


def _toggle_results_acknowledgement(self: Any, run_id: str, key: str) -> None:
    """Toggle one acknowledged finding on the selected run and persist it."""
    if not run_id or run_id != getattr(self, "_results_tree_run_id", None):
        return
    acknowledged = set(getattr(self, "_results_acknowledged", frozenset()))
    if key in acknowledged:
        acknowledged.remove(key)
        message = "Acknowledgement cleared."
    else:
        acknowledged.add(key)
        message = "Acknowledged finding."
    updated = frozenset(acknowledged)
    self._results_acknowledged = updated
    if not save_run_acknowledgements(run_id, updated):
        message = f"{message} It could not be saved to the cache."
    findings_report = getattr(self, "_results_findings_widget", None)
    if findings_report is not None:
        findings_report.set_acknowledged(updated, run_id=run_id)
    _refresh_results_module_colors(self, updated)
    self._write_output(message)


def _request_results_run_selection(self: Any, run_id: str) -> None:
    """Load the run the user highlighted in the runs list, deferred.

    A highlight used to read the run from disk and rebuild the tree inline, so
    holding an arrow key down through a long list paid for every run on the way
    past. The request is deferred and coalesced instead: only the run the user
    settles on is read and rendered.
    """
    if not run_id or run_id == getattr(self, "_results_tree_run_id", None):
        return
    if run_id == self._results_pending_run_id:
        return
    self._results_pending_run_id = run_id
    self.call_after_refresh(self._apply_pending_results_run_selection)


def _apply_pending_results_run_selection(self: Any) -> None:
    run_id = self._results_pending_run_id
    self._results_pending_run_id = None
    if run_id is None or run_id == getattr(self, "_results_tree_run_id", None):
        return
    record = load_run(run_id)
    if record is None:
        self._report_error("Could not load run", "That run could not be loaded.")
        return
    self._selected_run_record = record
    self._render_selected_run()


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
    tree.root.expand()
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
        self._results_acknowledged = frozenset()
        tree = getattr(self, "_results_tree_widget", None)
        if tree is not None:
            tree.reset("No matching runs", data=None)
        findings_report = getattr(self, "_results_findings_widget", None)
        if findings_report is not None:
            findings_report.update("No findings")
        if not bool(getattr(self, "_results_empty_state_written", False)):
            self._results_empty_state_written = True
            self._write_output("No saved runs for this configuration. Run analyses from the Analyze view.")
        return
    self._results_empty_state_written = False
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
    if self._active_request is not None:
        return

    run_label = _format_run_timestamp(record.finished_at)

    def _do_delete(response: object) -> None:
        if not bool(response):
            self._write_output("Delete canceled.")
            return
        if not delete_run(record.run_id):
            self._write_output("That run could not be deleted.")
            return
        self._write_output(f"Deleted run {run_label}.")
        self._selected_run_record = None
        self._refresh_results_view()
        self._refresh_shell_state()

    self.present_request(
        InteractionRequest(
            kind="confirm",
            title="Delete run",
            message=f"Delete the stored run from {run_label}? This cannot be undone.",
            note="The run and its results will be removed from the run history.",
        ),
        on_response_fn=_do_delete,
    )


if TYPE_CHECKING:

    class _TextualResultsMixin:
        def on_tree_node_selected(self, event: Any) -> None: ...
        def on_tree_node_highlighted(self, event: Any) -> None: ...
        def _current_project_path(self) -> str: ...
        def _refresh_results_runs_list(self) -> None: ...
        def _render_results_tree(self, record: RunRecord) -> None: ...
        def _render_selected_run(self) -> None: ...
        def _toggle_results_acknowledgement(self, run_id: str, key: str) -> None: ...
        def _request_results_run_selection(self, run_id: str) -> None: ...
        def _apply_pending_results_run_selection(self) -> None: ...
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
        _current_project_path = _current_project_path
        _refresh_results_runs_list = _refresh_results_runs_list
        _render_results_tree = _render_results_tree
        _render_selected_run = _render_selected_run
        _toggle_results_acknowledgement = _toggle_results_acknowledgement
        _request_results_run_selection = _request_results_run_selection
        _apply_pending_results_run_selection = _apply_pending_results_run_selection
        _expand_all_results = _expand_all_results
        _collapse_all_results = _collapse_all_results
        _results_show_empty_analyzers = _results_show_empty_analyzers
        _toggle_results_show_empty_analyzers = _toggle_results_show_empty_analyzers
        _delete_selected_run = _delete_selected_run
        _refresh_results_view = _refresh_results_view
