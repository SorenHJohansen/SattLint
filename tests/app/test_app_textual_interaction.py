# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false
"""Interaction host requests and prompt handling."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from sattlint import ui as app_textual
from sattlint.ui import _app_textual_actions as app_textual_actions_module
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from tests.helpers.app_textual_support import (
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)

# Re-export the autouse fixtures so pytest registers them for this module.
__all__ = [
    "isolate_app_config_path",
    "isolate_textual_projects",
]


def test_textual_present_request_uses_inline_host_and_preserves_shell_chrome() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        request = app_textual_shared_module.InteractionRequest(
            kind="menu",
            title="Analyze",
            options=(
                SimpleNamespace(key="1", label="Run analysis", description=""),
                SimpleNamespace(key="b", label="Back", description=""),
            ),
        )

        async with app_instance.run_test() as pilot:
            app_instance.present_request(request)
            await pilot.pause()

            assert len(list(app_instance.query("#shell-banner"))) == 0
            assert len(list(app_instance.query("#status-summary"))) == 1
            assert app_instance.query_one("#interaction-host").has_class("active")
            assert app_instance.query_one("#output").has_class("interaction-active")

            await pilot.press("escape")
            await pilot.pause()

            assert request.result_future.done() is True
            assert request.result_future.result() == "b"
            assert request.response == "b"
            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance.query_one("#output").has_class("interaction-active") is False

    asyncio.run(_run())


def test_textual_second_request_waits_instead_of_being_denied() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()
        first = app_textual_shared_module.InteractionRequest(
            kind="confirm",
            title="First",
            message="Proceed?",
        )
        second = app_textual_shared_module.InteractionRequest(
            kind="prompt",
            title="Second",
            message="Name?",
            default="keep",
        )

        async with app_instance.run_test() as pilot:
            app_instance.present_request(first)
            app_instance.present_request(second)
            await pilot.pause()

            assert app_instance._active_request is first
            assert second.result_future.done() is False

            await pilot.press("escape")
            await pilot.pause()

            assert first.result_future.done() is True
            assert app_instance._active_request is second

            await pilot.press("escape")
            await pilot.pause()

            assert second.result_future.done() is True
            assert second.result_future.result() == "keep"
            assert app_instance._active_request is None

    asyncio.run(_run())


def test_textual_cancelled_prompt_does_not_run_its_response_callback() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()
        responses: list[object] = []
        request = app_textual_shared_module.InteractionRequest(
            kind="prompt",
            title="New configuration",
            message="Enter a name.",
            default=None,
        )

        async with app_instance.run_test() as pilot:
            app_instance.present_request(request, on_response_fn=responses.append)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            assert request.cancelled is True
            assert responses == []
            assert request.result_future.result() is None
            assert app_instance._active_request is None

            submitted = app_textual_shared_module.InteractionRequest(
                kind="prompt",
                title="New configuration",
                message="Enter a name.",
                default=None,
            )
            app_instance.present_request(submitted, on_response_fn=responses.append)
            await pilot.pause()
            app_instance.query_one("#interaction-input").value = "Alpha"
            await pilot.click("#submit")
            await pilot.pause()

            assert submitted.cancelled is False
            assert responses == ["Alpha"]

    asyncio.run(_run())


def test_textual_interaction_menu_without_options_can_mount_and_close() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance.present_request(
                app_textual_shared_module.InteractionRequest(kind="menu", title="Nothing to choose")
            )
            await pilot.pause()

            assert app_instance._active_request is not None
            assert app_instance.query_one("#interaction-empty") is not None

            await pilot.press("enter")
            await pilot.pause()

            assert app_instance._active_request is None

    asyncio.run(_run())


def test_textual_failed_interaction_mount_leaves_the_shell_unlocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        class _BrokenPane:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                raise RuntimeError("pane wiring failed")

        monkeypatch.setattr(app_textual_actions_module, "_InteractionPane", _BrokenPane)

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            with pytest.raises(RuntimeError, match="pane wiring failed"):
                app_instance.present_request(
                    app_textual_shared_module.InteractionRequest(kind="confirm", message="Continue?")
                )

            assert app_instance._active_request is None
            assert app_instance._interaction_pane is None

    asyncio.run(_run())
