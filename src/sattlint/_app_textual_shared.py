# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import io
import os
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .app_interaction import MenuInteraction
from .config_types import ConfigDict

_SessionOutputLog: type[Any] | None = None
_TEXTUAL_COLOR_SYSTEM_ENV = "TEXTUAL_COLOR_SYSTEM"

# Prefer 24-bit color for the Textual shell unless the caller explicitly overrides it.
os.environ.setdefault(_TEXTUAL_COLOR_SYSTEM_ENV, "truecolor")

try:
    from textual.app import App as _ImportedTextualApp  # type: ignore[import-untyped]
    from textual.app import ComposeResult as _ImportedComposeResult  # type: ignore[import-untyped]
    from textual.containers import Horizontal as _ImportedHorizontal  # type: ignore[import-untyped]
    from textual.containers import Vertical as _ImportedVertical  # type: ignore[import-untyped]
    from textual.css.query import NoMatches as _ImportedNoMatches  # type: ignore[import-untyped]
    from textual.css.query import WrongType as _ImportedWrongType  # type: ignore[import-untyped]
    from textual.screen import ModalScreen as _ImportedModalScreen  # type: ignore[import-untyped]
    from textual.widgets import Button as _ImportedButton  # type: ignore[import-untyped]
    from textual.widgets import DirectoryTree as _ImportedDirectoryTree  # type: ignore[import-untyped]
    from textual.widgets import Footer as _ImportedFooter  # type: ignore[import-untyped]
    from textual.widgets import Input as _ImportedInput  # type: ignore[import-untyped]
    from textual.widgets import ListItem as _ImportedListItem  # type: ignore[import-untyped]
    from textual.widgets import ListView as _ImportedListView  # type: ignore[import-untyped]
    from textual.widgets import Log as _ImportedLog  # type: ignore[import-untyped]
    from textual.widgets import RichLog as _ImportedRichLog  # type: ignore[import-untyped]
    from textual.widgets import SelectionList as _ImportedSelectionList  # type: ignore[import-untyped]
    from textual.widgets import Static as _ImportedStatic  # type: ignore[import-untyped]
    from textual.widgets import TextArea as _ImportedTextArea  # type: ignore[import-untyped]
    from textual.widgets.option_list import (
        OptionDoesNotExist as _ImportedOptionDoesNotExist,  # type: ignore[import-untyped]
    )
except ImportError:  # pragma: no cover - optional dependency path
    _TEXTUAL_APP: Any = None
    _TEXTUAL_COMPOSE_RESULT: Any = Any
    _TEXTUAL_QUERY_ERRORS: tuple[type[BaseException], ...] = (LookupError, AttributeError, TypeError)
    _TEXTUAL_HORIZONTAL: Any = None
    _TEXTUAL_VERTICAL: Any = None
    _TEXTUAL_MODAL_SCREEN: Any = object
    _TEXTUAL_BUTTON: Any = None
    _TEXTUAL_DIRECTORY_TREE: Any = None
    _TEXTUAL_FOOTER: Any = None
    _TEXTUAL_INPUT: Any = None
    _TEXTUAL_LIST_ITEM: Any = None
    _TEXTUAL_LIST_VIEW: Any = None
    _TEXTUAL_LOG: Any = None
    _TEXTUAL_OPTION_LIST_ERRORS: tuple[type[BaseException], ...] = (LookupError,)
    _TEXTUAL_RICH_LOG: Any = None
    _TEXTUAL_SELECTION_LIST: Any = None
    _TEXTUAL_STATIC: Any = None
    _TEXTUAL_TEXT_AREA: Any = None
else:

    class _CompatStatic(_ImportedStatic):
        @property
        def renderable(self) -> object:
            return self.content

    _TEXTUAL_APP = _ImportedTextualApp
    _TEXTUAL_COMPOSE_RESULT = _ImportedComposeResult
    _TEXTUAL_QUERY_ERRORS = (_ImportedNoMatches, _ImportedWrongType)
    _TEXTUAL_HORIZONTAL = _ImportedHorizontal
    _TEXTUAL_VERTICAL = _ImportedVertical
    _TEXTUAL_MODAL_SCREEN = _ImportedModalScreen
    _TEXTUAL_BUTTON = _ImportedButton
    _TEXTUAL_DIRECTORY_TREE = _ImportedDirectoryTree
    _TEXTUAL_FOOTER = _ImportedFooter
    _TEXTUAL_INPUT = _ImportedInput
    _TEXTUAL_LIST_ITEM = _ImportedListItem
    _TEXTUAL_LIST_VIEW = _ImportedListView
    _TEXTUAL_LOG = _ImportedLog
    _TEXTUAL_OPTION_LIST_ERRORS = (_ImportedOptionDoesNotExist,)
    _TEXTUAL_RICH_LOG = _ImportedRichLog
    _TEXTUAL_SELECTION_LIST = _ImportedSelectionList
    _TEXTUAL_STATIC = _CompatStatic
    _TEXTUAL_TEXT_AREA = _ImportedTextArea


if _TEXTUAL_RICH_LOG is not None:

    class _RichSessionOutputLog(_TEXTUAL_RICH_LOG):
        def __init__(self, *, id: str | None = None, classes: str | None = None) -> None:
            super().__init__(id=id, classes=classes, wrap=True, highlight=False, markup=False, auto_scroll=False)
            self._plain_text_parts: list[str] = []
            self.read_only = True
            self.show_line_numbers = False

        @property
        def text(self) -> str:
            return "".join(self._plain_text_parts)

        @property
        def selected_text(self) -> str:
            return ""

        def append_plain_text(self, text: str) -> None:
            if text:
                self._plain_text_parts.append(text)

    _SessionOutputLog = _RichSessionOutputLog


else:
    _SessionOutputLog = None


def has_textual() -> bool:
    return _TEXTUAL_APP is not None


def _query_required(widget_owner: Any, selector: str, expected_type: Any | None = None) -> Any:
    query_exactly_one = getattr(widget_owner, "query_exactly_one", None)
    if callable(query_exactly_one):
        if expected_type is None:
            return query_exactly_one(selector)
        return query_exactly_one(selector, expected_type)
    if expected_type is None:
        return widget_owner.query_one(selector)
    return widget_owner.query_one(selector, expected_type)


DEFAULT_SHELL_TITLE = "SattLint"
_ANALYZE_PLANNER_LIST_ID_PREFIX = "analyze-planner-section-"
TEXTUAL_SHELL_CSS = Path(__file__).with_name("app_textual.tcss").read_text(encoding="utf-8")


@dataclass(frozen=True)
class _ShellViewState:
    action_id: str
    title: str
    description: str
    note: str
    launch_label: str


@dataclass(frozen=True)
class _SetupTargetCandidate:
    name: str
    files: tuple[Path, ...]
    available: bool


@dataclass
class InteractionRequest:
    """Represents one modal interaction request flowing through the Textual bridge."""

    kind: str
    title: str | None = None
    options: tuple[Any, ...] = ()
    message: str | None = None
    default: str | None = None
    intro: str | None = None
    note: str | None = None
    response: object | None = None
    result_future: Future[object | None] = field(default_factory=Future, repr=False)


class TextualInteractionBridge:
    """Adapts the shared CLI interaction protocol onto the Textual request/response UI."""

    def __init__(self, *, submit_request_fn: Any) -> None:
        self._submit_request_fn = submit_request_fn

    def _request(self, request: InteractionRequest) -> object:
        try:
            self._submit_request_fn(request)
        except BaseException as exc:
            if not request.result_future.done():
                request.result_future.set_exception(exc)
            raise
        return request.result_future.result()

    async def _request_async(self, request: InteractionRequest) -> object:
        try:
            self._submit_request_fn(request)
        except BaseException as exc:
            if not request.result_future.done():
                request.result_future.set_exception(exc)
            raise
        return await asyncio.wrap_future(request.result_future)

    def as_menu_interaction(self) -> MenuInteraction:
        return MenuInteraction(
            choose_menu_option=self.choose_menu_option,
            prompt=self.prompt,
            confirm=self.confirm,
            pause=self.pause,
        )

    def choose_menu_option(
        self,
        title: str,
        options: list[Any] | tuple[Any, ...],
        *,
        intro: str | None = None,
        note: str | None = None,
    ) -> str:
        response = self._request(
            InteractionRequest(
                kind="menu",
                title=title,
                options=tuple(options),
                intro=intro,
                note=note,
            )
        )
        return str(response or "")

    async def choose_menu_option_async(
        self,
        title: str,
        options: list[Any] | tuple[Any, ...],
        *,
        intro: str | None = None,
        note: str | None = None,
    ) -> str:
        response = await self._request_async(
            InteractionRequest(
                kind="menu",
                title=title,
                options=tuple(options),
                intro=intro,
                note=note,
            )
        )
        return str(response or "")

    def prompt(self, message: str, default: str | None = None) -> str:
        response = self._request(InteractionRequest(kind="prompt", message=message, default=default))
        if response is None:
            return default or ""
        return str(response)

    async def prompt_async(self, message: str, default: str | None = None) -> str:
        response = await self._request_async(InteractionRequest(kind="prompt", message=message, default=default))
        if response is None:
            return default or ""
        return str(response)

    def confirm(self, message: str) -> bool:
        return bool(self._request(InteractionRequest(kind="confirm", message=message)))

    async def confirm_async(self, message: str) -> bool:
        return bool(await self._request_async(InteractionRequest(kind="confirm", message=message)))

    def pause(self) -> None:
        return None

    async def pause_async(self) -> None:
        return None


class _TextualOutput(io.TextIOBase):
    def __init__(self, *, emit_text_fn: Any) -> None:
        self._emit_text_fn = emit_text_fn

    def write(self, text: str) -> int:
        if text:
            self._emit_text_fn(text)
        return len(text)

    def flush(self) -> None:
        return None


def _menu_option_keys(options: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(str(getattr(option, "key", "")).strip().casefold() for option in options if getattr(option, "key", ""))


def advance_menu_choice_buffer(
    current_buffer: str, typed_key: str, option_keys: tuple[str, ...]
) -> tuple[str, str | None]:
    key = typed_key.casefold()
    candidate = f"{current_buffer}{key}"

    def _match_prefix(value: str) -> bool:
        return any(option_key.startswith(value) for option_key in option_keys)

    if _match_prefix(candidate):
        exact_match = candidate in option_keys
        has_longer_match = any(
            option_key.startswith(candidate) and option_key != candidate for option_key in option_keys
        )
        if exact_match and not has_longer_match:
            return "", candidate
        return candidate, None

    if _match_prefix(key):
        exact_match = key in option_keys
        has_longer_match = any(option_key.startswith(key) and option_key != key for option_key in option_keys)
        if exact_match and not has_longer_match:
            return "", key
        return key, None

    return current_buffer, None


def interaction_ledger_text(request: InteractionRequest, choice_buffer: str = "") -> str:
    if request.kind == "menu":
        prefix = f"Current choice: {choice_buffer}  " if choice_buffer else ""
        return (
            f"{prefix}Type a menu key and press Enter. Multi-digit choices are supported. "
            "Backspace edits, Esc goes back, Tab moves focus."
        )
    if request.kind == "prompt":
        return "Type your response. Enter submits, Esc cancels, Tab moves focus."
    if request.kind == "confirm":
        return "Press Y for yes, N or Esc for no, or Tab to move between buttons."
    return "Press Enter, Space, or Esc to continue."


def resolve_shell_title(app_or_title: object | None) -> str:
    if isinstance(app_or_title, str):
        title = app_or_title.strip()
    else:
        title = str(getattr(app_or_title, "title", "") or "").strip()
    return title or DEFAULT_SHELL_TITLE


def _stringify_value(value: object | None) -> str:
    return "" if value is None else str(value)


def _stringify_list_values(values: object | None) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    result: list[str] = []
    for item in cast(list[object], values):
        text = _stringify_value(item).strip()
        if text:
            result.append(text)
    return tuple(result)


def _config_directory_paths(cfg: ConfigDict) -> tuple[Path, ...]:
    other_dirs = cast(list[object], cfg.get("other_lib_dirs", []))
    values = [
        _stringify_value(cast(object | None, cfg.get("program_dir", ""))),
        _stringify_value(cast(object | None, cfg.get("ABB_lib_dir", ""))),
        *(_stringify_value(value) for value in other_dirs),
    ]
    paths: list[Path] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        paths.append(Path(text))
    return tuple(paths)


def _setup_candidate_is_available(cfg: ConfigDict, files: tuple[Path, ...]) -> bool:
    mode = str(cfg.get("mode", "official")).strip().casefold()
    allowed_extensions = {".s", ".x"} if mode == "draft" else {".x"}
    return any(path.suffix.casefold() in allowed_extensions for path in files)


def discover_setup_target_candidates(cfg: ConfigDict) -> tuple[_SetupTargetCandidate, ...]:
    preview_extensions = {".s", ".x", ".l", ".z"}
    candidate_program_extensions = {".s", ".x"}
    preview_files_by_stem: dict[str, list[Path]] = {}
    candidate_keys: set[str] = set()
    ordered_directories = tuple(path.resolve() for path in _config_directory_paths(cfg))
    directory_order = {path: index for index, path in enumerate(ordered_directories)}

    for directory in _config_directory_paths(cfg):
        if not directory.exists() or not directory.is_dir():
            continue
        try:
            entries = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
        except OSError:
            continue

        for entry in entries:
            if not entry.is_file():
                continue
            suffix = entry.suffix.casefold()
            if suffix not in preview_extensions:
                continue
            key = entry.stem.casefold()
            preview_files_by_stem.setdefault(key, []).append(entry)
            if suffix in candidate_program_extensions:
                candidate_keys.add(key)

    candidates: list[_SetupTargetCandidate] = []
    for key in candidate_keys:
        discovered_files = preview_files_by_stem.get(key, [])
        if not discovered_files:
            continue

        def _preview_sort_key(path: Path) -> tuple[int, str, str]:
            resolved = path.resolve()
            parent_rank = directory_order.get(resolved.parent, len(directory_order))
            return (parent_rank, resolved.name.casefold(), resolved.as_posix().casefold())

        unique_files = tuple(sorted({path.resolve() for path in discovered_files}, key=_preview_sort_key))
        if not unique_files:
            continue
        candidates.append(
            _SetupTargetCandidate(
                name=unique_files[0].stem,
                files=unique_files,
                available=_setup_candidate_is_available(cfg, unique_files),
            )
        )

    return tuple(sorted(candidates, key=lambda candidate: candidate.name.casefold()))
