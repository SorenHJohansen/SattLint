"""AST model definitions and formatting helpers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from ..grammar import constants as const
from ..utils.formatter import format_list, format_optional, format_expr, format_seq_nodes
import textwrap


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int


class IntLiteral(int):
    span: SourceSpan

    def __new__(cls, value: int, span: SourceSpan):
        obj = int.__new__(cls, value)
        obj.span = span
        return obj


class FloatLiteral(float):
    span: SourceSpan

    def __new__(cls, value: float, span: SourceSpan):
        obj = float.__new__(cls, value)
        obj.span = span
        return obj








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
    def from_any(cls, value: "Simple_DataType | str") -> "Simple_DataType":
        # Use the concrete class in isinstance for proper type narrowing in type checkers.
        if isinstance(value, Simple_DataType):
            return value
        if isinstance(value, str):
            # Accept any-case string for built-ins; will raise ValueError if not valid.
            return cls(value.lower())
        # Fallback for unexpected inputs to satisfy static typing.
        raise TypeError(f"Expected Simple_DataType or str, got {type(value).__name__}")


@dataclass
class Variable:
    name: str
    datatype: Simple_DataType | str  # accept either at init; we'll normalize
    global_var: bool | None = False
    const: bool | None = False
    state: bool | None = False
    opsave: bool | None = False
    secure: bool | None = False
    init_value: bool | None = None
    description: str | None = None

    @property
    def datatype_text(self) -> str:
        # Always return a string representation
        return (
            self.datatype.value
            if isinstance(self.datatype, Simple_DataType)
            else str(self.datatype)
        )

    def __post_init__(self):
        # Accept DataType or any-case string
        try:
            self.datatype = Simple_DataType.from_any(self.datatype)
        except ValueError:
            # Keep user-defined datatypes (record names) as strings
            if isinstance(self.datatype, str):
                self.datatype = self.datatype
            else:
                raise

    def __str__(self) -> str:
        return f"Name: {self.name!r}, Datatype: {self.datatype!r}, Global: {self.global_var}, Const: {self.const}, State: {self.state}, Init_value : {self.init_value!r}, Description: {self.description!r}"


@dataclass
class DataType:
    name: str
    description: str | None
    datecode: int | None
    var_list: list[Variable] = field(default_factory=list)
    read: bool | None = False
    written: bool | None = False
    usage_locations: list[tuple] = field(default_factory=list)
    origin_file: str | None = None
    origin_lib: str | None = None

    def mark_read(self, module_path):
        self.read = True
        self.usage_locations.append((module_path.copy(), "read"))

    def mark_written(self, module_path):
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
    # Left side of "=>" in a submodule call:
    # This is the submodule's parameter name, represented by the variable_name dict
    # returned from transformer.variable_name, or a plain string.
    target: dict | str

    # "value" vs "variable_name" (you set const.KEY_VALUE or const.TREE_TAG_VARIABLE_NAME)
    source_type: str

    # Whether Duration_Value was present
    is_duration: bool

    # Whether GLOBAL was present; if True, source is considered used
    is_source_global: bool

    # Right side of "=>" can be a variable_name dict or a Variable; allow both, or None
    source: dict | Variable | None = None

    # Or a literal (int/float/bool/str), or None
    source_literal: Any | None = None

    def __str__(self) -> str:
        tgt = (
            self.target.get(const.KEY_VAR_NAME)
            if isinstance(self.target, dict)
            else str(self.target)
        )

        if self.is_source_global:
            return f"{tgt} => GLOBAL"

        if self.source_type == const.TREE_TAG_VARIABLE_NAME and self.source:
            src = (
                self.source.get(const.KEY_VAR_NAME)
                if isinstance(self.source, dict)
                else str(self.source)
            )
            return f"{tgt} => {src}"

        if self.source_literal is not None:
            return f"{tgt} => {repr(self.source_literal)}"

        return f"{tgt} => <None>"


@dataclass
class GraphObject:
    type: str
    properties: dict = field(default_factory=dict)


@dataclass
class InteractObject:
    type: str
    properties: dict = field(default_factory=dict)


@dataclass
class ModuleDef:
    clipping_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None
    zoom_limits: tuple[float, float] | None = None
    seq_layers: Any | None = None
    grid: float = 0.2
    zoomable: bool = False
    graph_objects: list[GraphObject] = field(default_factory=list)
    interact_objects: list[InteractObject] = field(default_factory=list)

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
    code: list[Any] = field(default_factory=list)

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
    code: list[Any] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Equation(name={self.name}, pos={self.position},\n"
            f"    code={format_list(self.code)})"
        )


@dataclass
class ModuleCode:
    sequences: list[Sequence] | None = None
    equations: list[Equation] | None = None

    def __str__(self) -> str:
        def _unwrap_statement_node(x):
            if hasattr(x, "data") and getattr(x, "data") == const.KEY_STATEMENT:
                ch = getattr(x, "children", [])
                return ch[0] if ch else x
            return x

        # Sequences (unchanged pretty SFC if you added it)
        seq_lines = []
        if self.sequences:
            for s in self.sequences:
                size_str = (
                    f" with size {s.size}"
                    if getattr(s, "size", None) is not None
                    else ""
                )
                # If you implemented format_seq_nodes(s.code), use it here; otherwise keep existing
                seq_lines.append(
                    f"Sequence {s.name!r} at {s.position}{size_str} (type={s.type})\n"
                    f"    Code:\n"
                    + textwrap.indent(format_seq_nodes(s.code), "        ")
                )
        else:
            seq_lines.append("No sequences")

        # Equations: rely on format_expr for everything (handles IF recursively)
        eq_lines = []
        if self.equations:
            for e in self.equations:
                pretty_code = []
                for stmt in e.code:
                    pretty_code.append(format_expr(_unwrap_statement_node(stmt)))
                size_str = (
                    f" with size {e.size}"
                    if getattr(e, "size", None) is not None
                    else ""
                )
                eq_lines.append(
                    f"EquationBlock name={e.name!r} at {e.position}{size_str}\n"
                    f"    Code:\n" + textwrap.indent("\n".join(pretty_code), "        ")
                )

        return (
            "ModuleCode{\n"
            + textwrap.indent(
                "Sequences:\n" + textwrap.indent("\n\n".join(seq_lines), "    "), "    "
            )
            + "\n\n"
            + textwrap.indent(
                "Equations:\n" + textwrap.indent("\n\n".join(eq_lines), "    "), "    "
            )
            + "\n}"
        )


@dataclass
class ModuleHeader:
    name: str
    invoke_coord: tuple[float, float, float, float, float]
    layer_info: str | None = None
    enable: bool = True
    zoom_limits: tuple[float, float] | None = None
    zoomable: bool = False
    enable_tail: object | None = None
    groupconn: dict | None = None
    groupconn_global: bool = False


@dataclass
class SingleModule:
    header: ModuleHeader
    moduledef: ModuleDef | None
    datecode: int | None = None
    moduleparameters: list[Variable] = field(default_factory=list)
    localvariables: list[Variable] = field(default_factory=list)
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(
        default_factory=list
    )
    modulecode: ModuleCode | None = None
    parametermappings: list[ParameterMapping] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [
            f"Name            : {self.header.name!r}",
            f"Enable          : {self.header.enable}",
            f"Invoke_coord    : {self.header.invoke_coord!r}",
            f"Datecode        : {self.datecode!r}",
            f"Moduleparameters: {format_list(self.moduleparameters)}",
            f"Localvariables  : {format_list(self.localvariables)}",
            f"Submodules      : {format_list(self.submodules)}",
            f"ModuleDef       : {format_optional(self.moduledef)}",
            f"ModuleCode      : {format_optional(self.modulecode)}",
            f"ParameterMappings: {format_list(self.parametermappings)}",
        ]
        return "SingleModule{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


@dataclass
class FrameModule:
    header: ModuleHeader
    datecode: int | None = None
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(
        default_factory=list
    )
    moduledef: ModuleDef | None = None
    modulecode: ModuleCode | None = None

    def __str__(self) -> str:
        lines = [
            f"Name         : {self.header.name!r}",
            f"Enable       : {self.header.enable}",
            f"Invoke_coord : {self.header.invoke_coord!r}",
            f"Datecode     : {self.datecode!r}",
            f"Submodules   : {format_list(self.submodules)}",
            f"ModuleDef    : {format_optional(self.moduledef)}",
            f"ModuleCode   : {format_optional(self.modulecode)}",
        ]
        return "FrameModule{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


@dataclass
class ModuleTypeInstance:
    header: ModuleHeader
    moduletype_name: str
    parametermappings: list[ParameterMapping] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [
            f"Name             : {self.header.name!r}",
            f"Enable           : {self.header.enable}",
            f"Enable_tail      : {self.header.enable_tail}",
            f"Invoke_coord     : {self.header.invoke_coord!r}",
            f"ModuleTypeName   : {self.moduletype_name!r}",
            f"ParameterMappings: {format_list(self.parametermappings)}",
        ]
        return "ModuleTypeInstance{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


@dataclass
class ModuleTypeDef:
    name: str
    datecode: int | None = None
    moduleparameters: list[Variable] = field(
        default_factory=list
    )  # MODULEPARAMETERS declarations
    localvariables: list[Variable] = field(
        default_factory=list
    )  # LOCALVARIABLES declarations
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(
        default_factory=list
    )  # nested ModuleInstance nodes
    moduledef: ModuleDef | None = None
    modulecode: ModuleCode | None = None
    parametermappings: list[ParameterMapping] = field(default_factory=list)
    groupconn: dict | None = None
    groupconn_global: bool = False
    origin_file: str | None = None
    origin_lib: str | None = None

    def __str__(self) -> str:
        lines = [
            f"Name            : {self.name!r}",
            f"Datecode        : {self.datecode!r}",
            f"OriginFile      : {self.origin_file!r}",
            f"OriginLib       : {self.origin_lib!r}",
            f"Moduleparameters: {format_list(self.moduleparameters)}",
            f"Localvariables  : {format_list(self.localvariables)}",
            f"Submodules      : {format_list(self.submodules)}",
            f"ModuleDef       : {format_optional(self.moduledef)}",
            f"ModuleCode      : {format_optional(self.modulecode)}",
            f"ParameterMappings: {format_list(self.parametermappings)}",
        ]
        return "ModulType{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


@dataclass
class BasePicture:
    header: ModuleHeader
    name: str = "BasePicture"
    position: tuple[float, float, float, float, float] | None = None
    datatype_defs: list[DataType] = field(default_factory=list)
    moduletype_defs: list[ModuleTypeDef] = field(default_factory=list)
    localvariables: list[Variable] = field(default_factory=list)
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = field(
        default_factory=list
    )
    moduledef: ModuleDef | None = None
    modulecode: ModuleCode | None = None
    origin_file: str | None = None
    origin_lib: str | None = None
    # library_name.casefold() -> list of dependency library names (casefolded)
    library_dependencies: dict[str, list[str]] = field(default_factory=dict)
    parse_tree: Any | None = None

    def __str__(self) -> str:
        lines = [
            f"Name: {self.name!r}\n"
            f"Position: {self.position!r}\n\n"
            f"TYPEDEFINITIONS (Records): {format_list(self.datatype_defs)}\n\n"
            f"TYPEDEFINITIONS (Modules): {format_list(self.moduletype_defs)}\n"
            f"Localvariables: {format_list(self.localvariables)}\n\n"
            f"Submodules: {format_list(self.submodules)}\n\n"
            f"ModuleDef: {self.moduledef}\n\n"
            f"ModuleCode: {self.modulecode}\n\n"
        ]
        return "BasePicture{\n" + textwrap.indent("\n  ".join(lines), "    ") + "}"


@dataclass
class SFCCodeBlocks:
    enter: list[Any] = field(default_factory=list)
    active: list[Any] = field(default_factory=list)
    exit: list[Any] = field(default_factory=list)


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
    target: str


@dataclass
class SFCBreak:
    pass
