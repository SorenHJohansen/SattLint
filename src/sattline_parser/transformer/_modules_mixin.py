"""Module structure mixin for SLTransformer.

Handles module definitions, headers, parameters, local variables, module invocations,
layout specifications (coordinates, sizes, grid), and related module-level constructs.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from lark import Token, Tree, v_args

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


def _meta_span(meta: Any) -> SourceSpan | None:
    """Extract source span from Lark meta."""
    line = getattr(meta, "line", None)
    column = getattr(meta, "column", None)
    if line is None or column is None:
        return None
    return SourceSpan(line=int(line), column=int(column))


def _is_tree(node: Any) -> bool:
    """Check if node is a Lark Tree."""
    return hasattr(node, "data") and hasattr(node, "children")


def _flatten_items(items):
    """Yield flat stream of items from possibly nested lists and Trees."""
    for it in items:
        if isinstance(it, list):
            yield from _flatten_items(it)
        elif isinstance(it, Tree) and it.data in (
            const.TREE_TAG_BASE_MODULE_BODY,
            const.TREE_TAG_MODULE_BODY,
        ):
            tree = cast(Tree, it)
            yield from _flatten_items(tree.children)
        else:
            yield it


class _ModulesMixin:
    """Mixin providing module structure and layout transformation methods."""

    # ---- Module body and structure ----

    def module_body(self, items):
        """Grammar module_body -> Tree (keep structure for collectors)."""
        return Tree(const.TREE_TAG_MODULE_BODY, items)

    def base_module_body(self, items):
        """Grammar base_module_body -> Tree (keep structure for collectors)."""
        return Tree(const.TREE_TAG_BASE_MODULE_BODY, items)

    def IGNOREMAXMODULE(self, _):
        """Grammar IGNOREMAXMODULE terminal -> string marker."""
        return const.GRAMMAR_VALUE_IGNOREMAXMODULE

    def LAYERMODULE(self, _):
        """Grammar LAYERMODULE terminal -> string marker."""
        return const.GRAMMAR_VALUE_LAYERMODULE

    def argument(self, items):
        """Grammar argument rule -> pass through single non-Token child."""
        for it in items:
            if not isinstance(it, Token):
                return it
        return None

    def arguments(self, items):
        """Grammar arguments -> Tree of non-Token argument items."""
        return Tree(const.TREE_TAG_ARGUMENTS, [it for it in items if not isinstance(it, Token)])

    @v_args(meta=True)
    def module_header(self, meta, items) -> ModuleHeader:
        """Grammar module_header -> ModuleHeader with position, arguments, layer, enable."""
        name = None
        coords5: tuple[float, float, float, float, float] | None = None
        coord_tails: list[Any] = []
        args_trees: list[Tree] = []
        invocation_arguments: list[str] = []
        layer = None
        enable_val = True
        zoom_limits = None
        zoomable = False
        enable_tail = None

        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, dict) and const.TREE_TAG_INVOKE_COORD in it:
                raw = it[const.TREE_TAG_INVOKE_COORD]
                if isinstance(raw, tuple) and len(raw) >= 5 and all(isinstance(x, int | float) for x in raw):
                    coords5 = (
                        float(raw[0]),
                        float(raw[1]),
                        float(raw[2]),
                        float(raw[3]),
                        float(raw[4]),
                    )
                    coord_tails = list(it.get(const.KEY_TAILS) or [])
            elif isinstance(it, tuple) and len(it) >= 5 and all(isinstance(x, int | float) for x in it):
                coords5 = (
                    float(it[0]),
                    float(it[1]),
                    float(it[2]),
                    float(it[3]),
                    float(it[4]),
                )
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_ARGUMENTS:
                args_trees.append(cast(Tree, it))

        if coords5 is None:
            raise ValueError("module_header missing invoke_coord")

        header_arg_strings: list[str] = []
        for t in args_trees:
            for ch in t.children:
                if isinstance(ch, int) and layer is None:
                    layer = ch
                elif isinstance(ch, dict):
                    d = cast(dict, ch)
                    if const.TREE_TAG_ENABLE in d:
                        enable_val = cast(bool, d[const.TREE_TAG_ENABLE])
                        if const.KEY_TAIL in d and d[const.KEY_TAIL] is not None:
                            enable_tail = d[const.KEY_TAIL]
                    elif const.GRAMMAR_VALUE_ZOOMLIMITS in d:
                        zoom_limits = cast(tuple[float, float], d[const.GRAMMAR_VALUE_ZOOMLIMITS])
                    elif const.GRAMMAR_VALUE_ZOOMABLE in d:
                        zoomable = True
                elif isinstance(ch, str):
                    header_arg_strings.append(ch)
                    invocation_arguments.append(ch)

        return ModuleHeader(
            name=name or "",
            invoke_coord=coords5,
            declaration_span=_meta_span(meta),
            invocation_arguments=tuple(invocation_arguments),
            zoomable=zoomable,
            layer_info=(str(layer) if layer is not None else None),
            enable=enable_val,
            zoom_limits=zoom_limits,
            enable_tail=enable_tail,
            invoke_coord_tails=coord_tails,
        )

    # ---- BasePicture module ----

    def base_picture_module(self, items) -> BasePicture:
        """Grammar base_picture_module -> BasePicture (root module with header + definitions)."""
        if not items:
            raise ValueError("No items in base_picture_module")

        header: ModuleHeader = items[0]
        datatype_defs: list[DataType] = []
        moduletype_defs: list[ModuleTypeDef] = []
        localvariables: list[Variable] = []
        submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = []
        moduledef: ModuleDef | None = None
        modulecode: ModuleCode | None = None
        scan_group_info: dict | None = None

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
                scan_group_info = it
            elif isinstance(it, Tree):
                tree = cast(Tree, it)
                if tree.data == const.TREE_TAG_DATATYPE_LIST:
                    datatype_defs.extend([x for x in tree.children if isinstance(x, DataType)])
                elif tree.data == const.TREE_TAG_MODULETYPE_LIST:
                    moduletype_defs.extend([x for x in tree.children if isinstance(x, ModuleTypeDef)])
                elif tree.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend([x for x in tree.children if isinstance(x, Variable)])
                elif tree.data == const.TREE_TAG_SUBMODULES:
                    for ch in tree.children:
                        if isinstance(ch, list):
                            submodules.extend(
                                [x for x in ch if isinstance(x, SingleModule | FrameModule | ModuleTypeInstance)]
                            )
                        elif isinstance(ch, SingleModule | FrameModule | ModuleTypeInstance):
                            submodules.append(ch)

        if scan_group_info:
            header.groupconn = scan_group_info.get("groupconn")
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

    # ---- Module invocation (new module) ----

    def invocation_new_module(self, items) -> FrameModule | SingleModule:
        """Grammar invocation_new_module -> FrameModule or SingleModule."""
        header: ModuleHeader | None = None
        datecode = None
        moduleparameters = []
        localvariables = []
        submodules = []
        moduledef = None
        modulecode = None
        param_mappings: list[ParameterMapping] = []
        scan_group_info: dict | None = None
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
                scan_group_info = item
            elif isinstance(item, Tree):
                tree = cast(Tree, item)
                if tree.data == const.GRAMMAR_VALUE_MODULEPARAMETERS:
                    moduleparameters.extend([x for x in tree.children if isinstance(x, Variable)])
                elif tree.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend([x for x in tree.children if isinstance(x, Variable)])
                elif tree.data == const.TREE_TAG_SUBMODULES:
                    for ch in tree.children:
                        if isinstance(ch, list):
                            submodules.extend(
                                [x for x in ch if isinstance(x, SingleModule | FrameModule | ModuleTypeInstance)]
                            )
                        elif isinstance(ch, SingleModule | FrameModule | ModuleTypeInstance):
                            submodules.append(ch)
                elif tree.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                    param_mappings.extend([x for x in tree.children if isinstance(x, ParameterMapping)])

        if not header:
            raise ValueError("Missing module header")

        if scan_group_info:
            header.groupconn = scan_group_info.get("groupconn")
            header.groupconn_global = bool(scan_group_info.get("global", False))

        if is_frame_module:
            return FrameModule(
                header=header,
                datecode=datecode,
                submodules=submodules,
                moduledef=moduledef,
                modulecode=modulecode,
            )
        else:
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

    def frame_module(self, _items) -> Literal[True]:
        """Grammar frame_module -> True marker for frame module."""
        return True

    # ---- Module type invocation ----

    def invocation_module_type(self, items) -> ModuleTypeInstance:
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
                tree = cast(Tree, item)
                param_mappings.extend([x for x in tree.children if isinstance(x, ParameterMapping)])

        if not header:
            raise ValueError("Missing module header")
        if not moduletype_name:
            raise ValueError("Missing module type name")

        return ModuleTypeInstance(
            header=header,
            moduletype_name=moduletype_name,
            parametermappings=param_mappings,
        )

    # ---- Variable names and references ----

    @v_args(meta=True)
    def variable_name(self, meta, children):
        """Grammar variable_name -> dict with full dotted path and optional state suffix."""
        parts: list[str] = []
        state: str | None = None

        for ch in children:
            if isinstance(ch, Token):
                if ch.type == const.KEY_NAME:
                    parts.append(ch.value)
                elif ch.type == const.KEY_DOT:
                    parts.append(".")
                elif ch.type == "STATE_SUFFIX":
                    state = ch.value[1:].strip().lower()
                elif ch.type in (const.TOKEN_NEW, const.TOKEN_OLD):
                    state = ch.type.lower()
            elif isinstance(ch, str):
                if ch.lower() in (const.GRAMMAR_VALUE_NEW, const.GRAMMAR_VALUE_OLD):
                    state = ch.lower()
                elif ch == ".":
                    parts.append(".")
                elif ch not in (":",):
                    parts.append(ch)

        full_name = "".join(parts)
        return {
            const.KEY_VAR_NAME: full_name,
            "state": state,
            "span": _meta_span(meta),
        }

    # ---- Module types ----

    @v_args(meta=True)
    def moduletype_definition(self, meta, items) -> ModuleTypeDef:
        """Grammar moduletype_definition -> ModuleTypeDef (named module type with datecode)."""
        datecode: int | None = None
        moduleparameters: list[Variable] = []
        localvariables: list[Variable] = []
        submodules: list[SingleModule | FrameModule | ModuleTypeInstance] = []
        moduledef: ModuleDef | None = None
        modulecode: ModuleCode | None = None
        name: str | None = None
        scan_group_info: dict | None = None

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
                scan_group_info = it
            elif isinstance(it, Tree):
                if it.data == const.GRAMMAR_VALUE_MODULEPARAMETERS:
                    moduleparameters.extend([x for x in it.children if isinstance(x, Variable)])
                elif it.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend([x for x in it.children if isinstance(x, Variable)])
                elif it.data == const.TREE_TAG_SUBMODULES:
                    for ch in it.children:
                        if isinstance(ch, list):
                            submodules.extend(
                                [x for x in ch if isinstance(x, SingleModule | FrameModule | ModuleTypeInstance)]
                            )
                        elif isinstance(ch, SingleModule | FrameModule | ModuleTypeInstance):
                            submodules.append(ch)

        if name is None:
            raise Exception("Name cannot be none")

        mtd = ModuleTypeDef(
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
            mtd.groupconn = scan_group_info.get("groupconn")
            mtd.groupconn_global = bool(scan_group_info.get("global", False))
        return mtd

    def moduletype_definitions(self, items) -> Tree:
        """Grammar moduletype_definitions -> Tree of ModuleTypeDefs."""
        out: list[Any] = []
        for it in items:
            if isinstance(it, ModuleTypeDef):
                out.append(it)
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_MODULETYPE_DEFINITION:
                tree = cast(Tree, it)
                for ch in tree.children:
                    if isinstance(ch, ModuleTypeDef):
                        out.append(ch)
        return Tree(const.TREE_TAG_MODULETYPE_LIST, out)

    def moduletype_par_transfer(self, items) -> ParameterMapping:
        """Grammar moduletype_par_transfer -> ParameterMapping (variable => value)."""

        if not items:
            raise ValueError("moduletype_par_transfer received empty items")

        idx = 0
        target_raw = items[idx]
        idx += 1

        if target_raw is None:
            raise ValueError("moduletype_par_transfer missing target variable_name")

        if isinstance(target_raw, dict):
            target_val: dict | str = cast(dict, target_raw)
        elif isinstance(target_raw, str):
            target_val = target_raw
        else:
            target_val = str(target_raw)

        is_global = False
        if idx < len(items) and isinstance(items[idx], bool):
            is_global = items[idx]
            idx += 1

        is_duration = False
        if idx < len(items) and items[idx] == const.GRAMMAR_VALUE_DURATION_VALUE:
            is_duration = True
            idx += 1

        source_literal: Any | None = None
        source_var: dict | None = None
        source_type: str = const.KEY_VALUE

        if idx < len(items):
            src = items[idx]
            if isinstance(src, int | float | str | bool) or (
                isinstance(src, dict) and const.GRAMMAR_VALUE_TIME_VALUE in src
            ):
                source_literal = src
                source_type = const.KEY_VALUE
            elif isinstance(src, dict):
                source_var = cast(dict, src)
                source_type = const.TREE_TAG_VARIABLE_NAME
            else:
                source_literal = str(src)
                source_type = const.KEY_VALUE

        return ParameterMapping(
            target=target_val,
            source_type=source_type,
            is_source_global=is_global,
            is_duration=is_duration,
            source=source_var,
            source_literal=source_literal,
        )

    def moduletype_par_list(self, items) -> Tree:
        """Grammar moduletype_par_list -> Tree of ParameterMappings."""
        return Tree(
            const.TREE_TAG_MODULETYPE_PAR_LIST,
            cast(list, [x for x in items if isinstance(x, ParameterMapping)]),
        )

    def invocation_tail(self, items) -> Tree | None:
        """Grammar invocation_tail -> optional parameter list Tree."""
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                tree = cast(Tree, it)
                return tree
        return None

    def scan_group(self, items):
        """Grammar scan_group -> dict with groupconn variable and global flag."""
        is_global = any(isinstance(it, bool) and it for it in items)
        var = None
        for it in items:
            if isinstance(it, dict) and const.KEY_VAR_NAME in it:
                var = it
        return {"groupconn": var, "global": is_global}

    # ---- Variables and parameters ----

    @v_args(meta=True)
    def variable_item(self, meta, items):
        """Grammar variable_item -> (name, description, span) tuple."""
        name = items[0]
        desc = None
        if len(items) > 1 and isinstance(items[1], str):
            desc = items[1]
        return (name, desc, _meta_span(meta))

    def opt_var_init(self, items):
        """Grammar opt_var_init -> (value, is_duration) tuple or None."""
        if not items:
            return None
        is_duration = any(item == const.GRAMMAR_VALUE_DURATION_VALUE for item in items[:-1])
        return (items[-1], is_duration)

    def time_value(self, items):
        """Grammar time_value -> dict with time string."""
        time_string = None
        for it in items:
            if isinstance(it, str):
                time_string = it
        return {const.GRAMMAR_VALUE_TIME_VALUE: time_string}

    def variable_group(self, items):
        """Grammar variable_group -> list of Variables with common datatype and modifiers."""
        from sattline_parser.transformer._tokens_mixin import DEFAULT_INIT

        items = [x for x in items if x is not None]

        var_items = []
        idx = 0
        while idx < len(items) and isinstance(items[idx], tuple):
            var_items.append(items[idx])
            idx += 1
        if not var_items:
            return []

        global_flag = False
        if idx < len(items) and items[idx] is True:
            global_flag = True
            idx += 1

        if idx >= len(items) or not isinstance(items[idx], str):
            raise ValueError("Expected datatype NAME in variable_group")
        else:
            datatype = items[idx]
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
            mod = items[idx]
            if mod == const.GRAMMAR_VALUE_CONST_KW:
                is_const = True
            elif mod == const.GRAMMAR_VALUE_STATE_KW:
                is_state = True
            elif mod == const.GRAMMAR_VALUE_OPSAVE_KW:
                is_opsave = True
            elif mod == const.GRAMMAR_VALUE_SECURE_KW:
                is_secure = True
            idx += 1

        init_value = None
        init_is_duration = False
        if idx < len(items):
            init_raw = items[idx]
            if isinstance(init_raw, tuple) and len(init_raw) == 2:
                init_value, init_is_duration = init_raw
            else:
                init_value = init_raw

        variables = []
        for name, desc, declaration_span in var_items:
            v = Variable(
                name=name,
                datatype=datatype,
                global_var=global_flag,
                const=is_const,
                state=is_state,
                opsave=is_opsave,
                secure=is_secure,
                init_value=(None if init_value is DEFAULT_INIT else init_value),
                description=desc,
                declaration_span=declaration_span,
                init_is_duration=(init_is_duration and init_value is not DEFAULT_INIT),
            )
            variables.append(v)
        return variables

    def variable_list(self, items):
        """Grammar variable_list -> Tree of all Variables in group."""
        out = []
        for grp in items:
            if isinstance(grp, list):
                out.extend(grp)
        return Tree(const.TREE_TAG_VAR_LIST, out)

    def moduleparameters(self, items):
        """Grammar moduleparameters -> Tree of module parameter Variables."""
        parameters = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                tree = cast(Tree, it)
                parameters = tree.children
        return Tree(const.GRAMMAR_VALUE_MODULEPARAMETERS, parameters)

    def localvariables(self, items):
        """Grammar localvariables -> Tree of local Variables."""
        variables = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                tree = cast(Tree, it)
                variables = tree.children
        return Tree(const.GRAMMAR_VALUE_LOCALVARIABLES, variables)

    # ---- Module definitions and layout ----

    def origo_coord(self, items):
        """Grammar origo_coord -> coordinate values list."""
        return items

    def size(self, items):
        """Grammar size -> size values list."""
        return items

    def coordinates(self, items):
        """Grammar coordinates -> dict with (x,y) and optional coordinate tails."""
        # Filter out all Tokens first
        items_filtered = [v for v in items if not isinstance(v, Token)]
        nums = [float(v) for v in items_filtered if isinstance(v, int | float)]
        if len(nums) < 2:
            raise ValueError(f"coordinates missing REAL values (got {len(nums)})")
        tails = self._extract_coord_tails(items)  # type: ignore[attr-defined]
        return {
            const.KEY_COORDS: (nums[0], nums[1]),
            const.KEY_TAILS: tails or None,
        }

    def origo_size_pair(self, items):
        """Grammar origo_size_pair -> dict with two coordinate pairs and tails."""
        coords: list[tuple[float, float]] = []
        tails: list[Any] = []
        for it in items:
            if isinstance(it, dict) and const.KEY_COORDS in it:
                coord = it[const.KEY_COORDS]
                if isinstance(coord, tuple) and len(coord) == 2 and all(isinstance(x, int | float) for x in coord):
                    coords.append((float(coord[0]), float(coord[1])))
                    tails.extend(it.get(const.KEY_TAILS) or [])
            elif isinstance(it, tuple) and len(it) == 2 and all(isinstance(x, int | float) for x in it):
                coords.append((float(it[0]), float(it[1])))
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_COORDINATES:
                tree = cast(Tree, it)
                nums = [float(x) for x in tree.children if isinstance(x, int | float)]
                if len(nums) >= 2:
                    coords.append((nums[0], nums[1]))
        if len(coords) != 2:
            raise ValueError(f"origo_size_pair expected 2 coordinate pairs, found {len(coords)}")
        return {
            const.KEY_COORDS: (coords[0], coords[1]),
            const.KEY_TAILS: tails or None,
        }

    def invoke_coord(self, items):
        """Grammar invoke_coord -> dict with 5-tuple and coordinate tails."""
        # Filter out all Tokens first
        items_filtered = [v for v in items if not isinstance(v, Token)]
        nums = [float(v) for v in items_filtered if isinstance(v, int | float)]
        if len(nums) < 5:
            raise ValueError(f"invoke_coord expected 5 REALs, found {len(nums)}")
        tails = self._extract_coord_tails(items)  # type: ignore[attr-defined]
        return {
            const.TREE_TAG_INVOKE_COORD: tuple(nums[:5]),
            const.KEY_TAILS: tails or None,
        }

    def coord_invar_tail(self, items):
        """Grammar coord_invar_tail -> connected variable value."""
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError("coord_invar_tail expected connected variable or value")

    def coord_clippingbounds(self, items):
        """Grammar coord_clippingbounds -> Tree of clipping specification."""
        return Tree(const.GRAMMAR_VALUE_CLIPPINGBOUNDS, items)

    def clippingbounds(self, items):
        """Grammar clippingbounds -> dict with clipping values and tails."""
        payload = items[-1]
        if isinstance(payload, dict) and const.KEY_COORDS in payload:
            return {
                const.GRAMMAR_VALUE_CLIPPINGBOUNDS: payload[const.KEY_COORDS],
                const.KEY_TAILS: payload.get(const.KEY_TAILS) or None,
            }
        return {const.GRAMMAR_VALUE_CLIPPINGBOUNDS: payload}

    def seq_layers(self, items) -> dict[str, Any]:
        """Grammar seq_layers -> dict with sequence layer mapping."""
        return {const.KEY_SEQ_LAYERS: items[-1]}

    def zoomlimits(self, items) -> dict[str, tuple[Any, Any]]:
        """Grammar zoomlimits -> dict with min/max zoom values."""
        return {const.GRAMMAR_VALUE_ZOOMLIMITS: (items[-2], items[-1])}

    def ZOOMABLE(self, _) -> dict[str, bool]:
        """Grammar ZOOMABLE -> dict marking module as zoomable."""
        return {const.GRAMMAR_VALUE_ZOOMABLE: True}

    def grid(self, items) -> float:
        """Grammar grid -> float grid spacing value."""
        nums: list[float] = []
        for v in items:
            if isinstance(v, Token):
                continue
            try:
                nums.append(float(v))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"grid expected a numeric value; got {type(v).__name__}: {v!r}") from exc

        if not nums:
            types = ", ".join(type(x).__name__ for x in items)
            raise ValueError(f"grid expected at least one numeric value; got: {types}")

        return nums[-1]

    def moduledef_opts_seq(self, items) -> Tree:
        """Grammar moduledef_opts_seq -> Tree with merged option dict."""
        merged: dict[str, Any] = {}
        for d in items:
            merged.update(d)
        return Tree(const.TREE_TAG_MODULEDEF_OPTS_SEQ, cast(list, [merged]))

    def moduledef(self, items) -> ModuleDef:
        """Grammar moduledef -> ModuleDef with graphics, layout, and interact objects."""
        m = ModuleDef()
        for it in items:
            if isinstance(it, dict) and const.GRAMMAR_VALUE_CLIPPINGBOUNDS in it:
                m.clipping_bounds = it[const.GRAMMAR_VALUE_CLIPPINGBOUNDS]
                tails = it.get(const.KEY_TAILS) or []
                if tails:
                    m.properties.setdefault(const.KEY_TAILS, []).extend(tails)
            elif isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                m.clipping_bounds = it
            elif isinstance(it, list) and it:
                # Check what kind of list it is (GraphObjects or InteractObjects)
                from sattline_parser.models.ast_model import GraphObject, InteractObject

                if isinstance(it[0], GraphObject):
                    m.graph_objects = it
                elif isinstance(it[0], InteractObject):
                    m.interact_objects = it
            elif isinstance(it, dict):
                if const.GRAMMAR_VALUE_ZOOMLIMITS in it:
                    m.zoom_limits = it[const.GRAMMAR_VALUE_ZOOMLIMITS]
                if const.GRAMMAR_VALUE_ZOOMABLE in it:
                    m.zoomable = it[const.GRAMMAR_VALUE_ZOOMABLE]
                if const.GRAMMAR_VALUE_GRID in it and it[const.GRAMMAR_VALUE_GRID] is not None:
                    m.grid = float(it[const.GRAMMAR_VALUE_GRID])
                if const.KEY_SEQ_LAYERS in it:
                    m.seq_layers = it[const.KEY_SEQ_LAYERS]
        return m
