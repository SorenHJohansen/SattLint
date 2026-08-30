# pyright: reportPrivateUsage=false
"""Cache manager wiring for sattlint.cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from . import cache as cache_module
from ._cache_classes import AnalysisReportCache, ASTCache, FileASTCache, FileLookupCache


class CacheManager:
    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        file_lookup_cache_cls: type[FileLookupCache] = FileLookupCache,
        file_ast_cache_cls: type[FileASTCache] = FileASTCache,
        ast_cache_cls: type[ASTCache] = ASTCache,
        analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
    ) -> None:
        resolved_cache_dir = cache_module.get_cache_dir() if cache_dir is None else cache_dir
        self.cache_dir = resolved_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._file_lookup_cache_cls = file_lookup_cache_cls
        self._file_ast_cache_cls = file_ast_cache_cls
        self._ast_cache_cls = ast_cache_cls
        self._analysis_report_cache_cls = analysis_report_cache_cls
        self._file_lookup_cache: FileLookupCache | None = None
        self._file_ast_cache: FileASTCache | None = None
        self._ast_cache: ASTCache | None = None
        self._analysis_report_cache: AnalysisReportCache | None = None

    @property
    def file_lookup_cache(self) -> FileLookupCache:
        if self._file_lookup_cache is None:
            self._file_lookup_cache = self._file_lookup_cache_cls(self.cache_dir)
        return self._file_lookup_cache

    @property
    def file_ast_cache(self) -> FileASTCache:
        if self._file_ast_cache is None:
            self._file_ast_cache = self._file_ast_cache_cls(self.cache_dir)
        return self._file_ast_cache

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
        file_lookup_cache = self.file_lookup_cache
        file_ast_cache = self.file_ast_cache
        ast_cache = self.ast_cache
        analysis_report_cache = self.analysis_report_cache
        result = result.combine(
            cache_module.CachePruneResult(
                file_lookup_entries=file_lookup_cache.drain_startup_pruned_entries()
                + file_lookup_cache.prune_stale_entries()
            )
        )
        result = result.combine(
            cache_module.CachePruneResult(
                file_ast_entries=file_ast_cache.drain_startup_pruned_entries() + file_ast_cache.prune_stale_entries()
            )
        )
        result = result.combine(ast_cache.drain_startup_prune_result().combine(ast_cache.prune_stale_entries()))
        result = result.combine(
            cache_module.CachePruneResult(
                analysis_report_entries=analysis_report_cache.drain_startup_pruned_entries()
                + analysis_report_cache.prune_stale_entries()
            )
        )
        return result

    def clear_all(self) -> cache_module.CachePruneResult:
        result = cache_module.CachePruneResult()

        lookup_path = self.file_lookup_cache.path
        if lookup_path.exists() and cache_module._remove_file(lookup_path):
            result = result.combine(cache_module.CachePruneResult(file_lookup_entries=1))
        self._file_lookup_cache = self._file_lookup_cache_cls(self.cache_dir)

        file_ast_entries = 0
        for path in self.file_ast_cache.cache_dir.glob("*.pickle"):
            if cache_module._remove_file(path):
                file_ast_entries += 1
        result = result.combine(cache_module.CachePruneResult(file_ast_entries=file_ast_entries))
        self._file_ast_cache = self._file_ast_cache_cls(self.cache_dir)

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


_CACHE_MANAGERS: dict[Path, CacheManager] = {}


def _uses_default_cache_types(
    *,
    file_lookup_cache_cls: type[FileLookupCache],
    file_ast_cache_cls: type[FileASTCache],
    ast_cache_cls: type[ASTCache],
    analysis_report_cache_cls: type[AnalysisReportCache],
) -> bool:
    return (
        file_lookup_cache_cls is FileLookupCache
        and file_ast_cache_cls is FileASTCache
        and ast_cache_cls is ASTCache
        and analysis_report_cache_cls is AnalysisReportCache
    )


def get_cache_manager(
    cache_dir: Path | None = None,
    *,
    file_lookup_cache_cls: type[FileLookupCache] = FileLookupCache,
    file_ast_cache_cls: type[FileASTCache] = FileASTCache,
    ast_cache_cls: type[ASTCache] = ASTCache,
    analysis_report_cache_cls: type[AnalysisReportCache] = AnalysisReportCache,
) -> CacheManager:
    raw_cache_dir = cache_module.get_cache_dir() if cache_dir is None else cache_dir
    resolved_cache_dir = cache_module._normalize_cache_dir(raw_cache_dir)
    if not _uses_default_cache_types(
        file_lookup_cache_cls=file_lookup_cache_cls,
        file_ast_cache_cls=file_ast_cache_cls,
        ast_cache_cls=ast_cache_cls,
        analysis_report_cache_cls=analysis_report_cache_cls,
    ):
        return CacheManager(
            raw_cache_dir,
            file_lookup_cache_cls=file_lookup_cache_cls,
            file_ast_cache_cls=file_ast_cache_cls,
            ast_cache_cls=ast_cache_cls,
            analysis_report_cache_cls=analysis_report_cache_cls,
        )

    manager = _CACHE_MANAGERS.get(resolved_cache_dir)
    if manager is None:
        manager = CacheManager(resolved_cache_dir)
        _CACHE_MANAGERS[resolved_cache_dir] = manager
    return manager


def build_file_lookup_cache(cache_dir: Path, file_lookup_cache_cls: type[Any] = FileLookupCache) -> Any:
    return get_cache_manager(
        cache_dir,
        file_lookup_cache_cls=cast(type[FileLookupCache], file_lookup_cache_cls),
    ).file_lookup_cache


def build_file_ast_cache(cache_dir: Path, file_ast_cache_cls: type[Any] = FileASTCache) -> Any:
    return get_cache_manager(
        cache_dir,
        file_ast_cache_cls=cast(type[FileASTCache], file_ast_cache_cls),
    ).file_ast_cache


def build_ast_cache(cache_dir: Path, ast_cache_cls: type[Any] = ASTCache) -> Any:
    return get_cache_manager(
        cache_dir,
        ast_cache_cls=cast(type[ASTCache], ast_cache_cls),
    ).ast_cache


def build_analysis_report_cache(cache_dir: Path, analysis_report_cache_cls: type[Any] = AnalysisReportCache) -> Any:
    return get_cache_manager(
        cache_dir,
        analysis_report_cache_cls=cast(type[AnalysisReportCache], analysis_report_cache_cls),
    ).analysis_report_cache


def prune_cache_dir(cache_dir: Path | None = None) -> cache_module.CachePruneResult:
    return get_cache_manager(cache_dir).prune_stale_entries()
