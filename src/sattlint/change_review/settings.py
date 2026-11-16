"""Change Review output-location helpers."""

from __future__ import annotations

from pathlib import Path

from ..config.paths import get_change_review_dir, get_change_review_dir_location
from ..config.types import ConfigDict


def review_output_dir_location(cfg: ConfigDict) -> Path:
    """The configured Change Review output directory without creating it."""
    raw = cfg.get("review", {}).get("output_dir", "")
    if raw and str(raw).strip():
        return Path(str(raw)).expanduser()
    return get_change_review_dir_location()


def resolve_review_output_dir(cfg: ConfigDict) -> Path:
    """Return the configured Change Review output directory, creating it.

    An empty or missing ``review.output_dir`` resolves to the default
    ``<config dir>/change-review`` location.
    """
    raw = cfg.get("review", {}).get("output_dir", "")
    if raw and str(raw).strip():
        return Path(str(raw)).expanduser()
    return get_change_review_dir()


__all__ = ["resolve_review_output_dir", "review_output_dir_location"]
