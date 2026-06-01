"""AST model definitions and formatting helpers."""

from __future__ import annotations

import textwrap
from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from typing import Any, cast

from ..grammar import constants as const
from ._ast_model_support import (
    AstNodeDict,
    ModulePath,
    PropertyMap,
    UsageLocation,
    any_list,
    datatype_def_list,
    format_list,
    graph_object_list,
    interact_object_list,
    library_dependency_map,
    moduletype_def_list,
    parameter_mapping_list,
    property_map,
    render_base_picture,
    render_frame_module,
    render_module_code,
    render_moduletype_def,
    render_moduletype_instance,
    render_single_module,
    submodule_list,
    usage_location_list,
    variable_list,
)

__all__ = [
    "BasePicture",
    "DataType",
    "Equation",
    "FloatLiteral",
    "FrameModule",
    "GraphObject",
    "GraphicsBinding",
    "IntLiteral",
    "InteractObject",
    "ModuleCode",
    "ModuleDef",
    "ModuleHeader",
    "ModuleTypeDef",
    "ModuleTypeInstance",
    "ParameterMapping",
    "SFCAlternative",
    "SFCBreak",
    "SFCCodeBlocks",
    "SFCFork",
    "SFCParallel",
    "SFCStep",
    "SFCSubsequence",
    "SFCTransition",
    "SFCTransitionSub",
    "Sequence",
    "Simple_DataType",
    "SingleModule",
    "SourceSpan",
    "Variable",
]


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int

    def __reduce__(self):
        return (type(self), (self.line, self.column))


class IntLiteral(int):
    span: SourceSpan | None

    def __new__(cls, value: int, span: SourceSpan | None = None):
        obj = int.__new__(cls, value)
        obj.span = span
        return obj

    def __reduce__(self):
        return (type(self), (int(self), self.span))


class FloatLiteral(float):
    span: SourceSpan | None

    def __new__(cls, value: float, span: SourceSpan | None = None):
        obj = float.__new__(cls, value)
        obj.span = span
        return obj

    def __reduce__(self):
        return (type(self), (float(self), self.span))


class Simple_DataType(Enum):
    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    IDENTSTRING = "identstring"
    TAGSTRING = "tagstring"
    TIME = "time"
    DURATION = "duration"
    LINESTRING = "linestring"
    MAXSTRING = "maxstring"
    REAL = "real"

    @classmethod
    def from_any(cls, value: object) -> Simple_DataType:
        # Use the concrete class in isinstance for proper type narrowing in type checkers.
        if isinstance(value, Simple_DataType):
            return value
        if not isinstance(value, str):
            raise TypeError("Expected Simple_DataType or str")
        # Accept any-case string for built-ins; will raise ValueError if not valid.
        return cls(value.lower())


@dataclass
class Variable:
    name: str
    datatype: Simple_DataType | str  # accept either at init; we'll normalize
    global_var: bool | None = False
    const: bool | None = False
    state: bool | None = False
    opsave: bool | None = False
    secure: bool | None = False
    init_value: Any | None = None
    description: str | None = None
    declaration_span: SourceSpan | None = None
    init_is_duration: bool = False

    @property
    def datatype_text(self) -> str:
        # Always return a string representation
        return self.datatype.value if isinstance(self.datatype, Simple_DataType) else str(self.datatype)

    def __post_init__(self):
        # Accept DataType or any-case string
        try:
            self.datatype = Simple_DataType.from_any(self.datatype)
        except ValueError:
            if not isinstance(self.datatype, str):
                raise
            # Keep user-defined datatypes (record names) as strings
            self.datatype = str(self.datatype)

    def __str__(self) -> str:
        return (
            f"Name: {self.name!r}, Datatype: {self.datatype!r}, Global: {self.global_var}, "
            f"Const: {self.const}, State: {self.state}, Init_value : {self.init_value!r}, "
            f"Description: {self.description!r}"
        )


@dataclass
class DataType:
    name: str
    description: str | None
    datecode: int | None
    var_list: list[Variable] = field(default_factory=variable_list)
    read: bool | None = False
    written: bool | None = False
    usage_locations: list[UsageLocation] = field(default_factory=usage_location_list)
    origin_file: str | None = None
    origin_lib: str | None = None
    declaration_span: SourceSpan | None = None

    def mark_read(self, module_path: ModulePath) -> None:
        self.read = True
        self.usage_locations.append((module_path.copy(), "read"))

    def mark_written(self, module_path: ModulePath) -> None:
        self.written = True
        self.usage_locations.append((module_path.copy(), "write"))

    def __str__(self) -> str:
        from ..utils.formatter import format_list

        lines = [
            f"Name       : {self.name!r}",
            f"Description: {self.description!r}",
            f"Datecode   : {self.datecode!r}",
            f"OriginFile : {self.origin_file!r}",
            f"OriginLib  : {self.origin_lib!r}",
            f"Variables in datatype   : {format_list(self.var_list)}",
        ]
        return "Datatype{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


@dataclass
class ParameterMapping:
    target: AstNodeDict | str
    source_type: str
    is_duration: bool
    is_source_global: bool
    source: AstNodeDict | str | None = None
    source_literal: Any | None = None

    def __post_init__(self) -> None:
        self.target = _normalize_variable_ref(self.target, field_name="target")
        if self.source_type == const.TREE_TAG_VARIABLE_NAME and self.source is not None:
            self.source = _normalize_variable_ref(self.source, field_name="source")

    def __str__(self) -> str:
        tgt = _variable_ref_name(self.target) or "<None>"

        if self.is_source_global:
            return f"{tgt} => GLOBAL"

        if self.source_type == const.TREE_TAG_VARIABLE_NAME and self.source:
            src = _variable_ref_name(self.source) or "<None>"
            return f"{tgt} => {src}"

        if self.source_literal is not None:
            return f"{tgt} => {self.source_literal!r}"

        return f"{tgt} => <None>"


def _variable_ref_name(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Variable):
        return value.name
    if isinstance(value, dict):
        mapping = cast(AstNodeDict, value)
        full_name = mapping.get(const.KEY_VAR_NAME)
        if isinstance(full_name, str):
            return full_name
    return None


def _normalize_variable_ref(value: object, *, field_name: str) -> AstNodeDict:
    if isinstance(value, str):
        return {const.KEY_VAR_NAME: value}
    if isinstance(value, Variable):
        return {const.KEY_VAR_NAME: value.name}
    if isinstance(value, dict):
        mapping = cast(AstNodeDict, value)
        full_name = mapping.get(const.KEY_VAR_NAME)
        if isinstance(full_name, str):
            return mapping
    raise TypeError(f"ParameterMapping.{field_name} must be a variable reference")


@dataclass
class GraphObject:
    type: str
    properties: PropertyMap = field(default_factory=property_map)


@dataclass
class InteractObject:
    type: str
    properties: PropertyMap = field(default_factory=property_map)


@dataclass
class GraphicsBinding:
    kind: str
    raw_text: str
    value: Any | None = None
    span: SourceSpan | None = None


@dataclass
class ModuleDef:
    clipping_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None
    zoom_limits: tuple[float, float] | None = None
    seq_layers: Any | None = None
    grid: float = 0.2
    zoomable: bool = False
    graph_objects: list[GraphObject] = field(default_factory=graph_object_list)
    interact_objects: list[InteractObject] = field(default_factory=interact_object_list)
    properties: PropertyMap = field(default_factory=property_map)

    def __str__(self) -> str:
        lines = [
            f"ClippingBounds : {self.clipping_bounds}",
            f"ZoomLimits     : {self.zoom_limits}",
            f"SeqLayers      : {self.seq_layers}",
            f"Grid           : {self.grid}",
            f"Zoomable       : {self.zoomable}",
            # f"GraphObjects   : {format_list(self.graph_objects)}",
            # f"InteractObjects: {format_list(self.interact_objects)}",
        ]
        return "\n" + textwrap.indent("\n".join(lines), "    ")


@dataclass
class Sequence:
    name: str
    type: str
    position: tuple[float, float]
    size: tuple[float, float]
    seqcontrol: bool = False
    seqtimer: bool = False
    code: list[Any] = field(default_factory=any_list)

    def __str__(self) -> str:
        return (
            f"Sequence(name={self.name}, pos={self.position}, "
            f"type={self.type}, control={self.seqcontrol}, timer={self.seqtimer},\n"
            f"    code={format_list(self.code)})"
        )


@dataclass
class Equation:
    name: str
    position: tuple[float, float]
    size: tuple[float, float]
    code: list[Any] = field(default_factory=any_list)

    def __str__(self) -> str:
        return f"Equation(name={self.name}, pos={self.position},\n    code={format_list(self.code)})"


@dataclass
class ModuleCode:
    sequences: list[Sequence] | None = None
    equations: list[Equation] | None = None

    def __str__(self) -> str:
        return render_module_code(self, statement_key=const.KEY_STATEMENT)


@dataclass
class ModuleHeader:
    name: str
    invoke_coord: tuple[float, float, float, float, float]
    declaration_span: SourceSpan | None = None
    invocation_arguments: tuple[str, ...] = ()
    layer_info: str | None = None
    enable: bool = True
    zoom_limits: tuple[float, float] | None = None
    zoomable: bool = False
    enable_tail: object | None = None
    invoke_coord_tails: list[Any] = field(default_factory=any_list)
    groupconn: AstNodeDict | None = None
    groupconn_global: bool = False


@dataclass
class SingleModule:
    header: ModuleHeader
    moduledef: ModuleDef | None
    datecode: int | None = None
    moduleparameters: list[Variable] = field(default_factory=variable_list)
    localvariables: list[Variable] = field(default_factory=variable_list)
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(default_factory=submodule_list)
    modulecode: ModuleCode | None = None
    parametermappings: list[ParameterMapping] = field(default_factory=parameter_mapping_list)

    def __str__(self) -> str:
        return render_single_module(self)


@dataclass
class FrameModule:
    header: ModuleHeader
    datecode: int | None = None
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(default_factory=submodule_list)
    moduledef: ModuleDef | None = None
    modulecode: ModuleCode | None = None

    def __str__(self) -> str:
        return render_frame_module(self)


@dataclass
class ModuleTypeInstance:
    header: ModuleHeader
    moduletype_name: str
    parametermappings: list[ParameterMapping] = field(default_factory=parameter_mapping_list)

    def __str__(self) -> str:
        return render_moduletype_instance(self)


@dataclass
class ModuleTypeDef:
    name: str
    datecode: int | None = None
    moduleparameters: list[Variable] = field(default_factory=variable_list)
    localvariables: list[Variable] = field(default_factory=variable_list)
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(default_factory=submodule_list)
    moduledef: ModuleDef | None = None
    modulecode: ModuleCode | None = None
    parametermappings: list[ParameterMapping] = field(default_factory=parameter_mapping_list)
    groupconn: AstNodeDict | None = None
    groupconn_global: bool = False
    origin_file: str | None = None
    origin_lib: str | None = None
    declaration_span: SourceSpan | None = None

    def __str__(self) -> str:
        return render_moduletype_def(self)


@dataclass
class BasePicture:
    header: ModuleHeader
    name: str = "BasePicture"
    program_name: str | None = None
    position: tuple[float, float, float, float, float] | None = None
    datatype_defs: list[DataType] = field(default_factory=datatype_def_list)
    moduletype_defs: list[ModuleTypeDef] = field(default_factory=moduletype_def_list)
    localvariables: list[Variable] = field(default_factory=variable_list)
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(default_factory=submodule_list)
    moduledef: ModuleDef | None = None
    modulecode: ModuleCode | None = None
    origin_file: str | None = None
    origin_lib: str | None = None
    graphics_file: str | None = None
    graphics_bindings: list[GraphicsBinding] = field(default_factory=any_list)
    graphics_messages: list[Any] = field(default_factory=any_list)
    graphics_composite_records: list[Any] = field(default_factory=any_list)
    graphics_composite_occurrences: list[Any] = field(default_factory=any_list)
    graphics_picture_display_records: list[Any] = field(default_factory=any_list)
    graphics_picture_display_occurrences: list[Any] = field(default_factory=any_list)
    library_dependencies: dict[str, list[str]] = field(default_factory=library_dependency_map)
    parse_tree: Any | None = None

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        # Cached AST payloads do not need the original Lark tree and it dominates pickle size.
        state["parse_tree"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        for dataclass_field in fields(type(self)):
            if dataclass_field.name in self.__dict__:
                continue
            if dataclass_field.default is not MISSING:
                self.__dict__[dataclass_field.name] = dataclass_field.default
                continue
            default_factory = dataclass_field.default_factory
            if default_factory is not MISSING:
                self.__dict__[dataclass_field.name] = default_factory()

    def __str__(self) -> str:
        return render_base_picture(self)


@dataclass
class SFCCodeBlocks:
    enter: list[Any] = field(default_factory=any_list)
    active: list[Any] = field(default_factory=any_list)
    exit: list[Any] = field(default_factory=any_list)


@dataclass
class SFCStep:
    kind: str  # 'init' or 'step'
    name: str
    code: SFCCodeBlocks


@dataclass
class SFCTransition:
    name: str | None
    condition: Any


@dataclass
class SFCAlternative:
    branches: list[list[Any]]  # each branch is a list of SFC nodes


@dataclass
class SFCParallel:
    branches: list[list[Any]]


@dataclass
class SFCSubsequence:
    name: str
    body: list[Any]


@dataclass
class SFCTransitionSub:
    name: str
    body: list[Any]


@dataclass
class SFCFork:
    targets: tuple[str, ...]


@dataclass
class SFCBreak:
    pass
