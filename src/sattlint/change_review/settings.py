"""Change Review output-location helpers."""

from __future__ import annotations

from pathlib import Path

from ..config.paths import config_dir_location, get_change_review_dir, get_change_review_dir_location
from ..config.types import ConfigDict


def _configured_review_dir(cfg: ConfigDict) -> Path | None:
    """The configured review directory, or ``None`` when it is not set.

    A relative value resolves against the user configuration directory, the
    same directory that holds the config file that set it, so the location does
    not depend on the working directory the UI or CLI happens to start in.
    """
    raw = cfg.get("review", {}).get("output_dir", "")
    if not raw or not str(raw).strip():
        return None
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path
    return config_dir_location() / path


def review_output_dir_location(cfg: ConfigDict) -> Path:
    """The configured Change Review output directory without creating it."""
    configured = _configured_review_dir(cfg)
    return configured if configured is not None else get_change_review_dir_location()


def resolve_review_output_dir(cfg: ConfigDict) -> Path:
    """Return the configured Change Review output directory, creating it.

    An empty or missing ``review.output_dir`` resolves to the default
    ``<config dir>/change-review`` location.
    """
    configured = _configured_review_dir(cfg)
    if configured is not None:
        return configured
    return get_change_review_dir()


__all__ = ["resolve_review_output_dir", "review_output_dir_location"]
