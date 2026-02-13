from __future__ import annotations
from typing import Any

from ..models.ast_model import (
    BasePicture,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    ParameterMapping,
)
from ..reporting.mms_report import (
    MMSInterfaceHit,
    MMSInterfaceReport,
    WriteFields,
)
from ..resolution.common import (
    find_var_in_scope,
    find_all_aliases,
    find_all_aliases_upstream,
    varname_full,
    varname_base,
    resolve_moduletype_def_strict,
)
from .variables import VariablesAnalyzer


def analyze_mms_interface_variables(
    base_picture: BasePicture,
    debug: bool = False,
) -> MMSInterfaceReport:
    """
    Find variables mapped into MMSWriteVar.WriteData or MMSReadVar.Outputvariable.

    This scans module instances and collects the source variables used in the
    parameter mapping for those module types.
    """
    target_types = {
        "mmswritevar": {"localvariable", "writedata"},
        "mmsreadvar": {"localvariable", "outputvariable"},
        "mmsreadwrite": {"inputvariable", "outputvariable"},
    }

    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
    )
    analyzer.run()

    hits: list[MMSInterfaceHit] = []

    def _collect_write_locations(
        module_path: list[str],
        source_variable: str,
    ) -> WriteFields | None:
        if not source_variable:
            return None

        base = source_variable.split(".", 1)[0]
        field_path = source_variable.split(".", 1)[1] if "." in source_variable else None

        # Use imported find_var_in_scope
        var = find_var_in_scope(base_picture, module_path, base)
        if var is None:
            return None

        # Access private _alias_links from analyzer
        aliases = find_all_aliases(var, analyzer._alias_links, debug=debug)
        aliases.insert(0, (var, ""))
        upstream_aliases = find_all_aliases_upstream(var, analyzer._alias_links)

        field_writes: dict[str, list[list[str]]] = {}
        whole_var_writes: list[list[str]] = []

        for alias_var, prefix in aliases:
            usage = analyzer.usage_tracker.get_usage(alias_var)
            for field, locs in (usage.field_writes or {}).items():
                if prefix and field:
                    full_field = f"{prefix}.{field}"
                elif prefix:
                    full_field = prefix
                else:
                    full_field = field

                field_writes.setdefault(full_field.casefold(), []).extend(locs)

            for loc, kind in (usage.usage_locations or []):
                if kind == "write":
                    whole_var_writes.append(loc)

        # Include upstream mappings (parent variables) by stripping the mapping prefix.
        for alias_var, strip_prefix in upstream_aliases:
            usage = analyzer.usage_tracker.get_usage(alias_var)
            for field, locs in (usage.field_writes or {}).items():
                if strip_prefix:
                    if field == strip_prefix:
                        full_field = ""
                    elif field.startswith(strip_prefix + "."):
                        full_field = field[len(strip_prefix) + 1 :]
                    else:
                        continue
                else:
                    full_field = field

                field_writes.setdefault(full_field.casefold(), []).extend(locs)

            if not strip_prefix:
                for loc, kind in (usage.usage_locations or []):
                    if kind == "write":
                        whole_var_writes.append(loc)

        if field_path:
            prefix = field_path.casefold()
            matched_fields = {
                field: locs
                for field, locs in field_writes.items()
                if field == prefix or field.startswith(prefix + ".")
            }
            if not matched_fields:
                return ()

            results = []
            for field, locs in sorted(matched_fields.items()):
                counts: dict[tuple[str, ...], int] = {}
                for loc in locs:
                    key = tuple(loc)
                    counts[key] = counts.get(key, 0) + 1
                results.append(
                    (field, tuple(sorted(counts.items(), key=lambda item: ".".join(item[0]))))
                )
            return tuple(results)

        if not field_writes and not whole_var_writes:
            return ()

        results = []
        for field, locs in sorted(field_writes.items()):
            counts: dict[tuple[str, ...], int] = {}
            for loc in locs:
                key = tuple(loc)
                counts[key] = counts.get(key, 0) + 1
            results.append(
                (field, tuple(sorted(counts.items(), key=lambda item: ".".join(item[0]))))
            )

        if whole_var_writes:
            counts = {}
            for loc in whole_var_writes:
                key = tuple(loc)
                counts[key] = counts.get(key, 0) + 1
            results.append(
                ("", tuple(sorted(counts.items(), key=lambda item: ".".join(item[0]))))
            )

        return tuple(results)

    def _resolve_param_source(
        param_map: dict[str, str],
        source: Any,
        allow_passthrough: bool,
    ) -> str | None:
        full = varname_full(source)
        if not full:
            return None

        base = full.split(".", 1)[0] if full else ""
        suffix = full[len(base) :] if len(full) > len(base) else ""

        if base:
            mapped = param_map.get(base.casefold())
            if mapped:
                return f"{mapped}{suffix}"

        return full if allow_passthrough else None

    def _build_param_map(
        param_mappings: list[ParameterMapping] | None,
        param_map: dict[str, str],
        allow_passthrough: bool,
    ) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for pm in param_mappings or []:
            target_name = varname_base(pm.target)
            if not target_name or pm.is_source_global:
                continue

            resolved_source = _resolve_param_source(
                param_map,
                pm.source,
                allow_passthrough,
            )
            if not resolved_source:
                continue

            resolved[target_name] = resolved_source
        return resolved

    def _walk_typedef(
        modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
        path: list[str],
        param_map: dict[str, str],
        visited_types: set[str],
    ) -> None:
        for mod in modules or []:
            if isinstance(mod, ModuleTypeInstance):
                mt_name = mod.moduletype_name or ""
                mt_key = mt_name.casefold()
                next_path = path + [mod.header.name]
                current_map = _build_param_map(
                    mod.parametermappings,
                    param_map,
                    allow_passthrough=False,
                )

                if mt_key in target_types:
                    param_targets = target_types[mt_key]
                    for target_name in sorted(param_targets):
                        resolved = current_map.get(target_name)
                        if not resolved:
                            continue

                        writes = _collect_write_locations(next_path, resolved)
                        hits.append(
                            MMSInterfaceHit(
                                module_path=next_path,
                                moduletype_name=mt_name,
                                parameter_name=target_name,
                                source_variable=resolved,
                                write_fields=writes or (),
                                write_note=None if writes is not None else "unknown (variable not found)",
                            )
                        )

                if mt_key in visited_types:
                    continue

                try:
                    inner_def = resolve_moduletype_def_strict(base_picture, mt_name)
                except ValueError:
                    continue

                visited_types.add(mt_key)
                _walk_typedef(
                    inner_def.submodules,
                    next_path,
                    current_map,
                    visited_types,
                )
                visited_types.remove(mt_key)
            elif isinstance(mod, (SingleModule, FrameModule)):
                _walk_typedef(
                    mod.submodules,
                    path + [mod.header.name],
                    param_map,
                    visited_types,
                )

    def _walk_modules(
        modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
        path: list[str],
        param_map: dict[str, str],
    ) -> None:
        for mod in modules or []:
            if isinstance(mod, SingleModule):
                next_path = path + [mod.header.name]
                _walk_modules(mod.submodules, next_path, param_map)
            elif isinstance(mod, FrameModule):
                next_path = path + [mod.header.name]
                _walk_modules(mod.submodules, next_path, param_map)
            elif isinstance(mod, ModuleTypeInstance):
                next_path = path + [mod.header.name]
                mt_name = mod.moduletype_name or ""
                mt_key = mt_name.casefold()
                current_map = _build_param_map(
                    mod.parametermappings,
                    param_map,
                    allow_passthrough=True,
                )

                if mt_key in target_types:
                    param_targets = target_types[mt_key]
                    for target_name in sorted(param_targets):
                        resolved = current_map.get(target_name)
                        if not resolved:
                            continue

                        writes = _collect_write_locations(next_path, resolved)
                        hits.append(
                            MMSInterfaceHit(
                                module_path=next_path,
                                moduletype_name=mt_name,
                                parameter_name=target_name,
                                source_variable=resolved,
                                write_fields=writes or (),
                                write_note=None if writes is not None else "unknown (variable not found)",
                            )
                        )

                try:
                    mt_def = resolve_moduletype_def_strict(base_picture, mt_name)
                except ValueError:
                    continue

                if current_map:
                    _walk_typedef(
                        mt_def.submodules,
                        next_path,
                        current_map,
                        {mt_key},
                    )

    _walk_modules(base_picture.submodules, [base_picture.header.name], {})

    return MMSInterfaceReport(basepicture_name=base_picture.header.name, hits=hits)
