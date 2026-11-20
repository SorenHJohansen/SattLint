from pathlib import Path

from sattline_parser.ast import ModuleDef, ModuleHeader
from sattline_parser.models.ast_model import BasePicture

from sattlint.graphics.picture_display_paths import resolve_picture_display_path
from sattlint.graphics.validation import (
    picture_display_asset_candidate_paths,
    validate_graphics_text,
)


def _base_picture(program_dir: Path) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(),
        origin_file=str(program_dir / "Root.s"),
    )


def _resolve(path_text: str, program_dir: Path):
    return resolve_picture_display_path(
        path_text, base_picture=_base_picture(program_dir), declaring_module_path=["Root"]
    )


def _picture_display_graphics_text(path_text: str) -> str:
    return f"5\n1\n1\n1\n2\n1\n0 {path_text}\n1\nT\n0\n\n"


def _assert_silent_skip(path_text: str, program_dir: Path) -> None:
    resolution = _resolve(path_text, program_dir)
    assert resolution.ok
    assert resolution.failure_reason is None
    assert resolution.detail is None
    assert resolution.resolved_module_path == ("Root",)


def test_candidates_stay_inside_the_program_directory_and_its_scr_folder(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    graphics_path = program_dir / "Root.g"

    candidates = picture_display_asset_candidate_paths(graphics_path, "icons/logo.bmp")

    assert set(candidates) == {
        program_dir / "icons/logo.bmp",
        program_dir / "logo.bmp",
        program_dir / "scr/icons/logo.bmp",
        program_dir / "scr/logo.bmp",
    }
    assert all(program_dir in candidate.parents or candidate.parent == program_dir for candidate in candidates)


def test_candidates_reject_parent_directory_segments(tmp_path: Path) -> None:
    graphics_path = tmp_path / "Program" / "Root.g"

    assert picture_display_asset_candidate_paths(graphics_path, "../outside/logo.bmp") == ()
    assert picture_display_asset_candidate_paths(graphics_path, "icons/../../logo.bmp") == ()


def test_candidates_reject_absolute_paths(tmp_path: Path) -> None:
    graphics_path = tmp_path / "Program" / "Root.g"
    absolute_asset = tmp_path / "outside" / "logo.bmp"

    assert picture_display_asset_candidate_paths(graphics_path, str(absolute_asset)) == ()


def test_wmf_asset_beside_the_program_is_a_candidate_and_a_silent_skip(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    (program_dir / "scr").mkdir(parents=True)
    (program_dir / "scr" / "logo.wmf").write_bytes(b"asset")

    candidates = picture_display_asset_candidate_paths(program_dir / "Root.g", "logo.wmf")

    assert program_dir / "scr" / "logo.wmf" in candidates
    _assert_silent_skip("scr:logo.wmf", program_dir)


def test_wmf_parent_directory_escape_is_a_silent_skip(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()
    (tmp_path / "secret.wmf").write_bytes(b"asset")

    assert picture_display_asset_candidate_paths(program_dir / "Root.g", "../secret.wmf") == ()
    _assert_silent_skip("scr:../secret.wmf", program_dir)


def test_absolute_wmf_asset_path_is_a_silent_skip(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()
    absolute_asset = tmp_path / "absolute.wmf"
    absolute_asset.write_bytes(b"asset")

    assert picture_display_asset_candidate_paths(program_dir / "Root.g", str(absolute_asset)) == ()
    _assert_silent_skip(f"scr:{absolute_asset}", program_dir)


def test_wmf_asset_in_a_parent_directory_is_a_silent_skip(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()
    (tmp_path / "shared.wmf").write_bytes(b"asset")

    _assert_silent_skip("scr:shared.wmf", program_dir)


def test_wmf_asset_symlink_that_leaves_the_program_directory_is_not_a_candidate(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()
    outside = tmp_path / "outside.wmf"
    outside.write_bytes(b"asset")
    (program_dir / "logo.wmf").symlink_to(outside)

    candidates = picture_display_asset_candidate_paths(program_dir / "Root.g", "logo.wmf")

    assert (program_dir / "logo.wmf") not in candidates
    _assert_silent_skip("scr:logo.wmf", program_dir)


def test_asset_symlink_that_stays_inside_the_program_directory_is_a_candidate(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()
    asset = program_dir / "icons" / "logo.bmp"
    asset.parent.mkdir()
    asset.write_bytes(b"asset")
    (program_dir / "logo.bmp").symlink_to(asset)

    candidates = picture_display_asset_candidate_paths(program_dir / "Root.g", "logo.bmp")

    assert program_dir / "logo.bmp" in candidates


def test_wmf_scr_folder_symlink_that_leaves_the_program_directory_is_not_a_candidate(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()
    outside = tmp_path / "shared"
    outside.mkdir()
    (outside / "logo.wmf").write_bytes(b"asset")
    (program_dir / "scr").symlink_to(outside)

    candidates = picture_display_asset_candidate_paths(program_dir / "Root.g", "logo.wmf")

    assert not any(candidate.parent == program_dir / "scr" for candidate in candidates)
    _assert_silent_skip("scr:logo.wmf", program_dir)


def test_scr_wmf_literal_path_produces_no_graphics_warning(tmp_path: Path) -> None:
    result = validate_graphics_text(_picture_display_graphics_text("scr:logo.wmf"), tmp_path / "Root.g")

    assert result.messages == ()


def test_bare_emf_literal_path_produces_no_graphics_warning(tmp_path: Path) -> None:
    result = validate_graphics_text(_picture_display_graphics_text("Vendor Background.emf"), tmp_path / "Root.g")

    assert result.messages == ()


def test_scr_png_literal_path_is_still_verified(tmp_path: Path) -> None:
    program_dir = tmp_path / "Program"
    program_dir.mkdir()

    result = validate_graphics_text(_picture_display_graphics_text("scr:missing.png"), program_dir / "Root.g")

    assert [message.severity for message in result.messages] == ["warning"]
    assert "could not be verified" in result.messages[0].message
