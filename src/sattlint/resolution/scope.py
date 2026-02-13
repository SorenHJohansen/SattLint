from __future__ import annotations
from dataclasses import dataclass
from ..models.ast_model import Variable

@dataclass
class ScopeContext:
    """Tracks variable environment with field-aware parameter mappings."""
    env: dict[str, Variable]  # Direct variable declarations
    # param_name -> (source_var, field_prefix, source_decl_module_path, source_decl_display_path)
    param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]]
    module_path: list[str]
    display_module_path: list[str]
    current_library: str | None = None
    parent_context: ScopeContext | None = None

    def resolve_variable(self, var_ref: str) -> tuple[Variable | None, str, list[str], list[str]]:
        """
        Resolve a variable reference, reconstructing the full field path.

        Examples:
        - "signal.Comp_signal.value" with mapping (signal -> Dv.I.WT001)
          returns (Dv_variable, "I.WT001.Comp_signal.value")
        - "Dv.I.WT001.Comp_signal.value" in parent scope
          returns (Dv_variable, "I.WT001.Comp_signal.value")
        """
        base = var_ref.split(".", 1)[0].lower()
        field_path = var_ref.split(".", 1)[1] if "." in var_ref else ""

        # Resolve parameter aliases first (field-aware).
        if base in self.param_mappings:
            source_var, prefix, source_decl_path, source_decl_display_path = self.param_mappings[base]
            # Rebuild the field path using the mapping prefix.
            if prefix and field_path:
                full_field_path = f"{prefix}.{field_path}"
            elif prefix:
                full_field_path = prefix
            else:
                full_field_path = field_path
            return source_var, full_field_path, source_decl_path, source_decl_display_path

        # Fall back to variables declared in the current scope.
        var = self.env.get(base)
        if var:
            return var, field_path, self.module_path, self.display_module_path

        # Walk up to the parent scope if still unresolved.
        if self.parent_context:
            return self.parent_context.resolve_variable(var_ref)

        return None, field_path, self.module_path, self.display_module_path

    def resolve_global_name(self, base_name: str) -> tuple[Variable | None, list[str], list[str]]:
        """Resolve a GLOBAL-mapped name by walking up scopes (env only).

        GLOBAL lookup ignores parameter mappings and searches localvariables
        and moduleparameters from the current scope up to BasePicture.
        """
        if not base_name:
            return None, self.module_path, self.display_module_path

        key = base_name.lower()
        var = self.env.get(key)
        if var is not None:
            return var, self.module_path, self.display_module_path

        if self.parent_context:
            return self.parent_context.resolve_global_name(base_name)

        return None, self.module_path, self.display_module_path
