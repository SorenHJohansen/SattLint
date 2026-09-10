"""Write Change Review artifacts to a configured output directory.

Both serializations (JSON and Markdown) are written for the same canonical
``ChangeReview`` so humans and AI consumers share the identical review. The
base file name is derived deterministically from the project name and a
generation timestamp.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .review import ChangeReview
from .serialization.json_serializer import review_to_json
from .serialization.markdown_serializer import review_to_markdown


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "project"


def artifact_base_name(project_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{_safe_component(project_name)}-change-review-{timestamp}"


def write_review_artifacts(
    review: ChangeReview,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts, returning (json_path, markdown_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = artifact_base_name(review.metadata.project)
    json_path = output_dir / f"{base}.json"
    markdown_path = output_dir / f"{base}.md"
    json_path.write_text(review_to_json(review), encoding="utf-8")
    markdown_path.write_text(review_to_markdown(review), encoding="utf-8")
    return json_path, markdown_path
