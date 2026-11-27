# pyright: reportPrivateUsage=false
"""Input size limits: config validation, preflight rejection, and partial runs."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sattline_parser.models.ast_model import BasePicture

from sattlint.cache import ASTCache, compute_cache_key
from sattlint.config.analysis import (
    DEFAULT_ICF_BYTE_LIMIT,
    DEFAULT_PROJECT_BYTE_LIMIT,
    DEFAULT_SOURCE_BYTE_LIMIT,
    icf_byte_limit,
    project_byte_limit,
    source_byte_limit,
)
from sattlint.config.types import ConfigDict
from sattlint.config.validation import validate_config
from sattlint.models.project_graph import ProjectGraph
from sattlint.project.loading import _enforce_input_limits, iter_loaded_projects, load_project
from sattlint.project.support import cache_key_for_target, require_analyzed_targets

_LIMIT_KEYS = ("source_byte_limit", "icf_byte_limit", "project_byte_limit")

_PROGRAM = """"Syntax version 2.23, date: 2026-02-02-11:05:04.749 N"
"Original file date: ---"
"Program date: 2026-02-02-11:05:04.749, name: {name}"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   vUnused: integer;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
"""


def _config(program_dir: Path, **analysis: object) -> ConfigDict:
    return cast(
        ConfigDict,
        {
            "program_dir": program_dir,
            "ABB_lib_dir": "",
            "other_lib_dirs": [],
            "icf_dir": "",
            "mode": "official",
            "debug": False,
            "analysis": analysis,
        },
    )


def _unexpected_cache_dir() -> Path | None:
    raise AssertionError("the input preflight must reject before the cache is used")


def _unexpected_cache_key(_cfg: ConfigDict, _target: str) -> str:
    raise AssertionError("the input preflight must reject before the parser is used")


def test_source_file_over_the_limit_fails_before_parsing(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()
    oversized = programs / "Big.s"
    oversized.write_bytes(b"x" * 4096)

    with pytest.raises(ValueError) as excinfo:
        load_project(
            _config(programs, source_byte_limit=1024),
            target_name="Big",
            require_analyzed_targets_fn=lambda _cfg: ["Big"],
            cache_key_for_target_fn=_unexpected_cache_key,
            target_load_error_factory=None,
            get_cache_dir_fn=_unexpected_cache_dir,
            ast_cache_cls=object,
        )

    message = str(excinfo.value)
    assert str(oversized) in message
    assert "4096" in message
    assert "1024" in message
    assert "[analysis].source_byte_limit" in message


def test_project_total_over_the_limit_fails_with_the_total(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()
    for name in ("One", "Two"):
        (programs / f"{name}.s").write_bytes(b"x" * 4096)

    with pytest.raises(ValueError) as excinfo:
        load_project(
            _config(programs, project_byte_limit=4096),
            target_name="One",
            require_analyzed_targets_fn=lambda _cfg: ["One", "Two"],
            cache_key_for_target_fn=_unexpected_cache_key,
            target_load_error_factory=None,
            get_cache_dir_fn=_unexpected_cache_dir,
            ast_cache_cls=object,
        )

    message = str(excinfo.value)
    assert "8192" in message
    assert "4096" in message
    assert "[analysis].project_byte_limit" in message


def test_only_source_suffixes_count_toward_the_limits(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()
    (programs / "Small.S").write_bytes(b"x" * 128)
    (programs / "Small.x").write_bytes(b"x" * 128)
    (programs / "Small.sattline").write_bytes(b"x" * 128)
    (programs / "Notes.txt").write_bytes(b"x" * 8192)

    _enforce_input_limits(
        _config(programs, source_byte_limit=1024, project_byte_limit=1024),
        target_name="Small",
        target_names=["Small"],
    )


def test_source_limit_fails_only_the_oversized_target(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()
    (programs / "Good.s").write_text(_PROGRAM.format(name="Good"), encoding="utf-8")
    oversized = programs / "Huge.s"
    oversized.write_bytes(b"x" * 4096)
    cfg = cast(
        ConfigDict,
        {
            "analyzed_programs_and_libraries": ["Huge", "Good"],
            "mode": "draft",
            "debug": False,
            "program_dir": str(programs),
            "ABB_lib_dir": "",
            "icf_dir": "",
            "other_lib_dirs": [],
            "analysis": {"source_byte_limit": 1024},
        },
    )

    def real_load_project(
        load_cfg: ConfigDict,
        *,
        target_name: str,
        refresh_ast: bool,
        collect_stage_timings: bool,
    ) -> tuple[BasePicture, ProjectGraph]:
        return load_project(
            load_cfg,
            target_name,
            refresh_ast=refresh_ast,
            collect_stage_timings=collect_stage_timings,
            require_analyzed_targets_fn=require_analyzed_targets,
            cache_key_for_target_fn=lambda key_cfg, name: cache_key_for_target(
                key_cfg,
                name,
                compute_cache_key_fn=compute_cache_key,
            ),
            target_load_error_factory=None,
            get_cache_dir_fn=lambda: None,
            ast_cache_cls=ASTCache,
        )

    emitted: list[str] = []
    failures: list[tuple[str, str]] = []
    loaded = list(
        iter_loaded_projects(
            cfg,
            refresh_ast=True,
            require_analyzed_targets_fn=require_analyzed_targets,
            load_project_fn=real_load_project,
            emit_output_fn=emitted.append,
            failure_sink=lambda name, detail: failures.append((name, detail.message)),
        )
    )

    assert [name for name, _bp, _graph in loaded] == ["Good"]
    assert [name for name, _message in failures] == ["Huge"]
    assert str(oversized) in failures[0][1]
    assert "4096" in failures[0][1]
    assert "1024" in failures[0][1]
    assert "[analysis].source_byte_limit" in failures[0][1]


def test_analysis_limits_do_not_change_the_project_cache_key() -> None:
    base: dict[str, object] = {
        "mode": "official",
        "debug": False,
        "program_dir": "/tmp/programs",
        "ABB_lib_dir": "",
        "icf_dir": "",
        "other_lib_dirs": [],
        "string_capacities": {},
    }
    with_limits = {
        **base,
        "analysis": {
            "source_byte_limit": 1,
            "icf_byte_limit": 1,
            "project_byte_limit": 1,
        },
    }

    assert compute_cache_key(with_limits, analysis_target="Unit") == compute_cache_key(base, analysis_target="Unit")


@pytest.mark.parametrize("key", _LIMIT_KEYS)
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "8MiB"])
def test_input_limits_reject_non_positive_or_wrong_typed_values(key: str, value: object) -> None:
    result = validate_config(cast(ConfigDict, {"analysis": {key: value}}))

    assert not result.passed
    assert any(error.key_path == f"analysis.{key}" for error in result.errors)


@pytest.mark.parametrize("key", _LIMIT_KEYS)
def test_input_limits_accept_one_or_more(key: str) -> None:
    result = validate_config(cast(ConfigDict, {"analysis": {key: 1}}))

    assert result.passed


def test_input_limit_accessors_use_defaults_and_reject_invalid_values() -> None:
    assert source_byte_limit(None) == DEFAULT_SOURCE_BYTE_LIMIT == 8 * 1024 * 1024
    assert icf_byte_limit(None) == DEFAULT_ICF_BYTE_LIMIT == 16 * 1024 * 1024
    assert project_byte_limit(None) == DEFAULT_PROJECT_BYTE_LIMIT == 512 * 1024 * 1024

    overrides: dict[str, object] = {
        "analysis": {
            "source_byte_limit": 11,
            "icf_byte_limit": 12,
            "project_byte_limit": 13,
        }
    }
    assert source_byte_limit(overrides) == 11
    assert icf_byte_limit(overrides) == 12
    assert project_byte_limit(overrides) == 13

    invalid: dict[str, object] = {
        "analysis": {
            "source_byte_limit": 0,
            "icf_byte_limit": True,
            "project_byte_limit": "big",
        }
    }
    assert source_byte_limit(invalid) == DEFAULT_SOURCE_BYTE_LIMIT
    assert icf_byte_limit(invalid) == DEFAULT_ICF_BYTE_LIMIT
    assert project_byte_limit(invalid) == DEFAULT_PROJECT_BYTE_LIMIT
