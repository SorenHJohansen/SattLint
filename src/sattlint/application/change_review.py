"""Application-layer entry point for generating a Change Review.

Binds the Change Review engine to the configured project so the TUI and the
headless CLI can trigger generation with a single call. The structured result
carries per-target success and failure detail; the string wrapper keeps the
existing TUI contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..change_review import generate_change_review as run_review
from ..change_review.settings import resolve_review_output_dir
from ..config.types import ConfigDict
from ..project.support import get_analyzed_targets


class ChangeReviewError(RuntimeError):
    """A Change Review failure that the caller must report."""


class ChangeReviewNoTargetsError(ChangeReviewError):
    """No target was selected and the project configures none."""


class ChangeReviewOutputError(ChangeReviewError):
    """The review output directory cannot be created or used."""


@dataclass(frozen=True, slots=True)
class GeneratedChangeReview:
    """The two artifacts generated for one target."""

    target: str
    json_path: Path
    markdown_path: Path


@dataclass(frozen=True, slots=True)
class ChangeReviewFailure:
    """One target that could not be reviewed."""

    target: str
    message: str


@dataclass(frozen=True, slots=True)
class ChangeReviewOutcome:
    """Structured per-target result of a Change Review run."""

    output_dir: Path
    generated: tuple[GeneratedChangeReview, ...]
    failures: tuple[ChangeReviewFailure, ...]

    @property
    def generated_targets(self) -> int:
        return len(self.generated)

    @property
    def failed_targets(self) -> int:
        return len(self.failures)


def _prepare_output_dir(path: Path) -> Path:
    """Create the output directory, or raise a stable application error."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ChangeReviewOutputError(
            f"Change Review output directory {path} is not usable: {exc}",
        ) from exc
    return path


def _resolve_output_dir(cfg: ConfigDict, output_dir: Path | None) -> Path:
    if output_dir is not None:
        return _prepare_output_dir(output_dir)
    try:
        configured = resolve_review_output_dir(cfg)
    except OSError as exc:
        raise ChangeReviewOutputError(
            f"Change Review output directory is not usable: {exc}",
        ) from exc
    return _prepare_output_dir(configured)


def run_change_review(
    cfg: ConfigDict,
    target_names: list[str],
    *,
    output_dir: Path | None = None,
) -> ChangeReviewOutcome:
    """Generate Change Review artifacts and return structured per-target detail.

    Every selected target is reviewed independently: one bad target does not
    block the rest. The caller decides the exit code from the returned counts.
    """
    targets = list(target_names) or list(get_analyzed_targets(cfg))
    if not targets:
        raise ChangeReviewNoTargetsError("No analysis targets are configured for Change Review.")

    selected_output_dir = _resolve_output_dir(cfg, output_dir)
    generated: list[GeneratedChangeReview] = []
    failures: list[ChangeReviewFailure] = []
    for target in targets:
        try:
            result = run_review(cfg, target, output_dir=selected_output_dir)
        except Exception as exc:  # noqa: BLE001 - one bad target must not block the rest
            failures.append(ChangeReviewFailure(target=target, message=str(exc)))
            continue
        generated.append(
            GeneratedChangeReview(
                target=target,
                json_path=result.json_path,
                markdown_path=result.markdown_path,
            )
        )

    return ChangeReviewOutcome(
        output_dir=selected_output_dir,
        generated=tuple(generated),
        failures=tuple(failures),
    )


def generate_change_review(
    cfg: ConfigDict,
    target_names: list[str],
    *,
    output_dir: Path | None = None,
) -> str:
    """Generate Change Review artifacts and return a human-readable summary.

    This is the TUI contract: the interactive Output view prints the returned
    string. Headless callers use :func:`run_change_review` for structured data.
    """
    outcome = run_change_review(cfg, target_names, output_dir=output_dir)
    if not outcome.generated:
        details = "\n".join(f"- {failure.target}: {failure.message}" for failure in outcome.failures)
        raise ChangeReviewError(f"Change Review failed for every target:\n{details}")

    lines = [
        f"Change Review generated for {outcome.generated_targets} target(s) in {outcome.output_dir}:",
    ]
    for generated in outcome.generated:
        lines.append(f"- {generated.target}: {generated.markdown_path.name}")
    if outcome.failures:
        lines.append(f"Change Review failed for {outcome.failed_targets} target(s):")
        for failure in outcome.failures:
            lines.append(f"- {failure.target}: {failure.message}")
    return "\n".join(lines)
