# ast_model.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from enum import Enum
import constants as const
import textwrap


def format_list(
    items: list[Any],
    indent: str = "    ",
    align_variables: bool = True,
    inline_if_singleline: bool = False,
) -> str:
    if not items:
        return "[]"
    # Special aligned rendering for Variable lists
    if align_variables and all(isinstance(x, Variable) for x in items):
        # Compute column widths across the list
        name_w = max(len(repr(v.name)) for v in items)
        dtype_w = max(len(repr(v.datatype)) for v in items)
        global_w = max(len(str(v.global_var)) for v in items)
        const_w = max(len(str(v.const)) for v in items)
        state_w = max(len(str(v.state)) for v in items)
        init_w = max(len(repr(v.init_value)) for v in items)
        desc_w = max(len(repr(v.description)) for v in items)

        lines = []
        for v in items:
            lines.append(
                indent + f"Name: {repr(v.name):<{name_w}} , "
                f"Datatype: {repr(v.datatype):<{dtype_w}}, "
                f"Global: {str(v.global_var):<{global_w}}, "
                f"Const: {str(v.const):<{const_w}}, "
                f"State: {str(v.state):<{state_w}}, "
                f"Init_value : {repr(v.init_value):<{init_w}}, "
                f"Description: {repr(v.description):<{desc_w}}"
            )
        return "[\n" + "\n".join(lines) + "]"
    # Generic rendering for any other items
    strs = [str(obj) for obj in items]
    if inline_if_singleline and all("\n" not in s for s in strs):
        return "[" + ", ".join(strs) + "]"
    indented = [textwrap.indent(s, indent) for s in strs]
    return "[\n" + "\n".join(indented) + "]"


def format_optional(obj: Any) -> str:
    return "None" if obj is None else str(obj)


def format_expr(expr, indent="    "):
    """
    Pretty-print nested expressions and statements (assign/IF/AND/OR/compare/add/mul/function).
    Produces SattLine-like multi-line formatting where appropriate.
    """

    # 0) Unwrap a Statement tree anywhere (so nested IFs also render pretty)
    if hasattr(expr, "data") and getattr(expr, "data") == const.KEY_STATEMENT:
        children = getattr(expr, "children", [])
        if children:
            return format_expr(children[0], indent)

    # 1) Variable reference dict
    if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
        return expr[const.KEY_VAR_NAME]

    # 2) Literals
    if isinstance(expr, (int, float, bool, str)):
        return repr(expr) if isinstance(expr, str) else str(expr)

    # 3) Lists = block of expressions/statements
    if isinstance(expr, list):
        return "\n".join(format_expr(e, indent) for e in expr)

    # 4) Tuples = operators or structured statements
    if isinstance(expr, tuple):
        op = expr[0]

        # assignment: ('assign', targetdict, valueexpr)
        if op == const.KEY_ASSIGN:
            _, target, value = expr
            lhs = (
                target[const.KEY_VAR_NAME]
                if isinstance(target, dict) and const.KEY_VAR_NAME in target
                else str(target)
            )
            rhs = format_expr(value, indent)
            return f"{lhs} = {rhs}"

        # IF statement: ('IF', branches, else_block)
        # branches: list of (condition, [statements...])
        if op == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = expr
            out_lines = []
            for i, (cond, stmts) in enumerate(branches):
                head = "IF" if i == 0 else "ELSIF"
                cond_str = format_expr(cond, indent)
                out_lines.append(f"{head} {cond_str}")
                out_lines.append("THEN")
                # Each stmt can itself be a tuple or a Statement tree; format recursively
                for s in stmts:
                    out_lines.append(textwrap.indent(format_expr(s, indent), indent))
            if else_block:
                out_lines.append("ELSE")
                for s in else_block:
                    out_lines.append(textwrap.indent(format_expr(s, indent), indent))
            out_lines.append("ENDIF")
            return "\n".join(out_lines)

        # ('Ternary', [(cond, then_expr), (cond2, then_expr2), ...], else_expr)
        if op == const.KEY_TERNARY or op == "Ternary":
            _, branches, else_expr = expr
            out_lines = []
            for i, (cond, then_expr) in enumerate(branches):
                head = "IF" if i == 0 else "ELSIF"
                out_lines.append(f"{head} {format_expr(cond, indent)}")
                out_lines.append("THEN")
                out_lines.append(
                    textwrap.indent(format_expr(then_expr, indent), indent)
                )
            if else_expr is not None:
                out_lines.append("ELSE")
                out_lines.append(
                    textwrap.indent(format_expr(else_expr, indent), indent)
                )
            out_lines.append("ENDIF")
            return "\n".join(out_lines)

        # Boolean OR
        if op == const.GRAMMAR_VALUE_OR:
            parts = [format_expr(x, indent) for x in expr[1]]
            return (" OR \n").join(parts)

        # Boolean AND
        if op == const.GRAMMAR_VALUE_AND:
            parts = [format_expr(x, indent) for x in expr[1]]
            return (" AND \n").join(parts)

        # NOT
        if op == const.GRAMMAR_VALUE_NOT:
            return "NOT(" + format_expr(expr[1], indent) + ")"

        # compare: ('compare', left, [(symbol, right), ...])
        if op == const.KEY_COMPARE or op == "compare":
            _, left, pairs = expr
            left_str = format_expr(left, indent)
            if not pairs:
                return left_str
            parts = [
                f"{left_str} {sym} {format_expr(rhs, indent)}" for sym, rhs in pairs
            ]
            return " AND ".join(parts)

        # add: ('add', left, [(op, right), ...])
        if op == const.KEY_ADD:
            _, left, parts = expr
            base = format_expr(left, indent)
            tail = " ".join(f"{opval} {format_expr(r, indent)}" for opval, r in parts)
            return f"({base} {tail})"

        # mul/div: ('mul', left, [(op, right), ...])
        if op == const.KEY_MUL:
            _, left, parts = expr
            base = format_expr(left, indent)
            tail = " ".join(f"{opval} {format_expr(r, indent)}" for opval, r in parts)
            return f"({base} {tail})"

        # function call: ('FunctionCall', name, [args...])
        if op == const.KEY_FUNCTION_CALL:
            _, fn_name, args = expr
            arg_str = ", ".join(format_expr(a, indent) for a in (args or []))
            return f"{fn_name}({arg_str})"

        # Fallback: safe repr for anything unhandled
        import pprint

        return pprint.pformat(expr)

    # 5) Default
    return str(expr)


def format_seq_nodes(nodes: list[Any], indent: str = "    ") -> str:
    # Pretty-print a list of SFC nodes recursively
    lines: list[str] = []

    def _fmt_stmt_list(stmts: list[Any], level: int = 2):
        for s in stmts:
            lines.append(indent * level + format_expr(s, indent))

    for n in nodes:
        if isinstance(n, SFCStep):
            header = "InitStep" if n.kind == "init" else "Step"
            lines.append(f"{header} {n.name}")
            if n.code.enter:
                lines.append(indent + "Enter:")
                _fmt_stmt_list(n.code.enter)
            if n.code.active:
                lines.append(indent + "Active:")
                _fmt_stmt_list(n.code.active)
            if n.code.exit:
                lines.append(indent + "Exit:")
                _fmt_stmt_list(n.code.exit)

        elif isinstance(n, SFCTransition):
            nm = f" {n.name}" if n.name else ""
            cond = format_expr(n.condition, indent)
            lines.append(f"Transition{nm} WAIT_FOR {cond}")

        elif isinstance(n, SFCAlternative):
            lines.append("Alternative:")
            for i, branch in enumerate(n.branches, start=1):
                lines.append(indent + f"Branch {i}:")
                branch_str = format_seq_nodes(branch, indent)
                for ln in branch_str.splitlines():
                    lines.append(indent * 2 + ln)
            lines.append("EndAlternative")

        elif isinstance(n, SFCParallel):
            lines.append("Parallel:")
            for i, branch in enumerate(n.branches, start=1):
                lines.append(indent + f"Branch {i}:")
                branch_str = format_seq_nodes(branch, indent)
                for ln in branch_str.splitlines():
                    lines.append(indent * 2 + ln)
            lines.append("EndParallel")

        elif isinstance(n, SFCSubsequence):
            lines.append(f"Subsequence {n.name}:")
            sub_str = format_seq_nodes(n.body, indent)
            for ln in sub_str.splitlines():
                lines.append(indent + ln)
            lines.append("EndSubsequence")

        elif isinstance(n, SFCTransitionSub):
            lines.append(f"TransitionSub {n.name}:")
            ts_str = format_seq_nodes(n.body, indent)
            for ln in ts_str.splitlines():
                lines.append(indent + ln)
            lines.append("EndTransitionSub")

        elif isinstance(n, SFCFork):
            lines.append(f"Fork to {n.target}")

        elif isinstance(n, SFCBreak):
            lines.append("Break")

        else:
            # fallback for any unhandled node
            lines.append(str(n))

    return "\n".join(lines)


class Simple_DataType(Enum):
    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    IDENTSTRING = "identstring"
    TAGSTRING = "tagstring"
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
    @property
    def is_unused(self) -> bool:
        return not (bool(self.read) or bool(self.written))

    @property
    def is_read_only(self) -> bool:
        return bool(self.read) and not bool(self.written)

    @property
    def datatype_text(self) -> str:
        # Always return a string representation
        return (
            self.datatype.value
            if isinstance(self.datatype, Simple_DataType)
            else str(self.datatype)
        )

    name: str
    datatype: Simple_DataType | str  # accept either at init; we'll normalize
    global_var: bool | None = False
    const: bool | None = False
    state: bool | None = False
    opsave: bool | None = False
    secure: bool | None = False
    init_value: bool | None = None
    description: str | None = None
    read: bool | None = False
    written: bool | None = False
    usage_locations: list[tuple] = field(default_factory=list)

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

    def mark_read(self, module_path):
        self.read = True
        self.usage_locations.append((module_path.copy(), "read"))

    def mark_written(self, module_path):
        self.written = True
        self.usage_locations.append((module_path.copy(), "write"))

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
            #f"ModuleDef       : {format_optional(self.moduledef)}",
            #f"ModuleCode      : {format_optional(self.modulecode)}",
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
            #f"ModuleDef    : {format_optional(self.moduledef)}",
            #f"ModuleCode   : {format_optional(self.modulecode)}",
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
            f"ModuleCode: {self.modulecode!r}\n\n"
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

