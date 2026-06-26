# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportConstantRedefinition=false, reportPrivateUsage=false, reportUnusedClass=false, reportUnusedFunction=false, reportUnknownArgumentType=false

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from ._app_textual_shared import (
    _TEXTUAL_APP,
    _TEXTUAL_BUTTON,
    _TEXTUAL_COMPOSE_RESULT,
    _TEXTUAL_DIRECTORY_TREE,
    _TEXTUAL_HORIZONTAL,
    _TEXTUAL_INPUT,
    _TEXTUAL_LIST_ITEM,
    _TEXTUAL_LIST_VIEW,
    _TEXTUAL_MODAL_SCREEN,
    _TEXTUAL_STATIC,
    _TEXTUAL_VERTICAL,
    InteractionRequest,
    _menu_option_keys,
    _query_required,
    advance_menu_choice_buffer,
    interaction_ledger_text,
)

if _TEXTUAL_APP is not None:

    class _ShellBannerImpl(_TEXTUAL_VERTICAL):
        def __init__(self) -> None:
            super().__init__(id="shell-banner")

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            yield _TEXTUAL_STATIC("", id="shell-banner-title")
            yield _TEXTUAL_STATIC("", id="shell-banner-subtitle")

        def on_mount(self) -> None:
            title_widget = self.query_one("#shell-banner-title", _TEXTUAL_STATIC)
            subtitle_widget = self.query_one("#shell-banner-subtitle", _TEXTUAL_STATIC)
            title_widget.update("")
            subtitle_widget.update("Analysis, docs, setup, and tools")

    class _InteractionPaneImpl(_TEXTUAL_VERTICAL):
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

    class _HelpScreenImpl(_TEXTUAL_MODAL_SCREEN):
        CSS = """
        Screen {
            background: transparent !important;
        }
        """

        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "dismiss_help", "Close")]

        def __init__(self, *, help_text: str) -> None:
            super().__init__()
            self._help_text = help_text

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_VERTICAL(id="help-overlay"), _TEXTUAL_VERTICAL(id="help-dialog"):
                yield _TEXTUAL_STATIC("Help & Guide", id="help-dialog-title")
                yield _TEXTUAL_STATIC(self._help_text, id="help-dialog-body")
                with _TEXTUAL_HORIZONTAL(id="help-dialog-actions"):
                    yield _TEXTUAL_BUTTON("Close guide", id="help-dialog-close", classes="raised-button")

        def on_button_pressed(self, event: Any) -> None:
            button_id = getattr(event.button, "id", "") or ""
            if button_id == "help-dialog-close":
                self.dismiss(None)

        def action_dismiss_help(self) -> None:
            self.dismiss(None)

    class _FileBrowserScreenImpl(_TEXTUAL_MODAL_SCREEN):
        BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "dismiss_cancel", "Cancel")]

        def __init__(
            self,
            *,
            start_paths: list[Path],
            candidates: tuple[tuple[str, tuple[str, ...]], ...] = (),
        ) -> None:
            super().__init__()
            self._start_paths = start_paths if start_paths else [Path.home()]
            self._current_path: Path | None = None
            self._candidates = candidates
            self._candidate_name: str | None = None
            self._show_candidate_list = bool(candidates)

        def compose(self) -> _TEXTUAL_COMPOSE_RESULT:
            with _TEXTUAL_VERTICAL(id="file-browser-dialog"):
                yield _TEXTUAL_STATIC("Select Target File or Folder", id="file-browser-title")
                if len(self._start_paths) > 1 and not self._show_candidate_list:
                    with _TEXTUAL_HORIZONTAL(id="file-browser-dirs"):
                        for i, p in enumerate(self._start_paths):
                            yield _TEXTUAL_BUTTON(p.name or str(p), id=f"file-browser-dir-{i}", classes="raised-button")
                yield _TEXTUAL_STATIC("Highlighted: (none)", id="file-browser-selection")
                if self._show_candidate_list:
                    yield _TEXTUAL_STATIC(
                        "Discovered targets are grouped by base name so sibling files appear once.",
                        id="file-browser-intro",
                    )
                    yield _TEXTUAL_LIST_VIEW(id="file-browser-targets")
                else:
                    yield _TEXTUAL_DIRECTORY_TREE(str(self._start_paths[0]), id="file-browser-tree")
                with _TEXTUAL_HORIZONTAL(id="file-browser-actions"):
                    yield _TEXTUAL_BUTTON("Select", id="file-browser-select", classes="raised-button", disabled=True)
                    if self._candidates:
                        yield _TEXTUAL_BUTTON(
                            "Browse filesystem",
                            id="file-browser-browse-filesystem",
                            classes="raised-button",
                        )
                    yield _TEXTUAL_BUTTON("Cancel", id="file-browser-cancel", classes="raised-button")

        def on_mount(self) -> None:
            if self._show_candidate_list:
                list_view = _query_required(self, "#file-browser-targets", _TEXTUAL_LIST_VIEW)
                list_view.clear()
                for name, _paths in self._candidates:
                    list_view.append(_TEXTUAL_LIST_ITEM(_TEXTUAL_STATIC(name)))
                if self._candidates:
                    list_view.index = 0
                list_view.focus()
                self._set_candidate_selection(0)
                return
            _query_required(self, "#file-browser-tree").focus()

        def _candidate_summary(self, index: int) -> str:
            if not (0 <= index < len(self._candidates)):
                return "Highlighted: (none)"
            name, paths = self._candidates[index]
            return f"Highlighted: {name} ({', '.join(paths)})"

        def _set_candidate_selection(self, index: int | None) -> None:
            if index is None or not (0 <= index < len(self._candidates)):
                self._candidate_name = None
                _query_required(self, "#file-browser-selection", _TEXTUAL_STATIC).update("Highlighted: (none)")
                _query_required(self, "#file-browser-select", _TEXTUAL_BUTTON).disabled = True
                return
            self._candidate_name = self._candidates[index][0]
            _query_required(self, "#file-browser-selection", _TEXTUAL_STATIC).update(self._candidate_summary(index))
            _query_required(self, "#file-browser-select", _TEXTUAL_BUTTON).disabled = False

        def _update_selection(self, path: Path) -> None:
            self._current_path = path
            _query_required(self, "#file-browser-selection", _TEXTUAL_STATIC).update(f"Highlighted: {path}")
            _query_required(self, "#file-browser-select", _TEXTUAL_BUTTON).disabled = False

        def on_list_view_highlighted(self, event: Any) -> None:
            if not self._show_candidate_list:
                return
            list_view = getattr(event, "list_view", None)
            if list_view is None or getattr(list_view, "id", None) != "file-browser-targets":
                return
            index = getattr(list_view, "index", None)
            self._set_candidate_selection(index if isinstance(index, int) else None)

        def on_list_view_selected(self, event: Any) -> None:
            if not self._show_candidate_list:
                return
            list_view = getattr(event, "list_view", None)
            if list_view is None or getattr(list_view, "id", None) != "file-browser-targets":
                return
            index = getattr(list_view, "index", None)
            if isinstance(index, int) and 0 <= index < len(self._candidates):
                self.dismiss(self._candidates[index][0])

        def on_tree_node_highlighted(self, event: Any) -> None:
            node_data = getattr(event.node, "data", None)
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
                if self._show_candidate_list:
                    if self._candidate_name is not None:
                        self.dismiss(self._candidate_name)
                elif self._current_path is not None:
                    self.dismiss(self._current_path)
            elif button_id == "file-browser-browse-filesystem":
                self._show_candidate_list = False
                self.app.pop_screen()
                self.app.push_screen(_FileBrowserScreen(start_paths=self._start_paths))
            elif button_id.startswith("file-browser-dir-"):
                index = int(button_id[len("file-browser-dir-") :])
                new_path = self._start_paths[index]
                _query_required(self, "#file-browser-tree", _TEXTUAL_DIRECTORY_TREE).path = new_path
                self._current_path = None
                _query_required(self, "#file-browser-selection", _TEXTUAL_STATIC).update("Highlighted: (none)")
                _query_required(self, "#file-browser-select", _TEXTUAL_BUTTON).disabled = True

        def action_dismiss_cancel(self) -> None:
            self.dismiss(None)

    _ShellBanner = _ShellBannerImpl
    _InteractionPane = _InteractionPaneImpl
    _HelpScreen = _HelpScreenImpl
    _FileBrowserScreen = _FileBrowserScreenImpl
else:  # pragma: no cover - optional dependency path
    _ShellBanner: Any = None
    _InteractionPane: Any = None
    _HelpScreen: Any = None
    _FileBrowserScreen: Any = None
