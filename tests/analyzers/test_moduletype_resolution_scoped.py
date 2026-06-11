"""Tests for moduletype resolution within library scopes."""

import pytest

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.resolution.common import (
    find_all_aliases,
    find_all_aliases_upstream,
    find_module_by_name,
    find_var_in_scope,
    get_module_path,
    is_external_to_module,
    varname_base,
    varname_full,
)
from sattlint.resolution.common import resolve_module_by_strict_path as _resolve_module_by_strict_path
from sattlint.resolution.common import resolve_moduletype_def_strict as _resolve_moduletype_def_strict


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


def test_resolves_same_library_prefers_draft_source_file():
    mt_source = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="KaHAXDiluteLib.s")
    mt_fallback = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="KaHAXModullLib.x")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        origin_file="Root.s",
        moduletype_defs=[mt_fallback, mt_source],
        library_dependencies={"lib1": []},
    )

    resolved = _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")

    assert resolved is mt_source


def test_resolution_helper_source_preference_and_label_edges():
    from sattlint.resolution.common import (  # noqa: PLC0415
        dedupe_moduletype_defs,
        format_moduletype_label,
        narrow_matches_by_source_preference,
        path_startswith_casefold,
        preferred_source_extensions,
    )

    draft = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="KaHAXDiluteLib.s")
    duplicate = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="KaHAXDiluteLib.s")
    official = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="KaHAXModullLib.x")
    bare = ModuleTypeDef(name="Bare")

    assert path_startswith_casefold(["BasePicture", "Child"], ["basepicture"]) is True
    assert path_startswith_casefold(["BasePicture"], ["BasePicture", "Child"]) is False
    assert path_startswith_casefold(["BasePicture", "Child"], ["BasePicture", "Other"]) is False

    assert format_moduletype_label(draft) == "Lib1:CIP (KaHAXDiluteLib.s)"
    assert format_moduletype_label(ModuleTypeDef(name="CIP", origin_lib="Lib1")) == "Lib1:CIP"
    assert format_moduletype_label(bare) == "Bare"

    assert dedupe_moduletype_defs([draft, duplicate, official, bare]) == [draft, official, bare]
    assert preferred_source_extensions("Root.s") == [".s", ".x"]
    assert preferred_source_extensions("Root.x") == [".x", ".s"]
    assert preferred_source_extensions(None) == []
    assert preferred_source_extensions("Root.txt") == []

    assert narrow_matches_by_source_preference([draft], [".x"]) == [draft]
    assert narrow_matches_by_source_preference([draft, official], []) == [draft, official]
    assert narrow_matches_by_source_preference([draft, official], [".s", ".x"]) == [draft]
    assert narrow_matches_by_source_preference([bare, ModuleTypeDef(name="Other")], [".s"]) == [
        bare,
        ModuleTypeDef(name="Other"),
    ]


def test_resolve_moduletype_strict_uses_origin_library_and_reports_missing_or_ambiguous():
    local = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="LocalA.txt")
    local_other = ModuleTypeDef(name="CIP", origin_lib="Lib1", origin_file="LocalB.txt")
    dependency = ModuleTypeDef(name="CIP", origin_lib="Lib2", origin_file="Dep.s")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[local, local_other, dependency],
        library_dependencies={"lib1": ["lib2"]},
    )

    with pytest.raises(ValueError, match="Ambiguous moduletype 'CIP'") as exc_info:
        _resolve_moduletype_def_strict(bp, "CIP")

    message = str(exc_info.value)
    assert "Lib1:CIP (LocalA.txt)" in message
    assert "Lib1:CIP (LocalB.txt)" in message

    missing_bp = BasePicture(header=_header(), origin_lib="Lib1", moduletype_defs=[])
    with pytest.raises(ValueError, match="Some libraries are unavailable"):
        _resolve_moduletype_def_strict(
            missing_bp,
            "MissingType",
            unavailable_libraries={"ControlLib"},
        )


def test_strict_path_prefers_enclosing_draft_moduletype_definition():
    transfer_source = ModuleTypeDef(
        name="Transfer",
        origin_lib="ProjectLib",
        origin_file="KaHAXDiluteLib.s",
        submodules=[SingleModule(header=_header("Dilute"), moduledef=None)],
    )
    transfer_fallback = ModuleTypeDef(
        name="Transfer",
        origin_lib="ProjectLib",
        origin_file="KaHAXModullLib.x",
        submodules=[SingleModule(header=_header("Legacy"), moduledef=None)],
    )
    wrapper = ModuleTypeDef(
        name="Wrapper",
        origin_lib="ProjectLib",
        origin_file="KaHAXDiluteLib.s",
        submodules=[ModuleTypeInstance(header=_header("Transfer"), moduletype_name="Transfer")],
    )
    bp = BasePicture(
        header=_header("BasePicture"),
        origin_lib="AppLib",
        origin_file="Root.s",
        moduletype_defs=[transfer_fallback, transfer_source, wrapper],
        submodules=[ModuleTypeInstance(header=_header("Wrapper"), moduletype_name="Wrapper")],
        library_dependencies={"applib": ["projectlib"]},
    )

    resolved = _resolve_module_by_strict_path(bp, "Wrapper.Transfer.Dilute")

    assert resolved.node.header.name == "Dilute"


def test_analyzer_uses_library_scoped_moduletype_defs():
    dt_lib1 = DataType(
        name="CIPType1",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Active", datatype=Simple_DataType.BOOLEAN),
            Variable(name="DefaultComm", datatype=Simple_DataType.STRING),
        ],
    )
    dt_lib2 = DataType(
        name="CIPType2",
        description=None,
        datecode=None,
        var_list=[Variable(name="Other", datatype=Simple_DataType.INTEGER)],
    )

    cip_lib1 = ModuleTypeDef(
        name="CIP",
        origin_lib="Lib1",
        origin_file="Lib1.x",
        localvariables=[Variable(name="DV", datatype="CIPType1")],
        moduleparameters=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "InitVariable",
                            [{const.KEY_VAR_NAME: "DV.Active"}],
                        )
                    ],
                )
            ]
        ),
    )

    cip_lib2 = ModuleTypeDef(
        name="CIP",
        origin_lib="Lib2",
        origin_file="Lib2.x",
        localvariables=[Variable(name="DV", datatype="CIPType2")],
        moduleparameters=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "InitVariable",
                            [{const.KEY_VAR_NAME: "DV.Active"}],
                        )
                    ],
                )
            ]
        ),
    )

    wrapper = ModuleTypeDef(
        name="Wrapper",
        origin_lib="Lib1",
        origin_file="Lib1Wrapper.x",
        localvariables=[],
        moduleparameters=[],
        submodules=[ModuleTypeInstance(header=_header("CIP1"), moduletype_name="CIP")],
        moduledef=None,
        modulecode=None,
    )

    bp = BasePicture(
        header=_header("BasePicture"),
        origin_lib="AppLib",
        origin_file="Root.x",
        datatype_defs=[dt_lib1, dt_lib2],
        moduletype_defs=[cip_lib1, cip_lib2, wrapper],
        localvariables=[],
        submodules=[ModuleTypeInstance(header=_header("WrapperInst"), moduletype_name="Wrapper")],
        modulecode=None,
        moduledef=None,
        library_dependencies={"applib": ["lib1", "lib2"]},
    )

    analyzer = VariablesAnalyzer(bp, debug=False, fail_loudly=False)
    analyzer.run()

    assert not any("unknown field 'Active'" in warning for warning in analyzer.analysis_warnings)


def test_resolve_module_by_strict_path_rejects_empty_or_invalid_paths():
    bp = BasePicture(header=_header("BasePicture"), submodules=[])

    with pytest.raises(ValueError, match="Empty module path"):
        _resolve_module_by_strict_path(bp, "")
    with pytest.raises(ValueError, match="cannot continue past"):
        _resolve_module_by_strict_path(bp, "BasePicture")
    with pytest.raises(ValueError, match="Invalid module path syntax"):
        _resolve_module_by_strict_path(bp, "Child..Leaf")


def test_resolve_module_by_strict_path_reports_close_matches_for_unknown_segment():
    bp = BasePicture(
        header=_header("BasePicture"),
        submodules=[SingleModule(header=_header("Dilute"), moduledef=None)],
    )

    with pytest.raises(ValueError, match="Close matches"):
        _resolve_module_by_strict_path(bp, "Delute")


def test_module_lookup_and_scope_helpers_cover_typedef_and_regular_paths():
    local = Variable(name="LocalOnly", datatype=Simple_DataType.INTEGER)
    mp = Variable(name="FromParam", datatype=Simple_DataType.INTEGER)
    child = SingleModule(
        header=_header("Child"),
        moduledef=None,
        localvariables=[local],
        moduleparameters=[mp],
        submodules=[],
    )
    typedef = ModuleTypeDef(name="MyType", localvariables=[Variable(name="TypeLocal", datatype="integer")])
    bp = BasePicture(
        header=_header("BasePicture"),
        moduletype_defs=[typedef],
        localvariables=[Variable(name="RootVar", datatype=Simple_DataType.BOOLEAN)],
        submodules=[child],
    )

    assert find_module_by_name(bp, "mytype") is typedef
    assert find_module_by_name(bp, "child") is child
    assert find_module_by_name(bp, "missing") is None

    assert get_module_path(bp, typedef) == ["BasePicture", "TypeDef:MyType"]
    assert get_module_path(bp, child) == ["BasePicture", "Child"]

    assert is_external_to_module(["BasePicture", "Child"], ["BasePicture", "Child"]) is False
    assert is_external_to_module(["BasePicture"], ["BasePicture", "Child"]) is True
    assert is_external_to_module(["BasePicture", "TypeDef:MyType", "Inner"], ["BasePicture", "TypeDef:MyType"]) is False
    assert is_external_to_module(["BasePicture", "Other"], ["BasePicture", "TypeDef:MyType"]) is True

    assert find_var_in_scope(bp, ["BasePicture", "Child", "Leaf"], "LocalOnly") is local
    assert find_var_in_scope(bp, ["BasePicture", "Child", "Leaf"], "FromParam") is mp
    assert find_var_in_scope(bp, ["BasePicture", "Child", "Leaf"], "RootVar") is bp.localvariables[0]
    assert find_var_in_scope(bp, ["BasePicture", "Child", "Leaf"], "NotThere") is None


def test_varname_and_alias_helpers_cover_valid_and_invalid_inputs():
    const_ref = {const.KEY_VAR_NAME: "Root.Signal.Value"}
    assert varname_base(const_ref) == "root"
    assert varname_base("Root.Signal") == "root"
    assert varname_base(42) is None

    assert varname_full(const_ref) == "Root.Signal.Value"
    assert varname_full("Root.Signal") == "Root.Signal"
    assert varname_full(None) is None

    root = Variable(name="Root", datatype=Simple_DataType.INTEGER)
    child = Variable(name="Child", datatype=Simple_DataType.INTEGER)
    leaf = Variable(name="Leaf", datatype=Simple_DataType.INTEGER)
    alias_links = [
        (root, child, "A"),
        (child, leaf, "B"),
    ]

    assert find_all_aliases(root, alias_links) == [(child, "A"), (leaf, "A.B")]
    assert find_all_aliases_upstream(leaf, alias_links) == [(child, "B"), (root, "A.B")]
