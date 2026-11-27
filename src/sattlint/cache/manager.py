# pyright: reportPrivateUsage=false
"""Cache manager wiring for sattlint.cache."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from .. import cache as cache_module
from .classes import AnalysisReportCache, ASTCache


class CacheManager:
    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        ast_cache_cls: type[ASTCache] = ASTCache,
        analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
    ) -> None:
        resolved_cache_dir = cache_module.get_cache_dir() if cache_dir is None else cache_dir
        self.cache_dir = resolved_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ast_cache_cls = ast_cache_cls
        self._analysis_report_cache_cls = analysis_report_cache_cls
        self._ast_cache: ASTCache | None = None
        self._analysis_report_cache: AnalysisReportCache | None = None

    @property
    def ast_cache(self) -> ASTCache:
        if self._ast_cache is None:
            self._ast_cache = self._ast_cache_cls(self.cache_dir)
        return self._ast_cache

    @property
    def analysis_report_cache(self) -> AnalysisReportCache:
        if self._analysis_report_cache is None:
            self._analysis_report_cache = self._analysis_report_cache_cls(self.cache_dir)
        return self._analysis_report_cache

    def prune_stale_entries(self) -> cache_module.CachePruneResult:
        result = cache_module.CachePruneResult()
        ast_cache = self.ast_cache
        analysis_report_cache = self.analysis_report_cache
        result = result.combine(ast_cache.drain_startup_prune_result().combine(ast_cache.prune_stale_entries()))
        result = result.combine(ast_cache.prune_over_budget_entries())
        result = result.combine(
            cache_module.CachePruneResult(
                analysis_report_entries=analysis_report_cache.drain_startup_pruned_entries()
                + analysis_report_cache.prune_stale_entries()
            )
        )
        return result

    def clear_all(self) -> cache_module.CachePruneResult:
        result = cache_module.CachePruneResult()

        ast_payload_entries = 0
        ast_manifest_entries = 0
        ast_cache_dir = self.ast_cache.cache_dir
        for path in ast_cache_dir.glob("*.pickle"):
            if cache_module._remove_file(path):
                ast_payload_entries += 1
        for path in ast_cache_dir.glob("*.manifest.json"):
            if cache_module._remove_file(path):
                ast_manifest_entries += 1
        result = result.combine(
            cache_module.CachePruneResult(
                ast_payload_entries=ast_payload_entries,
                ast_manifest_entries=ast_manifest_entries,
            )
        )
        self._ast_cache = self._ast_cache_cls(self.cache_dir)

        analysis_report_entries = self.analysis_report_cache.clear_all()
        result = result.combine(cache_module.CachePruneResult(analysis_report_entries=analysis_report_entries))
        self._analysis_report_cache = self._analysis_report_cache_cls(self.cache_dir)

        return result


# The manager memo is a small process cache, not a permanent registry: a
# caller that asks for many cache roots must not grow it without bound.
_CACHE_MANAGERS: dict[Path, CacheManager] = {}
_CACHE_MANAGER_LIMIT = 4
#: Analysis runs can share the process with a worker thread; the memo is small,
#: so a single lock around lookups keeps two builders from racing the eviction.
_CACHE_MANAGERS_LOCK = Lock()


def _uses_default_cache_types(
    *,
    ast_cache_cls: type[ASTCache],
    analysis_report_cache_cls: type[AnalysisReportCache],
) -> bool:
    return ast_cache_cls is ASTCache and analysis_report_cache_cls is AnalysisReportCache


def get_cache_manager(
    cache_dir: Path | None = None,
    *,
    ast_cache_cls: type[ASTCache] = ASTCache,
    analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
) -> CacheManager:
    raw_cache_dir = cache_module.get_cache_dir() if cache_dir is None else cache_dir
    resolved_cache_dir = cache_module._normalize_cache_dir(raw_cache_dir)
    if not _uses_default_cache_types(
        ast_cache_cls=ast_cache_cls,
        analysis_report_cache_cls=analysis_report_cache_cls,
    ):
        return CacheManager(
            raw_cache_dir,
            ast_cache_cls=ast_cache_cls,
            analysis_report_cache_cls=analysis_report_cache_cls,
        )

    with _CACHE_MANAGERS_LOCK:
        manager = _CACHE_MANAGERS.get(resolved_cache_dir)
        if manager is None:
            if len(_CACHE_MANAGERS) >= _CACHE_MANAGER_LIMIT:
                _CACHE_MANAGERS.pop(next(iter(_CACHE_MANAGERS)))
            manager = CacheManager(resolved_cache_dir)
            _CACHE_MANAGERS[resolved_cache_dir] = manager
    return manager


def build_ast_cache(cache_dir: Path, ast_cache_cls: type[ASTCache] = ASTCache) -> ASTCache | None:
    """Build the AST cache, or return ``None`` when the cache directory is unusable.

    A cache is an optimisation: an unwritable or blocked cache location must
    not stop an analysis run.
    """
    try:
        return get_cache_manager(cache_dir, ast_cache_cls=ast_cache_cls).ast_cache
    except OSError:
        return None


def build_analysis_report_cache(
    cache_dir: Path,
    analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
) -> AnalysisReportCache | None:
    """Build the analysis-report cache, or return ``None`` when the location is unusable.

    The report cache is an optimisation, exactly like the AST cache, so an
    unwritable or blocked cache location must not stop an analysis run.
    """
    try:
        return get_cache_manager(
            cache_dir,
            analysis_report_cache_cls=analysis_report_cache_cls,
        ).analysis_report_cache
    except OSError:
        return None


def prune_cache_dir(cache_dir: Path | None = None) -> cache_module.CachePruneResult:
    return get_cache_manager(cache_dir).prune_stale_entries()
