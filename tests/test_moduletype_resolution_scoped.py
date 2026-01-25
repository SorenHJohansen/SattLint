import pytest

from sattlint.analyzers.variables import _resolve_moduletype_def_strict
from sattlint.models.ast_model import BasePicture, ModuleHeader, ModuleTypeDef


def _header(name: str = "BP") -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_resolves_same_library_first():
    mt_lib1 = ModuleTypeDef(name="CIP", origin_lib="Lib1")
    mt_lib2 = ModuleTypeDef(name="CIP", origin_lib="Lib2")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[mt_lib1, mt_lib2],
        library_dependencies={"lib1": ["lib2"]},
    )

    resolved = _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")

    assert resolved is mt_lib1


def test_resolves_via_dependency_when_missing_local():
    mt_lib2 = ModuleTypeDef(name="CIP", origin_lib="Lib2")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[mt_lib2],
        library_dependencies={"lib1": ["lib2"]},
    )

    resolved = _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")

    assert resolved is mt_lib2


def test_ambiguous_within_dependencies_raises():
    mt_lib2 = ModuleTypeDef(name="CIP", origin_lib="Lib2")
    mt_lib3 = ModuleTypeDef(name="CIP", origin_lib="Lib3")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[mt_lib2, mt_lib3],
        library_dependencies={"lib1": ["lib2", "lib3"]},
    )

    with pytest.raises(ValueError):
        _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")
