# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false

from __future__ import annotations

import io
import re
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, cast

from . import _app_analysis_catalog as analysis_catalog
from . import _app_analysis_planner as analysis_planner
from .app_interaction import MenuInteraction

try:
    from textual.app import App as _ImportedTextualApp  # type: ignore[import-untyped]
    from textual.app import ComposeResult as _ImportedComposeResult  # type: ignore[import-untyped]
    from textual.containers import Horizontal as _ImportedHorizontal  # type: ignore[import-untyped]
    from textual.containers import Vertical as _ImportedVertical  # type: ignore[import-untyped]
    from textual.screen import ModalScreen as _ImportedModalScreen  # type: ignore[import-untyped]
    from textual.widgets import (  # type: ignore[import-untyped]
        Button as _ImportedButton,
    )
    from textual.widgets import (
        DirectoryTree as _ImportedDirectoryTree,
    )
    from textual.widgets import (
        Footer as _ImportedFooter,
    )
    from textual.widgets import (
        Input as _ImportedInput,
    )
    from textual.widgets import (
        ListItem as _ImportedListItem,
    )
    from textual.widgets import (
        ListView as _ImportedListView,
    )
    from textual.widgets import (
        Log as _ImportedLog,
    )
    from textual.widgets import (
        SelectionList as _ImportedSelectionList,
    )
    from textual.widgets import (
        Static as _ImportedStatic,
    )
except ImportError:  # pragma: no cover - optional dependency path
    _TEXTUAL_APP: Any = None
    _TEXTUAL_COMPOSE_RESULT: Any = Any
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
    _TEXTUAL_SELECTION_LIST: Any = None
    _TEXTUAL_STATIC: Any = None
else:
    _TEXTUAL_APP = _ImportedTextualApp
    _TEXTUAL_COMPOSE_RESULT = _ImportedComposeResult
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
    _TEXTUAL_SELECTION_LIST = _ImportedSelectionList
    _TEXTUAL_STATIC = _ImportedStatic


def has_textual() -> bool:
    return _TEXTUAL_APP is not None


DEFAULT_SHELL_TITLE = "SattLint"
_ANALYZE_PLANNER_LIST_ID_PREFIX = "analyze-planner-section-"


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
    kind: str
    title: str | None = None
    options: tuple[Any, ...] = ()
    message: str | None = None
    default: str | None = None
    intro: str | None = None
    note: str | None = None
    response: object | None = None
    completed: threading.Event = field(default_factory=threading.Event, repr=False)


class TextualInteractionBridge:
    def __init__(self, *, submit_request_fn: Any) -> None:
        self._submit_request_fn = submit_request_fn

    def _request(self, request: InteractionRequest) -> object:
        self._submit_request_fn(request)
        request.completed.wait()
        return request.response

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

    def prompt(self, message: str, default: str | None = None) -> str:
        response = self._request(InteractionRequest(kind="prompt", message=message, default=default))
        if response is None:
            return default or ""
        return str(response)

    def confirm(self, message: str) -> bool:
        return bool(self._request(InteractionRequest(kind="confirm", message=message)))

    def pause(self) -> None:
        # In the Textual UI, output stays visible in the log pane so no pause is needed.
        return


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


def _config_directory_paths(cfg: dict[str, Any]) -> tuple[Path, ...]:
    raw_other_dirs = cfg.get("other_lib_dirs", [])
    other_dirs = cast(list[object], raw_other_dirs) if isinstance(raw_other_dirs, list) else []
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


def _setup_candidate_is_available(cfg: dict[str, Any], files: tuple[Path, ...]) -> bool:
    mode = str(cfg.get("mode", "official")).strip().casefold()
    allowed_extensions = {".s", ".x"} if mode == "draft" else {".x"}
    return any(path.suffix.casefold() in allowed_extensions for path in files)


def discover_setup_target_candidates(cfg: dict[str, Any]) -> tuple[_SetupTargetCandidate, ...]:
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


TEXTUAL_SHELL_CSS = """
        Screen {
            background: #f5edd5;
            color: #001ba3;
            scrollbar-background: #f5edd5;
            scrollbar-background-hover: #b9d9df;
            scrollbar-background-active: #b9d9df;
            scrollbar-color: #58787e;
            scrollbar-color-hover: #0077b3;
            scrollbar-color-active: #0077b3;
            scrollbar-corner-color: #f5edd5;
        }

        Footer {
            background: #58787e;
            color: #fbfbee;
        }

        #shell-top {
            height: 5;
            margin: 1 2 0 2;
        }

        #shell-banner {
            width: 24;
            height: 5;
            padding: 1 2;
            background: #58787e;
            color: #fbfbee;
            border: tall #001ba3;
        }

        #shell-banner-title {
            text-style: bold;
        }

        #shell-banner-subtitle {
            margin-top: 1;
            color: #dbeef2;
        }

        #content-host {
            height: 1fr;
            layout: vertical;
            background: #f5edd5;
        }

        #view-host {
            height: 2fr;
            min-height: 18;
            margin: 0 1 1 1;
            padding: 1 2;
            background: #d8d4c8;
            color: #000000;
            border: tall #0077b3;
            overflow-y: auto;
        }

        #view-host.config-mode {
            background: #7e5858;
            color: #fbfbee;
        }

        #view-title {
            text-style: bold;
        }

        #view-description {
            margin-top: 1;
        }

        #view-note {
            margin-top: 1;
            color: #58787e;
        }

        #view-host.config-mode #view-note {
            color: #ebebeb;
        }

        #view-actions {
            height: auto;
            margin-top: 1;
        }

        #analyze-browser {
            height: 1fr;
            margin-top: 1;
        }

        #setup-browser {
            height: 1fr;
            margin-top: 1;
        }

        #analyze-browser-left,
        #analyze-browser-right {
            width: 1fr;
            min-height: 12;
            padding: 1 2;
            background: #b9d9df;
            color: #001ba3;
            border: tall #0077b3;
            overflow-y: auto;
        }

        #analyze-browser-right {
            margin-left: 1;
        }

        #analyze-browser-left Button.raised-button {
            width: 1fr;
            margin: 0 0 1 0;
            content-align: left middle;
        }

        #setup-targets-col {
            width: 44;
            padding: 1 2;
            background: #b9d9df;
            color: #001ba3;
            border: tall #0077b3;
        }

        #setup-settings-col {
            width: 1fr;
            margin-left: 1;
            padding: 1 2;
            background: #b9d9df;
            color: #001ba3;
            border: tall #0077b3;
            overflow-y: auto;
        }

        #view-host.config-mode #setup-targets-col,
        #view-host.config-mode #setup-settings-col {
            background: #b26d6d;
            color: #fbfbee;
        }

        #setup-target-listview {
            height: 1fr;
            background: #f5edd5;
            color: #001ba3;
            border: tall #0077b3;
            margin: 1 0;
            scrollbar-background: #f5edd5;
            scrollbar-color: #58787e;
            scrollbar-color-hover: #0077b3;
            scrollbar-color-active: #0077b3;
            scrollbar-corner-color: #f5edd5;
        }

        #setup-target-listview > ListItem {
            background: #f5edd5;
            color: #001ba3;
        }

        #setup-target-listview > ListItem.--highlight {
            background: #0077b3;
            color: #fbfbee;
        }

        #setup-target-actions {
            height: auto;
            margin-top: 1;
        }

        #setup-target-actions Button.raised-button {
            width: auto;
            margin-right: 1;
        }

        .setup-section-title {
            text-style: bold;
            margin-bottom: 1;
        }

        .setup-group-title {
            text-style: bold;
            margin-top: 1;
            color: #58787e;
        }

        .setup-row {
            height: 3;
            margin-top: 0;
            align: left middle;
        }

        .setup-row-label {
            width: 1fr;
            height: 3;
            content-align: left middle;
            padding-left: 2;
            color: #58787e;
        }

        .setup-row-button {
            width: auto;
            min-width: 24;
        }

        #view-host.config-mode .setup-row-label {
            color: #d9c0c0;
        }

        #view-host.config-mode .setup-group-title {
            color: #ebebeb;
        }

        .browser-section-title {
            margin: 0 0 1 0;
            text-style: bold;
        }

        .browser-empty-state {
            margin: 0 0 1 0;
            color: #58787e;
        }

        .planner-section-note {
            margin: 0 0 1 0;
            color: #58787e;
        }

        #analyze-browser-left SelectionList {
            height: auto;
            min-height: 4;
            margin: 0 0 1 0;
            background: #f5edd5;
            color: #001ba3;
            border: tall #0077b3;
        }

        #analyze-actions-primary,
        #analyze-actions-secondary,
        #documentation-actions,
        #tools-actions {
            height: auto;
            margin-top: 1;
        }

        .is-hidden {
            display: none;
        }

        #interaction-host {
            display: none;
            height: auto;
            margin: 0 1 1 1;
            background: #f5edd5;
        }

        #interaction-host.active {
            display: block;
        }

        #interaction-screen {
            width: 100%;
            height: auto;
            padding: 1 2 2 2;
            padding-bottom: 2;
            background: #f5edd5;
        }

        #actions {
            height: auto;
            padding: 0 1 1 1;
            background: #f5edd5;
        }

        #actions-spacer {
            width: 1fr;
        }

        #summary {
            width: 1fr;
            height: 5;
            padding: 1 2;
            margin-left: 1;
            background: #b9d9df;
            color: #001ba3;
            border: tall #0077b3;
            content-align: left top;
            overflow-y: auto;
        }

        #summary.attention {
            background: #ffff00;
            color: #7e5858;
            border: tall #0077b3;
        }

        #summary.config-mode {
            background: #7e5858;
            color: #fbfbee;
            border: tall #0077b3;
        }

        Button.raised-button {
            min-width: 16;
            height: 3;
            padding: 0 2;
            background: #b0b0b0;
            color: #000000;
            opacity: 100%;
            text-opacity: 100%;
            tint: transparent;
            background-tint: transparent;
            content-align: center middle;
            text-style: bold;
            outline: none;
            border: none;
        }

        Button.raised-button:hover,
        Button.raised-button:focus {
            background: #cacaca;
            color: #000000;
            outline: none;
            border: none;
        }

        Button.raised-button.action-active {
            background: #888888;
            color: #000000;
            outline: none;
            border: none;
        }

        Button.raised-button.config-active {
            background: #888888;
            color: #000000;
            outline: none;
            border: none;
        }

        #actions Button.raised-button,
        #view-actions Button.raised-button,
        #analyze-actions-primary Button.raised-button,
        #analyze-actions-secondary Button.raised-button,
        #documentation-actions Button.raised-button,
        #tools-actions Button.raised-button,
        #interaction-actions Button.raised-button {
            width: auto;
            margin-right: 1;
        }

        #actions Button.toolbar-button {
            width: auto;
            min-width: 9;
            padding: 0 1;
            margin-right: 1;
        }

        #interaction-options {
            height: auto;
        }

        #interaction-options Button.raised-button {
            width: 1fr;
            margin: 0 0 1 0;
            content-align: left middle;
        }

        #output {
            height: 1fr;
            min-height: 8;
            margin: 0 1 1 1;
            padding: 1 2;
            background: #b9d9df;
            color: #001ba3;
            border: tall #0077b3;
            scrollbar-background: #b9d9df;
            scrollbar-background-hover: #c2c2c2;
            scrollbar-background-active: #ebebeb;
            scrollbar-color: #58787e;
            scrollbar-color-hover: #0077b3;
            scrollbar-color-active: #0077b3;
            scrollbar-corner-color: #b9d9df;
        }

        #output.config-mode {
            background: #7e5858;
            color: #fbfbee;
            border: tall #0077b3;
            scrollbar-background: #7e5858;
            scrollbar-background-hover: #858585;
            scrollbar-background-active: #c2c2c2;
            scrollbar-color: #ebebeb;
            scrollbar-color-hover: #ffffff;
            scrollbar-color-active: #ffffff;
            scrollbar-corner-color: #7e5858;
        }

        #output-title {
            margin: 0 1 0 1;
            padding: 0 1;
            color: #16323b;
            text-style: bold;
        }

        #interaction-dialog {
            width: 1fr;
            max-width: 1fr;
            height: auto;
            margin: 1 0 0 0;
            padding: 1 2;
            background: #b9d9df;
            color: #001ba3;
            border: heavy #0077b3;
            scrollbar-background: #b9d9df;
            scrollbar-background-hover: #c2c2c2;
            scrollbar-background-active: #ebebeb;
            scrollbar-color: #58787e;
            scrollbar-color-hover: #0077b3;
            scrollbar-color-active: #0077b3;
            scrollbar-corner-color: #b9d9df;
        }

        #interaction-title {
            color: #001ba3;
            text-style: bold;
        }

        #interaction-intro,
        #interaction-message {
            color: #001ba3;
        }

        #interaction-ledger {
            margin: 1 0;
            color: #58787e;
        }

        #interaction-note {
            color: #58787e;
        }

        #interaction-actions {
            height: auto;
            margin-top: 1;
        }

        #interaction-input {
            background: #f5edd5;
            color: #001ba3;
            border: tall #0077b3;
        }

        #interaction-input:focus {
            border: tall #0077b3;
        }

        _FileBrowserScreen {
            align: center middle;
            background: #f5edd5;
        }

        #file-browser-dialog {
            width: 80%;
            height: 80%;
            background: #f5edd5;
            color: #001ba3;
            border: thick #0077b3;
        }

        #file-browser-title {
            text-style: bold;
            height: 3;
            padding: 0 2;
            content-align: left middle;
            background: #0077b3;
            color: #fbfbee;
        }

        #file-browser-selection {
            height: 1;
            padding: 0 2;
            color: #58787e;
            margin-top: 1;
        }

        #file-browser-dirs {
            height: auto;
            padding: 0 2;
            margin-top: 1;
        }

        #file-browser-dirs Button.raised-button {
            width: auto;
            margin-right: 1;
        }

        #file-browser-tree {
            height: 1fr;
            background: #b9d9df;
            color: #001ba3;
            border: tall #0077b3;
            margin: 1 2;
            scrollbar-background: #b9d9df;
            scrollbar-color: #58787e;
            scrollbar-color-hover: #0077b3;
            scrollbar-color-active: #0077b3;
            scrollbar-corner-color: #b9d9df;
        }

        #file-browser-actions {
            height: auto;
            padding: 0 2 1 2;
        }

        _HelpScreen {
            align: center middle;
            background: transparent;
        }

        #help-dialog {
            width: 60%;
            height: 60%;
            background: #f5edd5;
            color: #001ba3;
            border: thick #0077b3;
        }

        #help-dialog-title {
            text-style: bold;
            height: 3;
            padding: 0 2;
            content-align: left middle;
            background: #0077b3;
            color: #fbfbee;
        }

        #help-dialog-body {
            height: 1fr;
            padding: 1 2;
            overflow-y: auto;
        }

        #help-dialog-actions {
            height: auto;
            padding: 0 2 1 2;
        }
        """


if _TEXTUAL_APP is not None:

    class _ShellBanner(_TEXTUAL_VERTICAL):
        def __init__(self) -> None:
            super().__init__(id="shell-banner")

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            yield _TEXTUAL_STATIC("", id="shell-banner-title")
            yield _TEXTUAL_STATIC("", id="shell-banner-subtitle")

        def on_mount(self) -> None:
            title_widget = self.query_one("#shell-banner-title", _TEXTUAL_STATIC)
            subtitle_widget = self.query_one("#shell-banner-subtitle", _TEXTUAL_STATIC)
            title_widget.update(resolve_shell_title(getattr(self, "app", None)))
            subtitle_widget.update("Analysis, docs, setup, and tools")

    class _InteractionPane(_TEXTUAL_VERTICAL):
        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
            ("enter", "submit_or_activate", "Select"),
            ("escape", "cancel_or_back", "Back"),
            ("backspace", "erase_choice", "Erase"),
            ("tab", "focus_next_control", "Next"),
            ("shift+tab", "focus_previous_control", "Prev"),
        ]

        def __init__(self, request: InteractionRequest, *, submit_response_fn: Any) -> None:
            super().__init__()
            self._request = request
            self._submit_response_fn = submit_response_fn
            self._choice_buffer = ""

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_VERTICAL(id="interaction-screen"), _TEXTUAL_VERTICAL(id="interaction-dialog"):
                if self._request.title:
                    yield _TEXTUAL_STATIC(self._request.title, id="interaction-title")
                if self._request.intro:
                    yield _TEXTUAL_STATIC(self._request.intro, id="interaction-intro")
                if self._request.note:
                    yield _TEXTUAL_STATIC(self._request.note, id="interaction-note")
                if self._request.message:
                    yield _TEXTUAL_STATIC(self._request.message, id="interaction-message")
                yield _TEXTUAL_STATIC("", id="interaction-ledger")

                if self._request.kind == "menu":
                    with _TEXTUAL_VERTICAL(id="interaction-options"):
                        for option in self._request.options:
                            label = f"{getattr(option, 'key', '')}) {getattr(option, 'label', '')}".strip()
                            description = getattr(option, "description", "")
                            if description:
                                label = f"{label} - {description}"
                            yield _TEXTUAL_BUTTON(
                                label,
                                id=f"option-{getattr(option, 'key', '')}",
                                classes="raised-button menu-button",
                            )
                elif self._request.kind == "prompt":
                    yield _TEXTUAL_INPUT(value=self._request.default or "", id="interaction-input")
                    with _TEXTUAL_HORIZONTAL(id="interaction-actions"):
                        yield _TEXTUAL_BUTTON("Submit", id="submit", classes="raised-button dialog-button")
                        yield _TEXTUAL_BUTTON("Cancel", id="cancel", classes="raised-button dialog-button")
                elif self._request.kind == "confirm":
                    with _TEXTUAL_HORIZONTAL(id="interaction-actions"):
                        yield _TEXTUAL_BUTTON("Yes", id="yes", classes="raised-button dialog-button")
                        yield _TEXTUAL_BUTTON("No", id="no", classes="raised-button dialog-button")
                else:
                    yield _TEXTUAL_BUTTON("Continue", id="continue", classes="raised-button dialog-button")

        def on_mount(self) -> None:
            self._refresh_ledger()
            if self._request.kind == "prompt":
                self.query_one("#interaction-input", _TEXTUAL_INPUT).focus()
                return

            if self._request.kind == "menu" and self._request.options:
                first_key = getattr(self._request.options[0], "key", "")
                self.query_one(f"#option-{first_key}", _TEXTUAL_BUTTON).focus()
                return

            default_button_id = "yes" if self._request.kind == "confirm" else "continue"
            self.query_one(f"#{default_button_id}", _TEXTUAL_BUTTON).focus()

        def _refresh_ledger(self) -> None:
            self.query_one("#interaction-ledger", _TEXTUAL_STATIC).update(
                interaction_ledger_text(self._request, self._choice_buffer)
            )

        def _focus_matching_option(self, choice_prefix: str) -> None:
            if self._request.kind != "menu" or not choice_prefix:
                return
            for option_key in _menu_option_keys(self._request.options):
                if option_key.startswith(choice_prefix):
                    self.query_one(f"#option-{option_key}", _TEXTUAL_BUTTON).focus()
                    return

        def _focused_menu_choice(self) -> str | None:
            focused = getattr(getattr(self, "app", None), "focused", None)
            focused_id = getattr(focused, "id", None)
            if isinstance(focused_id, str) and focused_id.startswith("option-"):
                return focused_id.removeprefix("option-")
            return None

        def _submit_response(self, response: object) -> None:
            self._submit_response_fn(response)

        def _submit_current_request(self) -> None:
            if self._request.kind == "menu":
                option_keys = _menu_option_keys(self._request.options)
                if self._choice_buffer in option_keys:
                    self._submit_response(self._choice_buffer)
                    return
                focused_choice = self._focused_menu_choice()
                if focused_choice is not None:
                    self._submit_response(focused_choice)
                return
            if self._request.kind == "prompt":
                self._submit_response(self.query_one("#interaction-input", _TEXTUAL_INPUT).value)
                return
            if self._request.kind == "confirm":
                focused = getattr(getattr(self, "app", None), "focused", None)
                focused_id = getattr(focused, "id", None)
                self._submit_response(focused_id == "yes")
                return
            self._submit_response(None)

        def _cancel_current_request(self) -> None:
            if self._request.kind == "menu":
                option_keys = _menu_option_keys(self._request.options)
                if "b" in option_keys:
                    self._submit_response("b")
                    return
                self._submit_response(None)
                return
            if self._request.kind == "prompt":
                self._submit_response(self._request.default)
                return
            if self._request.kind == "confirm":
                self._submit_response(False)
                return
            self._submit_response(None)

        def action_submit_or_activate(self) -> None:
            self._submit_current_request()

        def action_cancel_or_back(self) -> None:
            self._cancel_current_request()

        def action_erase_choice(self) -> None:
            if self._request.kind != "menu" or not self._choice_buffer:
                return
            self._choice_buffer = self._choice_buffer[:-1]
            self._focus_matching_option(self._choice_buffer)
            self._refresh_ledger()

        def action_focus_next_control(self) -> None:
            self.focus_next()

        def action_focus_previous_control(self) -> None:
            self.focus_previous()

        def on_key(self, event: Any) -> None:
            if self._request.kind == "menu":
                key = getattr(event, "key", "")
                if isinstance(key, str) and len(key) == 1 and key.isprintable():
                    self._choice_buffer, resolved_choice = advance_menu_choice_buffer(
                        self._choice_buffer,
                        key,
                        _menu_option_keys(self._request.options),
                    )
                    self._focus_matching_option(self._choice_buffer)
                    self._refresh_ledger()
                    if resolved_choice is not None:
                        self._submit_response(resolved_choice)
                    event.stop()
                    return

            if self._request.kind == "confirm":
                key = getattr(event, "key", "")
                if key in {"y", "Y"}:
                    self._submit_response(True)
                    event.stop()
                elif key in {"n", "N"}:
                    self._submit_response(False)
                    event.stop()

        def on_button_pressed(self, event: Any) -> None:
            button_id = event.button.id or ""
            if self._request.kind == "menu" and button_id.startswith("option-"):
                self._submit_response(button_id.removeprefix("option-"))
                return
            if self._request.kind == "prompt":
                if button_id == "submit":
                    self._submit_response(self.query_one("#interaction-input", _TEXTUAL_INPUT).value)
                    return
                if button_id == "cancel":
                    self._submit_response(self._request.default)
                    return
            if self._request.kind == "confirm":
                self._submit_response(button_id == "yes")
                return
            self._submit_response(None)

        def on_input_submitted(self, event: Any) -> None:
            if self._request.kind == "prompt":
                self._submit_response(event.value)

    class _HelpScreen(_TEXTUAL_MODAL_SCREEN):
        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
            ("escape", "dismiss_help", "Close"),
        ]

        def __init__(self, *, help_text: str) -> None:
            super().__init__()
            self._help_text = help_text

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_VERTICAL(id="help-dialog"):
                yield _TEXTUAL_STATIC("Help", id="help-dialog-title")
                yield _TEXTUAL_STATIC(self._help_text, id="help-dialog-body")
                with _TEXTUAL_HORIZONTAL(id="help-dialog-actions"):
                    yield _TEXTUAL_BUTTON("Close", id="help-dialog-close", classes="raised-button")

        def on_button_pressed(self, event: Any) -> None:
            button_id = getattr(event.button, "id", "") or ""
            if button_id == "help-dialog-close":
                self.dismiss(None)

        def action_dismiss_help(self) -> None:
            self.dismiss(None)

    class _FileBrowserScreen(_TEXTUAL_MODAL_SCREEN):
        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
            ("escape", "dismiss_cancel", "Cancel"),
        ]

        def __init__(self, *, start_paths: list[Path]) -> None:
            super().__init__()
            self._start_paths = start_paths if start_paths else [Path.home()]
            self._current_path: Path | None = None

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_VERTICAL(id="file-browser-dialog"):
                yield _TEXTUAL_STATIC("Select Target File or Folder", id="file-browser-title")
                if len(self._start_paths) > 1:
                    with _TEXTUAL_HORIZONTAL(id="file-browser-dirs"):
                        for i, p in enumerate(self._start_paths):
                            yield _TEXTUAL_BUTTON(
                                p.name or str(p),
                                id=f"file-browser-dir-{i}",
                                classes="raised-button",
                            )
                yield _TEXTUAL_STATIC("Highlighted: (none)", id="file-browser-selection")
                yield _TEXTUAL_DIRECTORY_TREE(str(self._start_paths[0]), id="file-browser-tree")
                with _TEXTUAL_HORIZONTAL(id="file-browser-actions"):
                    yield _TEXTUAL_BUTTON("Select", id="file-browser-select", classes="raised-button", disabled=True)
                    yield _TEXTUAL_BUTTON("Cancel", id="file-browser-cancel", classes="raised-button")

        def on_mount(self) -> None:
            with suppress(Exception):
                self.query_one("#file-browser-tree").focus()

        def _update_selection(self, path: Path) -> None:
            self._current_path = path
            with suppress(Exception):
                self.query_one("#file-browser-selection", _TEXTUAL_STATIC).update(f"Highlighted: {path}")
                self.query_one("#file-browser-select", _TEXTUAL_BUTTON).disabled = False

        def on_tree_node_highlighted(self, event: Any) -> None:
            node = event.node
            node_data = getattr(node, "data", None)
            if node_data is not None:
                path = getattr(node_data, "path", None)
                if isinstance(path, Path):
                    self._update_selection(path)

        def on_directory_tree_file_selected(self, event: Any) -> None:
            path = getattr(event, "path", None)
            if isinstance(path, Path):
                self.dismiss(path)

        def on_button_pressed(self, event: Any) -> None:
            button_id = getattr(event.button, "id", "") or ""
            if button_id == "file-browser-cancel":
                self.dismiss(None)
            elif button_id == "file-browser-select":
                if self._current_path is not None:
                    self.dismiss(self._current_path)
            elif button_id.startswith("file-browser-dir-"):
                with suppress(Exception):
                    index = int(button_id[len("file-browser-dir-") :])
                    new_path = self._start_paths[index]
                    self.query_one("#file-browser-tree", _TEXTUAL_DIRECTORY_TREE).path = new_path
                    self._current_path = None
                    self.query_one("#file-browser-selection", _TEXTUAL_STATIC).update("Highlighted: (none)")
                    self.query_one("#file-browser-select", _TEXTUAL_BUTTON).disabled = True

        def action_dismiss_cancel(self) -> None:
            self.dismiss(None)

    class SattLintTextualApp(_TEXTUAL_APP):
        TITLE = DEFAULT_SHELL_TITLE

        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
            ("1", "show_analyze", "Analyze"),
            ("2", "show_documentation", "Docs"),
            ("3", "show_setup", "Setup"),
            ("4", "show_tools", "Tools"),
            ("5", "show_help", "Help"),
            ("q", "quit_shell", "Quit"),
            ("tab", "focus_next_control", "Next"),
            ("shift+tab", "focus_previous_control", "Prev"),
        ]

        _ACTION_IDS = (
            "action-analyze",
            "action-documentation",
            "action-setup",
            "action-tools",
            "action-help",
            "action-quit",
        )

        _VIEW_ACTIONS: ClassVar[dict[str, str]] = {
            "action-analyze": "analyze",
            "action-documentation": "documentation",
            "action-setup": "setup",
            "action-tools": "tools",
        }

        CSS = TEXTUAL_SHELL_CSS

        def __init__(
            self,
            *,
            cfg: dict[str, Any],
            summarize_targets_fn: Any,
            analysis_menu_fn: Any,
            documentation_menu_fn: Any,
            config_menu_fn: Any,
            tools_menu_fn: Any,
            show_help_fn: Any,
            save_config_fn: Any,
            config_path: Any,
            quit_app_error: type[BaseException],
            app_module: Any | None = None,
            self_check_fn: Any | None = None,
            dump_menu_fn: Any | None = None,
            source_diff_fn: Any | None = None,
            force_refresh_ast_fn: Any | None = None,
        ) -> None:
            super().__init__()
            self._app_module = app_module
            self._cfg = cfg
            self._summarize_targets_fn = summarize_targets_fn
            self._analysis_menu_fn = analysis_menu_fn
            self._documentation_menu_fn = documentation_menu_fn
            self._config_menu_fn = config_menu_fn
            self._tools_menu_fn = tools_menu_fn
            self._show_help_fn = show_help_fn
            self._save_config_fn = save_config_fn
            self._config_path = config_path
            self._quit_app_error = quit_app_error
            self._busy = False
            self._dirty = False
            self._active_view = "analyze"
            self._active_job_action_id: str | None = None
            self._active_job_label: str | None = None
            self._analyze_focused_entry_id: str | None = None
            self._analyze_selected_entry_ids: set[str] = set()
            self._suppress_analyze_planner_events = False
            self._setup_candidate_index = 0
            self._setup_target_names_list: list[str] = []
            self._selected_configured_target: str | None = None
            self._active_request: InteractionRequest | None = None
            self._active_request_callback: Any = None
            self._interaction_pane: Any = None
            self._self_check_fn = self_check_fn or (lambda _cfg: None)
            self._dump_menu_fn = dump_menu_fn or (lambda _cfg: None)
            self._source_diff_fn = source_diff_fn or (lambda _cfg: None)
            self._force_refresh_ast_fn = force_refresh_ast_fn or (lambda _cfg: None)

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_HORIZONTAL(id="shell-top"):
                yield _ShellBanner()
                yield _TEXTUAL_STATIC("", id="summary")
            with _TEXTUAL_HORIZONTAL(id="actions"):
                yield _TEXTUAL_BUTTON("Analyze", id="action-analyze", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON(
                    "Docs",
                    id="action-documentation",
                    classes="raised-button toolbar-button",
                )
                yield _TEXTUAL_BUTTON("Tools", id="action-tools", classes="raised-button toolbar-button")
                yield _TEXTUAL_STATIC("", id="actions-spacer")
                yield _TEXTUAL_BUTTON("Setup", id="action-setup", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Help", id="action-help", classes="raised-button toolbar-button")
                yield _TEXTUAL_BUTTON("Quit", id="action-quit", classes="raised-button toolbar-button")
            with _TEXTUAL_VERTICAL(id="content-host"):
                with _TEXTUAL_VERTICAL(id="view-host"):
                    yield _TEXTUAL_STATIC("", id="view-title")
                    yield _TEXTUAL_STATIC("", id="view-description")
                    yield _TEXTUAL_STATIC("", id="view-note")
                    with _TEXTUAL_HORIZONTAL(id="view-actions"):
                        yield _TEXTUAL_BUTTON("", id="view-primary-action", classes="raised-button toolbar-button")
                    with _TEXTUAL_HORIZONTAL(id="analyze-actions-primary", classes="is-hidden"):
                        yield _TEXTUAL_BUTTON(
                            "Run selected analyses",
                            id="analyze-run-selected",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Clear selection",
                            id="analyze-clear-selection",
                            classes="raised-button toolbar-button",
                        )
                    with _TEXTUAL_HORIZONTAL(id="analyze-browser", classes="is-hidden"):
                        with _TEXTUAL_VERTICAL(id="analyze-browser-left"):
                            pass
                        yield _TEXTUAL_STATIC("", id="analyze-browser-right")
                    with _TEXTUAL_HORIZONTAL(id="documentation-actions", classes="is-hidden"):
                        yield _TEXTUAL_BUTTON(
                            "Generate DOCX", id="documentation-generate", classes="raised-button toolbar-button"
                        )
                        yield _TEXTUAL_BUTTON(
                            "Preview candidates",
                            id="documentation-preview-candidates",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Use all detected units",
                            id="documentation-scope-all",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Scope by moduletype",
                            id="documentation-scope-moduletype",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Scope by instance path",
                            id="documentation-scope-instance-path",
                            classes="raised-button toolbar-button",
                        )
                    with _TEXTUAL_HORIZONTAL(id="setup-browser", classes="is-hidden"):
                        with _TEXTUAL_VERTICAL(id="setup-targets-col"):
                            yield _TEXTUAL_STATIC("Analysis Targets", classes="setup-section-title")
                            yield _TEXTUAL_LIST_VIEW(id="setup-target-listview")
                            with _TEXTUAL_HORIZONTAL(id="setup-target-actions"):
                                yield _TEXTUAL_BUTTON(
                                    "Remove",
                                    id="setup-target-remove",
                                    classes="raised-button",
                                    disabled=True,
                                )
                                yield _TEXTUAL_BUTTON(
                                    "Add from file...",
                                    id="setup-target-browse",
                                    classes="raised-button",
                                )
                        with _TEXTUAL_VERTICAL(id="setup-settings-col"):
                            yield _TEXTUAL_STATIC("Configuration", classes="setup-section-title")
                            yield _TEXTUAL_STATIC("Directories", classes="setup-group-title")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit program_dir",
                                    id="setup-edit-program-dir",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-program-dir", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit ABB_lib_dir",
                                    id="setup-edit-abb-dir",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-abb-dir", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit other_lib_dirs",
                                    id="setup-edit-other-lib-dirs",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-other-dirs", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Edit icf_dir", id="setup-edit-icf-dir", classes="raised-button setup-row-button"
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-icf-dir", classes="setup-row-label")
                            yield _TEXTUAL_STATIC("Mode & Config", classes="setup-group-title")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle mode", id="setup-toggle-mode", classes="raised-button setup-row-button"
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-mode", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle scan_root_only",
                                    id="setup-toggle-scan-root-only",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-scan-root-only", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle fast_cache_val.",
                                    id="setup-toggle-fast-cache-validation",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-fast-cache", classes="setup-row-label")
                            yield _TEXTUAL_STATIC("Runtime", classes="setup-group-title")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle debug", id="setup-toggle-debug", classes="raised-button setup-row-button"
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-debug", classes="setup-row-label")
                            with _TEXTUAL_HORIZONTAL(classes="setup-row"):
                                yield _TEXTUAL_BUTTON(
                                    "Toggle telemetry",
                                    id="setup-toggle-telemetry",
                                    classes="raised-button setup-row-button",
                                )
                                yield _TEXTUAL_STATIC("", id="setup-label-telemetry", classes="setup-row-label")
                            yield _TEXTUAL_STATIC("Save", classes="setup-group-title")
                            yield _TEXTUAL_BUTTON(
                                "Save configuration", id="setup-save", classes="raised-button setup-row-button"
                            )
                    with _TEXTUAL_HORIZONTAL(id="tools-actions", classes="is-hidden"):
                        yield _TEXTUAL_BUTTON(
                            "Self-check diagnostics",
                            id="tools-self-check",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Diagnostics & dumps",
                            id="tools-dumps",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Source diff report",
                            id="tools-source-diff",
                            classes="raised-button toolbar-button",
                        )
                        yield _TEXTUAL_BUTTON(
                            "Refresh cached ASTs",
                            id="tools-refresh-ast",
                            classes="raised-button toolbar-button",
                        )
                yield _TEXTUAL_STATIC("Session output", id="output-title")
                yield _TEXTUAL_LOG(id="output")
                with _TEXTUAL_VERTICAL(id="interaction-host"):
                    pass
            yield _TEXTUAL_FOOTER()

        def on_mount(self) -> None:
            self._refresh_summary()
            self._refresh_view()
            self._set_active_action(None)
            self._refresh_shell_state()
            self.query_one("#action-analyze", _TEXTUAL_BUTTON).focus()
            self._write_output("Textual shell ready. Use the action bar to move between native TUI views and actions.")

        def _view_state(self, view_name: str) -> _ShellViewState:
            if view_name == "documentation":
                return _ShellViewState(
                    action_id="action-documentation",
                    title="Documentation",
                    description="Preview unit candidates, adjust scope, and generate DOCX output directly from this screen.",
                    note="Documentation actions are available directly in this view.",
                    launch_label="Open Documentation Flow",
                )
            if view_name == "setup":
                return _ShellViewState(
                    action_id="action-setup",
                    title="Setup",
                    description="Click targets to add or remove them, then adjust directories and runtime settings inline.",
                    note="Changes happen directly in this view and remain unsaved until you use Save.",
                    launch_label="Open Setup Flow",
                )
            if view_name == "tools":
                return _ShellViewState(
                    action_id="action-tools",
                    title="Tools",
                    description="Run diagnostics, dumps, source diffs, and cache refresh operations directly from this screen.",
                    note="These buttons are for setup validation and troubleshooting when paths or cached results look wrong.",
                    launch_label="Open Tools Flow",
                )
            if view_name == "help":
                return _ShellViewState(
                    action_id="action-help",
                    title="Help",
                    description="See first-run guidance and the recommended workflow for setup, analysis, and documentation.",
                    note="Open the help flow to print the detailed guidance into the output pane.",
                    launch_label="Show Help Output",
                )
            return _ShellViewState(
                action_id="action-analyze",
                title="Analyze",
                description="Plan one or more analyses, inspect the normalized queue, and run the selected steps directly.",
                note="Build an analysis queue in this view and run the shared planner directly.",
                launch_label="Open Analyze Planner",
            )

        def _setup_candidates(self) -> tuple[_SetupTargetCandidate, ...]:
            return discover_setup_target_candidates(self._cfg)

        def _selected_setup_candidate(self) -> _SetupTargetCandidate | None:
            candidates = self._setup_candidates()
            if not candidates:
                self._setup_candidate_index = 0
                return None
            self._setup_candidate_index %= len(candidates)
            return candidates[self._setup_candidate_index]

        def _setup_candidate_status(self, candidate: _SetupTargetCandidate) -> str:
            if not candidate.available:
                return "not valid for current mode"
            if self._is_target_configured(candidate.name):
                return "already configured"
            return "available"

        def _configured_target_names(self) -> tuple[str, ...]:
            return _stringify_list_values(self._cfg.get("analyzed_programs_and_libraries", []))

        def _summary_text(self) -> str:
            configured_targets = self._configured_target_names()
            if not configured_targets:
                return str(self._summarize_targets_fn(self._cfg))

            target_count = len(configured_targets)
            target_label = "target" if target_count == 1 else "targets"
            target_names = ", ".join(configured_targets)
            return f"{target_count} {target_label} configured\n{target_names}"

        def _documentation_selection(self) -> dict[str, Any]:
            app_module = self._app_module
            if app_module is None:
                return {"mode": "all", "instance_paths": [], "moduletype_names": []}
            selection_fn = getattr(app_module, "_get_documentation_unit_selection", None)
            if not callable(selection_fn):
                return {"mode": "all", "instance_paths": [], "moduletype_names": []}
            selection = selection_fn()
            if not isinstance(selection, dict):
                return {"mode": "all", "instance_paths": [], "moduletype_names": []}
            return cast(dict[str, Any], selection)

        def _documentation_scope_summary_text(self) -> str:
            selection = self._documentation_selection()
            mode = _stringify_value(cast(object | None, selection.get("mode", "all"))).strip().casefold() or "all"
            if mode == "all":
                return "all units"
            if mode == "moduletype_names":
                values = _stringify_list_values(selection.get("moduletype_names"))
                return "moduletype: " + ", ".join(values) if values else "moduletype filter not set"
            if mode == "instance_paths":
                values = _stringify_list_values(selection.get("instance_paths"))
                return "instance path: " + ", ".join(values) if values else "instance-path filter not set"
            return mode

        def _active_job_text(self) -> str | None:
            if not self._busy:
                return None
            label = (self._active_job_label or "").strip()
            return label or None

        def _output_title_text(self) -> str:
            active_job_text = self._active_job_text()
            if active_job_text is None:
                return "Session output"
            return f"Session output - {active_job_text} in progress"

        def _analyze_note_text(self) -> str:
            if self._busy and self._active_job_action_id == "action-analyze":
                return "Selected analyses are running. Live output is shown in Session output below."
            if not self._setup_has_targets():
                return "No analysis targets are configured yet. Add one in Setup to enable the planner queue runner."
            plan = self._analyze_plan()
            if not self._ordered_selected_analyze_entry_ids():
                return "Select one or more analyses below. Suites collapse overlapping leaf checks when the queue is planned."
            if plan.missing_handlers:
                return "Some selected analyses are unavailable in the current Textual session. Review the queue summary before running anything."
            return (
                f"{len(plan.executable_steps)} queued step(s) are ready to run. "
                "Use Run selected analyses to execute the normalized plan in catalog order."
            )

        def _documentation_note_text(self) -> str:
            scope_summary = self._documentation_scope_summary_text()
            if not self._setup_has_targets():
                return "No analysis targets are configured yet. Add one in Setup before previewing units or generating documentation."
            return f"Current scope: {scope_summary}. Preview candidates before narrowing scope if you need a smaller DOCX output."

        def _is_target_configured(self, target_name: str) -> bool:
            return any(existing.casefold() == target_name.casefold() for existing in self._configured_target_names())

        def _set_setup_candidate_by_name(self, target_name: str) -> None:
            for index, candidate in enumerate(self._setup_candidates()):
                if candidate.name.casefold() == target_name.casefold():
                    self._setup_candidate_index = index
                    return

        def _mark_setup_changed(self, message: str, *, reset_candidate_selection: bool = False) -> None:
            self._dirty = True
            if reset_candidate_selection:
                self._setup_candidate_index = 0
            self._refresh_summary()
            self._refresh_view()
            self._set_active_action(None)
            self._refresh_shell_state()
            self._write_output(message)

        def _setup_note_text(self) -> str:
            return (
                "Click a target in the list to select it, then use Remove to delete it. "
                "Use Add from file to add a new target. Settings on the right update immediately."
            )

        def _refresh_setup_target_list(self) -> None:
            try:
                lv = self.query_one("#setup-target-listview", _TEXTUAL_LIST_VIEW)
            except Exception:
                return

            configured_targets = list(self._configured_target_names())

            if self._selected_configured_target is not None and not any(
                t.casefold() == self._selected_configured_target.casefold() for t in configured_targets
            ):
                self._selected_configured_target = None

            self._setup_target_names_list = configured_targets
            lv.clear()
            for target in configured_targets:
                lv.append(_TEXTUAL_LIST_ITEM(_TEXTUAL_STATIC(target)))

            if self._selected_configured_target is not None:
                for i, name in enumerate(configured_targets):
                    if name.casefold() == self._selected_configured_target.casefold():
                        lv.index = i
                        break

            has_selection = self._selected_configured_target is not None and bool(configured_targets)
            with suppress(Exception):
                self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = not has_selection

        def _refresh_setup_settings_labels(self) -> None:
            program_dir = _stringify_value(cast(object | None, self._cfg.get("program_dir", "")))
            abb_dir = _stringify_value(cast(object | None, self._cfg.get("ABB_lib_dir", "")))
            other_dirs = self._cfg.get("other_lib_dirs", [])
            other_dirs_str = (
                ", ".join(_stringify_value(d) for d in cast(list[object], other_dirs))
                if isinstance(other_dirs, list)
                else _stringify_value(cast(object | None, other_dirs))
            )
            icf_dir = _stringify_value(cast(object | None, self._cfg.get("icf_dir", "")))
            mode = _stringify_value(cast(object | None, self._cfg.get("mode", "official"))) or "official"
            scan_root_only = "on" if bool(self._cfg.get("scan_root_only", False)) else "off"
            fast_cache = "on" if bool(self._cfg.get("fast_cache_validation", False)) else "off"
            debug = "on" if bool(self._cfg.get("debug", False)) else "off"
            telemetry = self._cfg.get("telemetry")
            telemetry_enabled = (
                bool(cast(object | None, telemetry.get("enabled", False))) if isinstance(telemetry, dict) else False
            )
            telemetry_str = "on" if telemetry_enabled else "off"

            def _safe_update(widget_id: str, text: str) -> None:
                with suppress(Exception):
                    self.query_one(f"#{widget_id}", _TEXTUAL_STATIC).update(text)

            _safe_update("setup-label-program-dir", program_dir or "(not set)")
            _safe_update("setup-label-abb-dir", abb_dir or "(not set)")
            _safe_update("setup-label-other-dirs", other_dirs_str or "(none)")
            _safe_update("setup-label-icf-dir", icf_dir or "(not set)")
            _safe_update("setup-label-mode", mode)
            _safe_update("setup-label-scan-root-only", scan_root_only)
            _safe_update("setup-label-fast-cache", fast_cache)
            _safe_update("setup-label-debug", debug)
            _safe_update("setup-label-telemetry", telemetry_str)

        def on_list_view_highlighted(self, event: Any) -> None:
            lv = getattr(event, "list_view", None)
            if lv is None or getattr(lv, "id", None) != "setup-target-listview":
                return
            index = getattr(lv, "index", None)
            if index is not None and 0 <= index < len(self._setup_target_names_list):
                self._selected_configured_target = self._setup_target_names_list[index]
            else:
                self._selected_configured_target = None
            has_selection = self._selected_configured_target is not None
            with suppress(Exception):
                self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = not has_selection or not bool(
                    self._configured_target_names()
                )

        def _setup_browser_detail_text(self) -> str:
            candidate = self._selected_setup_candidate()
            directories = _config_directory_paths(self._cfg)
            lines = [
                "Selected Target Detail",
                f"Mode: {self._cfg.get('mode', 'official')}",
                f"scan_root_only: {bool(self._cfg.get('scan_root_only', False))}",
                f"fast_cache_validation: {bool(self._cfg.get('fast_cache_validation', False))}",
            ]
            if candidate is None:
                lines.append("Target: none")
            else:
                lines.append(f"Target: {candidate.name}")
                lines.append(f"Status: {self._setup_candidate_status(candidate)}")
                lines.append("Files:")
                lines.extend(f"- {path}" for path in candidate.files)

            lines.append("")
            lines.append("Directories")
            if directories:
                lines.extend(f"- {path}" for path in directories)
            else:
                lines.append("(none configured)")
            telemetry = self._cfg.get("telemetry")
            telemetry_enabled = (
                bool(cast(object | None, telemetry.get("enabled", False))) if isinstance(telemetry, dict) else False
            )
            lines.append("")
            lines.append("Runtime")
            lines.append(f"debug: {bool(self._cfg.get('debug', False))}")
            lines.append(f"telemetry: {telemetry_enabled}")
            return "\n".join(lines)

        def _add_selected_setup_target(self, target_name: str | None = None) -> None:
            if target_name is not None:
                self._set_setup_candidate_by_name(target_name)
            candidate = self._selected_setup_candidate()
            if candidate is None:
                self._write_output("No discovered target is available to add from the Setup view.")
                return
            if target_name is not None and candidate.name.casefold() != target_name.casefold():
                self._write_output(f"Target '{target_name}' is not currently discovered in the Setup view.")
                return

            targets = self._cfg.setdefault("analyzed_programs_and_libraries", [])
            if not isinstance(targets, list):
                self._write_output("Configured targets are not editable in the current config state.")
                return
            target_values = cast(list[object], targets)
            if any(_stringify_value(existing).casefold() == candidate.name.casefold() for existing in target_values):
                self._write_output(f"Target '{candidate.name}' is already configured.")
                return
            if not candidate.available:
                self._write_output(
                    f"Target '{candidate.name}' is not available for the current mode '{self._cfg.get('mode', 'official')}'."
                )
                return

            target_values.append(candidate.name)
            self._mark_setup_changed(f"Added analysis target '{candidate.name}' from the Setup view.")

        def _remove_selected_setup_target(self, target_name: str | None = None) -> None:
            candidate = self._selected_setup_candidate()
            selected_name = target_name or (candidate.name if candidate is not None else None)
            if selected_name is None:
                self._write_output("No discovered target is selected in the Setup view.")
                return

            if target_name is not None:
                self._set_setup_candidate_by_name(target_name)

            targets = self._cfg.get("analyzed_programs_and_libraries", [])
            if not isinstance(targets, list):
                self._write_output("Configured targets are not editable in the current config state.")
                return
            target_values = cast(list[object], targets)

            remove_index = next(
                (
                    index
                    for index, existing in enumerate(target_values)
                    if _stringify_value(existing).casefold() == selected_name.casefold()
                ),
                None,
            )
            if remove_index is None:
                self._write_output(f"Target '{selected_name}' is not currently configured.")
                return

            removed_name = _stringify_value(target_values.pop(remove_index))
            self._selected_configured_target = None
            self._mark_setup_changed(f"Removed analysis target '{removed_name}' from the Setup view.")

        def _add_target_from_path(self, selected_path: Path) -> None:
            if selected_path.is_dir():
                target_dir = selected_path
                stem: str | None = None
            else:
                target_dir = selected_path.parent
                stem = selected_path.stem

            configured_dirs = {d.resolve() for d in _config_directory_paths(self._cfg)}
            if target_dir.resolve() not in configured_dirs:
                other_dirs = self._cfg.get("other_lib_dirs", [])
                if not isinstance(other_dirs, list):
                    other_dirs = []
                other_dirs.append(str(target_dir))
                self._cfg["other_lib_dirs"] = other_dirs

            if stem is not None:
                targets = self._cfg.setdefault("analyzed_programs_and_libraries", [])
                if isinstance(targets, list):
                    target_values = cast(list[object], targets)
                    if any(_stringify_value(t).casefold() == stem.casefold() for t in target_values):
                        self._write_output(f"Target '{stem}' is already configured.")
                        return
                    target_values.append(stem)
                    self._mark_setup_changed(f"Added '{stem}' as analysis target from file browser.")
                    return
                self._write_output("Configured targets are not editable in the current config state.")
            else:
                self._mark_setup_changed(
                    "Updated directory configuration from file browser.", reset_candidate_selection=True
                )

        def _open_file_browser(self) -> None:
            if _TEXTUAL_DIRECTORY_TREE is None:
                self._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)
                return

            start_paths: list[Path] = []
            seen: set[Path] = set()
            program_dir = _stringify_value(cast(object | None, self._cfg.get("program_dir", ""))).strip()
            if program_dir:
                p = Path(program_dir)
                if p.exists() and p not in seen:
                    start_paths.append(p)
                    seen.add(p)
            other_lib_dirs = self._cfg.get("other_lib_dirs", [])
            if isinstance(other_lib_dirs, list):
                for d in cast(list[object], other_lib_dirs):
                    ds = _stringify_value(d).strip()
                    if ds:
                        p = Path(ds)
                        if p.exists() and p not in seen:
                            start_paths.append(p)
                            seen.add(p)
            if not start_paths:
                start_paths = [Path.home()]

            def _on_browser_result(result: object) -> None:
                if isinstance(result, Path):
                    self._add_target_from_path(result)

            self.push_screen(_FileBrowserScreen(start_paths=start_paths), _on_browser_result)

        def _open_help_popup(self) -> None:
            def _run() -> None:
                lines: list[str] = []

                def _append_help_text(text: object) -> None:
                    lines.append(str(text))

                output_stream = _TextualOutput(emit_text_fn=_append_help_text)
                # Replace sys.stdin with a no-op reader so that input() calls in the
                # help function (used for terminal pause prompts) return immediately
                # rather than blocking this thread and consuming Textual keystrokes.
                _fake_stdin = io.StringIO("")
                _saved_stdin = sys.stdin
                sys.stdin = _fake_stdin
                try:
                    with redirect_stdout(output_stream), redirect_stderr(output_stream):
                        self._show_help_fn(self._cfg)
                except Exception as exc:
                    lines.append(f"Error generating help: {exc}")
                finally:
                    sys.stdin = _saved_stdin
                    # Strip ANSI escape sequences (e.g. from clear_screen)
                    raw = "".join(lines)
                    help_text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw).strip()
                    help_text = help_text or "No help content available."
                    self.call_from_thread(self._show_help_modal, help_text)

            threading.Thread(target=_run, daemon=True).start()

        def _show_help_modal(self, help_text: str) -> None:
            self.push_screen(_HelpScreen(help_text=help_text))

        def _toggle_setup_flag(self, key: str, *, label: str) -> None:
            self._cfg[key] = not bool(self._cfg.get(key, False))
            self._mark_setup_changed(f"Updated {label} from the Setup view.")

        def _toggle_setup_mode(self) -> None:
            current_mode = _stringify_value(cast(object | None, self._cfg.get("mode", "official"))).strip().casefold()
            self._cfg["mode"] = "draft" if current_mode == "official" else "official"
            self._mark_setup_changed("Updated mode from the Setup view.", reset_candidate_selection=True)

        def _toggle_setup_telemetry(self) -> None:
            telemetry = self._cfg.get("telemetry")
            if not isinstance(telemetry, dict):
                telemetry = {"enabled": False}
                self._cfg["telemetry"] = telemetry
            telemetry["enabled"] = not bool(cast(object | None, telemetry.get("enabled", False)))
            self._mark_setup_changed("Updated telemetry from the Setup view.")

        def _setup_has_targets(self) -> bool:
            return bool(self._configured_target_names())

        def _targets_action_allowed(self, action_text: str) -> bool:
            if self._setup_has_targets():
                return True
            self._write_output(f"No configured analysis targets are available for {action_text}.")
            return False

        def _run_app_module_cfg_action(
            self,
            attr_name: str,
            label: str,
            *,
            action_id: str,
            require_targets: bool = False,
            action_text: str | None = None,
            marks_dirty: bool = False,
        ) -> None:
            if require_targets and not self._targets_action_allowed(action_text or label.casefold()):
                return
            app_module = self._app_module
            action_fn = getattr(app_module, attr_name, None) if app_module is not None else None
            if not callable(action_fn):
                self._write_output(f"{label} is unavailable in the current Textual session.")
                return
            self._start_action(
                label,
                lambda action_fn=action_fn: action_fn(self._cfg),
                action_id=action_id,
                marks_dirty=marks_dirty,
            )

        def _run_analyze_checks(self) -> None:
            self._run_app_module_cfg_action(
                "run_checks_menu",
                "Analyzer checks",
                action_id="action-analyze",
                require_targets=True,
                action_text="analysis checks",
            )

        def _run_documentation_generate(self) -> None:
            self._run_app_module_cfg_action(
                "run_generate_documentation",
                "Generate DOCX",
                action_id="action-documentation",
                require_targets=True,
                action_text="documentation generation",
            )

        def _run_documentation_preview_candidates(self) -> None:
            self._run_app_module_cfg_action(
                "preview_documentation_unit_candidates",
                "Preview candidates",
                action_id="action-documentation",
                require_targets=True,
                action_text="documentation preview",
            )

        def _run_documentation_scope_all(self) -> None:
            self._run_app_module_cfg_action(
                "reset_documentation_scope",
                "Use all detected units",
                action_id="action-documentation",
                require_targets=True,
                action_text="documentation scope reset",
                marks_dirty=True,
            )

        def _run_documentation_scope_moduletype(self) -> None:
            self._run_app_module_cfg_action(
                "configure_documentation_scope_by_moduletype",
                "Scope by moduletype",
                action_id="action-documentation",
                require_targets=True,
                action_text="documentation moduletype scoping",
                marks_dirty=True,
            )

        def _run_documentation_scope_instance_path(self) -> None:
            self._run_app_module_cfg_action(
                "configure_documentation_scope_by_instance_path",
                "Scope by instance path",
                action_id="action-documentation",
                require_targets=True,
                action_text="documentation instance-path scoping",
                marks_dirty=True,
            )

        def _run_tool_self_check(self) -> None:
            self._start_action(
                "Self-check diagnostics", lambda: self._self_check_fn(self._cfg), action_id="action-tools"
            )

        def _run_tool_dumps(self) -> None:
            if not self._targets_action_allowed("diagnostics and dumps"):
                return
            self._start_action("Diagnostics & dumps", lambda: self._dump_menu_fn(self._cfg), action_id="action-tools")

        def _run_tool_source_diff(self) -> None:
            if not self._targets_action_allowed("source diff reports"):
                return
            self._start_action("Source diff report", lambda: self._source_diff_fn(self._cfg), action_id="action-tools")

        def _run_tool_refresh_ast(self) -> None:
            if not self._targets_action_allowed("cached AST refresh"):
                return
            self._start_action(
                "Refresh cached ASTs", lambda: self._force_refresh_ast_fn(self._cfg), action_id="action-tools"
            )

        def _prompt_setup_value(self, field_key: str, *, label: str, is_list: bool = False) -> None:
            if self._active_request is not None:
                return

            current_value = self._cfg.get(field_key)
            current_items = cast(list[object], current_value) if isinstance(current_value, list) else []
            default_text = (
                ", ".join(_stringify_value(item) for item in current_items)
                if is_list
                else _stringify_value(cast(object | None, current_value))
            )
            message = (
                f"Enter comma-separated paths for {label}. Leave blank to clear the list."
                if is_list
                else f"Enter a new path for {label}."
            )
            request = InteractionRequest(kind="prompt", message=message, default=default_text)

            def _apply_response(response: object) -> None:
                raw_value = str(response or "").strip()
                new_value: list[str] | str = (
                    [part.strip() for part in raw_value.split(",") if part.strip()] if is_list else raw_value
                )
                if self._cfg.get(field_key) == new_value:
                    return
                self._cfg[field_key] = new_value
                self._dirty = True
                self._setup_candidate_index = 0
                self._refresh_summary()
                self._refresh_view()
                self._set_active_action(None)
                self._refresh_shell_state()
                self._write_output(f"Updated {label} from the Setup view.")

            self.present_request(request, on_response_fn=_apply_response)

        def _activate_view(self, view_name: str) -> None:
            if self._active_view == "setup" and view_name != "setup" and self._dirty:
                self._start_action(
                    "Save configuration",
                    lambda: self._save_config_fn(self._config_path, self._cfg),
                    action_id="action-setup",
                    clear_dirty_on_success=True,
                )
            self._active_view = view_name
            self._refresh_view()
            self._set_active_action(None)
            self._refresh_shell_state()

        def present_request(self, request: InteractionRequest, on_response_fn: Any | None = None) -> None:
            if self._active_request is not None:
                self._complete_request(request, None)
                return

            interaction_host = self.query_one("#interaction-host", _TEXTUAL_VERTICAL)

            def _resolve_response(response: object) -> None:
                self._resolve_request(request, response)

            pane = _InteractionPane(
                request,
                submit_response_fn=_resolve_response,
            )
            self._active_request = request
            self._active_request_callback = on_response_fn
            self._interaction_pane = pane
            interaction_host.mount(pane)
            self._refresh_shell_state()

        def _complete_request(self, request: InteractionRequest, response: object) -> None:
            request.response = response
            request.completed.set()

        def _resolve_request(self, request: InteractionRequest, response: object) -> None:
            if request is not self._active_request:
                return

            pane = self._interaction_pane
            request_callback = self._active_request_callback
            self._active_request = None
            self._active_request_callback = None
            self._interaction_pane = None
            if pane is not None:
                pane.remove()
            self._refresh_shell_state()
            self._complete_request(request, response)
            if request_callback is not None:
                request_callback(response)

        def _refresh_summary(self) -> None:
            summary = self._summary_text()
            active_job_text = self._active_job_text()
            running_suffix = f"\n\nRunning: {active_job_text}" if active_job_text is not None else ""
            dirty_suffix = "\n\nUnsaved configuration changes pending." if self._dirty else ""
            summary_widget = self.query_one("#summary", _TEXTUAL_STATIC)
            summary_widget.update(f"{summary}{running_suffix}{dirty_suffix}")
            summary_widget.set_class(self._dirty, "attention")

        def _set_active_action(self, action_id: str | None) -> None:
            self._active_job_action_id = action_id
            try:
                summary_widget = self.query_one("#summary", _TEXTUAL_STATIC)
                output_widget = self.query_one("#output", _TEXTUAL_LOG)
            except Exception:
                return

            active_view = self._view_state(self._active_view)
            highlighted_action_id = self._active_job_action_id or active_view.action_id
            config_mode = active_view.action_id == "action-setup"
            summary_widget.set_class(config_mode, "config-mode")
            output_widget.set_class(config_mode, "config-mode")
            for button_id in self._ACTION_IDS:
                button = self.query_one(f"#{button_id}", _TEXTUAL_BUTTON)
                button.set_class(button_id == highlighted_action_id, "action-active")
                button.set_class(config_mode and button_id == active_view.action_id, "config-active")

        def _write_output(self, text: str) -> None:
            log_widget = self.query_one("#output", _TEXTUAL_LOG)
            for line in text.splitlines() or [text]:
                if line:
                    log_widget.write_line(line)

        def _emit_output_from_thread(self, text: str) -> None:
            self.call_from_thread(self._write_output, text.rstrip("\n"))

        def _finish_action(self, dirty: bool = False, *, clear_dirty_on_success: bool = False) -> None:
            self._busy = False
            self._active_job_label = None
            if clear_dirty_on_success:
                self._dirty = False
            else:
                self._dirty = self._dirty or dirty
            self._set_active_action(None)
            self._refresh_summary()
            self._refresh_shell_state()
            self._refresh_view()

        def _interaction_screen_active(self) -> bool:
            return self._active_request is not None

        def _handle_toolbar_action(self, button_id: str) -> None:
            if self._interaction_screen_active():
                return
            view_name = self._VIEW_ACTIONS.get(button_id)
            if view_name is not None:
                self._activate_view(view_name)
            elif button_id == "setup-save":
                self._start_action(
                    "Save configuration",
                    lambda: self._save_config_fn(self._config_path, self._cfg),
                    action_id="action-setup",
                    clear_dirty_on_success=True,
                )
            elif button_id == "action-help":
                self._open_help_popup()
            elif button_id == "action-quit":
                if self._busy:
                    self._write_output("An action is still running. Wait for it to finish before quitting.")
                    return
                self._set_active_action(button_id)
                self.exit()

        def action_show_analyze(self) -> None:
            self._handle_toolbar_action("action-analyze")

        def action_show_documentation(self) -> None:
            self._handle_toolbar_action("action-documentation")

        def action_show_setup(self) -> None:
            self._handle_toolbar_action("action-setup")

        def action_show_tools(self) -> None:
            self._handle_toolbar_action("action-tools")

        def action_show_help(self) -> None:
            self._handle_toolbar_action("action-help")

        def action_quit_shell(self) -> None:
            self._handle_toolbar_action("action-quit")

        def action_focus_next_control(self) -> None:
            self.focus_next()

        def action_focus_previous_control(self) -> None:
            self.focus_previous()

        def _start_action(
            self,
            label: str,
            action_fn: Any,
            *,
            action_id: str,
            marks_dirty: bool = False,
            clear_dirty_on_success: bool = False,
        ) -> None:
            if self._busy:
                self._write_output("Another action is still running. Wait for it to finish first.")
                return

            self._busy = True
            self._active_job_label = label
            self._set_active_action(action_id)
            self._refresh_summary()
            self._refresh_shell_state()
            self._refresh_view()
            self._write_output(f"Starting {label}... Live output is shown in this panel.")

            def _run() -> None:
                output_stream = _TextualOutput(emit_text_fn=self._emit_output_from_thread)
                dirty = False
                clear_dirty = False
                try:
                    with redirect_stdout(output_stream), redirect_stderr(output_stream):
                        result = action_fn()
                        dirty = marks_dirty and bool(result)
                        clear_dirty = clear_dirty_on_success
                except self._quit_app_error:
                    self.call_from_thread(self.exit)
                    return
                except Exception as exc:  # pragma: no cover - runtime-only fallback
                    self._emit_output_from_thread(f"{label} failed: {exc}")
                finally:
                    self.call_from_thread(lambda: self._finish_action(dirty, clear_dirty_on_success=clear_dirty))

            threading.Thread(target=_run, daemon=True).start()

        def on_selection_list_selection_toggled(self, event: Any) -> None:
            if self._suppress_analyze_planner_events:
                return
            selection_list = getattr(event, "selection_list", None)
            if selection_list is None:
                return
            if not self._sync_analyze_selection_from_selection_list(selection_list):
                return
            highlighted_entry_id = self._selection_list_highlighted_entry_id(selection_list)
            if highlighted_entry_id is not None:
                self._analyze_focused_entry_id = highlighted_entry_id
            self._refresh_analyze_planner_summary_widgets()
            self._refresh_shell_state()

        def on_selection_list_selection_highlighted(self, event: Any) -> None:
            if self._suppress_analyze_planner_events:
                return
            selection_list = getattr(event, "selection_list", None)
            if selection_list is None:
                return
            if not bool(getattr(selection_list, "has_focus", False)):
                return
            highlighted_entry_id = self._selection_list_highlighted_entry_id(selection_list)
            if highlighted_entry_id is None or highlighted_entry_id == self._analyze_focused_entry_id:
                return
            self._analyze_focused_entry_id = highlighted_entry_id
            self._refresh_analyze_planner_summary_widgets()
            self._refresh_shell_state()

        def _available_analyzer_specs(self) -> tuple[Any, ...]:
            app_module = self._app_module
            get_analyzers_fn = getattr(app_module, "_get_enabled_analyzers", None) if app_module is not None else None
            if not callable(get_analyzers_fn):
                return ()
            analyzers_obj = get_analyzers_fn()
            if isinstance(analyzers_obj, list):
                return cast(tuple[Any, ...], tuple(cast(list[object], analyzers_obj)))
            if isinstance(analyzers_obj, tuple):
                return cast(tuple[Any, ...], analyzers_obj)
            return ()

        def _planner_section_groups(
            self,
        ) -> tuple[tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]], ...]:
            analyzer_specs = self._available_analyzer_specs()
            groups: list[
                tuple[analysis_catalog.AnalysisSectionSpec, tuple[analysis_catalog.AnalysisCatalogEntry, ...]]
            ] = []
            for section in analysis_catalog.analysis_section_specs():
                if section.section_id == analysis_catalog.SECTION_CATALOG_SUITE:
                    continue
                entries = analysis_catalog.analysis_entries_for_section(
                    section.section_id,
                    analyzer_specs=analyzer_specs,
                )
                if not entries:
                    continue
                groups.append((section, entries))
            return tuple(groups)

        def _planner_entry_ids(self) -> tuple[str, ...]:
            return tuple(entry.entry_id for _section, entries in self._planner_section_groups() for entry in entries)

        def _planner_entry(self, entry_id: str | None) -> analysis_catalog.AnalysisCatalogEntry | None:
            if entry_id is None:
                return None
            return analysis_catalog.analysis_catalog_entry(
                entry_id,
                analyzer_specs=self._available_analyzer_specs(),
            )

        def _normalize_analyze_planner_state(self) -> None:
            valid_entry_ids = self._planner_entry_ids()
            valid_entry_id_set = set(valid_entry_ids)
            self._analyze_selected_entry_ids.intersection_update(valid_entry_id_set)
            if self._analyze_focused_entry_id not in valid_entry_id_set:
                self._analyze_focused_entry_id = valid_entry_ids[0] if valid_entry_ids else None

        def _ordered_selected_analyze_entry_ids(self) -> tuple[str, ...]:
            self._normalize_analyze_planner_state()
            return tuple(
                entry_id for entry_id in self._planner_entry_ids() if entry_id in self._analyze_selected_entry_ids
            )

        def _analyze_plan(self) -> analysis_planner.AnalysisPlan:
            return analysis_planner.plan_analysis_entries(
                self._ordered_selected_analyze_entry_ids(),
                analyzer_specs=self._available_analyzer_specs(),
                available_handler_names=analysis_planner.available_handler_names(self._app_module),
            )

        def _analyze_section_list_id(self, section_id: str) -> str:
            return f"{_ANALYZE_PLANNER_LIST_ID_PREFIX}{section_id}"

        def _analyze_section_id_from_list(self, selection_list: Any) -> str | None:
            widget_id = str(getattr(selection_list, "id", "") or "")
            if not widget_id.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
                return None
            return widget_id[len(_ANALYZE_PLANNER_LIST_ID_PREFIX) :]

        def _selection_list_highlighted_entry_id(self, selection_list: Any) -> str | None:
            section_id = self._analyze_section_id_from_list(selection_list)
            if section_id is None:
                return None
            highlighted_index = getattr(selection_list, "highlighted", None)
            if not isinstance(highlighted_index, int) or highlighted_index < 0:
                return None
            try:
                option = selection_list.get_option_at_index(highlighted_index)
            except Exception:
                return None
            value = _stringify_value(cast(object | None, getattr(option, "value", None))).strip()
            entry = self._planner_entry(value)
            return entry.entry_id if entry is not None else None

        def _sync_analyze_selection_from_selection_list(self, selection_list: Any) -> bool:
            section_id = self._analyze_section_id_from_list(selection_list)
            if section_id is None:
                return False
            section_entry_ids = {
                entry.entry_id
                for entry in analysis_catalog.analysis_entries_for_section(
                    section_id,
                    analyzer_specs=self._available_analyzer_specs(),
                )
            }
            selected_ids = {
                _stringify_value(cast(object | None, value)).strip()
                for value in cast(list[object], getattr(selection_list, "selected", []))
            }
            selected_ids.discard("")
            self._analyze_selected_entry_ids.difference_update(section_entry_ids)
            self._analyze_selected_entry_ids.update(selected_ids)
            return True

        def _update_analyze_planner_selection_list(
            self,
            selection_list: Any,
            entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
        ) -> None:
            selection_list.clear_options()
            selection_list.add_options(
                [(entry.label, entry.entry_id, entry.entry_id in self._analyze_selected_entry_ids) for entry in entries]
            )
            if entries:
                highlighted_index = 0
                if self._analyze_focused_entry_id is not None:
                    for index, entry in enumerate(entries):
                        if entry.entry_id == self._analyze_focused_entry_id:
                            highlighted_index = index
                            break
                selection_list.highlighted = highlighted_index

        def _refresh_analyze_planner(self) -> None:
            try:
                container = self.query_one("#analyze-browser-left", _TEXTUAL_VERTICAL)
            except Exception:
                return

            self._suppress_analyze_planner_events = True
            try:
                self._normalize_analyze_planner_state()
                section_groups = self._planner_section_groups()
                if not section_groups:
                    if not list(getattr(container, "children", [])):
                        container.mount(
                            _TEXTUAL_STATIC(
                                "No analysis planner entries are available in the current Textual session.",
                                classes="browser-empty-state",
                            )
                        )
                    return

                expected_list_ids = tuple(
                    self._analyze_section_list_id(section.section_id) for section, _entries in section_groups
                )
                children = tuple(cast(tuple[Any, ...], getattr(container, "children", ())))
                current_list_ids: list[str] = []
                for child_widget in children:
                    child_id = getattr(child_widget, "id", None)
                    if child_id is None:
                        continue
                    child_id_str = str(child_id)
                    if child_id_str.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
                        current_list_ids.append(child_id_str)
                if tuple(current_list_ids) == expected_list_ids and children:
                    for section, entries in section_groups:
                        selection_list = self.query_one(
                            f"#{self._analyze_section_list_id(section.section_id)}",
                            _TEXTUAL_SELECTION_LIST,
                        )
                        self._update_analyze_planner_selection_list(selection_list, entries)
                    return

                for child in list(getattr(container, "children", [])):
                    child.remove()

                for section, entries in section_groups:
                    container.mount(_TEXTUAL_STATIC(section.label, classes="browser-section-title"))
                    if section.description:
                        container.mount(_TEXTUAL_STATIC(section.description, classes="planner-section-note"))
                    selection_list = _TEXTUAL_SELECTION_LIST(
                        *[
                            (entry.label, entry.entry_id, entry.entry_id in self._analyze_selected_entry_ids)
                            for entry in entries
                        ],
                        id=self._analyze_section_list_id(section.section_id),
                        classes="analyze-planner-list",
                    )
                    if entries:
                        highlighted_index = 0
                        if self._analyze_focused_entry_id is not None:
                            for index, entry in enumerate(entries):
                                if entry.entry_id == self._analyze_focused_entry_id:
                                    highlighted_index = index
                                    break
                        selection_list.highlighted = highlighted_index
                    container.mount(selection_list)
            finally:
                self._suppress_analyze_planner_events = False

        def _entry_family_label(self, entry: analysis_catalog.AnalysisCatalogEntry) -> str:
            return analysis_catalog.top_level_analysis_family(entry.family_id).label

        def _entry_section_label(self, entry: analysis_catalog.AnalysisCatalogEntry) -> str:
            for section in analysis_catalog.analysis_section_specs():
                if section.section_id == entry.section_id:
                    return section.label
            return entry.section_id

        def _entry_issue_kind_summary(self, entry: analysis_catalog.AnalysisCatalogEntry) -> str | None:
            issue_kinds = entry.execution.variable_issue_kinds
            if not issue_kinds:
                return None
            return ", ".join(
                kind.name.casefold().replace("_", " ") for kind in sorted(issue_kinds, key=lambda item: item.name)
            )

        def _refresh_analyze_planner_summary_widgets(self) -> None:
            try:
                self.query_one("#view-note", _TEXTUAL_STATIC).update(self._analyze_note_text())
                self.query_one("#analyze-browser-right", _TEXTUAL_STATIC).update(self._analyze_browser_detail_text())
            except Exception:
                return

        def _analyze_browser_detail_text(self) -> str:
            self._normalize_analyze_planner_state()
            focused_entry = self._planner_entry(self._analyze_focused_entry_id)
            plan = self._analyze_plan()
            if self._busy and self._active_job_action_id == "action-analyze":
                status_text = "Status: Running selected analyses. Live output is shown in Session output below."
            elif not self._setup_has_targets():
                status_text = "Status: Configure a target in Setup to enable the planner runner."
            elif not self._ordered_selected_analyze_entry_ids():
                status_text = "Status: Select one or more analyses to build a queue."
            elif plan.missing_handlers:
                status_text = "Status: Queue blocked by unavailable handlers in the current Textual session."
            else:
                status_text = "Status: Ready to run."
            lines = [
                "Analyze planner",
                status_text,
                f"Selected entries: {len(self._ordered_selected_analyze_entry_ids())}",
                f"Runnable steps: {len(plan.executable_steps)}",
            ]
            if focused_entry is not None:
                lines.extend(
                    [
                        "",
                        f"Focused entry: {focused_entry.label}",
                        f"Family: {self._entry_family_label(focused_entry)}",
                        f"Section: {self._entry_section_label(focused_entry)}",
                        f"Description: {focused_entry.description}",
                        f"Action: {focused_entry.execution.action_text}",
                    ]
                )
                if focused_entry.execution.selected_analyzer_keys:
                    lines.append("Analyzer keys: " + ", ".join(focused_entry.execution.selected_analyzer_keys))
                issue_kind_summary = self._entry_issue_kind_summary(focused_entry)
                if issue_kind_summary:
                    lines.append(f"Issue kinds: {issue_kind_summary}")
            lines.extend(["", "Queue summary", analysis_planner.render_analysis_plan_summary(plan)])
            return "\n".join(lines)

        def _execute_planned_analysis_step(self, step: analysis_planner.PlannedAnalysisStep) -> None:
            if step.execution.require_targets and not self._configured_target_names():
                raise RuntimeError(f"No configured analysis targets are available for {step.execution.action_text}.")
            app_module = self._app_module
            if app_module is None:
                raise RuntimeError("Analysis actions are unavailable in the current Textual session.")

            action_fn = getattr(app_module, step.execution.handler_name, None)
            if not callable(action_fn):
                raise RuntimeError(f"{step.label} is unavailable in the current Textual session.")

            if step.execution.kind == "run_checks":
                selected_keys = (
                    None
                    if step.execution.selected_analyzer_keys is None
                    else list(step.execution.selected_analyzer_keys)
                )
                action_fn(self._cfg, selected_keys)
                return
            if step.execution.kind == "run_variable_analysis":
                issue_kinds = (
                    None if step.execution.variable_issue_kinds is None else set(step.execution.variable_issue_kinds)
                )
                action_fn(self._cfg, issue_kinds)
                return
            action_fn(self._cfg)

        def _execute_analyze_plan(self, plan: analysis_planner.AnalysisPlan) -> None:
            print("Analyze planner queue")
            print(analysis_planner.render_analysis_plan_summary(plan))
            total_steps = len(plan.executable_steps)
            for index, step in enumerate(plan.executable_steps, start=1):
                print("")
                print(f"[{index}/{total_steps}] {step.label}")
                if len(step.source_labels) > 1:
                    print("Merged selections: " + ", ".join(step.source_labels))
                self._execute_planned_analysis_step(step)
            print("")
            print("Selected analyses completed.")

        def _run_selected_analysis_plan(self) -> None:
            if not self._targets_action_allowed("analysis planning"):
                return
            if not self._ordered_selected_analyze_entry_ids():
                self._write_output("Select one or more analyses in the planner first.")
                return
            plan = self._analyze_plan()
            if not plan.is_runnable:
                self._write_output(analysis_planner.render_analysis_plan_summary(plan))
                return
            self._start_action(
                "Run selected analyses",
                lambda plan=plan: self._execute_analyze_plan(plan),
                action_id="action-analyze",
            )

        def _clear_selected_analysis_plan(self) -> None:
            if not self._analyze_selected_entry_ids:
                return
            self._analyze_selected_entry_ids.clear()
            self._refresh_view()
            self._refresh_shell_state()
            self._write_output("Cleared the analyze planner selection.")

        def _refresh_view(self) -> None:
            try:
                view_host = self.query_one("#view-host", _TEXTUAL_VERTICAL)
                title_widget = self.query_one("#view-title", _TEXTUAL_STATIC)
                description_widget = self.query_one("#view-description", _TEXTUAL_STATIC)
                note_widget = self.query_one("#view-note", _TEXTUAL_STATIC)
                view_actions = self.query_one("#view-actions", _TEXTUAL_HORIZONTAL)
                launch_button = self.query_one("#view-primary-action", _TEXTUAL_BUTTON)
                analyze_actions_primary = self.query_one("#analyze-actions-primary", _TEXTUAL_HORIZONTAL)
                analyze_browser = self.query_one("#analyze-browser", _TEXTUAL_HORIZONTAL)
                analyze_right_widget = self.query_one("#analyze-browser-right", _TEXTUAL_STATIC)
                documentation_actions = self.query_one("#documentation-actions", _TEXTUAL_HORIZONTAL)
                setup_browser = self.query_one("#setup-browser", _TEXTUAL_HORIZONTAL)
                tools_actions = self.query_one("#tools-actions", _TEXTUAL_HORIZONTAL)
            except Exception:
                return

            view = self._view_state(self._active_view)
            analyze_view = self._active_view == "analyze"
            documentation_view = self._active_view == "documentation"
            setup_view = self._active_view == "setup"
            tools_view = self._active_view == "tools"

            title_widget.update(view.title)
            description_widget.update(view.description)
            if analyze_view:
                note_widget.update(self._analyze_note_text())
            elif documentation_view:
                note_widget.update(self._documentation_note_text())
            elif setup_view:
                note_widget.update(self._setup_note_text())
            else:
                note_widget.update(view.note)
            launch_button.label = view.launch_label
            view_host.set_class(view.action_id == "action-setup", "config-mode")
            note_widget.set_class(False, "is-hidden")
            view_actions.set_class(self._active_view not in ("help",), "is-hidden")
            analyze_actions_primary.set_class(not analyze_view, "is-hidden")
            analyze_browser.set_class(not analyze_view, "is-hidden")
            documentation_actions.set_class(not documentation_view, "is-hidden")
            setup_browser.set_class(not setup_view, "is-hidden")
            tools_actions.set_class(not tools_view, "is-hidden")

            if analyze_view:
                self._refresh_analyze_planner()
                analyze_right_widget.update(self._analyze_browser_detail_text())
            else:
                analyze_right_widget.update("")

            if setup_view:
                self._refresh_setup_target_list()
                self._refresh_setup_settings_labels()

        def _launch_active_view(self) -> None:
            view = self._view_state(self._active_view)
            if view.action_id == "action-documentation":
                self._write_output("Documentation actions are available directly in the Documentation view.")
                return
            if view.action_id == "action-analyze":
                self._write_output("The analyze planner is available directly in the Analyze view.")
                return
            if view.action_id == "action-setup":
                self._write_output("Setup actions are available directly in the Setup view.")
                return
            if view.action_id == "action-tools":
                self._write_output("Tool actions are available directly in the Tools view.")
                return
            if view.action_id == "action-help":
                self._open_help_popup()
                return
            self._start_action("Analyze", lambda: self._analysis_menu_fn(self._cfg), action_id=view.action_id)

        def _refresh_shell_state(self) -> None:
            try:
                output_title_widget = self.query_one("#output-title", _TEXTUAL_STATIC)
                output_widget = self.query_one("#output", _TEXTUAL_LOG)
                interaction_host = self.query_one("#interaction-host", _TEXTUAL_VERTICAL)
                launch_button = self.query_one("#view-primary-action", _TEXTUAL_BUTTON)
                analyze_run_selected_button = self.query_one("#analyze-run-selected", _TEXTUAL_BUTTON)
                analyze_clear_selection_button = self.query_one("#analyze-clear-selection", _TEXTUAL_BUTTON)
                documentation_generate_button = self.query_one("#documentation-generate", _TEXTUAL_BUTTON)
                documentation_preview_button = self.query_one("#documentation-preview-candidates", _TEXTUAL_BUTTON)
                documentation_scope_all_button = self.query_one("#documentation-scope-all", _TEXTUAL_BUTTON)
                documentation_scope_moduletype_button = self.query_one(
                    "#documentation-scope-moduletype", _TEXTUAL_BUTTON
                )
                documentation_scope_instance_button = self.query_one(
                    "#documentation-scope-instance-path", _TEXTUAL_BUTTON
                )
                tools_self_check_button = self.query_one("#tools-self-check", _TEXTUAL_BUTTON)
                tools_dumps_button = self.query_one("#tools-dumps", _TEXTUAL_BUTTON)
                tools_source_diff_button = self.query_one("#tools-source-diff", _TEXTUAL_BUTTON)
                tools_refresh_ast_button = self.query_one("#tools-refresh-ast", _TEXTUAL_BUTTON)
            except Exception:
                return

            output_title_widget.update(self._output_title_text())
            interaction_active = self._active_request is not None
            output_widget.set_class(interaction_active, "interaction-active")
            interaction_host.set_class(interaction_active, "active")
            toolbar_disabled = self._busy or interaction_active
            launch_button.disabled = toolbar_disabled
            analyze_view = self._active_view == "analyze"
            documentation_view = self._active_view == "documentation"
            setup_view = self._active_view == "setup"
            tools_view = self._active_view == "tools"
            analyze_plan = self._analyze_plan()

            analyze_run_selected_button.disabled = (
                toolbar_disabled or not analyze_view or not self._setup_has_targets() or not analyze_plan.is_runnable
            )
            analyze_clear_selection_button.disabled = (
                toolbar_disabled or not analyze_view or not bool(self._analyze_selected_entry_ids)
            )
            for selection_list in self.query(_TEXTUAL_SELECTION_LIST):
                widget_id = str(getattr(selection_list, "id", "") or "")
                if widget_id.startswith(_ANALYZE_PLANNER_LIST_ID_PREFIX):
                    selection_list.disabled = toolbar_disabled or not analyze_view

            documentation_buttons = (
                documentation_generate_button,
                documentation_preview_button,
                documentation_scope_all_button,
                documentation_scope_moduletype_button,
                documentation_scope_instance_button,
            )
            for button in documentation_buttons:
                button.disabled = toolbar_disabled or not documentation_view or not self._setup_has_targets()
            for btn_id in (
                "setup-edit-program-dir",
                "setup-edit-abb-dir",
                "setup-edit-other-lib-dirs",
                "setup-edit-icf-dir",
                "setup-toggle-mode",
                "setup-toggle-scan-root-only",
                "setup-toggle-fast-cache-validation",
                "setup-toggle-debug",
                "setup-toggle-telemetry",
                "setup-target-browse",
            ):
                with suppress(Exception):
                    self.query_one(f"#{btn_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled or not setup_view
            with suppress(Exception):
                self.query_one("#setup-save", _TEXTUAL_BUTTON).disabled = (
                    toolbar_disabled or not setup_view or not self._dirty
                )
            with suppress(Exception):
                self.query_one("#setup-target-remove", _TEXTUAL_BUTTON).disabled = (
                    toolbar_disabled
                    or not setup_view
                    or not bool(self._configured_target_names())
                    or self._selected_configured_target is None
                )
            if setup_view:
                self._refresh_setup_settings_labels()
            tools_self_check_button.disabled = toolbar_disabled or not tools_view
            tools_dumps_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
            tools_source_diff_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
            tools_refresh_ast_button.disabled = toolbar_disabled or not tools_view or not self._setup_has_targets()
            for button_id in self._ACTION_IDS:
                try:
                    self.query_one(f"#{button_id}", _TEXTUAL_BUTTON).disabled = toolbar_disabled
                except Exception:
                    continue

        def on_button_pressed(self, event: Any) -> None:
            button_id = event.button.id or ""
            if button_id == "setup-target-remove":
                self._remove_selected_setup_target(self._selected_configured_target)
                return
            if button_id == "setup-target-browse":
                self._open_file_browser()
                return
            if button_id == "view-primary-action":
                self._launch_active_view()
                return
            if button_id == "analyze-run-selected":
                self._run_selected_analysis_plan()
                return
            if button_id == "analyze-clear-selection":
                self._clear_selected_analysis_plan()
                return
            if button_id == "documentation-generate":
                self._run_documentation_generate()
                return
            if button_id == "documentation-preview-candidates":
                self._run_documentation_preview_candidates()
                return
            if button_id == "documentation-scope-all":
                self._run_documentation_scope_all()
                return
            if button_id == "documentation-scope-moduletype":
                self._run_documentation_scope_moduletype()
                return
            if button_id == "documentation-scope-instance-path":
                self._run_documentation_scope_instance_path()
                return
            if button_id == "setup-edit-program-dir":
                self._prompt_setup_value("program_dir", label="program_dir")
                return
            if button_id == "setup-edit-abb-dir":
                self._prompt_setup_value("ABB_lib_dir", label="ABB_lib_dir")
                return
            if button_id == "setup-edit-other-lib-dirs":
                self._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)
                return
            if button_id == "setup-toggle-mode":
                self._toggle_setup_mode()
                return
            if button_id == "setup-toggle-scan-root-only":
                self._toggle_setup_flag("scan_root_only", label="scan_root_only")
                return
            if button_id == "setup-toggle-fast-cache-validation":
                self._toggle_setup_flag("fast_cache_validation", label="fast_cache_validation")
                return
            if button_id == "setup-edit-icf-dir":
                self._prompt_setup_value("icf_dir", label="icf_dir")
                return
            if button_id == "setup-toggle-debug":
                self._toggle_setup_flag("debug", label="debug")
                return
            if button_id == "setup-toggle-telemetry":
                self._toggle_setup_telemetry()
                return
            if button_id == "tools-self-check":
                self._run_tool_self_check()
                return
            if button_id == "tools-dumps":
                self._run_tool_dumps()
                return
            if button_id == "tools-source-diff":
                self._run_tool_source_diff()
                return
            if button_id == "tools-refresh-ast":
                self._run_tool_refresh_ast()
                return
            self._handle_toolbar_action(button_id)


def run_textual_shell(
    cfg: dict[str, Any],
    *,
    app_module: Any,
    summarize_targets_fn: Any,
    analysis_menu_fn: Any,
    documentation_menu_fn: Any,
    config_menu_fn: Any,
    tools_menu_fn: Any,
    show_help_fn: Any,
    save_config_fn: Any,
    config_path: Any,
    quit_app_error: type[BaseException],
    **_unused: Any,
) -> None:
    if _TEXTUAL_APP is None:
        raise RuntimeError("Textual UI requested, but textual is not installed")

    textual_app = SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=summarize_targets_fn,
        analysis_menu_fn=analysis_menu_fn,
        documentation_menu_fn=documentation_menu_fn,
        config_menu_fn=config_menu_fn,
        tools_menu_fn=tools_menu_fn,
        app_module=app_module,
        self_check_fn=app_module.self_check,
        dump_menu_fn=app_module.dump_menu,
        source_diff_fn=lambda cfg: app_module.run_source_diff_report(cfg, _pause_fn=lambda: None),  # type: ignore[misc]
        force_refresh_ast_fn=app_module.force_refresh_ast,
        show_help_fn=show_help_fn,
        save_config_fn=save_config_fn,
        config_path=config_path,
        quit_app_error=quit_app_error,
    )
    bridge = TextualInteractionBridge(
        submit_request_fn=lambda request: textual_app.call_from_thread(textual_app.present_request, request)
    )
    app_module.set_textual_menu_interaction(bridge.as_menu_interaction())
    try:
        textual_app.run()
    finally:
        app_module.clear_textual_menu_interaction()
