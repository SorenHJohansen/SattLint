"""Optional cached Semble adapter for repo-local semantic search."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class SembleMatch:
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "score": self.score,
        }


@dataclass(frozen=True, slots=True)
class SembleSearchResponse:
    available: bool
    backend: str | None
    query: str
    repo_path: str
    top_k: int
    results: tuple[SembleMatch, ...]
    explanation: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "backend": self.backend,
            "query": self.query,
            "repo_path": self.repo_path,
            "top_k": self.top_k,
            "results": [match.to_dict() for match in self.results],
            "explanation": self.explanation,
            "error": self.error,
        }


@lru_cache(maxsize=1)
def _load_semble_index_class() -> type[Any] | None:
    try:
        semble_module = importlib.import_module("semble")
    except ImportError:
        return None
    semble_index = getattr(semble_module, "SembleIndex", None)
    if not isinstance(semble_index, type):
        return None
    return cast(type[Any], semble_index)


@lru_cache(maxsize=4)
def _index_for_repo(repo_path: str) -> Any:
    semble_index = _load_semble_index_class()
    if semble_index is None:
        raise ModuleNotFoundError("The 'semble' package is not installed.")
    return semble_index.from_path(repo_path)


@lru_cache(maxsize=32)
def _search_repo_cached(query: str, repo_path: str, top_k: int) -> SembleSearchResponse:
    semble_index = _load_semble_index_class()
    if semble_index is None:
        return SembleSearchResponse(
            available=False,
            backend=None,
            query=query,
            repo_path=repo_path,
            top_k=top_k,
            results=(),
            explanation="Semble semantic search is unavailable because the Python package is not installed.",
            error="missing_dependency",
        )

    try:
        index = _index_for_repo(repo_path)
        raw_results = index.search(query, top_k=top_k)
    except Exception as exc:  # pragma: no cover - defensive wrapper around optional dependency
        return SembleSearchResponse(
            available=False,
            backend="python-library",
            query=query,
            repo_path=repo_path,
            top_k=top_k,
            results=(),
            explanation="Semble semantic search could not build or query the local index.",
            error=str(exc),
        )

    repo_root = Path(repo_path)
    results: list[SembleMatch] = []
    for raw_result in list(raw_results):
        chunk = getattr(raw_result, "chunk", None)
        if chunk is None:
            continue
        file_path = _normalize_file_path(getattr(chunk, "file_path", ""), repo_root=repo_root)
        if not file_path:
            continue
        results.append(
            SembleMatch(
                file_path=file_path,
                start_line=_coerce_line_number(getattr(chunk, "start_line", 1)),
                end_line=_coerce_line_number(getattr(chunk, "end_line", 1)),
                content=str(getattr(chunk, "content", "")),
                score=_coerce_score(getattr(raw_result, "score", None)),
            )
        )

    explanation = "Semble semantic search returned candidate code chunks for the supplied query."
    if not results:
        explanation = "Semble semantic search ran successfully but found no matching code chunks."
    return SembleSearchResponse(
        available=True,
        backend="python-library",
        query=query,
        repo_path=repo_path,
        top_k=top_k,
        results=tuple(results),
        explanation=explanation,
    )


def search_local_repo(query: str, *, repo_root: Path, top_k: int = 5) -> SembleSearchResponse:
    normalized_query = query.strip()
    resolved_repo_root = repo_root.resolve()
    if not normalized_query:
        return SembleSearchResponse(
            available=False,
            backend="python-library" if _load_semble_index_class() is not None else None,
            query="",
            repo_path=resolved_repo_root.as_posix(),
            top_k=top_k,
            results=(),
            explanation="Semble semantic search was skipped because the query is empty.",
            error="empty_query",
        )
    return _search_repo_cached(normalized_query, resolved_repo_root.as_posix(), top_k)


def _normalize_file_path(raw_path: object, *, repo_root: Path) -> str:
    path_text = str(raw_path).strip().replace("\\", "/")
    if not path_text:
        return ""
    candidate = Path(path_text)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return candidate.as_posix()
    normalized = path_text.lstrip("./")
    repo_prefix = f"{repo_root.name}/"
    if normalized.startswith(repo_prefix):
        return normalized[len(repo_prefix) :]
    return normalized


def _coerce_line_number(value: object) -> int:
    if isinstance(value, bool):
        return 1
    try:
        line_number = int(str(value))
    except (TypeError, ValueError):
        return 1
    return line_number if line_number > 0 else 1


def _coerce_score(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


__all__ = ["SembleMatch", "SembleSearchResponse", "search_local_repo"]
