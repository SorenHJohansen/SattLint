from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from .analyzers.icf import format_icf_file
from .casefolding import casefold_equal, casefold_key, dedupe_casefolded_strings
from .engine import expected_unavailable_library_reason

ConfigDict = dict[str, Any]


class TargetLoadError(RuntimeError):
    def __init__(
        self,
        target_name: str,
        *,
        resolved: list[str],
        missing: list[str],
        warnings: list[str] | None = None,
        direct_dependencies: list[str] | None = None,
    ):
        self.target_name = target_name
        self.resolved = list(resolved)
        self.missing = list(missing)
        self.warnings = list(warnings or [])
        self.direct_dependencies = list(direct_dependencies or [])
        super().__init__(self._build_message())

    @staticmethod
    def _extract_missing_name(item: str) -> str | None:
        marker = " parse/transform error: "
        if marker in item:
            return item.split(marker, 1)[0]
        match = re.match(r"Missing code file for '([^']+)'", item)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_warning_name(item: str) -> str | None:
        if ": " not in item:
            return None
        return item.split(": ", 1)[0]

    @staticmethod
    def _format_missing_item(item: str) -> str:
        marker = " parse/transform error: "
        if marker in item:
            name, detail = item.split(marker, 1)
            return f"{name}: {detail}"
        return item

    def _build_message(self) -> str:
        direct_keys = {casefold_key(name) for name in self.direct_dependencies}
        root_failures: list[str] = []
        direct_failures: list[str] = []
        transitive_failures: list[str] = []
        other_failures: list[str] = []
        root_warnings: list[str] = []
        direct_warnings: list[str] = []
        transitive_warnings: list[str] = []
        other_warnings: list[str] = []

        for item in self.missing:
            failure_name = self._extract_missing_name(item)
            if failure_name is None:
                other_failures.append(item)
                continue
            if casefold_equal(failure_name, self.target_name):
                root_failures.append(item)
            elif casefold_key(failure_name) in direct_keys:
                direct_failures.append(item)
            else:
                transitive_failures.append(item)

        for item in self.warnings:
            warning_name = self._extract_warning_name(item)
            if warning_name is None:
                other_warnings.append(item)
            elif casefold_equal(warning_name, self.target_name):
                root_warnings.append(item)
            elif casefold_key(warning_name) in direct_keys:
                direct_warnings.append(item)
            else:
                transitive_warnings.append(item)

        lines = [f"Target {self.target_name!r} was not parsed."]
        if self.direct_dependencies:
            lines.append(f"Direct dependencies from the target file ({len(self.direct_dependencies)}):")
            lines.extend(f"  - {name}" for name in self.direct_dependencies)
        if self.resolved:
            lines.append(f"Resolved targets ({len(self.resolved)}):")
            lines.extend(f"  - {name}" for name in self.resolved)
        else:
            lines.append("Resolved targets: none")

        if root_failures:
            lines.append(f"Root target validation errors ({len(root_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in root_failures)

        if root_warnings:
            lines.append(f"Root target warnings ({len(root_warnings)}):")
            lines.extend(f"  - {item}" for item in root_warnings)

        if direct_failures:
            lines.append(f"Failed direct dependencies ({len(direct_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in direct_failures)

        if direct_warnings:
            lines.append(f"Direct dependency warnings ({len(direct_warnings)}):")
            lines.extend(f"  - {item}" for item in direct_warnings)

        if transitive_failures:
            lines.append(f"Transitive dependency failures ({len(transitive_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in transitive_failures)

        if transitive_warnings:
            lines.append(f"Transitive dependency warnings ({len(transitive_warnings)}):")
            lines.extend(f"  - {item}" for item in transitive_warnings)

        if other_failures:
            lines.append(f"Other missing/failed entries ({len(other_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in other_failures)

        if other_warnings:
            lines.append(f"Other warnings ({len(other_warnings)}):")
            lines.extend(f"  - {item}" for item in other_warnings)

        if not self.missing:
            lines.append("Missing/failed targets: none")

        return "\n".join(lines)


def print_validation_warnings(warnings: list[str], *, print_fn: Callable[..., None], limit: int = 12) -> None:
    if not warnings:
        return

    print_fn(f"Validation warnings ({len(warnings)}):")
    for item in warnings[:limit]:
        print_fn(f"  - {item}")
    if len(warnings) > limit:
        print_fn(f"  - ... (+{len(warnings) - limit} more)")


def extract_warning_name(item: str) -> str | None:
    if ": " not in item:
        return None
    return item.split(": ", 1)[0]


def is_expected_unavailable_warning(item: str) -> bool:
    match = re.match(r"^[^:]+: dependency '([^']+)' unavailable: (.+)$", item)
    if match is None:
        return False

    dependency_name, reason = match.groups()
    expected_reason = expected_unavailable_library_reason(dependency_name)
    return expected_reason is not None and reason == expected_reason


def target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return [
        item
        for item in warnings
        if ((warning_name := extract_warning_name(item)) is None or casefold_equal(warning_name, target_name))
        and not is_expected_unavailable_warning(item)
    ]


def configured_icf_files(cfg: ConfigDict) -> tuple[Path | None, list[Path]]:
    icf_dir_raw = str(cfg.get("icf_dir", "") or "").strip()
    if not icf_dir_raw:
        return None, []

    icf_dir = Path(icf_dir_raw)
    if not icf_dir.exists() or not icf_dir.is_dir():
        return icf_dir, []

    icf_files = sorted(path for path in icf_dir.iterdir() if path.is_file() and path.suffix.lower() == ".icf")
    return icf_dir, icf_files


def run_format_icf_command(
    cfg: ConfigDict,
    *,
    check: bool,
    print_fn: Callable[..., None],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    icf_dir, icf_files = configured_icf_files(cfg)
    if icf_dir is None:
        print_fn("❌ icf_dir is not set in the config. Set it before running ICF formatting.")
        return exit_usage_error

    if not icf_dir.exists() or not icf_dir.is_dir():
        print_fn(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        return exit_usage_error

    if not icf_files:
        print_fn(f"⚠ No .icf files found in {icf_dir}")
        return exit_usage_error

    changed_count = 0
    unchanged_count = 0
    action = "Would change" if check else "Changed"
    verb = "would change" if check else "changed"

    print_fn("\n--- ICF Formatting ---")
    for icf_file in icf_files:
        result = format_icf_file(icf_file, check=check)
        if result.changed:
            print_fn(f"  {icf_file.name}: {verb}")
            changed_count += 1
        else:
            print_fn(f"  {icf_file.name}: unchanged")
            unchanged_count += 1

    print_fn("Summary:")
    print_fn(f"  Files processed: {len(icf_files)}")
    print_fn(f"  {action}: {changed_count}")
    print_fn(f"  Unchanged: {unchanged_count}")

    if check and changed_count:
        return 1
    return exit_success


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    print_fn: Callable[..., None],
    intro: str | None = None,
    note: str | None = None,
) -> None:
    print_fn(f"\n--- {title} ---")
    if intro:
        print_fn(intro.strip())
        print_fn()

    label_width = max((len(option.label) for option in options), default=0)
    for option in options:
        if option.description:
            print_fn(f"{option.key}) {option.label:<{label_width}}  {option.description}")
        else:
            print_fn(f"{option.key}) {option.label}")

    if note:
        print_fn()
        print_fn(note.strip())


def get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    raw_targets = cfg.get("analyzed_programs_and_libraries", [])
    if not isinstance(raw_targets, list):
        return []
    return dedupe_casefolded_strings(cast(list[str], raw_targets))


def require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    targets = get_analyzed_targets(cfg)
    if not targets:
        raise RuntimeError(
            "No analyzed programs/libraries configured. Add entries to 'analyzed_programs_and_libraries' first."
        )
    return targets


def summarize_targets(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = get_analyzed_targets,
) -> str:
    targets = get_analyzed_targets_fn(cfg)
    if not targets:
        return "No analysis targets configured yet. Open Setup first."
    if len(targets) == 1:
        return f"1 target configured: {targets[0]}"
    preview = ", ".join(targets[:3])
    if len(targets) > 3:
        preview += ", ..."
    return f"{len(targets)} targets configured: {preview}"


def has_analyzed_targets(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = get_analyzed_targets,
) -> bool:
    return bool(get_analyzed_targets_fn(cfg))


def require_targets_for_menu_action(
    cfg: ConfigDict,
    action: str,
    *,
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    print_fn: Callable[..., None],
    pause_fn: Callable[[], None],
) -> bool:
    if has_analyzed_targets_fn(cfg):
        return True
    print_fn(f"\nNo analyzed programs/libraries configured. Add entries in Setup before {action}.")
    pause_fn()
    return False


def cache_key_for_target(
    cfg: ConfigDict,
    target_name: str,
    *,
    compute_cache_key_fn: Callable[[ConfigDict], str],
) -> str:
    cache_cfg: ConfigDict = dict(cfg)
    cache_cfg["analysis_target"] = target_name
    return compute_cache_key_fn(cache_cfg)


def split_csv_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def show_help(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    summarize_targets_fn: Callable[[ConfigDict], str],
    print_fn: Callable[..., None],
    pause_fn: Callable[[], None],
) -> None:
    clear_screen_fn()
    targets = get_analyzed_targets_fn(cfg)
    print_fn(
        """
--- Help ---
SattLint can validate a single file quickly or analyze configured programs and
libraries together with their dependencies.

Recommended first run:
1. Open Setup and configure program_dir, ABB_lib_dir, and any extra library folders.
2. Add one or more analysis targets without file extensions.
3. Save the configuration.
4. Open Tools and run Self-check diagnostics.
5. Open Analyze to run checks, or Documentation to build DOCX output.

Main areas:
- Analyze: run curated reports, the full analyzer suite, or registry-backed checks.
- Documentation: preview unit candidates, choose scope, and generate DOCX output.
- Setup: edit directories, targets, mode, caching, and debug settings.
- Tools: self-check, dumps, and AST cache refresh for troubleshooting.

Quick single-file validation:
  sattlint syntax-check /path/to/Program.s

ICF formatting:
    sattlint format-icf
    sattlint format-icf --check

That command is useful when you want a strict parser or transformer check for one file
without loading a whole workspace.
"""
    )
    if targets:
        print_fn(f"Current target status: {summarize_targets_fn(cfg)}")
    else:
        print_fn("Current target status: no configured targets yet.")
    pause_fn()
