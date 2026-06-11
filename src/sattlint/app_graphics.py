from __future__ import annotations

import importlib
import json
import logging
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_graphics_menus as graphics_menus_module
from . import _app_graphics_reports as graphics_reports_module
from . import config as config_module
from . import console as console_module
from . import graphics_rules as graphics_rules_module
from ._app_debug import log_debug_exception
from .app_interaction import MenuInteraction
from .docgenerator import classification as documentation_classification_module
from .models.project_graph import ProjectGraph

emit_output = console_module.print_output  # type: ignore[assignment]
log = logging.getLogger("SattLint")

ConfigDict = dict[str, Any]
GraphicsRule = dict[str, Any]
GraphicsRulesConfig = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]
LoadedProjectIterator = Callable[[ConfigDict], Iterator[LoadedProject]]
CollectGraphicsLayoutEntriesForTargetFn = Callable[[str, BasePicture, ProjectGraph], list[GraphicsRule]]
ClassifyDocumentationStructureFn = Callable[..., Any]
DiscoverDocumentationUnitCandidatesFn = Callable[[Any], Sequence[Any]]
_documentation_classification_module: Any = documentation_classification_module

DEFAULT_CLASSIFY_DOCUMENTATION_STRUCTURE_FN = cast(
    ClassifyDocumentationStructureFn,
    _documentation_classification_module.classify_documentation_structure,
)
DEFAULT_DISCOVER_DOCUMENTATION_UNIT_CANDIDATES_FN = cast(
    DiscoverDocumentationUnitCandidatesFn,
    _documentation_classification_module.discover_documentation_unit_candidates,
)


def get_graphics_rules_path(config_path: Path) -> Path:
    return graphics_rules_module.get_graphics_rules_path(config_path)


def load_graphics_rules(config_path: Path, path: Path | None = None) -> tuple[GraphicsRulesConfig, bool]:
    rules_path = path or get_graphics_rules_path(config_path)
    try:
        return graphics_rules_module.load_graphics_rules(rules_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        emit_output(f"Graphics rules unavailable at {rules_path}: {exc}. Using defaults.")
        return graphics_rules_module.normalize_graphics_rules(None), False


def save_graphics_rules(path: Path, rules: GraphicsRulesConfig) -> None:
    graphics_rules_module.save_graphics_rules(path, rules)


def _format_config_scalar(value: object) -> str:
    return graphics_reports_module.format_config_scalar(value)


def _print_config_section(title: str, rows: list[tuple[str, object]]) -> None:
    graphics_reports_module.print_config_section(
        title,
        rows,
        emit_output_fn=emit_output,
        format_config_scalar_fn=_format_config_scalar,
    )


def _print_config_list(title: str, items: list[object]) -> None:
    graphics_reports_module.print_config_list(
        title,
        items,
        emit_output_fn=emit_output,
        format_config_scalar_fn=_format_config_scalar,
    )


def show_config(
    cfg: ConfigDict,
    *,
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[GraphicsRulesConfig, bool]],
    graphics_rule_config_line_fn: Callable[[GraphicsRule], str],
) -> None:
    graphics_reports_module.show_config(
        cfg,
        get_documentation_config_fn=config_module.get_documentation_config,
        get_graphics_rules_path_fn=get_graphics_rules_path_fn,
        load_graphics_rules_fn=load_graphics_rules_fn,
        graphics_rule_config_line_fn=graphics_rule_config_line_fn,
        emit_output_fn=emit_output,
        print_config_list_fn=_print_config_list,
        print_config_section_fn=_print_config_section,
    )


def flatten_graphics_expected_fields(
    payload: dict[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    return graphics_reports_module.flatten_graphics_expected_fields(payload, prefix=prefix)


def truncate_table_cell(value: object, width: int) -> str:
    return graphics_reports_module.truncate_table_cell(value, width)


def graphics_rule_selector_text(rule: dict[str, Any]) -> str:
    return graphics_reports_module.graphics_rule_selector_text(rule)


def graphics_rule_label(rule: dict[str, Any]) -> str:
    return graphics_reports_module.graphics_rule_label(rule)


def graphics_rule_scope_text(rule: dict[str, Any]) -> str:
    return graphics_reports_module.graphics_rule_scope_text(rule)


def graphics_rule_config_line(rule: dict[str, Any]) -> str:
    return graphics_reports_module.graphics_rule_config_line(rule)


def print_graphics_rules_summary(path: Path, rules: dict[str, Any], *, dirty: bool) -> None:
    graphics_reports_module.print_graphics_rules_summary(
        path,
        rules,
        dirty=dirty,
        emit_output_fn=emit_output,
    )


class OptionalPromptSkippedError(Exception):
    """Raised when user explicitly skips an optional CLI prompt."""


# Backward-compatible alias for existing call sites and tests.
OptionalPromptSkipped = OptionalPromptSkippedError


class OptionalPromptValidationError(Exception):
    """Raised when optional prompt input is present but invalid."""


class RequiredPromptValidationError(Exception):
    """Raised when required prompt input is missing or invalid."""


def prompt_optional_float_list(
    label: str,
    expected_count: int,
    *,
    pause_fn: Callable[[], None],
    prompt_fn: Callable[..., str] | None = None,
) -> list[float]:
    raw = (
        prompt_fn(f"{label} ({expected_count} comma-separated numbers, blank to skip)", None).strip()
        if prompt_fn is not None
        else input(f"{label} ({expected_count} comma-separated numbers, blank to skip): ").strip()
    )
    if not raw:
        raise OptionalPromptSkipped()
    try:
        values = [float(part.strip()) for part in raw.split(",")]
    except ValueError as exc:
        emit_output("? Must be numeric")
        pause_fn()
        raise OptionalPromptValidationError("Must be numeric") from exc
    if len(values) != expected_count:
        emit_output(f"? Expected {expected_count} values")
        pause_fn()
        raise OptionalPromptValidationError(f"Expected {expected_count} values")
    return values


def prompt_optional_text_list(label: str, *, prompt_fn: Callable[..., str] | None = None) -> list[str]:
    raw = (
        prompt_fn(f"{label} (comma-separated, blank to skip)", None).strip()
        if prompt_fn is not None
        else input(f"{label} (comma-separated, blank to skip): ").strip()
    )
    if not raw:
        raise OptionalPromptSkipped()
    return [part.strip() for part in raw.split(",") if part.strip()]


def prompt_optional_bool(label: str, *, prompt_fn: Callable[..., str] | None = None) -> bool:
    raw = (
        prompt_fn(f"{label} [y/n, blank to skip]", None).strip().lower()
        if prompt_fn is not None
        else input(f"{label} [y/n, blank to skip]: ").strip().lower()
    )
    if not raw:
        raise OptionalPromptSkipped()
    if raw in {"y", "yes", "true", "1"}:
        return True
    if raw in {"n", "no", "false", "0"}:
        return False
    emit_output("? Enter y or n")
    raise OptionalPromptValidationError("Enter y or n")


def optional_prompt_or_none(prompt_fn: Callable[[], Any]) -> Any | None:
    try:
        return prompt_fn()
    except OptionalPromptSkipped:
        return None
    except OptionalPromptValidationError:
        return None


def prompt_graphics_rule_kind(*, interaction: MenuInteraction | None = None) -> str:
    return graphics_menus_module.prompt_graphics_rule_kind(emit_output_fn=emit_output, interaction=interaction)


def selector_prompt_text(selector_field: str) -> str:
    return graphics_menus_module.selector_prompt_text(selector_field)


def graphics_rule_target_kind_matches(module_kind: str, entry: dict[str, Any]) -> bool:
    return graphics_menus_module.graphics_rule_target_kind_matches(module_kind, entry)


def discover_graphics_rule_selector_options(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    iter_loaded_projects_fn: LoadedProjectIterator,
    collect_graphics_layout_entries_for_target_fn: CollectGraphicsLayoutEntriesForTargetFn,
) -> list[GraphicsRule]:
    return graphics_menus_module.discover_graphics_rule_selector_options(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
        has_analyzed_targets_fn=has_analyzed_targets_fn,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        collect_graphics_layout_entries_for_target_fn=collect_graphics_layout_entries_for_target_fn,
    )


def pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: ConfigDict | None = None,
    discover_graphics_rule_selector_options_fn: Callable[..., list[GraphicsRule]],
    interaction: MenuInteraction | None = None,
) -> str:
    return graphics_menus_module.pick_or_prompt_graphics_rule_selector_value(
        selector_field,
        module_kind,
        cfg=cfg,
        discover_graphics_rule_selector_options_fn=discover_graphics_rule_selector_options_fn,
        emit_output_fn=emit_output,
        required_prompt_validation_error=RequiredPromptValidationError,
        interaction=interaction,
    )


def prompt_graphics_rule_selector(
    module_kind: str,
    *,
    cfg: ConfigDict | None = None,
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
    interaction: MenuInteraction | None = None,
) -> tuple[str, str]:
    return graphics_menus_module.prompt_graphics_rule_selector(
        module_kind,
        cfg=cfg,
        pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
        emit_output_fn=emit_output,
        interaction=interaction,
    )


def path_startswith_casefold(path: Sequence[str], prefix: Sequence[str]) -> bool:
    return graphics_menus_module.path_startswith_casefold(path, prefix)


def graphics_entry_canonical_segment(entry: dict[str, Any]) -> str:
    return graphics_menus_module.graphics_entry_canonical_segment(entry)


def looks_like_graphics_unit_root(
    candidate_path: Sequence[str],
    entries: Sequence[dict[str, Any]],
) -> bool:
    return graphics_menus_module.looks_like_graphics_unit_root(candidate_path, entries)


def annotate_graphics_entries_with_structure_paths(
    entries: list[GraphicsRule],
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    classify_documentation_structure_fn: ClassifyDocumentationStructureFn = DEFAULT_CLASSIFY_DOCUMENTATION_STRUCTURE_FN,
    discover_documentation_unit_candidates_fn: DiscoverDocumentationUnitCandidatesFn = DEFAULT_DISCOVER_DOCUMENTATION_UNIT_CANDIDATES_FN,
) -> list[GraphicsRule]:
    return graphics_menus_module.annotate_graphics_entries_with_structure_paths(
        entries,
        project_bp,
        graph,
        classify_documentation_structure_fn=classify_documentation_structure_fn,
        discover_documentation_unit_candidates_fn=discover_documentation_unit_candidates_fn,
    )


def prompt_graphics_rule_definition(
    *,
    prompt_graphics_rule_definition_with_config_fn: Callable[[ConfigDict | None], GraphicsRule | None],
) -> GraphicsRule | None:
    return graphics_menus_module.prompt_graphics_rule_definition(
        prompt_graphics_rule_definition_with_config_fn=prompt_graphics_rule_definition_with_config_fn,
    )


def prompt_graphics_rule_definition_with_config(
    cfg: ConfigDict | None,
    *,
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
    interaction: MenuInteraction | None = None,
) -> GraphicsRule | None:
    return graphics_menus_module.prompt_graphics_rule_definition_with_config(
        cfg,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
        pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
        prompt_graphics_rule_kind_fn=prompt_graphics_rule_kind,
        prompt_graphics_rule_selector_fn=prompt_graphics_rule_selector,
        optional_prompt_or_none_fn=optional_prompt_or_none,
        prompt_optional_float_list_fn=prompt_optional_float_list,
        prompt_optional_text_list_fn=prompt_optional_text_list,
        prompt_optional_bool_fn=prompt_optional_bool,
        emit_output_fn=emit_output,
        required_prompt_validation_error=RequiredPromptValidationError,
        interaction=interaction,
    )


def collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    annotate_graphics_entries_with_structure_paths_fn: Callable[
        [list[dict[str, Any]], BasePicture, ProjectGraph], list[dict[str, Any]]
    ],
) -> list[dict[str, Any]]:
    structural_reports_module = importlib.import_module("sattlint.devtools.structural_reports")

    synthetic_entry_file = Path.cwd() / f"{target_name}.s"
    snapshot = SimpleNamespace(
        entry_file=synthetic_entry_file,
        base_picture=project_bp,
        project_graph=graph,
    )
    discovery = SimpleNamespace(
        program_files=(synthetic_entry_file,),
        dependency_files=(),
    )
    report = structural_reports_module.collect_graphics_layout_report(
        workspace_root=Path.cwd(),
        graph_inputs=(discovery, [snapshot], []),
    )
    return annotate_graphics_entries_with_structure_paths_fn(
        list(report.get("entries", [])),
        project_bp,
        graph,
    )


def graphics_rules_menu(
    cfg: dict[str, Any] | None = None,
    *,
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[dict[str, Any], bool]],
    save_graphics_rules_fn: Callable[[Path, dict[str, Any]], None],
    prompt_graphics_rule_definition_with_config_fn: Callable[[dict[str, Any] | None], dict[str, Any] | None],
    graphics_rule_label_fn: Callable[[dict[str, Any]], str],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    confirm_fn: Callable[[str], bool],
    prompt_fn: Callable[..., str],
    quit_app_fn: Callable[[], None],
    pause_fn: Callable[[], None],
    interaction: MenuInteraction | None = None,
) -> None:
    graphics_menus_module.graphics_rules_menu(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path_fn,
        load_graphics_rules_fn=load_graphics_rules_fn,
        save_graphics_rules_fn=save_graphics_rules_fn,
        prompt_graphics_rule_definition_with_config_fn=prompt_graphics_rule_definition_with_config_fn,
        graphics_rule_label_fn=graphics_rule_label_fn,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        confirm_fn=confirm_fn,
        prompt_fn=prompt_fn,
        quit_app_fn=quit_app_fn,
        pause_fn=pause_fn,
        print_graphics_rules_summary_fn=print_graphics_rules_summary,
        emit_output_fn=emit_output,
        upsert_graphics_rule_fn=graphics_rules_module.upsert_graphics_rule,
        remove_graphics_rule_fn=graphics_rules_module.remove_graphics_rule,
        interaction=interaction,
    )


def run_graphics_rules_validation(
    cfg: dict[str, Any],
    *,
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[dict[str, Any], bool]],
    iter_loaded_projects_fn: LoadedProjectIterator,
    collect_graphics_layout_entries_for_target_fn: Callable[[str, BasePicture, ProjectGraph], list[dict[str, Any]]],
    pause_fn: Callable[[], None],
) -> None:
    emit_output("\n--- Validate Graphics Rules ---")
    rules_path = get_graphics_rules_path_fn()
    rules, _created = load_graphics_rules_fn(rules_path)
    if not rules.get("rules"):
        emit_output("? No graphics rules configured. Open Setup -> Edit graphics rules to add rules first.")
        pause_fn()
        return

    with console_module.live_status_line() as status_update_fn:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            try:
                status_update_fn(f"Graphics rules: collecting layout entries for {target_name}")
                entries = collect_graphics_layout_entries_for_target_fn(
                    target_name,
                    project_bp,
                    graph,
                )
                status_update_fn(f"Graphics rules: validating {target_name}")
                report = graphics_rules_module.validate_graphics_layout_entries(
                    entries,
                    rules,
                    target_name=target_name,
                    rules_path=rules_path,
                )
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output(report.summary())
            except Exception as exc:  # noqa: BLE001
                log_debug_exception(cfg, f"Graphics rules validation failed for {target_name!r}", logger=log)
                emit_output(f"? Error during graphics rules validation for {target_name}: {exc}")

    pause_fn()
