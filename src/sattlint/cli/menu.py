"""Menu and help rendering for the CLI layer.

Elevated from the old flat ``app_support`` module as part of the Phase 2
layered refactor: target/ICF/csv queries and warning presentation now live
in :mod:`sattlint.project.support`, while the help/status presentation stays
here in the CLI package. The legacy terminal menu (``print_menu``,
``show_help``) was removed with the non-Textual interaction surface.
"""

from __future__ import annotations

from collections.abc import Callable

from ..config.types import ConfigDict
from ..project.support import get_analyzed_targets

_HELP_TEXT = """--- Help ---
SattLint analyzes configured programs and libraries together with their
dependencies.

Recommended first run:
1. Open Configuration or create a New Configuration.
2. Open Setup and configure program_dir, ABB_lib_dir, and any extra library folders.
3. Add one or more analysis targets without file extensions (saved automatically).
4. Open Analyze to run checks.

Main areas:
- Analyze: select the analyzers to run and review the results.
- Setup: edit directories, targets, and mode (saved automatically to the configuration).
"""


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
