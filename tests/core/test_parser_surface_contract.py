"""Contract tests for the supported ``sattline-parser`` surface.

These tests parse one fixture through the published parser and assert the exact
tree shapes the analyzers depend on. They are the destination for the parser
migration: a shape asserted here must keep working after the reflective
traversal layer is removed, and a shape that stops appearing here is a silent
loss of variable references.

The tests import only the supported doors: the top-level parse entry point and
``sattline_parser.ast``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import sattline_parser
from sattline_parser import parse_source_text
from sattline_parser.ast import (
    AssignClause,
    BasePicture,
    BinOp,
    ColourSpec,
    EnableClause,
    FlagClause,
    InteractObject,
    IntLiteral,
    ModuleDef,
    ModuleHeader,
    ModuleInViewClause,
    PickButton,
    ProcedureCall,
    VarRef,
    VarTail,
    walk,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "parser_surface" / "ParserSurfaceShapes.s"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def picture() -> BasePicture:
    return parse_source_text(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def module_def(picture: BasePicture) -> ModuleDef:
    definition = picture.moduledef
    assert definition is not None
    return definition


@pytest.fixture(scope="module")
def child_header(picture: BasePicture) -> ModuleHeader:
    return picture.submodules[0].header


@pytest.fixture(scope="module")
def text_box(module_def: ModuleDef) -> InteractObject:
    return next(obj for obj in module_def.interact_objects if obj.type == "TextBox_")


def test_text_object_names_a_variable_through_text_vars(module_def: ModuleDef) -> None:
    text_object = next(obj for obj in module_def.graph_objects if obj.type == "TextObject")

    assert text_object.properties.get("text_vars") == [VarRef("TextVar")]


def test_pick_button_names_a_variable_through_its_reference(text_box: InteractObject) -> None:
    body = text_box.properties.get("body")
    assert body is not None
    pick_button = next(entry for entry in body if isinstance(entry, PickButton))

    assert pick_button.value == "PickVar"
    assert pick_button.reference == VarRef("PickVar")


def test_header_named_argument_is_an_assignment_with_a_concrete_literal(
    child_header: ModuleHeader,
) -> None:
    assign = child_header.arguments.assigns[0]

    assert assign == AssignClause(name="Param1", value=5)
    assert isinstance(assign.value, IntLiteral)


def test_header_bound_enable_names_its_variable(child_header: ModuleHeader) -> None:
    assert child_header.arguments.enable == EnableClause(enabled=True, tail=VarTail(direction="in", value="Flag"))


def test_header_keeps_coordinate_tails_apart_from_named_arguments(
    child_header: ModuleHeader,
) -> None:
    arguments = child_header.arguments

    assert child_header.invoke_coord_tails == [VarTail(direction="in", value="PosVar")]
    assert arguments.assigns == (AssignClause(name="Param1", value=5),)
    assert arguments.module_in_view == ModuleInViewClause(in_view=True, tail=VarTail(direction="out", value="OutVal"))
    assert arguments.enable is not None


def test_module_definition_clipping_tails_name_their_variables(module_def: ModuleDef) -> None:
    clipping = module_def.clipping
    assert clipping is not None

    assert clipping.tails == (VarTail(direction="in", value="ClipVar"),)
    assert module_def.clipping_bounds == ((-1.0, -1.0), (1.0, 1.0))


def test_interactor_keeps_an_outvar_tail(text_box: InteractObject) -> None:
    assert text_box.properties.get("tails") == [VarTail(direction="out", value="OutVal")]


def test_procedure_call_keeps_an_expression_argument(module_def: ModuleDef) -> None:
    button = next(obj for obj in module_def.interact_objects if obj.type == "ComButProc_")
    procedure = button.properties.get("procedure")

    assert isinstance(procedure, ProcedureCall)
    assert procedure.name == "ToggleWindow"
    assert len(procedure.args) == 1
    argument = procedure.args[0]
    assert isinstance(argument, BinOp)
    assert argument.op == "+"
    assert isinstance(argument.left, VarRef)
    assert argument.left.name == "ProcArg"
    assert argument.right == 1


def test_interactor_body_holds_typed_assignment_flag_and_colour(
    text_box: InteractObject,
) -> None:
    body = text_box.properties.get("body")
    assert body is not None

    assign = next(entry for entry in body if isinstance(entry, AssignClause))
    assert assign == AssignClause(name="Variable", value=0, tail=VarTail(direction="out", value="OutVal"))

    flags = {entry.name for entry in body if isinstance(entry, FlagClause)}
    assert flags == {"Int_Value", "Custom_Flag"}

    colour = next(entry for entry in body if isinstance(entry, ColourSpec))
    assert colour.kind == "fill"
    assert [assignment.key for assignment in colour.assignments] == ["Colour0", "Colour1"]


def test_walk_reaches_references_and_bound_tails(picture: BasePicture) -> None:
    nodes = [event.node for event in walk(picture)]

    references = {node.name for node in nodes if isinstance(node, VarRef)}
    bound_tails = {(node.direction, node.bound_name) for node in nodes if isinstance(node, VarTail)}

    assert references == {"TextVar", "PickVar", "ProcArg", "Flag"}
    assert bound_tails == {
        ("in", "Flag"),
        ("in", "PosVar"),
        ("in", "ClipVar"),
        ("out", "OutVal"),
    }


def _declared_parser_requirement() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)
    dependencies = project["project"]["dependencies"]
    return next(dependency for dependency in dependencies if dependency.startswith("sattline-parser"))


def test_installed_parser_matches_declared_pin() -> None:
    requirement = _declared_parser_requirement()
    assert requirement.startswith("sattline-parser=="), requirement

    pinned = requirement.split("==", 1)[1].strip()
    assert pinned == sattline_parser.__version__, (
        f"declared parser {pinned} does not match installed {sattline_parser.__version__}"
    )


def test_declared_parser_requirement_is_pinned_exactly() -> None:
    requirement = _declared_parser_requirement()
    assert requirement.startswith("sattline-parser=="), requirement

    pinned = requirement.split("==", 1)[1].strip()
    assert pinned
    assert not any(operator in pinned for operator in "<>=!,"), requirement
