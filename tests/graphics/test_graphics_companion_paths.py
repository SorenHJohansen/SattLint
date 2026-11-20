from pathlib import Path

import pytest

from sattlint.core.syntax import CodeMode
from sattlint.graphics.graphics_context_helpers import resolve_graphics_companion_path


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("graphics", encoding="utf-8")
    return path


def test_draft_body_pairs_with_draft_companion(tmp_path: Path) -> None:
    graphics = _write(tmp_path / "Pump.g")

    resolved = resolve_graphics_companion_path(tmp_path / "Pump.s", mode=CodeMode.DRAFT)

    assert resolved == graphics


def test_official_body_pairs_with_official_companion(tmp_path: Path) -> None:
    graphics = _write(tmp_path / "Pump.y")

    resolved = resolve_graphics_companion_path(tmp_path / "Pump.x", mode=CodeMode.OFFICIAL)

    assert resolved == graphics


def test_mode_text_selects_the_same_family(tmp_path: Path) -> None:
    graphics = _write(tmp_path / "Pump.g")

    resolved = resolve_graphics_companion_path(tmp_path / "Pump.s", mode="draft")

    assert resolved == graphics


@pytest.mark.parametrize(
    ("body_name", "companion_name", "mode"),
    [
        ("Pump.x", "Pump.g", CodeMode.DRAFT),
        ("Pump.s", "Pump.y", CodeMode.DRAFT),
    ],
)
def test_companion_never_crosses_families(
    tmp_path: Path,
    body_name: str,
    companion_name: str,
    mode: CodeMode,
) -> None:
    _write(tmp_path / companion_name)

    resolved = resolve_graphics_companion_path(tmp_path / body_name, mode=mode)

    assert resolved is None


def test_companion_stem_matches_ignoring_case(tmp_path: Path) -> None:
    graphics = _write(tmp_path / "pump.g")

    resolved = resolve_graphics_companion_path(tmp_path / "PUMP.s", mode=CodeMode.DRAFT)

    assert resolved == graphics


def test_graphics_input_resolves_to_itself_without_touching_disk(tmp_path: Path) -> None:
    graphics_path = tmp_path / "Pump.g"

    resolved = resolve_graphics_companion_path(graphics_path, mode=CodeMode.DRAFT)

    assert resolved == graphics_path


def test_missing_mode_keeps_the_draft_family(tmp_path: Path) -> None:
    graphics = _write(tmp_path / "Pump.g")

    resolved = resolve_graphics_companion_path(tmp_path / "Pump.s")

    assert resolved == graphics
