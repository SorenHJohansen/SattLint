from pathlib import Path

from sattline_parser.models.ast_model import BasePicture, ModuleHeader, ModuleTypeDef, ModuleTypeInstance

from sattlint.analyzers.framework import Issue
from sattlint.analyzers.shared.instance_paths import (
    collect_instance_paths,
    rewrite_typedef_paths,
)
from sattlint.reporting.comment_code_report import CommentCodeHit


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _instance(name: str, moduletype_name: str) -> ModuleTypeInstance:
    return ModuleTypeInstance(header=_header(name), moduletype_name=moduletype_name, parametermappings=[])


def test_instance_paths_find_root_origin_invocation() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[_instance("InstA", "MyType")])

    assert collect_instance_paths(bp) == {"mytype": [["Root", "InstA"]]}


def test_instance_paths_are_case_insensitive() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[_instance("InstA", "mYtYpE")])

    assert collect_instance_paths(bp) == {"mytype": [["Root", "InstA"]]}


def test_rewrite_typedef_path_uses_first_invocation() -> None:
    bp = BasePicture(
        header=_header("Root"),
        submodules=[_instance("InstA", "MyType"), _instance("InstB", "MyType")],
    )
    issue = Issue(kind="write_without_effect", message="m", module_path=["Root", "TypeDef:MyType", "Sub"])

    (rewritten,) = rewrite_typedef_paths([issue], bp)

    assert rewritten is not issue
    assert rewritten.module_path == ["Root", "InstA", "Sub"]
    assert issue.module_path == ["Root", "TypeDef:MyType", "Sub"]


def test_rewrite_keeps_typedef_path_when_no_invocation_exists() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[])
    issue = Issue(kind="unused", message="m", module_path=["Root", "TypeDef:MyType"])

    (rewritten,) = rewrite_typedef_paths([issue], bp)

    assert rewritten.module_path == ["Root", "TypeDef:MyType"]


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

    (rewritten,) = rewrite_typedef_paths([issue], bp)

    assert rewritten.module_path == ["Root", "InstA"]
    assert rewritten.message == "race on Root.InstA.Output"
    assert rewritten.data == {"conflicts": ["Root.InstA.Output"]}
    # The frozen source record keeps its original text and payload.
    assert issue.message == "race on Root.TypeDef:MyType.Output"
    assert issue.data == {"conflicts": ["Root.TypeDef:MyType.Output"]}


def test_rewrite_resolves_nested_typedef_instance_chains() -> None:
    outer = ModuleTypeDef(
        name="VarLogic",
        moduleparameters=[],
        localvariables=[],
        submodules=[_instance("Inner Invocation", "InnerChild")],
        moduledef=None,
        modulecode=None,
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

    (rewritten,) = rewrite_typedef_paths([issue], bp)

    assert rewritten.module_path == ["Root", "VarInst", "Inner Invocation"]
    assert rewritten.message == "[BasePicture.VarInst.Inner Invocation] localvariable 'Setting'"


def test_rewrite_handles_frozen_tuple_paths() -> None:
    bp = BasePicture(
        header=_header("Root"),
        submodules=[_instance("InstA", "MyType")],
    )
    hit = CommentCodeHit(
        file_path=Path("Main.s"),
        start_line=10,
        end_line=10,
        start_col=1,
        end_col=20,
        indicators=("assignment",),
        preview="Value = 1;",
        module_path=("Root", "TypeDef:MyType", "Sub"),
    )

    (rewritten,) = rewrite_typedef_paths([hit], bp)

    assert rewritten.module_path == ("Root", "InstA", "Sub")
    assert hit.module_path == ("Root", "TypeDef:MyType", "Sub")


def test_rewrite_leaves_non_typedef_paths_unchanged() -> None:
    bp = BasePicture(header=_header("Root"), submodules=[_instance("InstA", "MyType")])
    issue = Issue(kind="unused", message="m", module_path=["Root", "InstA"])

    (rewritten,) = rewrite_typedef_paths([issue], bp)

    assert rewritten is issue
