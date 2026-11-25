"""Load a target through the same project loader the CLI and TUI use.

Corpus and crash-sweep tests exist to exercise the production load path, so
they must not construct a parallel loader of their own. This helper only fills
in the loader config a project file normally supplies and delegates to
:func:`sattlint.application.project.load_project`.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from sattlint.application import project as project_application
from sattlint.config.types import ConfigDict, ConfigMode
from sattlint.models.project_graph import ProjectGraph
from sattlint.parser_api import BasePicture


def load_target_project(
    target_path: Path,
    *,
    abb_lib_dir: Path | None = None,
    mode: ConfigMode = "draft",
    use_cache: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    """Load ``target_path`` through the production loader and return its view.

    The returned base picture is the merged project view, exactly what the
    analysis pipeline hands to the analyzers. The cache is disabled by default
    so a corpus result cannot depend on a developer's stale ``~/.cache/sattlint``
    entry.
    """
    cfg: dict[str, object] = {
        "program_dir": target_path.parent,
        "other_lib_dirs": [],
        "ABB_lib_dir": abb_lib_dir if abb_lib_dir is not None else target_path.parent,
        "mode": mode,
        "debug": False,
        "analyzed_programs_and_libraries": [target_path.stem],
    }
    return project_application.load_project(
        cast(ConfigDict, cfg),
        target_path.stem,
        use_cache=use_cache,
        status_update_fn=lambda _line: None,
    )
