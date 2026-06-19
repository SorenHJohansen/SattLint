# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sattlint.devtools import _semble_adapter as semble_adapter


def test_search_local_repo_refresh_rebuilds_repo_index(tmp_path, monkeypatch) -> None:
    build_ids: list[int] = []

    class FakeSembleIndex:
        def __init__(self, build_id: int) -> None:
            self._build_id = build_id

        @classmethod
        def from_path(cls, _repo_path: str):
            build_id = len(build_ids) + 1
            build_ids.append(build_id)
            return cls(build_id)

        def search(self, query: str, *, top_k: int):
            del top_k
            return [
                SimpleNamespace(
                    chunk=SimpleNamespace(
                        file_path="src/example.py",
                        start_line=1,
                        end_line=1,
                        content=f"{query}:{self._build_id}",
                    ),
                    score=0.5,
                )
            ]

    semble_adapter.invalidate_local_repo_cache()
    semble_adapter._index_for_repo.cache_clear()
    semble_adapter._search_repo_cached.cache_clear()
    monkeypatch.setattr(semble_adapter, "_load_semble_index_class", lambda: FakeSembleIndex)

    first = semble_adapter.search_local_repo("impact", repo_root=tmp_path)
    second = semble_adapter.search_local_repo("impact", repo_root=tmp_path)
    refreshed = semble_adapter.search_local_repo("impact", repo_root=tmp_path, refresh=True)

    assert first.results[0].content == "impact:1"
    assert second.results[0].content == "impact:1"
    assert refreshed.results[0].content == "impact:2"
    assert build_ids == [1, 2]


def test_invalidate_local_repo_cache_scopes_refresh_to_one_repo(tmp_path, monkeypatch) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    build_paths: list[str] = []

    class FakeSembleIndex:
        def __init__(self, repo_path: str, build_number: int) -> None:
            self._repo_path = Path(repo_path)
            self._build_number = build_number

        @classmethod
        def from_path(cls, repo_path: str):
            build_paths.append(repo_path)
            repo_build_number = sum(1 for built in build_paths if built == repo_path)
            return cls(repo_path, repo_build_number)

        def search(self, query: str, *, top_k: int):
            del top_k
            return [
                SimpleNamespace(
                    chunk=SimpleNamespace(
                        file_path="src/example.py",
                        start_line=1,
                        end_line=1,
                        content=f"{self._repo_path.name}:{query}:{self._build_number}",
                    ),
                    score=0.25,
                )
            ]

    semble_adapter.invalidate_local_repo_cache()
    semble_adapter._index_for_repo.cache_clear()
    semble_adapter._search_repo_cached.cache_clear()
    monkeypatch.setattr(semble_adapter, "_load_semble_index_class", lambda: FakeSembleIndex)

    first_a = semble_adapter.search_local_repo("impact", repo_root=repo_a)
    first_b = semble_adapter.search_local_repo("impact", repo_root=repo_b)
    semble_adapter.invalidate_local_repo_cache(repo_root=repo_a)
    second_a = semble_adapter.search_local_repo("impact", repo_root=repo_a)
    second_b = semble_adapter.search_local_repo("impact", repo_root=repo_b)

    assert first_a.results[0].content == "repo-a:impact:1"
    assert first_b.results[0].content == "repo-b:impact:1"
    assert second_a.results[0].content == "repo-a:impact:2"
    assert second_b.results[0].content == "repo-b:impact:1"
