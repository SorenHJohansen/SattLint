from __future__ import annotations

from typing import Any

from ..framework import Issue


def empty_issue_list() -> list[Issue]:
    return []


def empty_int_summary_data() -> dict[str, int]:
    return {}


def empty_object_summary_data() -> dict[str, object]:
    return {}


def empty_any_summary_data() -> dict[str, Any]:
    return {}
