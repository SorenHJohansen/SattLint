"""Write Change Review artifacts to a configured output directory.

Both serializations (JSON and Markdown) are written for the same canonical
``ChangeReview`` so humans and AI consumers share the identical review. The
base file name is derived deterministically from the project name and a
generation timestamp.
"""

from __future__ import annotations

import contextlib
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .review import ChangeReview
from .serialization.json_serializer import review_to_json
from .serialization.markdown_serializer import review_to_markdown

_REVIEW_DIRECTORY_MODE = 0o700
_ARTIFACT_MODE = 0o600


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


def _ensure_private_directory(path: Path) -> None:
    """Create the dedicated artifact directory owner-only and keep it that way."""
    path.mkdir(parents=True, exist_ok=True, mode=_REVIEW_DIRECTORY_MODE)
    if path.stat().st_mode & 0o777 & ~_REVIEW_DIRECTORY_MODE:
        path.chmod(_REVIEW_DIRECTORY_MODE)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text through a unique temp file and an atomic replace."""
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _ARTIFACT_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError:
        with contextlib.suppress(OSError):
            temp_path.unlink()
        raise


def write_review_artifacts(
    review: ChangeReview,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts, returning (json_path, markdown_path)."""
    _ensure_private_directory(output_dir)
    base = artifact_base_name(review.metadata.project, review.metadata.generated_at)
    json_path = output_dir / f"{base}.json"
    markdown_path = output_dir / f"{base}.md"
    _atomic_write_text(json_path, review_to_json(review))
    _atomic_write_text(markdown_path, review_to_markdown(review))
    return json_path, markdown_path
