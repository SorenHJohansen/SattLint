"""Write Change Review artifacts to a configured output directory.

Both serializations (JSON and Markdown) are written for the same canonical
``ChangeReview`` so humans and AI consumers share the identical review. The
base file name is derived deterministically from the project name and a
generation timestamp.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .review import ChangeReview
from .serialization.json_serializer import review_to_json
from .serialization.markdown_serializer import review_to_markdown


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "project"


def _artifact_timestamp(generated_at: str) -> str:
    """Format the review timestamp in UTC so the name matches its metadata."""
    try:
        moment = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        moment = datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%fZ")


def artifact_base_name(project_name: str, generated_at: str = "") -> str:
    return f"{_safe_component(project_name)}-change-review-{_artifact_timestamp(generated_at)}"


def write_review_artifacts(
    review: ChangeReview,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts, returning (json_path, markdown_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = artifact_base_name(review.metadata.project, review.metadata.generated_at)
    json_path = output_dir / f"{base}.json"
    markdown_path = output_dir / f"{base}.md"
    json_path.write_text(review_to_json(review), encoding="utf-8")
    markdown_path.write_text(review_to_markdown(review), encoding="utf-8")
    return json_path, markdown_path
