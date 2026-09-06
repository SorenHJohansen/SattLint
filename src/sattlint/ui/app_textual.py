from __future__ import annotations

from ._app_textual_app import SattLintTextualApp, run_textual_shell
from ._app_textual_shared import (
    DEFAULT_SHELL_TITLE,
    TEXTUAL_SHELL_CSS,
    InteractionRequest,
    TextualInteractionBridge,
    advance_menu_choice_buffer,
    discover_setup_target_candidates,
    has_textual,
    interaction_ledger_text,
    resolve_shell_title,
)

__all__ = [
    "DEFAULT_SHELL_TITLE",
    "TEXTUAL_SHELL_CSS",
    "InteractionRequest",
    "SattLintTextualApp",
    "TextualInteractionBridge",
    "advance_menu_choice_buffer",
    "discover_setup_target_candidates",
    "has_textual",
    "interaction_ledger_text",
    "resolve_shell_title",
    "run_textual_shell",
]
