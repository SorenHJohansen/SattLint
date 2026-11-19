# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false

"""Shared helpers and fixtures for the Textual shell tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from sattlint import ui as app_textual
from sattlint.config.types import ConfigDict
from sattlint.project.io import init_project
from sattlint.ui import _app_textual_shared as app_textual_shared_module


def typed_cfg(value: dict[str, Any]) -> ConfigDict:
    return cast(ConfigDict, value)


def query_any_screen(app_instance: Any, selector: str) -> Any:
    """Query a widget on the app or on any screen currently stacked above it."""
    try:
        return app_instance.query_one(selector)
    except app_textual_shared_module._TEXTUAL_QUERY_ERRORS as exc:
        last_error: BaseException = exc

    screen_stack = getattr(app_instance, "screen_stack", None)
    if screen_stack is None:
        screen_stack = getattr(app_instance, "_screen_stack", ())

    for screen in reversed(tuple(screen_stack)):
        query_one = getattr(screen, "query_one", None)
        if not callable(query_one):
            continue
        try:
            return query_one(selector)
        except app_textual_shared_module._TEXTUAL_QUERY_ERRORS as exc:
            last_error = exc

    raise last_error


def screen_row_bgcolors(app_instance: Any, row: int) -> list[Any]:
    screen = app_instance.screen
    chops = screen._compositor._render_chops(screen.size.region, lambda y: True)
    colors: list[Any] = []
    for strip in chops[row].values():
        if strip is None:
            continue
        for segment in strip:
            if segment.style is not None and segment.style.bgcolor is not None:
                colors.append(segment.style.bgcolor)
    return colors


def widget_text_lines(widget: Any) -> int | None:
    renderable = getattr(widget, "renderable", None)
    if renderable is None:
        return None
    return len(str(renderable).splitlines())


def assert_scroll_content_reachable(widget: Any, *, text_lines: int | None = None) -> None:
    """Assert a scrollable widget's content is fully reachable (not silently clipped)."""
    if text_lines is None:
        text_lines = widget_text_lines(widget)
    content_height = text_lines if text_lines is not None else widget.virtual_size.height
    overflow = content_height - widget.region.height
    assert widget.max_scroll_y >= overflow, (
        f"{widget.id} ({type(widget).__name__}): {overflow} rows of content are unreachable "
        f"(region={widget.region.height}, max_scroll_y={widget.max_scroll_y}, content={content_height})"
    )
    if overflow > 0:
        assert widget.max_scroll_y > 0, f"{widget.id} ({type(widget).__name__}): content overflows but has no scrollbar"


def assert_no_content_clipped_outside_visible_area(app_instance: Any) -> None:
    offenders: list[str] = []
    for widget in app_instance.screen.query("*"):
        overflow = getattr(widget.styles, "overflow_y", "visible")
        if overflow not in ("auto", "scroll"):
            continue
        if widget.region.width <= 0 or widget.region.height <= 0:
            continue
        try:
            assert_scroll_content_reachable(widget)
        except AssertionError as exc:
            offenders.append(str(exc))
    assert not offenders, "Content is clipped outside the visible area:\n" + "\n".join(offenders)


_test_project_root: Path | None = None
_test_project_sequence = 0


def attach_test_project(app_instance: Any) -> None:
    global _test_project_sequence
    if _test_project_root is None:
        raise RuntimeError("the per-test project root fixture is not active")
    _test_project_sequence += 1
    project_dir = _test_project_root / f"project-{_test_project_sequence}"
    app_instance._project = init_project(project_dir / ".slproj")
    app_instance._project_path = app_instance._project.path


def make_textual_app(
    *,
    cfg: dict[str, Any] | None = None,
    analysis_handlers: dict[str, Any] | None = None,
    get_enabled_analyzers_fn: Any | None = None,
    ensure_ast_cache_fn: Any | None = None,
    save_config_fn: Callable[[Any, Any], None] | None = None,
    project: bool = True,
) -> Any:
    """Build the Textual shell with inert defaults for the collaborators it needs."""
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg if cfg is not None else {"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=save_config_fn or (lambda _path, _cfg: None),
        config_path=None,
        quit_app_error=RuntimeError,
        analysis_handlers=analysis_handlers,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        ensure_ast_cache_fn=ensure_ast_cache_fn,
    )
    if project:
        attach_test_project(app_instance)
    return app_instance


@pytest.fixture(autouse=True)
def isolate_app_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Redirect the user config path to a temp file for these app tests.

    App settings are saved automatically on change; without this, the tests
    would read and write the real ``~/.config/sattlint/config.toml``.
    """
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("sattlint.config.paths.get_config_path", lambda: config_path)
    yield


@pytest.fixture(autouse=True)
def isolate_textual_projects(tmp_path: Path) -> Iterator[None]:
    """Keep every throwaway project inside the test's own ``tmp_path``.

    The app factory attaches a real ``.slproj`` project; creating it in the
    shared temp area left one directory per app on every run.
    """
    global _test_project_root, _test_project_sequence
    root = tmp_path / "projects"
    root.mkdir()
    _test_project_root = root
    _test_project_sequence = 0
    yield
    _test_project_root = None
    _test_project_sequence = 0
