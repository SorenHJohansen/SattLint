"""Module body and normalization helpers for the SattLine transformer."""

from __future__ import annotations

from typing import Any, Literal, cast

from lark import Token, Tree

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    SourceSpan,
    Variable,
)

from ._module_shared import (
    ModuleInvocation,
    TransformerItem,
    TransformerTree,
    _flatten_items,
    _groupconn_value,
    _meta_span,
    _submodule_children,
    _tree_children,
    _v_args,
)


class _ModuleAssemblyMixin:
    """Mixin providing module body normalization and AST assembly methods."""

    def module_body(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar module_body -> Tree (keep structure for collectors)."""
        return Tree(const.TREE_TAG_MODULE_BODY, cast(list[Any], items))

    def base_module_body(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar base_module_body -> Tree (keep structure for collectors)."""
        return Tree(const.TREE_TAG_BASE_MODULE_BODY, cast(list[Any], items))

    def base_picture_module(self, items: list[TransformerItem]) -> BasePicture:
        """Grammar base_picture_module -> BasePicture (root module with header + definitions)."""
        if not items:
            raise ValueError("No items in base_picture_module")

        header_item = items[0]
        if not isinstance(header_item, ModuleHeader):
            raise ValueError("base_picture_module missing ModuleHeader")
        header = header_item
        datatype_defs: list[DataType] = []
        moduletype_defs: list[ModuleTypeDef] = []
        localvariables: list[Variable] = []
        submodules: list[ModuleInvocation] = []
        moduledef: ModuleDef | None = None
        modulecode: ModuleCode | None = None
        scan_group_info: dict[str, object] | None = None

        for it in _flatten_items(items[1:]):
            if isinstance(it, DataType):
                datatype_defs.append(it)
            elif isinstance(it, ModuleTypeDef):
                moduletype_defs.append(it)
            elif isinstance(it, ModuleDef):
                moduledef = it
            elif isinstance(it, ModuleCode):
                modulecode = it
            elif isinstance(it, dict) and "groupconn" in it:
                scan_group_info = cast(dict[str, object], it)
            elif isinstance(it, Tree):
                tree = cast(TransformerTree, it)
                if tree.data == const.TREE_TAG_DATATYPE_LIST:
                    datatype_defs.extend([x for x in _tree_children(tree) if isinstance(x, DataType)])
                elif tree.data == const.TREE_TAG_MODULETYPE_LIST:
                    moduletype_defs.extend([x for x in _tree_children(tree) if isinstance(x, ModuleTypeDef)])
                elif tree.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend([x for x in _tree_children(tree) if isinstance(x, Variable)])
                elif tree.data == const.TREE_TAG_SUBMODULES:
                    submodules.extend(_submodule_children(_tree_children(tree)))

        if scan_group_info:
            header.groupconn = _groupconn_value(scan_group_info)
            header.groupconn_global = bool(scan_group_info.get("global", False))

        return BasePicture(
            header=header,
            name="BasePicture",
            position=header.invoke_coord,
            datatype_defs=datatype_defs,
            moduletype_defs=moduletype_defs,
            localvariables=localvariables,
            submodules=submodules,
            moduledef=moduledef,
            modulecode=modulecode,
        )

    def invocation_new_module(self, items: list[TransformerItem]) -> FrameModule | SingleModule:
        """Grammar invocation_new_module -> FrameModule or SingleModule."""
        header: ModuleHeader | None = None
        datecode: int | None = None
        moduleparameters: list[Variable] = []
        localvariables: list[Variable] = []
        submodules: list[ModuleInvocation] = []
        moduledef: ModuleDef | None = None
        modulecode: ModuleCode | None = None
        param_mappings: list[ParameterMapping] = []
        scan_group_info: dict[str, object] | None = None
        is_frame_module = any(it is True for it in items)

        for item in _flatten_items(items):
            if isinstance(item, ModuleHeader) and header is None:
                header = item
            elif isinstance(item, int) and datecode is None:
                datecode = item
            elif isinstance(item, ModuleDef):
                moduledef = item
            elif isinstance(item, ModuleCode):
                modulecode = item
            elif isinstance(item, dict) and "groupconn" in item:
                scan_group_info = cast(dict[str, object], item)
            elif isinstance(item, Tree):
                tree = cast(TransformerTree, item)
                if tree.data == const.GRAMMAR_VALUE_MODULEPARAMETERS:
                    moduleparameters.extend([x for x in _tree_children(tree) if isinstance(x, Variable)])
                elif tree.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend([x for x in _tree_children(tree) if isinstance(x, Variable)])
                elif tree.data == const.TREE_TAG_SUBMODULES:
                    submodules.extend(_submodule_children(_tree_children(tree)))
                elif tree.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                    param_mappings.extend([x for x in _tree_children(tree) if isinstance(x, ParameterMapping)])

        if not header:
            raise ValueError("Missing module header")

        if scan_group_info:
            header.groupconn = _groupconn_value(scan_group_info)
            header.groupconn_global = bool(scan_group_info.get("global", False))

        if is_frame_module:
            return FrameModule(
                header=header,
                datecode=datecode,
                submodules=submodules,
                moduledef=moduledef,
                modulecode=modulecode,
            )
        return SingleModule(
            header=header,
            datecode=datecode,
            moduleparameters=moduleparameters,
            localvariables=localvariables,
            submodules=submodules,
            moduledef=moduledef,
            modulecode=modulecode,
            parametermappings=param_mappings,
        )

    def frame_module(self, _items: list[TransformerItem]) -> Literal[True]:
        """Grammar frame_module -> True marker for frame module."""
        return True

    def invocation_module_type(self, items: list[TransformerItem]) -> ModuleTypeInstance:
        """Grammar invocation_module_type -> ModuleTypeInstance (invocation of a module type)."""
        header: ModuleHeader | None = None
        param_mappings: list[ParameterMapping] = []
        moduletype_name: str | None = None

        for item in items:
            if isinstance(item, ModuleHeader):
                header = item
            elif isinstance(item, str) and moduletype_name is None:
                moduletype_name = item
            elif isinstance(item, Tree) and item.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                tree = cast(TransformerTree, item)
                param_mappings.extend([x for x in _tree_children(tree) if isinstance(x, ParameterMapping)])

        if not header:
            raise ValueError("Missing module header")
        if not moduletype_name:
            raise ValueError("Missing module type name")

        return ModuleTypeInstance(
            header=header,
            moduletype_name=moduletype_name,
            parametermappings=param_mappings,
        )

    @_v_args(meta=True)
    def variable_name(self, meta: Any, children: list[TransformerItem]) -> dict[str, object | None]:
        """Grammar variable_name -> dict with full dotted path and optional state suffix."""
        parts: list[str] = []
        state: str | None = None

        for child in children:
            if isinstance(child, Token):
                if child.type == const.KEY_NAME:
                    parts.append(child.value)
                elif child.type == const.KEY_DOT:
                    parts.append(".")
                elif child.type == "STATE_SUFFIX":
                    state = child.value[1:].strip().lower()
                elif child.type in (const.TOKEN_NEW, const.TOKEN_OLD):
                    state = child.type.lower()
            elif isinstance(child, str):
                if child.lower() in (const.GRAMMAR_VALUE_NEW.lower(), const.GRAMMAR_VALUE_OLD.lower()):
                    state = child.lower()
                elif child == ".":
                    parts.append(".")
                elif child not in (":",):
                    parts.append(child)

        full_name = "".join(parts)
        return {
            const.KEY_VAR_NAME: full_name,
            "state": state,
            "span": _meta_span(meta),
        }

    @_v_args(meta=True)
    def moduletype_definition(self, meta: Any, items: list[TransformerItem]) -> ModuleTypeDef:
        """Grammar moduletype_definition -> ModuleTypeDef (named module type with datecode)."""
        datecode: int | None = None
        moduleparameters: list[Variable] = []
        localvariables: list[Variable] = []
        submodules: list[ModuleInvocation] = []
        moduledef: ModuleDef | None = None
        modulecode: ModuleCode | None = None
        name: str | None = None
        scan_group_info: dict[str, object] | None = None

        for it in _flatten_items(items):
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, int) and datecode is None:
                datecode = it
            elif isinstance(it, ModuleDef):
                moduledef = it
            elif isinstance(it, ModuleCode):
                modulecode = it
            elif isinstance(it, dict) and "groupconn" in it:
                scan_group_info = cast(dict[str, object], it)
            elif isinstance(it, Tree):
                if it.data == const.GRAMMAR_VALUE_MODULEPARAMETERS:
                    moduleparameters.extend(
                        [x for x in _tree_children(cast(TransformerTree, it)) if isinstance(x, Variable)]
                    )
                elif it.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend(
                        [x for x in _tree_children(cast(TransformerTree, it)) if isinstance(x, Variable)]
                    )
                elif it.data == const.TREE_TAG_SUBMODULES:
                    submodules.extend(_submodule_children(_tree_children(cast(TransformerTree, it))))

        if name is None:
            raise Exception("Name cannot be none")

        moduletype = ModuleTypeDef(
            name=name,
            datecode=datecode,
            moduleparameters=moduleparameters,
            localvariables=localvariables,
            submodules=submodules,
            moduledef=moduledef,
            modulecode=modulecode,
            declaration_span=_meta_span(meta),
        )
        if scan_group_info:
            moduletype.groupconn = _groupconn_value(scan_group_info)
            moduletype.groupconn_global = bool(scan_group_info.get("global", False))
        return moduletype

    def moduletype_definitions(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar moduletype_definitions -> Tree of ModuleTypeDefs."""
        out: list[Any] = []
        for it in items:
            if isinstance(it, ModuleTypeDef):
                out.append(it)
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_MODULETYPE_DEFINITION:
                tree = cast(TransformerTree, it)
                for child in _tree_children(tree):
                    if isinstance(child, ModuleTypeDef):
                        out.append(child)
        return Tree(const.TREE_TAG_MODULETYPE_LIST, out)

    def moduletype_par_transfer(self, items: list[TransformerItem]) -> ParameterMapping:
        """Grammar moduletype_par_transfer -> ParameterMapping (variable => value)."""
        if not items:
            raise ValueError("moduletype_par_transfer received empty items")

        idx = 0
        target_raw = items[idx]
        idx += 1

        if target_raw is None:
            raise ValueError("moduletype_par_transfer missing target variable_name")

        if isinstance(target_raw, dict):
            target_val: dict[str, object] | str = cast(dict[str, object], target_raw)
        elif isinstance(target_raw, str):
            target_val = target_raw
        else:
            target_val = str(target_raw)

        is_global = False
        if idx < len(items):
            global_raw = items[idx]
            if isinstance(global_raw, bool):
                is_global = global_raw
                idx += 1

        is_duration = False
        if idx < len(items) and items[idx] == const.GRAMMAR_VALUE_DURATION_VALUE:
            is_duration = True
            idx += 1

        source_literal: Any | None = None
        source_var: dict[str, object] | None = None
        source_type: str = const.KEY_VALUE

        if idx < len(items):
            source = items[idx]
            if isinstance(source, int | float | str | bool):
                source_literal = source
                source_type = const.KEY_VALUE
            elif isinstance(source, dict) and const.GRAMMAR_VALUE_TIME_VALUE in source:
                source_literal = cast(dict[str, object], source)
                source_type = const.KEY_VALUE
            elif isinstance(source, dict):
                source_var = cast(dict[str, object], source)
                source_type = const.TREE_TAG_VARIABLE_NAME
            else:
                source_literal = str(source)
                source_type = const.KEY_VALUE

        return ParameterMapping(
            target=target_val,
            source_type=source_type,
            is_source_global=is_global,
            is_duration=is_duration,
            source=source_var,
            source_literal=source_literal,
        )

    def moduletype_par_list(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar moduletype_par_list -> Tree of ParameterMappings."""
        return Tree(
            const.TREE_TAG_MODULETYPE_PAR_LIST,
            cast(list[Any], [x for x in items if isinstance(x, ParameterMapping)]),
        )

    def invocation_tail(self, items: list[TransformerItem]) -> TransformerTree | None:
        """Grammar invocation_tail -> optional parameter list Tree."""
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                return cast(TransformerTree, it)
        return None

    def scan_group(self, items: list[TransformerItem]) -> dict[str, object]:
        """Grammar scan_group -> dict with groupconn variable and global flag."""
        is_global = any(isinstance(it, bool) and it for it in items)
        var: dict[str, object] | None = None
        for it in items:
            if isinstance(it, dict) and const.KEY_VAR_NAME in it:
                var = cast(dict[str, object], it)
        return {"groupconn": var, "global": is_global}

    @_v_args(meta=True)
    def variable_item(self, meta: Any, items: list[TransformerItem]) -> tuple[str, str | None, SourceSpan | None]:
        """Grammar variable_item -> (name, description, span) tuple."""
        if not items or not isinstance(items[0], str):
            raise ValueError("variable_item missing variable name")
        name = items[0]
        desc = None
        if len(items) > 1 and isinstance(items[1], str):
            desc = items[1]
        return (name, desc, _meta_span(meta))

    def opt_var_init(self, items: list[TransformerItem]) -> tuple[TransformerItem, bool] | None:
        """Grammar opt_var_init -> (value, is_duration) tuple or None."""
        if not items:
            return None
        is_duration = any(item == const.GRAMMAR_VALUE_DURATION_VALUE for item in items[:-1])
        return (items[-1], is_duration)

    def time_value(self, items: list[TransformerItem]) -> dict[str, str | None]:
        """Grammar time_value -> dict with time string."""
        time_string = None
        for it in items:
            if isinstance(it, str):
                time_string = it
        return {const.GRAMMAR_VALUE_TIME_VALUE: time_string}

    def variable_group(self, items: list[TransformerItem]) -> list[Variable]:
        """Grammar variable_group -> list of Variables with common datatype and modifiers."""
        from sattline_parser.transformer._tokens_mixin import DEFAULT_INIT

        items = [x for x in items if x is not None]

        var_items: list[tuple[str, str | None, SourceSpan | None]] = []
        idx = 0
        while idx < len(items) and isinstance(items[idx], tuple):
            var_items.append(cast(tuple[str, str | None, SourceSpan | None], items[idx]))
            idx += 1
        if not var_items:
            return []

        global_flag = False
        if idx < len(items) and items[idx] is True:
            global_flag = True
            idx += 1

        if idx >= len(items) or not isinstance(items[idx], str):
            raise ValueError("Expected datatype NAME in variable_group")
        datatype = cast(str, items[idx])
        idx += 1

        is_const = False
        is_state = False
        is_opsave = False
        is_secure = False

        while (
            idx < len(items)
            and isinstance(items[idx], str)
            and items[idx]
            in (
                const.GRAMMAR_VALUE_CONST_KW,
                const.GRAMMAR_VALUE_STATE_KW,
                const.GRAMMAR_VALUE_OPSAVE_KW,
                const.GRAMMAR_VALUE_SECURE_KW,
            )
        ):
            modifier = items[idx]
            if modifier == const.GRAMMAR_VALUE_CONST_KW:
                is_const = True
            elif modifier == const.GRAMMAR_VALUE_STATE_KW:
                is_state = True
            elif modifier == const.GRAMMAR_VALUE_OPSAVE_KW:
                is_opsave = True
            elif modifier == const.GRAMMAR_VALUE_SECURE_KW:
                is_secure = True
            idx += 1

        init_value: object | None = None
        init_is_duration = False
        if idx < len(items):
            init_raw = items[idx]
            if isinstance(init_raw, tuple):
                init_tuple = cast(tuple[object, ...], init_raw)
                if len(init_tuple) == 2:
                    init_value = init_tuple[0]
                    init_is_duration = isinstance(init_tuple[1], bool) and init_tuple[1]
                else:
                    init_value = cast(object, init_raw)
            else:
                init_value = init_raw

        resolved_init_value: Any | None = None if init_value is DEFAULT_INIT else init_value

        variables: list[Variable] = []
        for name, desc, declaration_span in var_items:
            variables.append(
                Variable(
                    name=name,
                    datatype=datatype,
                    global_var=global_flag,
                    const=is_const,
                    state=is_state,
                    opsave=is_opsave,
                    secure=is_secure,
                    init_value=resolved_init_value,
                    description=desc,
                    declaration_span=declaration_span,
                    init_is_duration=(init_is_duration and resolved_init_value is not None),
                )
            )
        return variables

    def variable_list(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar variable_list -> Tree of all Variables in group."""
        out: list[Any] = []
        for group in items:
            if isinstance(group, list):
                out.extend(cast(list[Any], group))
        return Tree(const.TREE_TAG_VAR_LIST, out)

    def moduleparameters(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar moduleparameters -> Tree of module parameter Variables."""
        parameters: list[Any] = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                tree = cast(TransformerTree, it)
                parameters = cast(list[Any], _tree_children(tree))
        return Tree(const.GRAMMAR_VALUE_MODULEPARAMETERS, parameters)

    def localvariables(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar localvariables -> Tree of local Variables."""
        variables: list[Any] = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                tree = cast(TransformerTree, it)
                variables = cast(list[Any], _tree_children(tree))
        return Tree(const.GRAMMAR_VALUE_LOCALVARIABLES, variables)

    def submodules(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar submodules -> Tree of module invocation nodes."""
        submodule_items: list[ModuleInvocation] = []
        for item in _flatten_items(items):
            if isinstance(item, (SingleModule, FrameModule, ModuleTypeInstance)):
                submodule_items.append(item)
        return Tree(const.TREE_TAG_SUBMODULES, cast(list[Any], submodule_items))

    @_v_args(meta=True)
    def record(self, meta: Any, items: list[TransformerItem]) -> DataType:
        """Grammar record -> DataType definition with optional description and fields."""
        name: str | None = None
        description: str | None = None
        datecode: int | None = None
        fields: list[Variable] = []

        for item in items:
            if isinstance(item, str):
                if name is None:
                    name = item
                elif description is None:
                    description = item
            elif isinstance(item, int) and datecode is None:
                datecode = item
            elif isinstance(item, Tree) and item.data == const.TREE_TAG_VAR_LIST:
                fields = [child for child in _tree_children(cast(TransformerTree, item)) if isinstance(child, Variable)]

        if name is None:
            raise ValueError("record is missing datatype name")

        return DataType(
            name=name,
            description=description,
            datecode=datecode,
            var_list=fields,
            declaration_span=_meta_span(meta),
        )

    def datatype_typedefinitions(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar datatype_typedefinitions -> Tree of DataType records."""
        records: list[DataType] = []
        for item in items:
            if isinstance(item, DataType):
                records.append(item)
            elif isinstance(item, Tree):
                records.extend(
                    [child for child in _tree_children(cast(TransformerTree, item)) if isinstance(child, DataType)]
                )
        return Tree(const.TREE_TAG_DATATYPE_LIST, cast(list[Any], records))


__all__ = ["_ModuleAssemblyMixin"]
