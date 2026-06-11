from __future__ import annotations

import inspect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from . import _app_analysis_catalog as analysis_catalog


@dataclass(frozen=True)
class AnalysisPlanSkip:
    entry_id: str
    label: str
    reason: str


@dataclass(frozen=True)
class AnalysisMissingHandler:
    step_id: str
    label: str
    handler_name: str
    source_entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class PlannedAnalysisStep:
    step_id: str
    label: str
    description: str
    execution: analysis_catalog.AnalysisExecutionSpec
    source_entry_ids: tuple[str, ...]
    source_labels: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisPlan:
    selected_entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...]
    steps: tuple[PlannedAnalysisStep, ...]
    skipped_entries: tuple[AnalysisPlanSkip, ...]
    missing_handlers: tuple[AnalysisMissingHandler, ...]
    unknown_entry_ids: tuple[str, ...]

    @property
    def executable_steps(self) -> tuple[PlannedAnalysisStep, ...]:
        blocked = {item.step_id for item in self.missing_handlers}
        return tuple(step for step in self.steps if step.step_id not in blocked)

    @property
    def is_runnable(self) -> bool:
        return not self.missing_handlers and bool(self.executable_steps)


def available_handler_names(app_module: Any | None) -> frozenset[str]:
    if app_module is None:
        return frozenset()
    names: set[str] = set()
    for name in dir(app_module):
        try:
            value = inspect.getattr_static(app_module, name)
        except AttributeError:
            continue
        if callable(value):
            names.add(name)
    return frozenset(names)


def plan_analysis_entries(
    selected_entry_ids: Iterable[str],
    *,
    analyzer_specs: Sequence[Any] = (),
    available_handler_names: Iterable[str] | None = None,
) -> AnalysisPlan:
    ordered_catalog_entries = analysis_catalog.analysis_catalog_entries(analyzer_specs=analyzer_specs)
    entry_map = {entry.entry_id: entry for entry in ordered_catalog_entries}

    seen_selected_ids: set[str] = set()
    selected_entries_unordered: list[analysis_catalog.AnalysisCatalogEntry] = []
    unknown_entry_ids: list[str] = []
    for entry_id in selected_entry_ids:
        if entry_id in seen_selected_ids:
            continue
        seen_selected_ids.add(entry_id)
        entry = entry_map.get(entry_id)
        if entry is None:
            unknown_entry_ids.append(entry_id)
            continue
        selected_entries_unordered.append(entry)

    selected_lookup = {entry.entry_id for entry in selected_entries_unordered}
    selected_entries = tuple(entry for entry in ordered_catalog_entries if entry.entry_id in selected_lookup)

    kept_entries, skipped_entries = _apply_exclusivity(selected_entries)
    steps, dedupe_skips = _dedupe_steps(kept_entries)
    missing_handlers = _validate_missing_handlers(steps, available_handler_names)

    return AnalysisPlan(
        selected_entries=selected_entries,
        steps=steps,
        skipped_entries=skipped_entries + dedupe_skips,
        missing_handlers=missing_handlers,
        unknown_entry_ids=tuple(unknown_entry_ids),
    )


def render_analysis_plan_summary(plan: AnalysisPlan) -> str:
    if not plan.selected_entries and not plan.unknown_entry_ids:
        return "No analyses selected."

    lines = [
        f"Selected entries: {len(plan.selected_entries)}",
        f"Planned steps: {len(plan.steps)}",
    ]

    if plan.steps:
        blocked = {item.step_id for item in plan.missing_handlers}
        lines.append("")
        lines.append("Execution order")
        for index, step in enumerate(plan.steps, start=1):
            blocked_suffix = " (missing handler)" if step.step_id in blocked else ""
            lines.append(f"{index}. {step.label}{blocked_suffix}")

    if plan.skipped_entries:
        lines.append("")
        lines.append("Normalized overlaps")
        for item in plan.skipped_entries:
            lines.append(f"- {item.label}: {item.reason}")

    if plan.unknown_entry_ids:
        lines.append("")
        lines.append("Unknown selections")
        for entry_id in plan.unknown_entry_ids:
            lines.append(f"- {entry_id}")

    if plan.missing_handlers:
        lines.append("")
        lines.append("Missing handlers")
        for item in plan.missing_handlers:
            lines.append(f"- {item.label}: {item.handler_name}")

    return "\n".join(lines)


def _apply_exclusivity(
    selected_entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
) -> tuple[tuple[analysis_catalog.AnalysisCatalogEntry, ...], tuple[AnalysisPlanSkip, ...]]:
    group_members: dict[str, list[analysis_catalog.AnalysisCatalogEntry]] = {}
    for entry in selected_entries:
        group_id = entry.execution.exclusive_group_id
        if group_id is None:
            continue
        group_members.setdefault(group_id, []).append(entry)

    processed_groups: set[str] = set()
    kept_entries: list[analysis_catalog.AnalysisCatalogEntry] = []
    skipped_entries: list[AnalysisPlanSkip] = []
    for entry in selected_entries:
        group_id = entry.execution.exclusive_group_id
        if group_id is None:
            kept_entries.append(entry)
            continue
        if group_id in processed_groups:
            continue
        processed_groups.add(group_id)

        entries = group_members[group_id]
        suite_entries = tuple(item for item in entries if item.execution.suite_role == "suite")
        if not suite_entries:
            kept_entries.extend(entries)
            continue

        kept_entries.extend(suite_entries)
        suite_label = (
            suite_entries[0].label if len(suite_entries) == 1 else ", ".join(item.label for item in suite_entries)
        )
        for item in entries:
            if item.execution.suite_role == "suite":
                continue
            skipped_entries.append(
                AnalysisPlanSkip(
                    entry_id=item.entry_id,
                    label=item.label,
                    reason=f"Covered by {suite_label}.",
                )
            )

    return tuple(kept_entries), tuple(skipped_entries)


def _dedupe_steps(
    selected_entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
) -> tuple[tuple[PlannedAnalysisStep, ...], tuple[AnalysisPlanSkip, ...]]:
    steps_by_id: dict[str, PlannedAnalysisStep] = {}
    step_order: list[str] = []
    skipped_entries: list[AnalysisPlanSkip] = []

    for entry in selected_entries:
        step_id = entry.execution.normalized_step_id
        existing = steps_by_id.get(step_id)
        if existing is None:
            steps_by_id[step_id] = PlannedAnalysisStep(
                step_id=step_id,
                label=entry.execution.step_label or entry.label,
                description=entry.description,
                execution=entry.execution,
                source_entry_ids=(entry.entry_id,),
                source_labels=(entry.label,),
            )
            step_order.append(step_id)
            continue

        merged_execution = _merge_execution_specs(existing.execution, entry.execution)
        steps_by_id[step_id] = replace(
            existing,
            execution=merged_execution,
            source_entry_ids=(*existing.source_entry_ids, entry.entry_id),
            source_labels=(*existing.source_labels, entry.label),
        )
        skipped_entries.append(
            AnalysisPlanSkip(
                entry_id=entry.entry_id,
                label=entry.label,
                reason=f"Merged into {existing.label}.",
            )
        )

    return tuple(steps_by_id[step_id] for step_id in step_order), tuple(skipped_entries)


def _merge_execution_specs(
    existing: analysis_catalog.AnalysisExecutionSpec,
    incoming: analysis_catalog.AnalysisExecutionSpec,
) -> analysis_catalog.AnalysisExecutionSpec:
    merged_issue_kind_names = existing.selected_issue_kind_names
    if incoming.selected_issue_kind_names is not None:
        merged_issue_kind_names = frozenset(
            set(existing.selected_issue_kind_names or ()) | set(incoming.selected_issue_kind_names)
        )

    merged_variable_issue_kinds = existing.variable_issue_kinds
    if incoming.variable_issue_kinds is not None:
        merged_variable_issue_kinds = frozenset(
            set(existing.variable_issue_kinds or ()) | set(incoming.variable_issue_kinds)
        )

    if (
        merged_issue_kind_names == existing.selected_issue_kind_names
        and merged_variable_issue_kinds == existing.variable_issue_kinds
        and (existing.step_label or incoming.step_label) == existing.step_label
    ):
        return existing

    return replace(
        existing,
        step_label=existing.step_label or incoming.step_label,
        selected_issue_kind_names=merged_issue_kind_names,
        variable_issue_kinds=merged_variable_issue_kinds,
    )


def _validate_missing_handlers(
    steps: tuple[PlannedAnalysisStep, ...],
    available_names: Iterable[str] | None,
) -> tuple[AnalysisMissingHandler, ...]:
    if available_names is None:
        return ()
    available = frozenset(available_names)
    return tuple(
        AnalysisMissingHandler(
            step_id=step.step_id,
            label=step.label,
            handler_name=step.execution.handler_name,
            source_entry_ids=step.source_entry_ids,
        )
        for step in steps
        if step.execution.handler_name not in available
    )
