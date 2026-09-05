"""Menu and help rendering for the CLI layer.

Elevated from the old flat ``app_support`` module as part of the Phase 2
layered refactor: target/ICF/csv queries and warning presentation now live
in :mod:`sattlint.project.support`, while the menu/help presentation stays
here in the terminal-facing CLI package.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..config.types import ConfigDict
from ..project.support import get_analyzed_targets

_HELP_TEXT = """--- Help ---
SattLint can validate a single file quickly or analyze configured programs and
libraries together with their dependencies.

Recommended first run:
1. Open Setup and configure program_dir, ABB_lib_dir, and any extra library folders.
2. Add one or more analysis targets without file extensions.
3. Save the configuration.
4. Open Tools and run Self-check diagnostics.
5. Open Analyze to run checks.

Main areas:
- Analyze: run curated reports, the full analyzer suite, or registry-backed checks.
- Setup: edit directories, targets, mode, caching, and debug settings.
- Tools: self-check, dumps, source diff reports across configured targets, and AST cache refresh.

Quick single-file validation:
    sattlint syntax-check /path/to/Program.s
"""


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


def get_help_text(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    summarize_targets_fn: Callable[[ConfigDict], str],
) -> str:
    targets = get_analyzed_targets_fn(cfg)
    status_line = (
        f"Current target status: {summarize_targets_fn(cfg)}"
        if targets
        else "Current target status: no configured targets yet."
    )
    return f"{_HELP_TEXT.rstrip()}\n{status_line}"


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
    for line in get_help_text(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        summarize_targets_fn=summarize_targets_fn,
    ).splitlines():
        print_fn(line)
    pause_fn()
