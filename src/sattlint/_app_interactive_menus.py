from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .config_types import ConfigDict


def show_config(
    cfg: ConfigDict,
    *,
    show_config_fn: Callable[..., None],
) -> None:
    show_config_fn(cfg)


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None,
    note: str | None,
    print_menu_owner_fn: Callable[..., None],
    print_fn: Callable[..., None],
) -> None:
    print_menu_owner_fn(title, options, print_fn=print_fn, intro=intro, note=note)


def summarize_targets(
    cfg: ConfigDict,
    *,
    summarize_targets_fn: Callable[..., str],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
) -> str:
    return summarize_targets_fn(cfg, get_analyzed_targets_fn=get_analyzed_targets_fn)


def show_help(
    cfg: ConfigDict,
    *,
    show_help_fn: Callable[..., None],
    clear_screen_fn: Callable[[], None],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    summarize_targets_fn: Callable[[ConfigDict], str],
    print_fn: Callable[..., None],
    pause_fn: Callable[[], None],
) -> None:
    show_help_fn(
        cfg,
        clear_screen_fn=clear_screen_fn,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        summarize_targets_fn=summarize_targets_fn,
        print_fn=print_fn,
        pause_fn=pause_fn,
    )


def get_help_text(
    cfg: ConfigDict,
    *,
    get_help_text_fn: Callable[..., str],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    summarize_targets_fn: Callable[[ConfigDict], str],
) -> str:
    return str(
        get_help_text_fn(
            cfg,
            get_analyzed_targets_fn=get_analyzed_targets_fn,
            summarize_targets_fn=summarize_targets_fn,
        )
    )
