from sattline_parser.models.ast_model import BasePicture, ModuleHeader, ModuleTypeDef, ModuleTypeInstance

from sattlint.analyzers.framework import Issue
from sattlint.analyzers.shared.instance_paths import (
    first_instance_path_for_moduletype,
    rewrite_typedef_paths,
)


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _instance(name: str, moduletype_name: str) -> ModuleTypeInstance:
    return ModuleTypeInstance(header=_header(name), moduletype_name=moduletype_name, parametermappings=[])


def test_first_instance_path_finds_root_origin_invocation() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[_instance("InstA", "MyType")])

    assert first_instance_path_for_moduletype(bp, "MyType") == ["Root", "InstA"]


def test_first_instance_path_is_case_insensitive() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[_instance("InstA", "mYtYpE")])

    assert first_instance_path_for_moduletype(bp, "MyType") == ["Root", "InstA"]


def test_rewrite_typedef_path_uses_first_invocation() -> None:
    bp = BasePicture(
        header=_header("Root"),
        submodules=[_instance("InstA", "MyType"), _instance("InstB", "MyType")],
    )
    issue = Issue(kind="write_without_effect", message="m", module_path=["Root", "TypeDef:MyType", "Sub"])

    rewrite_typedef_paths([issue], bp)

    assert issue.module_path == ["Root", "InstA", "Sub"]


def test_rewrite_keeps_typedef_path_when_no_invocation_exists() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[])
    issue = Issue(kind="unused", message="m", module_path=["Root", "TypeDef:MyType"])

    rewrite_typedef_paths([issue], bp)

    assert issue.module_path == ["Root", "TypeDef:MyType"]


def test_rewrite_typedef_path_also_rewrites_message_and_context() -> None:
    bp = BasePicture(
        header=_header("Root"),
        submodules=[_instance("InstA", "MyType")],
    )
    issue = Issue(
        kind="sfc_parallel_write_race",
        message="race on Root.TypeDef:MyType.Output",
        module_path=["Root", "TypeDef:MyType"],
        data={"conflicts": ["Root.TypeDef:MyType.Output"]},
    )

    rewrite_typedef_paths([issue], bp)

    assert issue.module_path == ["Root", "InstA"]
    assert issue.message == "race on Root.InstA.Output"
    assert issue.data == {"conflicts": ["Root.InstA.Output"]}


def test_rewrite_resolves_nested_typedef_instance_chains() -> None:
    outer = ModuleTypeDef(
        name="VarLogic",
        moduleparameters=[],
        localvariables=[],
        submodules=[_instance("Inner Invocation", "InnerChild")],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_header("Root"),
        moduletype_defs=[outer],
        submodules=[_instance("VarInst", "VarLogic")],
    )
    issue = Issue(
        kind="read_only_non_const",
        message="[BasePicture.TypeDef:InnerChild] localvariable 'Setting'",
        module_path=["Root", "TypeDef:InnerChild"],
    )

    rewrite_typedef_paths([issue], bp)

    assert issue.module_path == ["Root", "VarInst", "Inner Invocation"]
    assert issue.message == "[BasePicture.VarInst.Inner Invocation] localvariable 'Setting'"


def test_rewrite_leaves_non_typedef_paths_unchanged() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[_instance("InstA", "MyType")])
    issue = Issue(kind="unused", message="m", module_path=["Root", "InstA"])

    rewrite_typedef_paths([issue], bp)

    assert issue.module_path == ["Root", "InstA"]
