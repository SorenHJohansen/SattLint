"""Cache construction must degrade gracefully when the cache location is unusable."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from sattlint import cache as cache_module
from sattlint.cache import AnalysisReportCache
from sattlint.config import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.project.cache import create_analysis_report_cache


def _blocked_cache_dir(tmp_path: Path) -> Path:
    """Return a path that exists as a file, so ``mkdir`` raises ``OSError``."""
    blocked = tmp_path / "blocked-cache"
    blocked.write_text("not a directory", encoding="utf-8")
    return blocked


def test_create_analysis_report_cache_returns_none_for_unusable_directory(tmp_path: Path) -> None:
    blocked = _blocked_cache_dir(tmp_path)

    cache = create_analysis_report_cache(
        cast(ConfigDict, DEFAULT_CONFIG.copy()),
        use_cache=True,
        debug_enabled_fn=lambda _cfg: False,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=lambda: blocked,
    )

    assert cache is None


def test_build_ast_cache_returns_none_for_unusable_directory(tmp_path: Path) -> None:
    blocked = _blocked_cache_dir(tmp_path)

    assert cache_module.build_ast_cache(blocked) is None
