"""Shared pytest fixtures and test utilities."""

# pyright: reportUnusedFunction=false, reportPrivateUsage=false
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from sattlint import cache as cache_module
from sattlint.cache import manager as cache_manager_module
from sattlint.project import loading as project_loading_module

# Ensure `src/` is on sys.path so `import sattlint` works in dev/test runs.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def _isolate_analysis_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep tests away from the user's AST, report, and run-history caches.

    The cache module's resolvers are the single source every importer reaches,
    so patching them here isolates AST caches, report caches, run records, the
    profiling log, and the foundation cache in one place.
    """
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(cache_module, "cache_dir_location", lambda: cache_dir)
    monkeypatch.setattr(cache_module, "get_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(cache_module, "get_cache_dir_or_none", lambda: cache_dir)
    # The manager registry is process-global and keyed by directory; a manager
    # built by an earlier test must never serve a later one.
    cache_manager_module._CACHE_MANAGERS.clear()
    # The input-size preflight keeps one stat snapshot per process load session.
    # A test that rewrites a source of the same size must see the new bytes.
    project_loading_module._reset_source_size_snapshot()
    yield
    cache_manager_module._CACHE_MANAGERS.clear()
    project_loading_module._reset_source_size_snapshot()
