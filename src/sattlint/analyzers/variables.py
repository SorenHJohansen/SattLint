"""Variable usage analysis and reporting utilities."""
from __future__ import annotations
from dataclasses import dataclass, field
import difflib
import re
from typing import Any, TypeAlias, Union, cast
from enum import Enum
from pathlib import Path
from .sattline_builtins import get_function_signature
from ..grammar import constants as const
import logging
from ..resolution.scope import ScopeContext
from ..reporting.variables_report import IssueKind, VariableIssue, VariablesReport
from ..resolution import (
    AccessEvent,
    AccessGraph,
    AccessKind,
    CanonicalPath,
    CanonicalSymbolTable,
    SymbolKind,
    TypeGraph,
    decorate_segment,
)
from ..models.ast_model import (
    BasePicture,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    ModuleTypeDef,
    ModuleCode,
    Sequence,
    ModuleDef,
    Variable,
    SFCStep,
    SFCTransition,
    SFCAlternative,
    SFCParallel,
    SFCSubsequence,
    SFCTransitionSub,
    SFCFork,
    SFCBreak,
    ParameterMapping,
    Simple_DataType,
)
from ..models.usage import VariableUsage
from ..resolution.common import (
    ResolvedModulePath,
    path_startswith_casefold,
    format_moduletype_label,
    dedupe_moduletype_defs,
    resolve_moduletype_def_strict,
    resolve_module_by_strict_path,
    find_module_by_name,
    get_module_path,
    is_external_to_module,
    find_var_in_scope,
    varname_base,
    varname_full,
    find_all_aliases,
    find_all_aliases_upstream,
)
from .framework import Issue, format_report_header
from .validators import MinMaxValidator, StringMappingValidator
from .usage_tracker import UsageTracker
from .context_builder import ContextBuilder

log = logging.getLogger("SattLint")

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def analyze_variables(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> VariablesReport:
    """
    Analyze a BasePicture AST and return a comprehensive report:
      - UNUSED variables
      - READ_ONLY_NON_CONST variables

    Variable.read / Variable.written are populated during traversal [3], and
    Variable itself remains the core AST (no report concerns baked in) [1].
    """
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=unavailable_libraries,
    )
    issues = analyzer.run()
    return VariablesReport(basepicture_name=base_picture.header.name, issues=issues)


def filter_variable_report(
    report: VariablesReport,
    kinds: set[IssueKind],
) -> VariablesReport:
    if not kinds:
        return report

    filtered = [i for i in report.issues if i.kind in kinds]

    return VariablesReport(
        basepicture_name=report.basepicture_name,
        issues=filtered,
    )





class VariablesAnalyzer:
    """
    Walks the AST and marks VariableUsage.read / VariableUsage.written.
    Propagates usage through ParameterMappings into child modules.
    GLOBAL mapping resolves by walking up the scope chain and only counts
    as used when the mapped parameter is read/written in the child.
    External ModuleTypeInstance mappings are considered used.
    """

    _OPAQUE_BUILTIN_TYPES: set[str] = {
        "alarm4realspar",
        "arrayobject",
        "eventqueueitem",
        "eventsortrectype",
        "multrealspar",
        "randomgenerator",
        "relaypidtunerpar",
        "sortedeventtype",
    }

    def __init__(
        self,
        base_picture: BasePicture,
        debug: bool = False,
        fail_loudly: bool = True,
        unavailable_libraries: set[str] | None = None,
    ):
        self.bp = base_picture
        self.debug = debug
        self.fail_loudly = fail_loudly
        self._unavailable_libraries = unavailable_libraries or set()
        self._analysis_warnings: list[str] = []

        # Unified collection of issues
        self._issues: list[VariableIssue] = []

        # Decoupled usage tracking
        self.usage_tracker = UsageTracker()

        # Traversal context for better error messages (equation/sequence/step/etc.)
        self._site_stack: list[str] = []

        # Resolution layers
        self.type_graph = TypeGraph.from_basepicture(self.bp)
        self.symbol_table = CanonicalSymbolTable()
        # self.access_graph is now managed by UsageTracker

        self.context_builder = ContextBuilder(
            base_picture=self.bp,
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            issues=self._issues,
            global_lookup_fn=self._lookup_global_variable
        )

        self.typedef_index = {
            mt.name.lower(): [] for mt in (self.bp.moduletype_defs or [])
        }
        for mt in self.bp.moduletype_defs or []:
            self.typedef_index.setdefault(mt.name.lower(), []).append(mt)
        self.used_params_by_typedef: dict[str, set[str]] = {}
        self.param_reads_by_typedef: dict[str, set[str]] = {}
        self.param_writes_by_typedef: dict[str, set[str]] = {}
        self._alias_links: list[
            tuple[Variable, Variable, str]
        ] = []  # (parent_var, child_param_var, field_path_in_parent)

        # Index BasePicture/global variables (localvariables)
        self._root_env: dict[str, Variable] = {
            v.name.lower(): v for v in (self.bp.localvariables or [])
        }

        # Fallback index across the whole AST (by name) to be robust
        self._any_var_index: dict[str, list[Variable]] = {}
        self._index_all_variables()
        self._analyzing_typedefs: set[str] = set()

        # Load dedicated validators
        self._min_max_validator = MinMaxValidator()
        self._string_validator = StringMappingValidator()

    def _get_usage(self, variable: Variable) -> VariableUsage:
        return self.usage_tracker.get_usage(variable)

    @property
    def access_graph(self) -> AccessGraph:
        return self.usage_tracker.access_graph


    @property
    def analysis_warnings(self) -> list[str]:
        return self._analysis_warnings

    def _warn(self, message: str) -> None:
        self._analysis_warnings.append(message)
        log.warning(message)

    @property
    def issues(self) -> list[VariableIssue]:
        return self._issues


    def _check_param_mappings_for_single(
        self,
        mod: SingleModule,
        child_env: dict[str, Variable],
        parent_env: dict[str, Variable],
        parent_path: list[str],
    ) -> None:
        params_by_name = {v.name.casefold(): v for v in (mod.moduleparameters or [])}

        for pm in mod.parametermappings or []:
            tgt_name = varname_base(pm.target)
            tgt_var = params_by_name.get(tgt_name) if tgt_name else None
            self._check_param_mapping(pm, tgt_var, parent_env, parent_path)

    def _check_param_mappings_for_type_instance(
        self,
        inst,  # ModuleTypeInstance
        parent_env: dict[str, Variable],
        parent_path: list[str],
        current_library: str | None = None,
    ) -> None:
        try:
            mt = resolve_moduletype_def_strict(
                self.bp,
                inst.moduletype_name,
                current_library=current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            return
        # Only parameters are valid mapping targets [2]
        params_by_name = {v.name.casefold(): v for v in (mt.moduleparameters or [])}
        for pm in inst.parametermappings or []:
            tgt_name = varname_base(pm.target)
            tgt_var = params_by_name.get(tgt_name) if tgt_name else None
            self._check_param_mapping(pm, tgt_var, parent_env, parent_path)

    def _check_param_mapping(
        self,
        pm: ParameterMapping,
        tgt_var: Variable | None,
        parent_env: dict[str, Variable],
        path: list[str],
    ) -> None:
        # If we cannot resolve target variable, we cannot validate types
        if tgt_var is None:
            return

        # 1) GLOBAL: no source variable to compare
        if pm.is_source_global:
            return

        # 2) Variable-to-variable mapping: enforce identical string type [2][4]
        src_var = self._lookup_env_var_from_varname_dict(pm.source, parent_env)
        if src_var is None:
            # Try resolving from root/global scope if not in parent env
            src_var = self._lookup_global_variable(varname_base(pm.source))

        if src_var is None:
            return  # cannot validate

        # Delegate validation to dedicated validators
        self._issues.extend(
            self._string_validator.check_string_mapping(tgt_var, src_var, path)
        )
        self._issues.extend(
            self._min_max_validator.check_min_max_mapping(
                pm, tgt_var, src_var, path
            )
        )

    def _index_all_variables(self) -> None:
        def _add(v: Variable):
            self._any_var_index.setdefault(v.name.lower(), []).append(v)

        # BasePicture locals
        for v in self.bp.localvariables or []:
            _add(v)

        # Descendants
        def _walk(mods):
            for m in mods or []:
                if isinstance(m, SingleModule):
                    for v in m.moduleparameters or []:
                        _add(v)
                    for v in m.localvariables or []:
                        _add(v)
                    _walk(m.submodules or [])
                elif isinstance(m, FrameModule):
                    _walk(m.submodules or [])
                # ModuleTypeInstance declares no variables

        _walk(self.bp.submodules or [])

        # TypeDefs declared in this file
        for mt in self.bp.moduletype_defs or []:
            for v in mt.moduleparameters or []:
                _add(v)
            for v in mt.localvariables or []:
                _add(v)

    def _is_const_candidate(self, v: Variable) -> bool:
        # Built-ins are normalized to Simple_DataType in Variable.__post_init__ [1]
        return isinstance(v.datatype, Simple_DataType)

    def _canonical_path(
        self,
        module_path: list[str],
        variable: Variable,
        field_path: str | None,
    ) -> CanonicalPath:
        segs = list(module_path) + [variable.name]
        if field_path:
            segs.extend([p for p in field_path.split(".") if p])
        return CanonicalPath(tuple(segs))

    def _record_access(
        self,
        kind: AccessKind,
        canonical_path: CanonicalPath,
        context: ScopeContext,
        syntactic_ref: str,
    ) -> None:
        self.usage_tracker.record_access(
            kind=kind,
            canonical_path=canonical_path,
            context=context,
            syntactic_ref=syntactic_ref,
        )

    def _mark_ref_access(
        self,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
    ) -> None:
        var, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if var is None:
            return

        self.usage_tracker.mark_ref_access(
            variable=var,
            field_path=field_path,
            decl_module_path=decl_module_path,
            context=context,
            path=path,
            kind=kind,
            syntactic_ref=full_ref,
        )

    def _site_str(self) -> str:
        if not self._site_stack:
            return ""
        return " > ".join(self._site_stack)

    def _push_site(self, label: str) -> None:
        if label:
            self._site_stack.append(label)

    def _pop_site(self) -> None:
        if self._site_stack:
            self._site_stack.pop()

    def _strict_datatype_at_field_prefix(
        self,
        root_type: Simple_DataType | str,
        field_prefix: str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
        use_path: list[str],
    ) -> Simple_DataType | str:
        """Resolve the datatype at a dotted field-prefix (strict).

        Used only for record-wide builtin semantics.

        Raises ValueError if:
        - a referenced record type is unknown
        - a referenced field segment doesn't exist
        - the prefix continues into a scalar type
        """
        segments = [s for s in (field_prefix or "").split(".") if s]
        current: Simple_DataType | str = root_type

        for seg in segments:
            if isinstance(current, Simple_DataType):
                site = self._site_str()
                if self.fail_loudly:
                    raise ValueError(
                        f"{fn_name}: at {' -> '.join(use_path)}"
                        f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"cannot access field {seg!r} on scalar datatype {current.value!r}."
                    )
                self._warn(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"cannot access field {seg!r} on scalar datatype {current.value!r}. Treating as leaf."
                )
                return current

            if isinstance(current, str) and current.casefold() in self._OPAQUE_BUILTIN_TYPES:
                return current

            rec = self.type_graph.record(str(current))
            if rec is None:
                site = self._site_str()
                if self._unavailable_libraries or not self.fail_loudly:
                    self._warn(
                        f"{fn_name}: at {' -> '.join(use_path)}"
                        f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown record datatype {str(current)!r}. Treating as leaf."
                    )
                    return current
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {str(current)!r}."
                )

            f = rec.fields_by_key.get(seg.casefold())
            if f is None:
                available = sorted({fd.name for fd in rec.fields_by_key.values()})
                close = difflib.get_close_matches(seg, available, n=5, cutoff=0.6)
                site = self._site_str()
                if self._unavailable_libraries or not self.fail_loudly:
                    self._warn(
                        f"{fn_name}: at {' -> '.join(use_path)}"
                        f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown field {seg!r} in record datatype {rec.name!r}. "
                        f"Available fields: {available[:50]}"
                        + (f". Close matches: {close}" if close else "")
                        + " Treating as leaf."
                    )
                    return str(current)
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown field {seg!r} in record datatype {rec.name!r}. "
                    f"Available fields: {available[:50]}"
                    + (f". Close matches: {close}" if close else "")
                )

            current = f.datatype

        return current

    def _iter_leaf_field_paths_strict(
        self,
        root_type: Simple_DataType | str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
    ) -> list[tuple[str, ...]]:
        """Expand all leaf field paths for a datatype (strict).

        Returns tuples relative to the datatype root.
        Raises ValueError on unknown record types or cycles.
        """
        if isinstance(root_type, Simple_DataType):
            return [()]

        # Builtin pseudo-type: cannot be expanded, treat as leaf.
        if isinstance(root_type, str) and root_type.casefold() == "anytype":
            return [()]

        start = str(root_type)
        results: list[tuple[str, ...]] = []
        stack: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [(start, (), ())]

        while stack:
            type_name, prefix, chain = stack.pop()
            key = type_name.casefold()

            if key in {c.casefold() for c in chain}:
                raise ValueError(
                    f"{fn_name}: datatype cycle detected while expanding {resolved_var_name!r} "
                    f"(ref {syntactic_ref!r}) at record datatype {type_name!r}."
                )

            rec = self.type_graph.record(type_name)
            if rec is None:
                if key in self._OPAQUE_BUILTIN_TYPES:
                    results.append(prefix)
                    continue
                # Unknown external type: record-wide expansion can't proceed.
                # Fail loudly for real record types, but allow the builtin pseudo-type.
                if self._unavailable_libraries:
                    self._warn(
                        f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown record datatype {type_name!r}. "
                        "Treating as leaf due to unavailable libraries."
                    )
                    results.append(prefix)
                    continue
                if type_name.casefold() == "anytype":
                    results.append(prefix)
                    continue
                if self.fail_loudly:
                    raise ValueError(
                        f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown record datatype {type_name!r}."
                    )
                self._warn(
                    f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {type_name!r}. Treating as leaf."
                )
                results.append(prefix)
                continue

            next_chain = chain + (type_name,)
            for field in rec.fields_by_key.values():
                new_prefix = prefix + (field.name,)
                if isinstance(field.datatype, Simple_DataType):
                    results.append(new_prefix)
                else:
                    stack.append((str(field.datatype), new_prefix, next_chain))

        return results

    def _mark_record_wide_builtin_access(
        self,
        syntactic_ref: str,
        *,
        kind: AccessKind,
        fn_name: str,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        """Mark read/write for every leaf field under the resolved datatype.

        The `syntactic_ref` is what appears in code (e.g. "Dv.Y_Søjle" or "control").
        Resolution (param mappings) is applied via ScopeContext.resolve_variable().
        """
        resolved_var, resolved_field_prefix, _decl_path, _decl_display = context.resolve_variable(
            syntactic_ref
        )
        if resolved_var is None:
            site = self._site_str()
            raise ValueError(
                f"{fn_name}: at {' -> '.join(path)}"
                f"{(' [' + site + ']') if site else ''}: cannot resolve variable reference {syntactic_ref!r} for record-wide access."
            )

        dtype_at_prefix = self._strict_datatype_at_field_prefix(
            resolved_var.datatype,
            resolved_field_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var.name,
            use_path=path,
        )

        leaf_paths = self._iter_leaf_field_paths_strict(
            dtype_at_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var.name,
        )

        for leaf in leaf_paths:
            if not leaf:
                self._mark_ref_access(syntactic_ref, context, path, kind)
            else:
                self._mark_ref_access(
                    f"{syntactic_ref}.{'.'.join(leaf)}",
                    context,
                    path,
                    kind,
                )

    def _repath_context(
        self,
        context: ScopeContext,
        module_path: list[str],
        display_module_path: list[str],
    ) -> ScopeContext:
        return ScopeContext(
            env=context.env,
            param_mappings=context.param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            current_library=context.current_library,
            parent_context=context.parent_context,
        )

    def _handle_function_call(
        self,
        fn_name: str | None,
        args: list,
        context: ScopeContext,
        path: list[str]
    ) -> None:
        """Handle function calls with proper parameter direction tracking."""
        if not fn_name:
            for a in args or []:
                self._walk_stmt_or_expr(a, context, path)
            return

        fn_key = fn_name.casefold()
        if fn_key in ("copyvariable", "copyvarnosort"):
            # Semantics: reads every field of Source, writes every field of Destination.
            if len(args or []) < 2:
                raise ValueError(f"{fn_name}: expected at least 2 arguments (Source, Destination)")

            src = args[0]
            dst = args[1]
            if not (isinstance(src, dict) and const.KEY_VAR_NAME in src):
                raise ValueError(f"{fn_name}: Source must be a variable reference")
            if not (isinstance(dst, dict) and const.KEY_VAR_NAME in dst):
                raise ValueError(f"{fn_name}: Destination must be a variable reference")

            self._mark_record_wide_builtin_access(
                src[const.KEY_VAR_NAME],
                kind=AccessKind.READ,
                fn_name=fn_name,
                context=context,
                path=path,
            )
            self._mark_record_wide_builtin_access(
                dst[const.KEY_VAR_NAME],
                kind=AccessKind.WRITE,
                fn_name=fn_name,
                context=context,
                path=path,
            )

            # Status is the 3rd arg (out) if present.
            if len(args) >= 3:
                status = args[2]
                if isinstance(status, dict) and const.KEY_VAR_NAME in status:
                    self._mark_ref_access(status[const.KEY_VAR_NAME], context, path, AccessKind.WRITE)
                else:
                    self._walk_stmt_or_expr(status, context, path)

            # Walk any extra args conservatively
            for extra in (args[3:] if len(args) > 3 else []):
                self._walk_stmt_or_expr(extra, context, path)
            return

        if fn_key == "initvariable":
            # Semantics (per user): writes defaults into every field of Rec; reads NOTHING.
            if len(args or []) < 1:
                raise ValueError(f"{fn_name}: expected at least 1 argument (Rec)")

            rec = args[0]
            if not (isinstance(rec, dict) and const.KEY_VAR_NAME in rec):
                raise ValueError(f"{fn_name}: Rec must be a variable reference")

            self._mark_record_wide_builtin_access(
                rec[const.KEY_VAR_NAME],
                kind=AccessKind.WRITE,
                fn_name=fn_name,
                context=context,
                path=path,
            )

            # Skip InitRec entirely (args[1]) to avoid counting reads.
            # Status is args[2] (out) if present.
            if len(args) >= 3:
                status = args[2]
                if isinstance(status, dict) and const.KEY_VAR_NAME in status:
                    self._mark_ref_access(status[const.KEY_VAR_NAME], context, path, AccessKind.WRITE)
                else:
                    self._walk_stmt_or_expr(status, context, path)

            for extra in (args[3:] if len(args) > 3 else []):
                self._walk_stmt_or_expr(extra, context, path)
            return

        sig = get_function_signature(fn_name)
        if sig is None:
            for a in args or []:
                self._walk_stmt_or_expr(a, context, path)
            return

        for idx, arg in enumerate(args or []):
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[idx].direction

            if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
                full_name = arg[const.KEY_VAR_NAME]
                if direction == "out":
                    self._mark_ref_access(full_name, context, path, AccessKind.WRITE)
                elif direction == "inout":
                    self._mark_ref_access(full_name, context, path, AccessKind.READ)
                    self._mark_ref_access(full_name, context, path, AccessKind.WRITE)
                else:
                    self._mark_ref_access(full_name, context, path, AccessKind.READ)
                continue

            self._walk_stmt_or_expr(arg, context, path)

    def _lookup_global_variable(self, base_name: str | None) -> Variable | None:
        if not base_name:
            return None
        normalized = base_name.lower()
        var = self._root_env.get(normalized)
        if var:
            return var
        lst = self._any_var_index.get(normalized)
        return lst[0] if lst else None

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            # If origin wasn't stamped (e.g., SCAN_ROOT_ONLY), treat as root.
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            # Without a root origin, be conservative: treat as not-from-root
            # (or return True if you want to analyze everything when origin is missing)
            return False

        try:
            return Path(origin_file).stem.lower() == Path(root_origin).stem.lower()
        except Exception:
            return (
                origin_file.rsplit(".", 1)[0].lower()
                == root_origin.rsplit(".", 1)[0].lower()
            )

    def _extract_field_path(self, var_dict: dict) -> tuple[str | None, str | None]:
        """
        Extract base variable name and field path from variable reference.
        E.g., "Dv.BatchID" -> ("Dv", "BatchID")
            "Dv.Recipe.Name" -> ("Dv", "Recipe.Name")
        """
        if not isinstance(var_dict, dict) or const.KEY_VAR_NAME not in var_dict:
            return None, None

        full_name = var_dict[const.KEY_VAR_NAME]
        if not full_name or "." not in full_name:
            return full_name.lower() if full_name else None, None

        parts = full_name.split(".", 1)
        base = parts[0].lower()
        field_path = parts[1] if len(parts) > 1 else None

        return base, field_path

    # ------------ Entry point ------------

    def run(
        self,
        apply_alias_back_propagation: bool = True,
        limit_to_module_path: list[str] | None = None,
    ) -> list[VariableIssue]:
        # NOTE: When `limit_to_module_path` is set (used by option 9), we must NOT
        # analyze every ModuleTypeDef in the project. That would pull in unrelated
        # code and can legitimately fail loudly (e.g., record-wide builtins) outside
        # the selected subtree.
        self._issues = []
        self.context_builder.issues = self._issues
        self._mapping_warnings: list[str] = []
        self._limit_to_module_path: list[str] | None = limit_to_module_path

        if self.debug:
            log.debug(
                "Variables analysis start: %s locals=%d submodules=%d typedefs=%d",
                self.bp.header.name,
                len(self.bp.localvariables or []),
                len(self.bp.submodules or []),
                len(self.bp.moduletype_defs or []),
            )

        # Build root scope context for BasePicture
        root_context = self.context_builder.build_for_basepicture()

        # Analyze BasePicture body
        self._walk_module_code(self.bp.modulecode, root_context, path=[self.bp.header.name])
        self._walk_moduledef(self.bp.moduledef, root_context, path=[self.bp.header.name])
        self._walk_header_enable(self.bp.header, root_context, path=[self.bp.header.name])
        self._walk_header_groupconn(self.bp.header, root_context, path=[self.bp.header.name])

        # Walk submodules with scope propagation
        self._walk_submodules(
            self.bp.submodules or [],
            parent_context=root_context,
            parent_path=[self.bp.header.name]
        )

        if apply_alias_back_propagation:
            self._apply_alias_back_propagation()

        self._detect_datatype_duplications()

        # Collect issues across this file
        bp_path = [self.bp.header.name]

        for v in self.bp.localvariables or []:
            role = "localvariable"
            usage = self._get_usage(v)
            if usage.is_unused:
                self._add_issue(IssueKind.UNUSED, bp_path, v, role=role)
            elif (
                usage.is_read_only
                and not bool(v.const)
                and self._is_const_candidate(v)
            ):
                self._add_issue(IssueKind.READ_ONLY_NON_CONST, bp_path, v, role=role)
            elif usage.written and not usage.read:
                self._add_issue(IssueKind.NEVER_READ, bp_path, v, role=role)

        for mod in self.bp.submodules or []:
            self._collect_issues_from_module(mod, path=bp_path)

        if self._limit_to_module_path is None:
            for mt in self.bp.moduletype_defs or []:
                if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                    continue
                td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]

                self._analyze_typedef(mt, path=[self.bp.header.name, f"TypeDef:{mt.name}"])

                # moduleparameters: UNUSED only
                for v in mt.moduleparameters or []:
                    role = "moduleparameter"
                    if self._get_usage(v).is_unused:
                        self._add_issue(IssueKind.UNUSED, td_path, v, role=role)
                # localvariables: UNUSED / READ_ONLY_NON_CONST / NEVER_READ
                for v in mt.localvariables or []:
                    role = "localvariable"
                    usage = self._get_usage(v)
                    if usage.is_unused:
                        self._add_issue(IssueKind.UNUSED, td_path, v, role=role)
                    elif (
                        usage.is_read_only
                        and not bool(v.const)
                        and self._is_const_candidate(v)
                    ):
                        self._add_issue(
                            IssueKind.READ_ONLY_NON_CONST, td_path, v, role=role
                        )
                    elif usage.written and not usage.read:
                        self._add_issue(IssueKind.NEVER_READ, td_path, v, role=role)

        if self.debug:
            log.debug("Variables analysis complete. Issues=%d", len(self._issues))

        return self._issues

    # ------------ Traversal helpers ------------

    def _add_issue(
        self, kind: IssueKind, path: list[str], variable: Variable, role: str
    ) -> None:
        self._issues.append(
            VariableIssue(
                kind=kind, module_path=path.copy(), variable=variable, role=role
            )
        )

    def _collect_issues_from_module(
        self,
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            # Moduleparameters: only classify UNUSED (const does not apply to params)
            for v in mod.moduleparameters or []:
                if self._get_usage(v).is_unused:
                    self._add_issue(
                        IssueKind.UNUSED, my_path, v, role="moduleparameter"
                    )
            # Localvariables: both UNUSED and READ_ONLY_NON_CONST apply
            for v in mod.localvariables or []:
                usage = self._get_usage(v)
                if usage.is_unused:
                    self._add_issue(IssueKind.UNUSED, my_path, v, role="localvariable")
                elif (
                    usage.is_read_only
                    and not bool(v.const)
                    and self._is_const_candidate(v)
                ):
                    self._add_issue(
                        IssueKind.READ_ONLY_NON_CONST, my_path, v, role="localvariable"
                    )
            for ch in mod.submodules or []:
                self._collect_issues_from_module(ch, my_path)

        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for ch in mod.submodules or []:
                self._collect_issues_from_module(ch, my_path)

        elif isinstance(mod, ModuleTypeInstance):
            return

    # ------------ Traversal helpers ------------

    def _collect_unused_from_module(
        self,
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
        out: list[VariableIssue],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            for v in mod.moduleparameters or []:
                if self._get_usage(v).is_unused:
                    out.append(
                        VariableIssue(
                            kind=IssueKind.UNUSED, module_path=my_path, variable=v
                        )
                    )
            for v in mod.localvariables or []:
                if self._get_usage(v).is_unused:
                    out.append(
                        VariableIssue(
                            kind=IssueKind.UNUSED, module_path=my_path, variable=v
                        )
                    )
            for ch in mod.submodules or []:
                self._collect_unused_from_module(ch, my_path, out)

        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for ch in mod.submodules or []:
                self._collect_unused_from_module(ch, my_path, out)

        elif isinstance(mod, ModuleTypeInstance):
            return

    def _is_external_typename(self, typename: str) -> bool:
        # Type is external to this file if not present in BasePicture.moduletype_defs [3]
        return typename.lower() not in self.typedef_index

    def _collect_read_only_non_const_from_module(
        self,
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
        out: list[VariableIssue],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            for v in mod.moduleparameters or []:
                usage = self._get_usage(v)
                if usage.is_read_only and not bool(v.const):
                    out.append(
                        VariableIssue(
                            kind=IssueKind.READ_ONLY_NON_CONST,
                            module_path=my_path,
                            variable=v,
                        )
                    )
            for v in mod.localvariables or []:
                usage = self._get_usage(v)
                if usage.is_read_only and not bool(v.const):
                    out.append(
                        VariableIssue(
                            kind=IssueKind.READ_ONLY_NON_CONST,
                            module_path=my_path,
                            variable=v,
                        )
                    )
            for ch in mod.submodules or []:
                self._collect_read_only_non_const_from_module(ch, my_path, out)

        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for ch in mod.submodules or []:
                self._collect_read_only_non_const_from_module(ch, my_path, out)

        elif isinstance(mod, ModuleTypeInstance):
            return

    # ------------ ModuleTypeDef analysis ------------

    def _analyze_typedef(self, mt: ModuleTypeDef, path: list[str]) -> None:
        # Prevent infinite recursion
        mt_key = mt.name.lower()
        if mt_key in self._analyzing_typedefs:
            return

        self._analyzing_typedefs.add(mt_key)

        try:
            params = list(mt.moduleparameters or [])
            locals_ = list(mt.localvariables or [])

            # Enforce: cannot have both a parameter and local with same name
            param_keys = {v.name.casefold(): v for v in params}
            local_keys = {v.name.casefold(): v for v in locals_}
            for k in (set(param_keys.keys()) & set(local_keys.keys())):
                p = param_keys[k]
                lv = local_keys[k]
                self._issues.append(
                    VariableIssue(
                        kind=IssueKind.NAME_COLLISION,
                        module_path=path.copy(),
                        variable=lv,
                        role=f"name collision with parameter {p.name!r}",
                        source_variable=p,
                    )
                )

            # Build environment from typedef's parameters + locals
            env: dict[str, Variable] = {}
            for v in params:
                env[v.name.lower()] = v
            for v in locals_:
                env[v.name.lower()] = v

            display_path: list[str] = []
            if path:
                display_path.append(decorate_segment(path[0], "BP"))
                for seg in path[1:]:
                    if seg.startswith("TypeDef:"):
                        display_path.append(decorate_segment(seg, "TD"))
                    else:
                        display_path.append(seg)

            # Create scope context
            context = ScopeContext(
                env=env,
                param_mappings={},
                module_path=path.copy(),
                display_module_path=display_path,
                current_library=mt.origin_lib,
                parent_context=None
            )

            # Scan typedef ModuleDef first (graph/interact), then ModuleCode
            self._walk_moduledef(mt.moduledef, context, path)
            self._walk_module_code(mt.modulecode, context, path)
            self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
            self._walk_typedef_groupconn(mt, context, path)

            # Track per-parameter read/write usage
            used_reads: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).read
            )
            used_writes: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).written
            )

            # Preserve existing "used" union for any other consumers
            used_params: set[str] = used_reads | used_writes
            self.used_params_by_typedef[mt.name] = used_params

            # Store separate read/write sets
            self.param_reads_by_typedef[mt.name.lower()] = used_reads
            self.param_writes_by_typedef[mt.name.lower()] = used_writes

            for pm in mt.parametermappings or []:
                tgt_name = varname_base(pm.target)
                tgt_var = env.get(tgt_name) if tgt_name else None
                self._check_param_mapping(pm, tgt_var, env, path)
        finally:
            self._analyzing_typedefs.discard(mt_key)

    def _apply_alias_back_propagation(self) -> None:
        """
        For every alias (parent_var -> child_param_var, field_prefix), replicate usage
        from the child parameter back to the parent variable WITH the field prefix.

        Example:
        parent_var = Dv
        child_var = OpMessage (parameter in child module)
        field_prefix = "OpMessage1"

        If OpMessage.AckText is accessed in child:
            -> Mark Dv field "OpMessage1.AckText" as accessed
        """
        for parent_var, child_var, field_prefix in self._alias_links:
            parent_usage = self._get_usage(parent_var)
            child_usage = self._get_usage(child_var)

            # **CHANGED**: Replicate field-level accesses WITH prefix reconstruction
            for field_path, locations in (child_usage.field_reads or {}).items():
                # Reconstruct full field path: prefix + field accessed on parameter
                if field_prefix and field_path:
                    full_field_path = f"{field_prefix}.{field_path}"
                elif field_prefix:
                    full_field_path = field_prefix
                else:
                    full_field_path = field_path

                for loc in locations:
                    parent_usage.mark_field_read(full_field_path, loc)

            for field_path, locations in (child_usage.field_writes or {}).items():
                # Reconstruct full field path
                if field_prefix and field_path:
                    full_field_path = f"{field_prefix}.{field_path}"
                elif field_prefix:
                    full_field_path = field_prefix
                else:
                    full_field_path = field_path

                for loc in locations:
                    parent_usage.mark_field_written(full_field_path, loc)

            # **CHANGED**: Replicate whole-variable accesses as field accesses
            # (accessing the parameter as a whole = accessing that field of parent)
            for loc, kind in (child_usage.usage_locations or []):
                if field_prefix:
                    # If there's a field prefix, mark that field as accessed
                    if kind == "read":
                        parent_usage.mark_field_read(field_prefix, loc)
                    elif kind == "write":
                        parent_usage.mark_field_written(field_prefix, loc) # type: ignore
                else:
                    # No field prefix means whole variable mapping (rare case)
                    if kind == "read":
                        parent_usage.mark_read(loc)
                    elif kind == "write":
                        parent_usage.mark_written(loc)

    def _walk_submodules(
        self,
        children: list[Union[SingleModule, FrameModule, ModuleTypeInstance]],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        """Walk submodules with proper scope context propagation."""

        for child in children:
            child_name = child.header.name
            child_path = parent_path + [child_name]

            if self._limit_to_module_path is not None:
                # Only traverse:
                #  - nodes along the path to the selected module, and
                #  - nodes within the selected module subtree.
                if not (
                    path_startswith_casefold(self._limit_to_module_path, child_path)
                    or path_startswith_casefold(child_path, self._limit_to_module_path)
                ):
                    continue

            if isinstance(child, SingleModule):
                child_display_path = parent_context.display_module_path + [
                    decorate_segment(child_name, "SM")
                ]
            elif isinstance(child, FrameModule):
                child_display_path = parent_context.display_module_path + [
                    decorate_segment(child_name, "FM")
                ]
            elif isinstance(child, ModuleTypeInstance):
                child_display_path = parent_context.display_module_path + [
                    decorate_segment(child_name, "MT", moduletype_name=child.moduletype_name)
                ]
            else:
                child_display_path = parent_context.display_module_path + [child_name]

            inst_context = self._repath_context(
                parent_context,
                module_path=child_path,
                display_module_path=child_display_path,
            )

            # Handle header-level enable and groupconn
            self._walk_header_enable(
                child.header, inst_context, path=child_path
            )
            self._walk_header_groupconn(
                child.header, inst_context, path=child_path
            )

            if isinstance(child, SingleModule):
                # **CHANGED**: Build scope context with parameter mappings
                child_context = self.context_builder.build_for_single(
                    child,
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )

                # **CHANGED**: Use child_context instead of building env dict
                self._walk_moduledef(
                    child.moduledef, child_context, child_path
                )
                self._walk_module_code(
                    child.modulecode, child_context, child_path
                )

                # Recursively walk submodules with child context
                self._walk_submodules(
                    child.submodules or [],
                    child_context,  # **CHANGED**: Pass child context, not parent
                    child_path,
                )

                # Track parameter usage for propagation (unchanged logic)
                used_reads: set[str] = set(
                    v.name.lower() for v in (child.moduleparameters or []) if self._get_usage(v).read
                )
                used_writes: set[str] = set(
                    v.name.lower() for v in (child.moduleparameters or []) if self._get_usage(v).written
                )

                # **CHANGED**: Create alias links with field path information
                for pm in child.parametermappings or []:
                    source_name = varname_base(pm.source)
                    target_name = varname_base(pm.target)

                    if source_name and target_name and not pm.is_source_global:
                        # **CHANGED**: Extract field prefix from mapping
                        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                            full_source_name = pm.source[const.KEY_VAR_NAME]
                        elif isinstance(pm.source, str):
                            full_source_name = pm.source
                        else:
                            continue

                        # **CHANGED**: Resolve with field path
                        source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(full_source_name)
                        target_key = target_name.casefold()
                        target_var = child_context.env.get(target_key)

                        if source_var and not target_var:
                            # Don't crash the full run for unrelated/broken mappings.
                            # We avoid fallbacks/heuristics and simply skip alias creation.
                            self._mapping_warnings.append(
                                f"Parameter mapping refers to unknown target parameter {target_name!r} "
                                f"in module {child_name!r}: {pm}"
                            )

                        if source_var and target_var:
                            # Store only the source field prefix (relative to the source variable).
                            # This must NOT include the target parameter name.
                            # Examples:
                            #   control => Dv        => mapping_name == ""         (Dv.cmd)
                            #   control => Dv.empty  => mapping_name == "empty"    (Dv.empty.cmd)
                            mapping_name = source_field_prefix or ""

                            self._alias_links.append((source_var, target_var, mapping_name))

                # Propagate usage (unchanged)
                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=used_reads,
                        child_used_writes=used_writes,
                        parent_env=parent_context.env,
                        parent_path=parent_path,
                        external_typename=None,
                        parent_context=parent_context,
                    )

                # Check string type mismatches (unchanged)
                self._check_param_mappings_for_single(
                    child,
                    child_env=child_context.env,
                    parent_env=parent_context.env,
                    parent_path=child_path,
                )

            elif isinstance(child, FrameModule):
                # FrameModule: no new scope, but access locations should be attributed to the frame's instance path.
                frame_context = self._repath_context(
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_moduledef(
                    child.moduledef, frame_context, child_path
                )
                self._walk_module_code(
                    child.modulecode, frame_context, child_path
                )

                self._walk_submodules(
                    child.submodules or [],
                    frame_context,
                    child_path,
                )

            elif isinstance(child, ModuleTypeInstance):
                external = self._is_external_typename(child.moduletype_name)
                mt: ModuleTypeDef | None = None

                if not external:
                    try:
                        mt = resolve_moduletype_def_strict(
                            self.bp,
                            child.moduletype_name,
                            current_library=parent_context.current_library,
                            unavailable_libraries=self._unavailable_libraries,
                        )
                    except ValueError:
                        mt = None
                        external = True

                reads, writes = None, None  # Initialize to None

                if not external and mt:
                    mt_key = child.moduletype_name.lower()

                    # **CHANGED**: Build typedef scope context with mappings
                    typedef_context = self.context_builder.build_for_typedef(
                        mt,
                        child,
                        parent_context,
                        module_path=child_path,
                        display_module_path=child_display_path,
                    )

                    # Analyze typedef if not already done
                    if mt_key not in self.param_reads_by_typedef and mt_key not in self._analyzing_typedefs:
                        # **CHANGED**: Use context-aware analysis
                        self._analyze_typedef_with_context(
                            mt, typedef_context, path=child_path
                        )

                    # **CHANGED**: Create alias links with field path information
                    for pm in child.parametermappings or []:
                        source_name = varname_base(pm.source)
                        target_name = varname_base(pm.target)

                        if source_name and target_name and not pm.is_source_global:
                            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                                full_source_name = pm.source[const.KEY_VAR_NAME]
                            elif isinstance(pm.source, str):
                                full_source_name = pm.source
                            else:
                                continue

                            # **CHANGED**: Resolve with field path
                            source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(full_source_name)
                            target_key = target_name.casefold()
                            target_var = typedef_context.env.get(target_key)

                            if source_var and not target_var:
                                # Don't crash the full run for unrelated/broken mappings.
                                # We avoid fallbacks/heuristics and simply skip alias creation.
                                self._mapping_warnings.append(
                                    f"Parameter mapping refers to unknown target parameter {target_name!r} "
                                    f"in typedef instance {child_name!r}: {pm}"
                                )

                            if source_var and target_var:
                                # Store only the source field prefix (relative to the source variable).
                                # Do not include the target parameter name.
                                mapping_name = source_field_prefix or ""

                                self._alias_links.append((source_var, target_var, mapping_name))

                    reads = self.param_reads_by_typedef.get(mt_key, set())
                    writes = self.param_writes_by_typedef.get(mt_key, set())

                # Propagate usage (unchanged)
                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=reads,
                        child_used_writes=writes,
                        parent_env=parent_context.env,
                        parent_path=parent_path,
                        external_typename=(child.moduletype_name if external else None),
                        parent_context=parent_context,
                    )

                if not external:
                    self._check_param_mappings_for_type_instance(
                        child,
                        parent_env=parent_context.env,
                        parent_path=parent_path + [child_name],
                        current_library=parent_context.current_library,
                    )


    def _analyze_single_module_with_context(
        self, mod: SingleModule, context: ScopeContext, path: list[str]
    ) -> tuple[set[str], set[str]]:
        """Analyze a SingleModule with scope context."""
        self._walk_moduledef(mod.moduledef, context, path)
        self._walk_module_code(mod.modulecode, context, path)
        self._walk_submodules(mod.submodules or [], parent_context=context, parent_path=path)

        used_reads: set[str] = set(
            v.name.lower() for v in (mod.moduleparameters or []) if self._get_usage(v).read
        )
        used_writes: set[str] = set(
            v.name.lower() for v in (mod.moduleparameters or []) if self._get_usage(v).written
        )
        return used_reads, used_writes

    def _analyze_typedef_with_context(
        self, mt: ModuleTypeDef, context: ScopeContext, path: list[str]
    ) -> None:
        """Analyze a ModuleTypeDef with scope context."""
        mt_key = mt.name.lower()
        if mt_key in self._analyzing_typedefs:
            return

        self._analyzing_typedefs.add(mt_key)

        try:
            self._walk_moduledef(mt.moduledef, context, path)
            self._walk_module_code(mt.modulecode, context, path)
            self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
            self._walk_typedef_groupconn(mt, context, path)

            used_reads: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).read
            )
            used_writes: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).written
            )

            self.used_params_by_typedef[mt.name] = used_reads | used_writes
            self.param_reads_by_typedef[mt_key] = used_reads
            self.param_writes_by_typedef[mt_key] = used_writes
        finally:
            self._analyzing_typedefs.discard(mt_key)

    # ---------------- ModuleDef walkers ----------------
    def _walk_header_enable(self, header, context: ScopeContext, path):
        # ModuleHeader.enable_tail is a Tree(KEY_ENABLE_EXPRESSION) or Tree('InVar_') [5]
        tail = getattr(header, "enable_tail", None)
        if tail is not None:
            self._walk_tail(tail, context, path)

    def _walk_header_groupconn(self, header, context: ScopeContext, path):
        # header.groupconn is the variable_name dict
        # header.groupconn_global is True iff GLOBAL_KW was present in scan_group
        var_dict = getattr(header, "groupconn", None)
        if not isinstance(var_dict, dict):
            return

        base = varname_base(var_dict)
        if not base:
            return

        is_global = bool(getattr(header, "groupconn_global", False))

        # Only consult the global index when GLOBAL_KW was used.
        # Otherwise, resolve strictly within the current module env.
        if is_global:
            var = self._lookup_global_variable(base)
        else:
            var = context.env.get(base)

        if var is not None:
            self._get_usage(var).mark_read(path)

    def _walk_typedef_groupconn(self, mt, context: ScopeContext, path):
        var_dict = getattr(mt, "groupconn", None)
        if not isinstance(var_dict, dict):
            return
        base = varname_base(var_dict)
        if not base:
            return
        is_global = bool(getattr(mt, "groupconn_global", False))
        var = self._lookup_global_variable(base) if is_global else context.env.get(base)
        if var is not None:
            self._get_usage(var).mark_read(path)

    def _walk_moduledef(
        self, mdef: ModuleDef | None, context: ScopeContext, path: list[str]
    ) -> None:
        """Walk ModuleDef with scope context."""
        if mdef is None:
            return

        for go in mdef.graph_objects or []:
            self._walk_graph_object(go, context, path)

        for io in mdef.interact_objects or []:
            self._walk_interact_object(io, context, path)

        props = getattr(mdef, "properties", {}) or {}
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, context, path)

    def _walk_graph_object(self, go, context: ScopeContext, path):
        props = getattr(go, "properties", {}) or {}
        # NEW: text_vars list -> mark each as used
        for s in props.get("text_vars", []) or []:
            base = s.split(".", 1)[0] if isinstance(s, str) else None
            self._mark_var_by_basename(base, context.env, path)
        # Existing tails handling
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, context, path)

    def _walk_interact_object(self, io, context: ScopeContext, path):
        props = getattr(io, "properties", {}) or {}
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, context, path)
        self._scan_for_varrefs(props.get(const.KEY_BODY), context, path)

        proc = props.get(const.KEY_PROCEDURE)
        if isinstance(proc, dict) and const.KEY_PROCEDURE_CALL in proc:
            call = proc[const.KEY_PROCEDURE_CALL]
            fn_name = call.get(const.KEY_NAME)
            args = call.get(const.KEY_ARGS) or []
            self._handle_function_call(fn_name, args, context, path)

    def _scan_for_varrefs(
        self, obj: Any, context: ScopeContext, path: list[str]
    ) -> None:
        # Generic recursive scan used for interact object bodies and nested dict/tree structures
        if obj is None:
            return
        if isinstance(obj, list):
            for it in obj:
                self._scan_for_varrefs(it, context, path)
            return
        if isinstance(obj, dict):
            # enable dict
            if const.TREE_TAG_ENABLE in obj and const.KEY_TAIL in obj:
                self._walk_tail(obj[const.KEY_TAIL], context, path)
            # explicit assignment dict from interact_assign_variable
            if const.KEY_ASSIGN in obj:
                tail = (obj[const.KEY_ASSIGN] or {}).get(const.KEY_TAIL)
                if tail is not None:
                    self._walk_tail(tail, context, path)
            # descend into any values
            for v in obj.values():
                self._scan_for_varrefs(v, context, path)
            return
        # Trees: enable_expression, InVar_, invar_tail
        if hasattr(obj, "data"):
            data = getattr(obj, "data")
            if data in (
                const.KEY_ENABLE_EXPRESSION,
                const.GRAMMAR_VALUE_INVAR_PREFIX,
                "invar_tail",
            ):
                self._walk_tail(obj, context, path)
                return
            # descend into children
            for ch in getattr(obj, "children", []):
                self._scan_for_varrefs(ch, context, path)

    # ---------------- Tail handlers ----------------

    def _walk_tail(self, tail, context: ScopeContext, path):
        if tail is None:
            return

        # Expression tuple (from enable_expression)
        if isinstance(tail, tuple):
            self._walk_stmt_or_expr(tail, context, path)
            return

        # InVar string result: "Allow.ProgramDebug"
        if isinstance(tail, str):
            base = tail.split(".", 1)[0].lower()
            self._mark_var_by_basename(base, context.env, path)
            return

        # InVar variable_name dict result
        if isinstance(tail, dict) and const.KEY_VAR_NAME in tail:
            base = varname_base(tail)
            self._mark_var_by_basename(base, context.env, path)
            return

        raise ValueError(
            f"_walk_tail: unexpected tail type {type(tail).__name__}: {tail}"
        )

    def _extract_var_basenames_from_tree(
        self, node, allow_single_ident: bool = False
    ) -> set[str]:
        names: set[str] = set()

        def looks_like_varpath(s: str) -> bool:
            # dotted var path: A.B or A.B.C …
            return "." in s and s.split(".", 1)[0].strip() != ""

        def looks_like_ident(s: str) -> bool:
            # accept a simple identifier (used when allow_single_ident is True)
            return bool(s) and s[0].isalpha()

        def visit(x):
            if x is None:
                return
            if isinstance(x, dict) and const.KEY_VAR_NAME in x:
                full = x[const.KEY_VAR_NAME]
                if isinstance(full, str) and full:
                    names.add(full.split(".", 1)[0])
                return
            if isinstance(x, str):
                s = x.strip()
                if looks_like_varpath(s):
                    names.add(s.split(".", 1)[0])
                elif allow_single_ident and looks_like_ident(s):
                    names.add(s)
                return
            if isinstance(x, list):
                for y in x:
                    visit(y)
                return
            if hasattr(x, "children"):
                for ch in getattr(x, "children", []):
                    visit(ch)

        visit(node)
        return names

    _VARPATH_RE = re.compile(
        r"^[A-Za-zÆØÅæøå][A-Za-zÆØÅæøå0-9_']*(\.[A-Za-zÆØÅæøå][A-Za-zÆØÅæøå0-9_']*)+$"
    )

    def _looks_like_varpath(self, s: str) -> bool:
        # connected_variable may be a STRING containing e.g. Colours.Text (from GraphObjects in SattLine) [4]
        return bool(self._VARPATH_RE.match(s))

    def _mark_var_by_basename(
        self, base_name: str | None, env: dict[str, Variable], path: list[str]
    ) -> None:
        if not base_name:
            return
        normalized = base_name.lower()
        var = env.get(normalized)
        if var is None:
            var = self._lookup_global_variable(normalized)
        if var is not None:
            self._get_usage(var).mark_read(path)
        else:
            if self.debug:
                log.debug(
                    "Variable not found in scope: %s (env size=%d, path=%s)",
                    base_name,
                    len(env),
                    " -> ".join(path),
                )

    # ------------ Propagation of parameter mappings ------------

    def _propagate_mapping_to_parent(
        self,
        pm: ParameterMapping,
        child_used_reads: set[str] | None,
        child_used_writes: set[str] | None,
        parent_env: dict[str, Variable],
        parent_path: list[str],
        external_typename: str | None,
        parent_context: ScopeContext | None = None,
    ) -> None:
        target_name = varname_base(pm.target)

        # GLOBAL: resolve by walking up scopes, and only mark if parameter is used
        if pm.is_source_global:
            full_source = None
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source

            if not full_source:
                return

            source_parts = full_source.split(".", 1)
            source_base = source_parts[0]
            source_field_path = source_parts[1] if len(source_parts) > 1 else ""

            if parent_context is not None:
                src_var, _decl_path, _decl_display = parent_context.resolve_global_name(source_base)
            else:
                src_var = parent_env.get(source_base.lower())
                if src_var is None:
                    src_var = self._lookup_global_variable(source_base)

            if src_var is None:
                return

            # External types: conservatively treat mapping as read+written
            if external_typename is not None:
                display_path: list[str] = []
                if parent_path:
                    display_path.append(decorate_segment(parent_path[0], "BP"))
                    display_path.extend(parent_path[1:])
                use_context = ScopeContext(
                    env=parent_env,
                    param_mappings={},
                    module_path=parent_path.copy(),
                    display_module_path=display_path,
                    parent_context=None,
                )

                if source_field_path:
                    self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                    self._get_usage(src_var).mark_field_written(source_field_path, parent_path)

                    cp = self._canonical_path(parent_path, src_var, source_field_path)
                    self._record_access(AccessKind.READ, cp, use_context, full_source)
                    self._record_access(AccessKind.WRITE, cp, use_context, full_source)
                else:
                    self._get_usage(src_var).mark_read(parent_path)
                    self._get_usage(src_var).mark_written(parent_path)

                    cp = self._canonical_path(parent_path, src_var, "")
                    self._record_access(AccessKind.READ, cp, use_context, full_source)
                    self._record_access(AccessKind.WRITE, cp, use_context, full_source)
                return

            if target_name is not None:
                if child_used_reads is not None and target_name in child_used_reads:
                    if source_field_path:
                        self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                    else:
                        self._get_usage(src_var).mark_read(parent_path)

                if child_used_writes is not None and target_name in child_used_writes:
                    if source_field_path:
                        self._get_usage(src_var).mark_field_written(source_field_path, parent_path)
                    else:
                        self._get_usage(src_var).mark_written(parent_path)
            return

        src_base = varname_base(pm.source)

        # **CHANGED**: Extract full source path with fields
        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
            full_source = pm.source[const.KEY_VAR_NAME]
        elif isinstance(pm.source, str):
            full_source = pm.source
        else:
            return

        # **CHANGED**: Parse the source to get base and field path
        source_parts = full_source.split(".", 1)
        source_base = source_parts[0].lower()
        source_field_path = source_parts[1] if len(source_parts) > 1 else ""

        # Resolve the actual source variable
        src_var = parent_env.get(source_base)
        if src_var is None:
            src_var = self._lookup_global_variable(source_base)

        if src_var is None:
            return

        # External types: conservatively treat mapping as read+written
        if external_typename is not None:
            display_path: list[str] = []
            if parent_path:
                display_path.append(decorate_segment(parent_path[0], "BP"))
                display_path.extend(parent_path[1:])
            use_context = ScopeContext(
                env=parent_env,
                param_mappings={},
                module_path=parent_path.copy(),
                display_module_path=display_path,
                parent_context=None,
            )

            if source_field_path:
                self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                self._get_usage(src_var).mark_field_written(source_field_path, parent_path)

                cp = self._canonical_path(parent_path, src_var, source_field_path)
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            else:
                self._get_usage(src_var).mark_read(parent_path)
                self._get_usage(src_var).mark_written(parent_path)

                cp = self._canonical_path(parent_path, src_var, "")
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            return

        # **CHANGED**: Internal types with field-aware propagation
        if target_name is not None:
            # If the child used the parameter for reading
            if child_used_reads is not None and target_name in child_used_reads:
                if source_field_path:
                    self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                else:
                    self._get_usage(src_var).mark_read(parent_path)

            # If the child used the parameter for writing
            if child_used_writes is not None and target_name in child_used_writes:
                if source_field_path:
                    self._get_usage(src_var).mark_field_written(source_field_path, parent_path)
                else:
                    self._get_usage(src_var).mark_written(parent_path)

    # ------------ ModuleCode walkers ------------

    def _walk_module_code(
        self,
        mc: ModuleCode | None,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        """Walk ModuleCode with scope context."""
        if mc is None:
            return

        for seq in mc.sequences or []:
            label = f"SEQ:{getattr(seq, 'name', '<unnamed>')}"
            self._push_site(label)
            try:
                self._walk_sequence(seq, context, path)
            finally:
                self._pop_site()

        for eq in mc.equations or []:
            label = f"EQ:{getattr(eq, 'name', '<unnamed>')}"
            self._push_site(label)
            try:
                for stmt in eq.code or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            finally:
                self._pop_site()

    def _walk_sequence(
        self, seq: Sequence, context: ScopeContext, path: list[str]
    ) -> None:
        """Walk Sequence with scope context."""
        for node in seq.code or []:
            if isinstance(node, SFCStep):
                base = f"STEP:{node.name}"
                self._push_site(f"{base}:ENTER")
                try:
                    for stmt in node.code.enter or []:
                        self._walk_stmt_or_expr(stmt, context, path)
                finally:
                    self._pop_site()

                self._push_site(f"{base}:ACTIVE")
                try:
                    for stmt in node.code.active or []:
                        self._walk_stmt_or_expr(stmt, context, path)
                finally:
                    self._pop_site()

                self._push_site(f"{base}:EXIT")
                try:
                    for stmt in node.code.exit or []:
                        self._walk_stmt_or_expr(stmt, context, path)
                finally:
                    self._pop_site()

            elif isinstance(node, SFCTransition):
                label = f"TRANS:{node.name or '<unnamed>'}"
                self._push_site(label)
                try:
                    self._walk_stmt_or_expr(node.condition, context, path)
                finally:
                    self._pop_site()

            elif isinstance(node, SFCAlternative):
                for i, branch in enumerate(node.branches or []):
                    self._push_site(f"ALT:BRANCH:{i}")
                    try:
                        self._walk_seq_nodes(branch, context.env, path)
                    finally:
                        self._pop_site()

            elif isinstance(node, SFCParallel):
                for i, branch in enumerate(node.branches or []):
                    self._push_site(f"PAR:BRANCH:{i}")
                    try:
                        self._walk_seq_nodes(branch, context.env, path)
                    finally:
                        self._pop_site()

            elif isinstance(node, SFCSubsequence):
                self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
                try:
                    self._walk_seq_nodes(node.body, context.env, path)
                finally:
                    self._pop_site()

            elif isinstance(node, SFCTransitionSub):
                self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
                try:
                    self._walk_seq_nodes(node.body, context.env, path)
                finally:
                    self._pop_site()

            elif isinstance(node, (SFCFork, SFCBreak)):
                # no variable usage in headers
                continue

    def _walk_seq_nodes(
        self, nodes: list[Any], env: dict[str, Variable], path: list[str]
    ) -> None:
        # Create a scope context from the environment
        display_path: list[str] = []
        if path:
            display_path.append(decorate_segment(path[0], "BP"))
            display_path.extend(path[1:])
        context = ScopeContext(
            env=env,
            param_mappings={},
            module_path=path.copy(),
            display_module_path=display_path,
            parent_context=None
        )
        for nd in nodes:
            if isinstance(nd, SFCStep):
                for stmt in nd.code.enter or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in nd.code.active or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in nd.code.exit or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            elif isinstance(nd, SFCTransition):
                self._walk_stmt_or_expr(nd.condition, context, path)
            elif isinstance(nd, SFCAlternative):
                for branch in nd.branches:
                    self._walk_seq_nodes(branch, env, path)
            elif isinstance(nd, SFCParallel):
                for branch in nd.branches:
                    self._walk_seq_nodes(branch, env, path)
            elif isinstance(nd, SFCSubsequence):
                self._walk_seq_nodes(nd.body, env, path)
            elif isinstance(nd, SFCTransitionSub):
                self._walk_seq_nodes(nd.body, env, path)

    # ------------ Statement/expression walkers ------------

    def _walk_stmt_or_expr(
        self,
        obj: Any,
        context: ScopeContext,
        path: list[str]
    ) -> None:
        # Tree wrapping for statements is present in transformer [5]; unwrap
        if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
            for ch in getattr(obj, "children", []):
                self._walk_stmt_or_expr(ch, context, path)
            return

        # IF Statement: (IF, branches, else_block) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = obj
            for cond, stmts in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                for st in stmts or []:
                    self._walk_stmt_or_expr(st, context, path)
            for st in else_block or []:
                self._walk_stmt_or_expr(st, context, path)
            return

        # Ternary: (Ternary, [(cond, then_expr), ...], else_expr) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
            _, branches, else_expr = obj
            for cond, then_expr in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                self._walk_stmt_or_expr(then_expr, context, path)
            if else_expr is not None:
                self._walk_stmt_or_expr(else_expr, context, path)
            return

        # Function call: (FunctionCall, name, [args...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _, fn_name, args = obj
            self._handle_function_call(fn_name, args or [], context, path)
            return

        # Boolean OR/AND [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND)
        ):
            for sub in obj[1] or []:
                self._walk_stmt_or_expr(sub, context, path)
            return

        # NOT [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
            self._walk_stmt_or_expr(obj[1], context, path)
            return

        # Compare: (compare, left, [(sym, right), ...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
            _, left, pairs = obj
            self._walk_stmt_or_expr(left, context, path)
            for _sym, rhs in pairs or []:
                self._walk_stmt_or_expr(rhs, context, path)
            return

        # Add/Mul [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
            _, left, parts = obj
            self._walk_stmt_or_expr(left, context, path)
            for _opval, r in parts or []:
                self._walk_stmt_or_expr(r, context, path)
            return

        # Unary [+/- term] [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.KEY_PLUS, const.KEY_MINUS)
        ):
            _, inner = obj
            self._walk_stmt_or_expr(inner, context, path)
            return

        # Interact/enable/invar tails may embed expressions/variable refs [5]
        if isinstance(obj, dict) and const.KEY_ENABLE_EXPRESSION in obj:
            tail = obj[const.KEY_ENABLE_EXPRESSION]
            self._walk_stmt_or_expr(tail, context, path)
            return

        # Tree wrappers for enable_expression / invar tails [5]
        if hasattr(obj, "data"):
            if getattr(obj, "data") == const.KEY_ENABLE_EXPRESSION:
                for ch in getattr(obj, "children", []):
                    self._walk_stmt_or_expr(ch, context, path)
                return
            if getattr(obj, "data") == const.GRAMMAR_VALUE_INVAR_PREFIX:
                for ch in getattr(obj, "children", []):
                    self._walk_stmt_or_expr(ch, context, path)
                return

        # Lists of nested statements
        if isinstance(obj, list):
            for it in obj:
                self._walk_stmt_or_expr(it, context, path)
            return

        # **CHANGED**: Variable reference with scope-aware resolution
        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            full_name = obj[const.KEY_VAR_NAME]
            self._mark_ref_access(full_name, context, path, AccessKind.READ)
            return

        # **CHANGED**: Assignment with scope-aware resolution
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _, target, expr = obj

            if isinstance(target, dict) and const.KEY_VAR_NAME in target:
                full_name = target[const.KEY_VAR_NAME]
                self._mark_ref_access(full_name, context, path, AccessKind.WRITE)

            self._walk_stmt_or_expr(expr, context, path)
            return

        # Tree wrapping for statements is present in transformer [5]; unwrap
        if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
            for ch in getattr(obj, "children", []):
                self._walk_stmt_or_expr(ch, context, path)
            return

        # IF Statement: (IF, branches, else_block) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = obj
            for cond, stmts in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                for st in stmts or []:
                    self._walk_stmt_or_expr(st, context, path)
            for st in else_block or []:
                self._walk_stmt_or_expr(st, context, path)
            return

        # Ternary: (Ternary, [(cond, then_expr), ...], else_expr) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
            _, branches, else_expr = obj
            for cond, then_expr in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                self._walk_stmt_or_expr(then_expr, context, path)
            if else_expr is not None:
                self._walk_stmt_or_expr(else_expr, context, path)
            return

        # Function call: (FunctionCall, name, [args...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _, fn_name, args = (
                obj  # transformer emits (FunctionCall, name, [args...]) [3]
            )
            self._handle_function_call(fn_name, args or [], context, path)
            return

        # Boolean OR/AND [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND)
        ):
            for sub in obj[1] or []:
                self._walk_stmt_or_expr(sub, context, path)
            return

        # NOT [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
            self._walk_stmt_or_expr(obj[1], context, path)
            return

        # Compare: (compare, left, [(sym, right), ...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
            _, left, pairs = obj
            self._walk_stmt_or_expr(left, context, path)
            for _sym, rhs in pairs or []:
                self._walk_stmt_or_expr(rhs, context, path)
            return

        # Add/Mul [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
            _, left, parts = obj
            self._walk_stmt_or_expr(left, context, path)
            for _opval, r in parts or []:
                self._walk_stmt_or_expr(r, context, path)
                return

            # Unary [+/- term] [5]
            if (
                isinstance(obj, tuple)
                and obj
                and obj[0] in (const.KEY_PLUS, const.KEY_MINUS)
            ):
                _, inner = obj
                self._walk_stmt_or_expr(inner, context, path)
                return
            # Interact/enable/invar tails may embed expressions/variable refs [5]
            if isinstance(obj, dict) and const.KEY_ENABLE_EXPRESSION in obj:
                obj_dict: dict[str, Any] = cast(dict[str, Any], obj)
                tail = obj_dict.get(const.KEY_ENABLE_EXPRESSION)
                if tail is not None:
                    self._walk_stmt_or_expr(tail, context, path)
                return

            # Tree wrappers for enable_expression / invar tails [5]
            if hasattr(obj, "data"):
                if getattr(obj, "data") == const.KEY_ENABLE_EXPRESSION:
                    for ch in getattr(obj, "children", []):
                        self._walk_stmt_or_expr(ch, context, path)
                    return
                if getattr(obj, "data") == const.GRAMMAR_VALUE_INVAR_PREFIX:
                    for ch in getattr(obj, "children", []):
                        self._walk_stmt_or_expr(ch, context, path)
                    return

            # Lists of nested statements
            if isinstance(obj, list):
                for it in obj:
                    self._walk_stmt_or_expr(it, context, path)

            if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
                obj_dict: dict[str, Any] = cast(dict[str, Any], obj)
                full_name = obj_dict.get(const.KEY_VAR_NAME)
                if full_name is not None:
                    self._mark_ref_access(full_name, context, path, AccessKind.READ)
                return

            if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
                _, target, expr = obj

                if isinstance(target, dict) and const.KEY_VAR_NAME in target:
                    full_name = target[const.KEY_VAR_NAME]
                    self._mark_ref_access(full_name, context, path, AccessKind.WRITE)

                self._walk_stmt_or_expr(expr, context, path)
                return

    # ------------ Var lookup helpers ------------

    def _lookup_env_var_from_varname_dict(
        self,
        var_dict_or_other: Any,
        env: dict[str, Variable],
    ) -> Variable | None:
        """
        var_dict_or_other is either a {var_name: "..."} dict (from transformer.variable_name) [5],
        or something else (literal, None, etc.).
        """
        if (
            isinstance(var_dict_or_other, dict)
            and const.KEY_VAR_NAME in var_dict_or_other
        ):
            base = varname_base(var_dict_or_other)
            if base is not None:
                return env.get(base)
        return None

    def _detect_datatype_duplications(self) -> None:
        """
        Find complex (record) datatypes that are declared multiple times
        across localvariables and moduleparameters instead of being defined
        as a RECORD type once and reused.
        """
        # Collect all variables with their locations
        var_locations: list[tuple[Variable, list[str], str]] = []

        # BasePicture locals
        bp_path = [self.bp.header.name]
        for v in self.bp.localvariables or []:
            var_locations.append((v, bp_path.copy(), "localvariable"))

        # Recursively collect from modules
        def _collect_from_module(
            mod: Union[SingleModule, FrameModule, ModuleTypeInstance], path: list[str]
        ):
            if isinstance(mod, SingleModule):
                my_path = path + [mod.header.name]
                for v in mod.moduleparameters or []:
                    var_locations.append((v, my_path.copy(), "moduleparameter"))
                for v in mod.localvariables or []:
                    var_locations.append((v, my_path.copy(), "localvariable"))
                for ch in mod.submodules or []:
                    _collect_from_module(ch, my_path)
            elif isinstance(mod, FrameModule):
                my_path = path + [mod.header.name]
                for ch in mod.submodules or []:
                    _collect_from_module(ch, my_path)

        for mod in self.bp.submodules or []:
            _collect_from_module(mod, bp_path)

        # Include TypeDef variables (only from root origin)
        for mt in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            for v in mt.moduleparameters or []:
                var_locations.append((v, td_path.copy(), "moduleparameter"))
            for v in mt.localvariables or []:
                var_locations.append((v, td_path.copy(), "localvariable"))

        # Only check non-built-in types (complex/record types)
        complex_vars = [
            (v, path, role)
            for v, path, role in var_locations
            if not isinstance(v.datatype, Simple_DataType)
        ]

        # Group by datatype name (case-insensitive)
        by_datatype: dict[str, list[tuple[Variable, list[str], str]]] = {}
        for v, path, role in complex_vars:
            dt_key = v.datatype_text.lower()
            by_datatype.setdefault(dt_key, []).append((v, path, role))

        # Report duplicates (2+ occurrences)
        for dt_name, occurrences in by_datatype.items():
            if len(occurrences) < 2:
                continue

            # Check if this is actually a defined RECORD type
            if dt_name in (d.name.lower() for d in self.bp.datatype_defs or []):
                # It's a legitimate record type being used multiple times - not a duplication issue
                continue

            # Create an issue for the first occurrence, listing all others
            first_var, first_path, first_role = occurrences[0]
            duplicate_locs = [(path, role) for _, path, role in occurrences[1:]]

            self._issues.append(
                VariableIssue(
                    kind=IssueKind.DATATYPE_DUPLICATION,
                    module_path=first_path,
                    variable=first_var,
                    role=first_role,
                    duplicate_count=len(occurrences),
                    duplicate_locations=duplicate_locs,
                )
            )
