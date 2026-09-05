# pyright: reportArgumentType=false
from __future__ import annotations

import logging

import pytest

from sattlint.core.debug import log_debug_exception


def test_log_debug_exception_logs_traceback_when_debug_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("SattLint")

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            log_debug_exception({"debug": False}, "Production failure", logger=logger)

    assert any("Production failure" in message for message in caplog.messages)
    assert "Traceback (most recent call last)" in caplog.text
