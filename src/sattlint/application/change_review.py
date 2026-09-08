"""Application-layer entry point for generating a Change Review.

Binds the Change Review engine to the configured project so the TUI can trigger
generation with a single callable. No CLI command is introduced: the only
caller is the interactive Textual shell.
"""

from __future__ import annotations

from pathlib import Path

from ..change_review import generate_change_review as run_review
from ..change_review.settings import resolve_review_output_dir
from ..config.types import ConfigDict
from ..project.support import get_analyzed_targets


def generate_change_review(
    cfg: ConfigDict,
    target_names: list[str],
    *,
    output_dir: Path | None = None,
) -> str:
    """Generate Change Review artifacts for the given targets.

    Returns a human-readable summary of the generated artifacts.
    """
    targets = target_names or list(get_analyzed_targets(cfg))
    if not targets:
        raise RuntimeError("No analysis targets are configured for Change Review.")

    selected_output_dir = output_dir or resolve_review_output_dir(cfg)
    generated: list[tuple[str, Path, Path]] = []
    for target in targets:
        result = run_review(cfg, target, output_dir=selected_output_dir)
        generated.append((target, result.json_path, result.markdown_path))

    lines = [f"Change Review generated for {len(generated)} target(s) in {selected_output_dir}:"]
    for target, _json_path, markdown_path in generated:
        lines.append(f"- {target}: {markdown_path.name}")
    return "\n".join(lines)
