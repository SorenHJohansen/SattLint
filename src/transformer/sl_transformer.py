# sl_transformer.py
from lark import Transformer, Token, Tree
from typing import Any, Literal, cast
import constants as const
from models.ast_model import (
    BasePicture,
    DataType,
    ModuleTypeDef,
    ModuleHeader,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    Variable,
    ParameterMapping,
    ModuleDef,
    GraphObject,
    InteractObject,
    ModuleCode,
    Sequence,
    Equation,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    SFCAlternative,
    SFCParallel,
    SFCSubsequence,
    SFCTransitionSub,
    SFCFork,
    SFCBreak,
)

DEFAULT_INIT = object()


def _strip_quoted(s: str) -> str:
    # Lark STRING includes quotes; "" inside is an escaped quote
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        inner = s[1:-1]
    else:
        inner = s
    return inner.replace('""', '"').rstrip("\n")


def _flatten_items(items):
    """
    Yield a flat stream of items from possibly nested lists and Trees.
    Specifically unwrap Trees named 'base_module_body' and 'module_body'
    so collectors can see their children.
    """
    for it in items:
        if isinstance(it, list):
            yield from _flatten_items(it)
        elif isinstance(it, Tree) and it.data in ("base_module_body", "module_body"):
            yield from _flatten_items(it.children)
        else:
            yield it

def _is_tree(node: Any) -> bool:
    return hasattr(node, "data") and hasattr(node, "children")

def _iter_tree_children(node: Any):
    if _is_tree(node):
        for ch in getattr(node, "children", []):
            yield ch


class SLTransformer(Transformer):
    def __init__(self):
        super().__init__()

    # ---------- top-level ----------
    def start(self, items) -> BasePicture:
        for it in items:
            if isinstance(it, BasePicture):
                return it
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(f"start expected a BasePicture; got: {types}")

    # ---- DATATYPES ----
    def record(self, items):
        name, description, datecode, var_list = None, None, None, []
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, str) and description is None:
                description = it
            elif isinstance(it, int):
                datecode = it
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                var_list = [v for v in it.children if isinstance(v, Variable)]
        return DataType(
            name=name or "",
            description=description,
            datecode=datecode,
            var_list=var_list,
        )

    def datatype_typedefinitions(self, items):
        out = []
        for it in items:
            if isinstance(it, DataType):
                out.append(it)
        return Tree(const.TREE_TAG_DATATYPE_LIST, out)

    # ---- MODULETYPES ----
    # ------------------------
    # Module header
    # ------------------------
    def module_body(self, items):
        # Keep structure; collectors will unwrap via _flatten_items
        return Tree("module_body", items)

    def base_module_body(self, items):
        # Keep structure; collectors will unwrap via _flatten_items
        return Tree("base_module_body", items)
    
    def IGNOREMAXMODULE(self, _):
        return const.GRAMMAR_VALUE_IGNOREMAXMODULE

    def LAYERMODULE(self, _):
        return const.GRAMMAR_VALUE_LAYERMODULE

    # argument is now a union; just pass through its single child
    def argument(self, items):
        # Each branch already transformed (layer_info -> int, enable/zoomlimits -> dict, flags -> str)
        for it in items:
            if not isinstance(it, Token):
                return it
        return None

    def arguments(self, items):
        # Keep the tag, drop raw tokens.
        return Tree(const.TREE_TAG_ARGUMENTS, [it for it in items if not isinstance(it, Token)])

    def module_header(self, items) -> ModuleHeader:
        name = None
        coords5: tuple[float, float, float, float, float] | None = None
        args_trees: list[Tree] = []
        layer = None
        enable_val = True
        zoom_limits = None
        zoomable = False
        enable_tail = None

        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, tuple) and len(it) >= 5 and all(isinstance(x, (int, float)) for x in it):
                coords5 = (float(it[0]), float(it[1]), float(it[2]), float(it[3]), float(it[4]))
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_ARGUMENTS:
                args_trees.append(it)

        if coords5 is None:
            raise ValueError("module_header missing invoke_coord")

        # Merge arguments from all blocks (unchanged)
        header_arg_strings: list[str] = []
        for t in args_trees:
            for ch in t.children:
                if isinstance(ch, int) and layer is None:
                    layer = ch
                elif isinstance(ch, dict):
                    if const.TREE_TAG_ENABLE in ch:
                        enable_val = ch[const.TREE_TAG_ENABLE]
                        if const.KEY_TAIL in ch and ch[const.KEY_TAIL] is not None:
                            enable_tail = ch[const.KEY_TAIL]
                    elif const.GRAMMAR_VALUE_ZOOMLIMITS in ch:
                        zoom_limits = ch[const.GRAMMAR_VALUE_ZOOMLIMITS]
                    elif const.GRAMMAR_VALUE_ZOOMABLE in ch:
                        zoomable = True
                elif isinstance(ch, str):
                    header_arg_strings.append(ch)

        return ModuleHeader(
            name=name or "",
            invoke_coord=coords5,
            zoomable=zoomable,
            layer_info=(str(layer) if layer is not None else None),
            enable=enable_val,
            zoom_limits=zoom_limits,
            enable_tail=enable_tail,
        )

    # ------------------------
    # BasePicture module
    # ------------------------
    def base_picture_module(self, items) -> BasePicture:
        """
        items[0] -> ModuleHeader
        items[1:] -> base_module_body items (datatype typedefs, module type defs, localvariables, submodules, moduledef, modulecode)
        """

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
                # Handle your tagged Trees
                if it.data == const.TREE_TAG_DATATYPE_LIST:
                    datatype_defs.extend(
                        [x for x in it.children if isinstance(x, DataType)]
                    )
                elif it.data == const.TREE_TAG_MODULETYPE_LIST:
                    moduletype_defs.extend(
                        [x for x in it.children if isinstance(x, ModuleTypeDef)]
                    )
                elif it.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend(
                        [x for x in it.children if isinstance(x, Variable)]
                    )
                elif it.data == const.GRAMMAR_VALUE_SUBMODULES:
                    # Children contains a single list of module instances
                    for ch in it.children:
                        if isinstance(ch, list):
                            submodules.extend(
                                [
                                    x
                                    for x in ch
                                    if isinstance(
                                        x,
                                        (SingleModule, FrameModule, ModuleTypeInstance),
                                    )
                                ]
                            )
                        elif isinstance(
                            ch, (SingleModule, FrameModule, ModuleTypeInstance)
                        ):
                            submodules.append(ch)
        if scan_group_info:
            header.groupconn = scan_group_info.get("groupconn")
            header.groupconn_global = bool(scan_group_info.get("global", False))

        base_picture = BasePicture(
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

        return base_picture

    # ------------------------
    # Invocation of a new module
    # ------------------------
    def invocation_new_module(self, items) -> FrameModule | SingleModule:
        header: ModuleHeader | None = None
        datecode = None
        moduleparameters = []
        localvariables = []
        submodules = []
        moduledef = None
        modulecode = None
        param_mappings: list[ParameterMapping] = []
        scan_group_info: dict | None = None

        # Check if this is a frame module
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
                if item.data == const.GRAMMAR_VALUE_MODULEPARAMETERS:
                    moduleparameters.extend(
                        [x for x in item.children if isinstance(x, Variable)]
                    )
                elif item.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend(
                        [x for x in item.children if isinstance(x, Variable)]
                    )
                elif item.data == const.GRAMMAR_VALUE_SUBMODULES:
                    for ch in item.children:
                        if isinstance(ch, list):
                            submodules.extend(
                                [
                                    x
                                    for x in ch
                                    if isinstance(
                                        x,
                                        (SingleModule, FrameModule, ModuleTypeInstance),
                                    )
                                ]
                            )
                        elif isinstance(
                            ch, (SingleModule, FrameModule, ModuleTypeInstance)
                        ):
                            submodules.append(ch)
                elif item.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                    param_mappings.extend(
                        [x for x in item.children if isinstance(x, ParameterMapping)]
                    )

        if not header:
            raise ValueError("Missing module header")
        
        if scan_group_info:
            header.groupconn = scan_group_info.get("groupconn")
            header.groupconn_global = bool(scan_group_info.get("global", False))

        if is_frame_module:
            module = FrameModule(
                header=header,
                datecode=datecode,
                submodules=submodules,
                moduledef=moduledef,
                modulecode=modulecode,
            )
        else:
            module = SingleModule(
                header=header,
                datecode=datecode,
                moduleparameters=moduleparameters,
                localvariables=localvariables,
                submodules=submodules,
                moduledef=moduledef,
                modulecode=modulecode,
                parametermappings=param_mappings,
            )
        return module

    def frame_module(self, _items) -> Literal[True]:
        # "(" FRAME_MODULE ")"
        return True

    # ------------------------
    # Invocation of a module type
    # ------------------------
    def invocation_module_type(self, items) -> ModuleTypeInstance:
        header: ModuleHeader | None = None
        param_mappings: list[ParameterMapping] = []
        moduletype_name: str | None = None

        for item in items:
            if isinstance(item, ModuleHeader):
                header = item
            elif isinstance(item, str) and moduletype_name is None:
                moduletype_name = item
            elif (
                isinstance(item, Tree)
                and item.data == const.TREE_TAG_MODULETYPE_PAR_LIST
            ):
                param_mappings.extend(
                    [x for x in item.children if isinstance(x, ParameterMapping)]
                )

        if not header:
            raise ValueError("Missing module header")
        if not moduletype_name:
            raise ValueError("Missing module type name")

        module = ModuleTypeInstance(
            header=header,
            moduletype_name=moduletype_name,
            parametermappings=param_mappings,
        )
        return module

    def variable_name(self, children):
        # NAME (DOT NAME)* ":"? (NEW | OLD)?
        parts: list[str] = []
        state: str | None = None

        for ch in children:
            if isinstance(ch, Token):
                if ch.type == const.KEY_NAME:
                    parts.append(ch.value)
                elif ch.type == const.KEY_DOT:
                    parts.append(".")
                elif ch.type in (const.GRAMMAR_VALUE_NEW, const.GRAMMAR_VALUE_OLD):
                    state = ch.type.lower()
            elif isinstance(ch, str):
                if ch.lower() in (const.GRAMMAR_VALUE_NEW, const.GRAMMAR_VALUE_OLD):
                    state = ch.lower()
                elif ch == ".":
                    parts.append(".")
                elif ch not in (":",):
                    parts.append(ch)

        # Join into a single dotted var_name; you can also preserve parts and state separately if needed
        var_name = "".join(parts)
        return {const.KEY_VAR_NAME: var_name, "state": state}

    def moduletype_definition(self, items) -> ModuleTypeDef:
        # NAME "=" MODULEDEFINITION sl_datecode scan_group? module_body ENDDEF_KW
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
                    moduleparameters.extend(
                        [x for x in it.children if isinstance(x, Variable)]
                    )
                elif it.data == const.GRAMMAR_VALUE_LOCALVARIABLES:
                    localvariables.extend(
                        [x for x in it.children if isinstance(x, Variable)]
                    )
                elif it.data == const.GRAMMAR_VALUE_SUBMODULES:
                    for ch in it.children:
                        if isinstance(ch, list):
                            submodules.extend(
                                [
                                    x
                                    for x in ch
                                    if isinstance(
                                        x,
                                        (SingleModule, FrameModule, ModuleTypeInstance),
                                    )
                                ]
                            )
                        elif isinstance(
                            ch, (SingleModule, FrameModule, ModuleTypeInstance)
                        ):
                            submodules.append(ch)

        if name is None:
            raise Exception("Name cannont be none")
         
        mtd = ModuleTypeDef(
            name=name,
            datecode=datecode,
            moduleparameters=moduleparameters,
            localvariables=localvariables,
            submodules=submodules,
            moduledef=moduledef,
            modulecode=modulecode,
        )
        if scan_group_info:
            mtd.groupconn = scan_group_info.get("groupconn")
            mtd.groupconn_global = bool(scan_group_info.get("global", False))
        return mtd

    def moduletype_definitions(self, items) -> Tree[Any]:
        out = []
        for it in items:
            if isinstance(it, ModuleTypeDef):
                out.append(it)
            elif isinstance(it, Tree) and it.data == "moduletype_definition":
                # Defensive in case Lark passes Trees; they will be transformed via moduletype_definition
                for ch in it.children:
                    if isinstance(ch, ModuleTypeDef):
                        out.append(ch)
        return Tree(const.TREE_TAG_MODULETYPE_LIST, out)

    def moduletype_par_transfer(self, items) -> ParameterMapping:
         # variable_name "=>" GLOBAL_KW? DURATION_VALUE? (value | variable_name)
        if not items:
            raise ValueError("moduletype_par_transfer received empty items")

        idx = 0

        # 1) Target (must be a variable_name dict or a string)
        target_raw = items[idx]
        idx += 1

        if target_raw is None:
            raise ValueError("moduletype_par_transfer missing target variable_name")

        if isinstance(target_raw, dict):
            target_val: dict | str = cast(dict, target_raw)
        elif isinstance(target_raw, str):
            target_val = target_raw
        else:
            # Fallback: stringify unexpected node types
            target_val = str(target_raw)

        # 2) Optional GLOBAL_KW
        is_global = False
        if idx < len(items) and isinstance(items[idx], bool):
            is_global = items[idx]
            idx += 1

        # 3) Optional DURATION_VALUE (your transformer returns None)
        is_duration = False
        if idx < len(items) and items[idx] is None:
            is_duration = True
            idx += 1

        # 4) Source: value (int/float/str/bool) or variable_name dict
        source_literal: Any | None = None
        source_var: dict | None = None
        source_type: str = const.KEY_VALUE  # default; overwritten below

        if idx < len(items):
            src = items[idx]
            if isinstance(src, (int, float, str, bool)):
                source_literal = src
                source_type = const.KEY_VALUE
            elif isinstance(src, dict):
                source_var = cast(dict, src)
                source_type = const.TREE_TAG_VARIABLE_NAME
            else:
                # Unexpected node -> treat as string ref
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

    def moduletype_par_list(self, items) -> Tree[ParameterMapping]:
        # Return a Tree tagged with moduletype parameter list
        return Tree(
            const.TREE_TAG_MODULETYPE_PAR_LIST,
            [x for x in items if isinstance(x, ParameterMapping)],
        )

    def invocation_tail(self, items) -> Tree[Any] | None:
        # ("(" moduletype_par_list ")")? ";"
        # Extract the parameter list if present
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_MODULETYPE_PAR_LIST:
                return it
        return None

    def scan_group(self, items):
        # "(" GROUPCONN "=" GLOBAL_KW? variable_name ")"
        # You can return a tuple or dict; model doesn’t store it, but this prevents confusion
        is_global = any(isinstance(it, bool) and it for it in items)
        var = None
        for it in items:
            if isinstance(it, dict) and const.KEY_VAR_NAME in it:
                var = it
        return {"groupconn": var, "global": is_global}

    # ---- Variables (AND PARAMETERS) ----
    def variable_item(self, items):
        name = items[0]  # already a str from NAME()
        desc = None
        if len(items) > 1 and isinstance(items[1], str):
            desc = items[1]
        return (name, desc)

    def opt_var_init(self, items):
        if not items:
            return None
        return items[-1]  # could be bool/int/float/str or DEFAULT_INIT

    def variable_group(self, items):
        # Remove Nones from punctuation we dropped
        items = [x for x in items if x is not None]

        # 1) Pull leading variable_item tuples
        var_items = []
        idx = 0
        while idx < len(items) and isinstance(items[idx], tuple):
            var_items.append(items[idx])
            idx += 1
        if not var_items:
            return []

        # 2) Optional GLOBAL flag
        global_flag = False
        if idx < len(items) and items[idx] is True:  # GLOBAL_KW returns True
            global_flag = True
            idx += 1

        # 3) Datatype (a NAME string)
        if idx >= len(items) or not isinstance(items[idx], str):
            # Defensive: datatype must be present
            raise ValueError("Expected datatype NAME in variable_group")
        else:
            datatype = self._unwrap_token(items[idx])
            idx += 1

        # 4) Modifiers (zero or more)
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

        # 5) Optional init (single value shared by all names in this group)
        init_value = None
        if idx < len(items):
            init_value = items[idx]  # primitive or DEFAULT_INIT

        # 6) Build Variables (each keeps its own description)
        variables = []
        for name, desc in var_items:
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
            )
            variables.append(v)
        return variables

    def variable_list(self, items):
        out = []
        for grp in items:
            if isinstance(grp, list):
                out.extend(grp)
        return Tree(const.TREE_TAG_VAR_LIST, out)

    def moduleparameters(self, items):
        parameters = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                parameters = it.children
        return Tree(const.GRAMMAR_VALUE_MODULEPARAMETERS, parameters)

    def localvariables(self, items):
        variables = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.TREE_TAG_VAR_LIST:
                variables = it.children
        return Tree(const.GRAMMAR_VALUE_LOCALVARIABLES, variables)

    # ---- MODULEDEF ----
    def origo_coord(self, items):
        return items

    def size(self, items):
        return items

    def coordinates(self, items):
        """
        Grammar: "(" REAL coord_tail* "," REAL coord_tail* ")"
        Extract only the two top-level REALs; ignore coord_tail Trees/dicts.
        """
        nums = [float(v) for v in items if isinstance(v, (int, float))]
        if len(nums) < 2:
            raise ValueError(f"coordinates missing REAL values (got {len(nums)})")
        return (nums[0], nums[1])
    
    def origo_size_pair(self, items):
        # coordinates coordinates
        coords = []
        for it in items:
            # Already-transformed coordinates -> plain (x, y) tuple
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(x, (int, float)) for x in it):
                coords.append((float(it[0]), float(it[1])))
            # Fallback: if for some reason coordinates wasn't transformed
            elif isinstance(it, Tree) and it.data == "coordinates":
                nums = [float(x) for x in it.children if isinstance(x, (int, float))]
                if len(nums) >= 2:
                    coords.append((nums[0], nums[1]))
        if len(coords) != 2:
            raise ValueError(f"origo_size_pair expected 2 coordinate pairs, found {len(coords)}")
        return (coords[0], coords[1])
    
    def invoke_coord(self, items):
        """
        Grammar: REAL coord_tail* ',' REAL coord_tail* ',' ... (5 times)
        Extract only the five top-level REALs; ignore coord_tail Trees/dicts.
        """
        nums = [float(v) for v in items if isinstance(v, (int, float))]
        if len(nums) < 5:
            raise ValueError(f"invoke_coord expected 5 REALs, found {len(nums)}")
        return tuple(nums[:5])  # (x, y, z1, z2, z3)

    def coord_invar_tail(self, items):
        # ":" (INVAR_PREFIX | OUTVAR_PREFIX) connected_variable
        # Extract and return the connected_variable value directly
        for it in items:
            if not isinstance(it, Token):
                return it  # Return the connected_variable string or dict
        raise ValueError("coord_invar_tail expected connected variable or value")

    def coord_clippingbounds(self, items):
        # (CLIPPINGBOUNDS | "ClippingBounds") "=" clip_values
        # Preserve as a Tree to avoid flattening clip_value REALs into parent nodes.
        return Tree(const.GRAMMAR_VALUE_CLIPPINGBOUNDS, items)

    def clippingbounds(self, items):
        # return the tuple-of-tuples directly
        return items[-1]  # ( (x1,y1), (x2,y2) )

    def seq_layers(self, items) -> dict[str, Any]:
        return {const.KEY_SEQ_LAYERS: items[-1]}

    def zoomlimits(self, items) -> dict[str, tuple[Any, Any]]:
        return {const.GRAMMAR_VALUE_ZOOMLIMITS: (items[-2], items[-1])}

    def ZOOMABLE(self, _) -> dict[str, bool]:
        return {const.GRAMMAR_VALUE_ZOOMABLE: True}

    def grid(self, items) -> float:
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

    def moduledef_opts_seq(self, items) -> Tree[dict[str, Any]]:
        # items is a list of 0..4 dicts; merge them
        merged: dict[str, Any] = {}
        for d in items:
            merged.update(d)
        # Return a Tree with a custom tag
        return Tree(const.TREE_TAG_MODULEDEF_OPTS_SEQ, [merged])

    def moduledef(self, items) -> ModuleDef:
        m = ModuleDef()
        for it in items:
            # clippingbounds now returns a tuple-of-tuples
            if (
                isinstance(it, tuple)
                and len(it) == 2
                and all(isinstance(t, tuple) for t in it)
            ):
                m.clipping_bounds = it
            elif isinstance(it, list) and it and isinstance(it[0], GraphObject):
                m.graph_objects = it
            elif isinstance(it, list) and it and isinstance(it[0], InteractObject):
                m.interact_objects = it
            elif isinstance(it, dict):
                if const.GRAMMAR_VALUE_ZOOMLIMITS in it:
                    m.zoom_limits = it[const.GRAMMAR_VALUE_ZOOMLIMITS]
                if const.GRAMMAR_VALUE_ZOOMABLE in it:
                    m.zoomable = it[const.GRAMMAR_VALUE_ZOOMABLE]
                if (
                    const.GRAMMAR_VALUE_GRID in it
                    and it[const.GRAMMAR_VALUE_GRID] is not None
                ):
                    m.grid = float(it[const.GRAMMAR_VALUE_GRID])
                if const.KEY_SEQ_LAYERS in it:
                    m.seq_layers = it[const.KEY_SEQ_LAYERS]
        return m

    def _collect_invar_enable_tails(self, nodes: list[Any]) -> list[Any]:
        """
        Find InVar_ trees and enable-expression tails anywhere in a nested structure.
        Returns a flat list of tail nodes to be stored on GraphObject/InteractObject.
        """
        tails: list[Any] = []

        def visit(x: Any):
            if x is None:
                return
            # enable() returns a dict with TREE_TAG_ENABLE + KEY_TAIL
            if isinstance(x, dict):
                if const.TREE_TAG_ENABLE in x and const.KEY_TAIL in x and x[const.KEY_TAIL] is not None:
                    tails.append(x[const.KEY_TAIL])
                # Also descend into any dict values to be safe
                for v in x.values():
                    visit(v)
                return
            # Trees: InVar_ tails and enable_expression trees are directly useful
            if _is_tree(x):
                data = getattr(x, "data", None)
                if data in (const.GRAMMAR_VALUE_INVAR_PREFIX, const.KEY_ENABLE_EXPRESSION, "invar_tail"):
                    tails.append(x)
                # Recurse into children
                for ch in getattr(x, "children", []):
                    visit(ch)
                return
            # Lists
            if isinstance(x, list):
                for y in x:
                    visit(y)
                return
            # Primitive -> ignore

        for n in nodes:
            visit(n)
        return tails

    def text_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_TEXTOBJECT)

        # Coordinates ((x,y),(w,h))
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break

        # Collect tails (Enable_/InVar_ etc.) across the object
        tails = self._collect_invar_enable_tails(items)  # robust recursive collector
        if tails:
            go.properties[const.KEY_TAILS] = tails

        # Pair each VARNAME with the nearest preceding top-level text (STRING or text_content)
        text_vars: list[str] = []

        def _extract_text_from_node(node) -> str:
            if isinstance(node, str):
                return node
            # Defensive: if the grammar still wraps it sometimes
            if hasattr(node, "data") and getattr(node, "data", None) == "text_content":
                for ch in getattr(node, "children", []):
                    if isinstance(ch, str):
                        return ch
            raise ValueError(
                f"_extract_text_from_node expected a str or a 'text_content' node; got {type(node).__name__}"
            )

        for i, it in enumerate(items):
            if isinstance(it, Token) and it.type == "VARNAME":
                # Walk backwards to find the nearest preceding text node
                j = i - 1
                while j >= 0:
                    prev = items[j]
                    s = _extract_text_from_node(prev)
                    if s:
                        text_vars.append(s)
                        break
                    j -= 1

        if text_vars:
            go.properties["text_vars"] = text_vars
        return go

    def text_content(self, items) -> str:
        # Unwrap the TEXT content so TextObject sees a plain str
        for it in items:
            if isinstance(it, str):
                return it
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(f"text_content expected a str; got: {types}")

    def rectangle_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_RECTANGLEOBJECT)
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._collect_invar_enable_tails(items)
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def line_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_LINEOBJECT)
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._collect_invar_enable_tails(items)
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def oval_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_OVALOBJECT)
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._collect_invar_enable_tails(items)
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def polygon_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_POLYGONOBJECT)
        # First coordinates are polygon vertices; not strictly needed for usage
        tails = self._collect_invar_enable_tails(items)
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def segment_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_SEGMENTOBJECT)
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._collect_invar_enable_tails(items)
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def composite_object(self, items) -> GraphObject:
        go = GraphObject(const.GRAMMAR_VALUE_COMPOSITEOBJECT)
        tails = self._collect_invar_enable_tails(items)
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def graph_object(self, items) -> GraphObject:
        obj = None
        layer = None
        for it in items:
            if isinstance(it, GraphObject) and obj is None:
                obj = it
            elif isinstance(it, int):
                layer = it

        if obj is None:
            types = ", ".join(type(x).__name__ for x in items)
            raise ValueError(f"graph_object expected a GraphObject in items; got: {types}")

        if layer is not None:
            obj.properties["layer"] = layer

        return obj

    def graph_objects(self, items) -> list[GraphObject]:
        return [it for it in items if isinstance(it, GraphObject)]

    def submodules(self, items) -> Tree[list[SingleModule | FrameModule | ModuleTypeInstance]]:
        submods = []
        for it in items:
            if isinstance(it, (SingleModule, FrameModule, ModuleTypeInstance)):
                submods.append(it)
            elif isinstance(it, Tree):
                for ch in it.children:
                    if isinstance(ch, (SingleModule, FrameModule, ModuleTypeInstance)):
                        submods.append(ch)
        return Tree(const.GRAMMAR_VALUE_SUBMODULES, [submods])

    # ---- ModuleCode ----
    def modulecode(self, items) -> ModuleCode:
        # Extract name from MODULECODE token (adjust based on your grammar)
        equations = []
        sequences = []

        for item in items:
            if isinstance(item, Equation):
                equations.append(item)
            elif isinstance(item, Sequence):
                sequences.append(item)

        return ModuleCode(equations=equations, sequences=sequences)

    def entercode(self, items) -> dict[str, list[Any]]:
        # ENTERCODE statement* [2]
        stmts = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_STATEMENT:
                stmts.extend(it.children)
        return {"enter": stmts}

    def activecode(self, items) -> dict[str, list[Any]]:
        # ACTIVECODE statement* [2]
        stmts = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_STATEMENT:
                stmts.extend(it.children)
        return {"active": stmts}

    def exitcode(self, items) -> dict[str, list[Any]]:
        # EXITCODE statement* [2]
        stmts = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_STATEMENT:
                stmts.extend(it.children)
        return {"exit": stmts}

    def code_blocks(self, items) -> SFCCodeBlocks:
        # entercode? activecode? exitcode? [2]
        blocks = {"enter": [], "active": [], "exit": []}
        for it in items:
            if isinstance(it, dict):
                for k in ("enter", "active", "exit"):
                    if k in it and it[k]:
                        blocks[k].extend(it[k])
        return SFCCodeBlocks(
            enter=blocks["enter"],
            active=blocks["active"],
            exit=blocks["exit"],
        )

    def seqinitstep(self, items) -> SFCStep:
        # SEQINITSTEP NAME code_blocks [2]
        name = None
        blocks = SFCCodeBlocks()
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, SFCCodeBlocks):
                blocks = it
        return SFCStep(kind="init", name=name or "", code=blocks)

    def seqstep(self, items) -> SFCStep:
        # SEQSTEP NAME code_blocks [2]
        name = None
        blocks = SFCCodeBlocks()
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, SFCCodeBlocks):
                blocks = it
        return SFCStep(kind="step", name=name or "", code=blocks)

    def seqtransition(self, items) -> SFCTransition:
        # SEQTRANSITION NAME? WAIT_FOR expression [2]
        name = None
        condition = None
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif not isinstance(it, Token):
                # The expression child
                condition = it
        return SFCTransition(name=name, condition=condition)

    def seqtransitionsub(self, items) -> SFCTransitionSub:
        # SUBSEQTRANSITION NAME sequence_body ENDSUBSEQTRANSITION [2]
        name = None
        body_nodes = []
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, Tree) and it.data == const.KEY_SEQUENCE_BODY:
                body_nodes = it.children
        return SFCTransitionSub(name=name or "", body=body_nodes)

    def seqsub(self, items) -> SFCSubsequence:
        # SUBSEQUENCE NAME sequence_body ENDSUBSEQUENCE [2]
        name = None
        body_nodes = []
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, Tree) and it.data == const.KEY_SEQUENCE_BODY:
                body_nodes = it.children
        return SFCSubsequence(name=name or "", body=body_nodes)

    def seqalternative(self, items) -> SFCAlternative:
        # ALTERNATIVESEQ sequence_body (ALTERNATIVEBRANCH sequence_body)+ ENDALTERNATIVE [2]
        branches = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_SEQUENCE_BODY:
                branches.append(it.children)
        return SFCAlternative(branches=branches)

    def seqparallel(self, items) -> SFCParallel:
        # PARALLELSEQ sequence_body (PARALLELBRANCH sequence_body)+ ENDPARALLEL [2]
        branches = []
        for it in items:
            if isinstance(it, Tree) and it.data == const.KEY_SEQUENCE_BODY:
                branches.append(it.children)
        return SFCParallel(branches=branches)

    def seqfork(self, items) -> SFCFork:
        # SEQFORK NAME [2]
        target = None
        for it in items:
            if isinstance(it, str) and target is None:
                target = it
        return SFCFork(target=target or "")

    def seqbreak(self, _items) -> SFCBreak:
        # SEQBREAK [2]
        return SFCBreak()

    def seq_element(self, items) -> Any:
        # passthrough whichever SFC node was produced
        for it in items:
            return it

    def sequence_body(self, items):
        # keep your existing tag, but children are now typed SFC nodes [1]
        return Tree(const.KEY_SEQUENCE_BODY, items)

    def sequence(self, items) -> Sequence:
        name: str | None = None
        position: tuple[float, float] | None = None
        size: tuple[float, float] | None = None  
        seqcontrol = False
        seqtimer = False
        code = []
        seqtype = const.GRAMMAR_VALUE_SEQUENCE  # default

        for item in items:
            if isinstance(item, Token):
                if item.type == const.GRAMMAR_VALUE_SEQUENCE:
                    seqtype = const.GRAMMAR_VALUE_SEQUENCE
                elif item.type == const.GRAMMAR_VALUE_OPENSEQUENCE:
                    seqtype = const.GRAMMAR_VALUE_OPENSEQUENCE
            elif isinstance(item, str) and name is None:
                name = item
            elif (
                isinstance(item, tuple)
                and len(item) == 2
                and all(isinstance(x, (int, float)) for x in item)
            ):
                # First 2-tuple is position, second 2-tuple (if present) is size [2]
                if position is None:
                    position = (float(item[0]), float(item[1]))
                elif size is None:
                    size = (float(item[0]), float(item[1]))
            elif isinstance(item, Tree) and item.data == const.KEY_SEQ_CONTROL_OPS:
                for child in item.children:
                    if isinstance(child, Token):
                        if child.type == const.GRAMMAR_VALUE_SEQCONTROL:
                            seqcontrol = True
                        elif child.type == const.GRAMMAR_VALUE_SEQTIMER:
                            seqtimer = True
            elif isinstance(item, Tree) and item.data == const.KEY_SEQUENCE_BODY:
                # children are already typed SFC nodes
                code.extend(item.children)

        if name is None:
            raise ValueError("Name can't be None")

        if position is None:
            raise ValueError("Position can't be None")
        
        if size is None:
            raise ValueError("Size can't be None")

        return Sequence(
            name=name or "",
            type=seqtype,
            position=position,
            size=size,
            seqcontrol=seqcontrol,
            seqtimer=seqtimer,
            code=code,
        )

    def equationblock(self, items) -> Equation:
        name: str | None = None
        position: tuple[float, float] | None = None
        size: tuple[float, float] | None = None
        code = []
        for item in items:
            if isinstance(item, str) and not isinstance(item, Token) and name is None:
                name = item
            elif (
                isinstance(item, tuple)
                and len(item) == 2
                and all(isinstance(x, (int, float)) for x in item)
                and position is None
            ):
                position = (float(item[0]), float(item[1]))  # from codeblock_coord
            elif (
                isinstance(item, tuple)
                and len(item) == 2
                and all(isinstance(x, (int, float)) for x in item)
                and size is None
            ):
                size = (float(item[0]), float(item[1]))
            elif isinstance(item, Tree) and item.data == const.KEY_STATEMENT:
                code.extend(item.children)

        if name is None:
            raise ValueError("Name can't be None")

        if position is None:
            raise ValueError("Position can't be None")
        
        if size is None:
            raise ValueError("Size can't be None")
        
        return Equation(name=name, position=position, size=size, code=code)

    def interact_objects(self, items):
        out = []
        for it in items:
            if isinstance(it, InteractObject):
                out.append(it)
            elif isinstance(it, Tree) and it.children:
                for child in it.children:  # don't shadow module 'c'
                    if isinstance(child, InteractObject):
                        out.append(child)
        return out

    def combutproc_item(self, items) -> InteractObject:
        props = {}
        coords = []
        proc = None
        tails = []
        for it in items:
            if isinstance(it, tuple):
                coords.append(it)
            elif isinstance(it, dict) and const.KEY_PROCEDURE_CALL in it:
                proc = it[const.KEY_PROCEDURE_CALL]
            elif isinstance(it, dict):
                tails.append(it)
            elif isinstance(it, list):
                # defensive
                for sub in it:
                    if isinstance(sub, dict) and const.KEY_PROCEDURE_CALL in sub:
                        proc = sub[const.KEY_PROCEDURE_CALL]
        props[const.KEY_COORDS] = coords or None
        if proc:
            props[const.KEY_PROCEDURE] = proc
        if tails:
            props[const.KEY_TAILS] = tails
        return InteractObject(type=const.GRAMMAR_VALUE_COMBUTPROC, properties=props)

    def procedure_call(self, items):
        name = None
        args = []
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_NAME and name is None:
                name = it.value
            else:
                args.append(it)
        return {const.KEY_PROCEDURE_CALL: {const.KEY_NAME: name, const.KEY_ARGS: args}}

    def invar(self, items):
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"invar expected a connected_variable child; got: {items}")

    def enable(self, items):
        # ENABLE_PREFIX "=" BOOL (invar | enable_expression)
        val = None
        tail = None
        for it in items:
            if isinstance(it, bool):
                val = it
            elif not isinstance(it, Token):
                # This is either invar result (string/dict) or enable_expression result (tuple)
                tail = it
        return {
            const.TREE_TAG_ENABLE: bool(val) if val is not None else True,
            const.KEY_TAIL: tail,
        }

    def enable_expression(self, items):
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"enable_expression expected an expression child; got: {items}")

    def interact_simple_item(self, items) -> InteractObject:
        itype = None
        coords = []
        body = []
        for it in items:
            if isinstance(it, Token) and itype is None:
                # COMBUT, OPTBUT, PROCEDUREINTERACT, CHECKBOX, TEXTBOX, MENUINTERACT, SIMPLEINTERACT are terminals
                # Use token.value directly so type matches the literal [4]
                itype = it.value
            elif isinstance(it, tuple):
                coords.append(it)
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_INTERACT_BODY_SEQ:
                for child in it.children:
                    body.append(child)
            elif isinstance(it, list):
                for child in it:
                    body.append(child)
        props = {const.KEY_COORDS: coords or None, const.KEY_BODY: body or None}
        return InteractObject(type=itype or const.KEY_INTERACT, properties=props)

    def interact_assign_variable(self, items):
        name = None
        val = None
        tail = None
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_NAME and name is None:
                name = it.value
            elif isinstance(it, Tree) and it.data == const.KEY_ENABLE_EXPRESSION:
                tail = it
            elif not isinstance(it, Token):
                # the 'value' subtree or other processed value
                val = it
        return {
            const.KEY_ASSIGN: {
                const.KEY_NAME: name,
                const.KEY_VALUE: val,
                const.KEY_TAIL: tail,
            }
        }

    def interact_flag(self, items) -> dict:
        name = None
        extra = None
        tail = None
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_NAME and name is None:
                name = it.value
            elif isinstance(it, Token) and it.type in (const.KEY_STRING, const.KEY_SIGNED_INT):
                extra = it.value
            elif not isinstance(it, Token):
                # tail is now already unwrapped (string or dict)
                tail = it
        return {const.KEY_NAME: name, const.KEY_EXTRA: extra, const.KEY_TAIL: tail}

    def interact_value_line(self, items):
        return [it for it in items]

    def or_expression(self, items):
        exprs = [it for it in items if not isinstance(it, Token)]
        if len(exprs) == 1:
            return exprs[0]
        return (const.GRAMMAR_VALUE_OR, exprs)

    def and_expression(self, items):
        exprs = [it for it in items if not isinstance(it, Token)]
        if len(exprs) == 1:
            return exprs[0]
        return (const.GRAMMAR_VALUE_AND, exprs)

    def not_expression(self, items):
        # Handles: NOT not_expression | comparison_expression
        if not items:
            return None
        # Single child: it's already a comparison_expression result; just passthrough
        if len(items) == 1:
            return items[0]
        # Two children: first is the NOT token, second is the operand
        # Be defensive if something odd shows up
        op, expr = items[0], items[1] if len(items) >= 2 else None
        return (const.GRAMMAR_VALUE_NOT, expr)

    def layer_info(self, items) -> int:
        # LAYER_PREFIX "=" SIGNED_INT
        for it in items:
            if isinstance(it, int):
                return it
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(f"text_content expected a str; got: {types}")


    def seq_control_opt(self, items) -> Tree[Token]:
        # "(" SEQCONTROL? ","? SEQTIMER? ")"
        return Tree(
            const.KEY_SEQ_CONTROL_OPS, [tok for tok in items if isinstance(tok, Token)]
        )

    def codeblock_coord(self, items) -> tuple[float, float]:
        nums = [float(v) for v in items if not isinstance(v, Token)]
        return (nums[0], nums[1])
    
    def objsizedef(self, items) -> tuple[float, float]:
        nums = [float(v) for v in items if not isinstance(v, Token)]
        return (nums[0], nums[1])

    def two_layers(self, items) -> dict[str, float]:
        # TWO_LAYERS LAYERLIMIT "=" REAL
        val: float | None = None
        for it in items:
            if isinstance(it, (int, float)):
                val = float(it)
            elif isinstance(it, Token):
                try:
                    val = float(it.value)
                except (TypeError, ValueError):
                    pass

        if val is None:
            types = ", ".join(
                f"{type(x).__name__}" + (f"[{getattr(x, 'type', '')}]" if isinstance(x, Token) else "")
                for x in items
            )
            raise ValueError(f"two_layers expected a numeric REAL value; got: {types}")

        return {const.KEY_SEQ_LAYERS: val}

    def compare(self, items):
        # items like: left, op, right, op, right ...
        left = items[0]
        pairs = []
        i = 1
        while i < len(items):
            op = items[i]
            right = items[i + 1]
            if isinstance(op, Token):
                # Use symbol: "<", ">", "==", "<=", ">=", "<>"
                pairs.append((op.value, right))
            else:
                pairs.append((str(op), right))
            i += 2
        if not pairs:
            return left
        return (const.KEY_COMPARE, left, pairs)

    def additive_expression(self, items):
        # items like: term, (+/-), term, (+/-), term ...
        if len(items) == 1:
            return items[0]
        left = items[0]
        ops = []
        i = 1
        while i < len(items):
            op = items[i]
            right = items[i + 1]
            if isinstance(op, Token):
                ops.append((op.value, right))
            else:
                ops.append((str(op), right))
            i += 2
        return (const.KEY_ADD, left, ops)

    def multiplicative_expression(self, items):
        # items like: term, (* or /), term, ...
        if len(items) == 1:
            return items[0]
        left = items[0]
        ops = []
        i = 1
        while i < len(items):
            op = items[i]
            right = items[i + 1]
            if isinstance(op, Token):
                ops.append((op.value, right))
            else:
                ops.append((str(op), right))
            i += 2
        return (const.KEY_MUL, left, ops)

    def unary_expression(self, items):
        # PLUS unary_expression | MINUS unary_expression | term
        if len(items) == 1:
            return items[0]
        op, expr = items
        if isinstance(op, Token):
            if op.type == const.KEY_PLUS:
                return (const.KEY_PLUS, expr)
            if op.type == const.KEY_MINUS:
                return (const.KEY_MINUS, expr)
            return (op.value, expr)
        return (str(op), expr)

    def function_call(self, items):
        # NAME LPAREN argument_list RPAREN
        fn_name = None
        args = []
        for it in items:
            if isinstance(it, str) and not isinstance(it, list) and fn_name is None:
                fn_name = it
            elif not isinstance(it, Token):
                # this is argument_list result
                args = it
        return (const.KEY_FUNCTION_CALL, fn_name, args)

    def argument_list(self, items):
        # expression (COMMA expression)*
        return [it for it in items if not isinstance(it, Token)]

    def ternary_if(self, items):
        # IF cond THEN expr (ELSIF cond THEN expr)* ELSE expr ENDIF
        branches = []
        else_expr = None
        i = 0
        # Expect IF
        while i < len(items):
            tok = items[i]
            if isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_IF:
                cond = items[i + 1]
                # skip THEN at i+2
                then_expr = items[i + 3]
                branches.append((cond, then_expr))
                i += 4
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSIF:
                cond = items[i + 1]
                then_expr = items[i + 3]  # skip THEN
                branches.append((cond, then_expr))
                i += 4
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSE:
                else_expr = items[i + 1]
                i += 2
            else:
                i += 1
        return (const.KEY_TERNARY, branches, else_expr)

    def assignment_statement(self, items):
        # variable_name "=" expression
        if len(items) != 2:
            # Be defensive in case of stray tokens
            target = items[0]
            expr = items[-1]
        else:
            target, expr = items
        return (const.KEY_ASSIGN, target, expr)

    def if_statement(self, items):
        # IF expression THEN statement* (ELSIF expression THEN statement*)* (ELSE statement*)? ENDIF
        branches = []
        else_block = None
        i = 0
        while i < len(items):
            tok = items[i]
            if isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_IF:
                cond = items[i + 1]
                i += 2  # now at THEN
                # skip THEN
                i += 1
                stmts = []
                while i < len(items):
                    t = items[i]
                    if isinstance(t, Token) and t.type in (
                        const.GRAMMAR_VALUE_ELSIF,
                        const.GRAMMAR_VALUE_ELSE,
                        const.GRAMMAR_VALUE_ENDIF,
                    ):
                        break
                    stmts.append(t)
                    i += 1
                branches.append((cond, stmts))
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSIF:
                cond = items[i + 1]
                i += 2  # now at THEN
                i += 1  # skip THEN
                stmts = []
                while i < len(items):
                    t = items[i]
                    if isinstance(t, Token) and t.type in (
                        const.GRAMMAR_VALUE_ELSIF,
                        const.GRAMMAR_VALUE_ELSE,
                        const.GRAMMAR_VALUE_ENDIF,
                    ):
                        break
                    stmts.append(t)
                    i += 1
                branches.append((cond, stmts))
            elif isinstance(tok, Token) and tok.type == const.GRAMMAR_VALUE_ELSE:
                i += 1
                else_block = []
                while i < len(items):
                    t = items[i]
                    if isinstance(t, Token) and t.type == const.GRAMMAR_VALUE_ENDIF:
                        break
                    else_block.append(t)
                    i += 1
                # ENDIF will be handled by loop increment
                i += 1
            else:
                i += 1
        return (const.GRAMMAR_VALUE_IF, branches, else_block)

    def statement(self, items) -> Tree:
        # assignment_statement ";" | function_call ";" | if_statement ";"
        for it in items:
            if not isinstance(it, Token):
                return Tree(const.KEY_STATEMENT, [it])  # Keep the Tree wrapper
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(
            f"statement expected a non-Token child "
            f"(assignment_statement | function_call | if_statement); got only tokens: {types}"
        )

    # ---------- helpers ----------
    def _unwrap_token(self, tok):
        if isinstance(tok, Token):
            return str(tok)
        return tok

    # ---- Convert basic terminals to Python values ----
    def value(self, items) -> Any:
        # items is a list of one child: BOOL | REAL | STRING | SIGNED_INT
        if not items:
            raise ValueError("value expected one item (BOOL|REAL|STRING|SIGNED_INT); got empty list")
        if len(items) != 1:
            raise ValueError(f"value expected exactly one item; got {len(items)}: {items!r}")
        v = items[0]
        if v is None:
            raise ValueError("value item is None")
        return v
    
    def connected_variable(self, items):
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"connected_variable expected a non-Token child; got: {items}")
    
    def invar_tail(self, items):
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"invar_tail expected a non-Token child; got: {items}")

    def NAME(self, tok: Token) -> str:
        return str(tok)

    def STRING(self, tok: Token) -> str:
        return _strip_quoted(str(tok))

    def STRING_CRLF(self, tok: Token) -> str:
        # Treat like STRING but drop the trailing newline
        return _strip_quoted(str(tok))

    def SIGNED_INT(self, tok: Token) -> int:
        return int(str(tok))

    def REAL(self, tok: Token) -> float:
        return float(str(tok))

    def BOOL(self, tok: Token) -> bool:
        s = str(tok)
        return True if s == "True" else False

    # Keywords we care about as flags
    def GLOBAL_KW(self, _) -> Literal[True]:  # "GLOBAL"
        return True

    def CONST_KW(self, _) -> Literal['Const']:  # const.GRAMMAR_VALUE_CONST_KW
        return const.GRAMMAR_VALUE_CONST_KW

    def STATE_KW(self, _) -> Literal['State']:  # const.GRAMMAR_VALUE_STATE_KW
        return const.GRAMMAR_VALUE_STATE_KW

    # We’ll ignore these (no fields in your model). Keep them if you add fields later.
    def OPSAVE_KW(self, _) -> Literal['OpSave']:
        return const.GRAMMAR_VALUE_OPSAVE_KW

    def SECURE_KW(self, _) -> Literal['Secure']:
        return const.GRAMMAR_VALUE_SECURE_KW

    # DEFAULT in init
    def DEFAULT(self, _) -> object:
        return DEFAULT_INIT

    # Punctuation tokens we don’t need as data (returning None is fine; we’ll filter Nones)
    def COLON(self, _) -> None:
        return None

    def COMMA(self, _) -> None:
        return None

    def SEMI(self, _) -> None:
        return None

    # And the := and optional Duration_Value inside opt_var_init
    def ASSIGN_INIT_VALUE(self, _) -> None:
        return None  # ":="

    def DURATION_VALUE(self, _) -> None:
        return None  # "Duration_Value"

    def sl_datecode(self, items) -> int:
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_SL_DATECODE:
                try:
                    return int(it.value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid {const.KEY_SL_DATECODE} value: {it.value!r}") from exc
            if isinstance(it, int):
                return it

        # Nothing matched -> fail loudly
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(
            f"sl_datecode expected a Token(type={const.KEY_SL_DATECODE}) or int; got: {types}"
        )
