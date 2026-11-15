"""Shared pytest fixtures and test utilities."""

# pyright: reportUnusedFunction=false
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from sattlint.application import checks as checks_module
from sattlint.application import project as project_application

# Ensure `src/` is on sys.path so `import sattlint` works in dev/test runs.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def _isolate_run_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Redirect analysis-run persistence away from the real cache dir."""
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(checks_module, "get_runs_dir", lambda: runs_dir)
    yield


@pytest.fixture(autouse=True)
def _isolate_analysis_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep tests away from the user's AST and analysis-report caches."""
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(checks_module, "get_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(project_application, "get_cache_dir", lambda: cache_dir)
    yield
