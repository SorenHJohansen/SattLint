# analyzers/module_comparison.py
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from models.ast_model import (
    BasePicture,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    ModuleTypeDef,
    Variable,
    ParameterMapping,
    ModuleCode,
    Sequence,
    Equation,
)


def debug_module_structure(base_picture: BasePicture, max_depth: int = 10) -> None:
    """Detailed debugging: show EVERYTHING about the structure."""
    print(f"\n=== DEBUGGING MODULE STRUCTURE ===")
    print(f"BasePicture type: {type(base_picture)}")
    print(f"BasePicture name: {base_picture.name!r}")
    print(f"BasePicture has {len(base_picture.submodules)} submodules")
    print(f"BasePicture has {len(base_picture.moduletype_defs)} moduletype_defs")
    
    # Show moduletype_defs
    print(f"\n--- ModuleTypeDefs ---")
    for mtd in base_picture.moduletype_defs:
        print(f"  ModuleTypeDef: {mtd.name!r}")
        print(f"    - has {len(mtd.submodules)} submodules")
        for i, sub in enumerate(mtd.submodules):
            print(f"    - submodule[{i}]: {type(sub).__name__} - {sub.header.name!r}")
    
    def _walk(node: Any, depth: int = 0, parent_name: str = "") -> None:
        if depth > max_depth:
            print(f"{'  ' * depth}[MAX DEPTH REACHED]")
            return
            
        indent = "  " * depth
        node_type = type(node).__name__
        
        if isinstance(node, SingleModule):
            name = node.header.name
            print(f"{indent}✓ SingleModule: name={name!r}, datecode={node.datecode}, parent={parent_name!r}")
            print(f"{indent}  - has {len(node.submodules)} submodules")
            for i, sub in enumerate(node.submodules):
                print(f"{indent}  - submodule[{i}] type: {type(sub).__name__}")
                _walk(sub, depth + 1, name)
                
        elif isinstance(node, FrameModule):
            name = node.header.name
            print(f"{indent}○ FrameModule: name={name!r}, datecode={node.datecode}, parent={parent_name!r}")
            print(f"{indent}  - has {len(node.submodules)} submodules")
            for i, sub in enumerate(node.submodules):
                print(f"{indent}  - submodule[{i}] type: {type(sub).__name__}")
                _walk(sub, depth + 1, name)
                
        elif isinstance(node, ModuleTypeInstance):
            name = node.header.name
            print(f"{indent}△ ModuleTypeInstance: name={name!r}, type={node.moduletype_name!r}, parent={parent_name!r}")
            
        elif isinstance(node, BasePicture):
            print(f"{indent}▣ BasePicture: name={node.name!r}")
            print(f"{indent}  - has {len(node.submodules)} submodules")
            for i, sub in enumerate(node.submodules):
                print(f"{indent}  - submodule[{i}] type: {type(sub).__name__}")
                _walk(sub, depth + 1, node.name)
        else:
            print(f"{indent}? Unknown type: {node_type}")
    
    print(f"\n--- Submodules Tree ---")
    _walk(base_picture)
    print(f"=== END DEBUGGING ===\n")


@dataclass
class ModuleFingerprint:
    """Represents the structure of a SingleModule for comparison."""
    name: str
    datecode: int | None
    num_moduleparameters: int
    num_localvariables: int
    num_submodules: int
    has_moduledef: bool
    has_modulecode: bool
    num_sequences: int
    num_equations: int
    num_parameter_mappings: int
    
    # Store actual lists for detailed comparison
    moduleparameters: list[Variable]
    localvariables: list[Variable]
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance]
    sequences: list[Sequence]
    equations: list[Equation]
    
    # Hashes for grouping (exclude datecode)
    moduleparameters_hash: int
    localvariables_hash: int
    submodules_hash: int
    parameter_mappings_hash: int
    
    # Store the actual module for access
    module: SingleModule
    module_path: list[str] = field(default_factory=list)


@dataclass
class VariableDiff:
    """Comparison of variable lists."""
    common: list[str]  # case-insensitive common names
    only_in_variant: dict[int, list[str]]  # variant_id -> list of names


def _get_submodule_tree_structure(submodules: list[SingleModule | FrameModule | ModuleTypeInstance], depth: int = 0, max_depth: int = 10) -> set[tuple]:
    """
    Recursively extract the complete tree structure of submodules.
    Returns a set of tuples representing the full hierarchy.
    """
    if depth > max_depth:
        return set()
    
    structure = set()
    
    for sm in submodules:
        name = _normalize_name(sm.header.name)
        
        if isinstance(sm, SingleModule):
            typ = "Single"
            # Add this node
            structure.add((depth, name, typ))
            # Recurse into its submodules
            child_structure = _get_submodule_tree_structure(sm.submodules, depth + 1, max_depth)
            structure.update(child_structure)
            
        elif isinstance(sm, FrameModule):
            typ = "Frame"
            # Add this node
            structure.add((depth, name, typ))
            # Recurse into its submodules
            child_structure = _get_submodule_tree_structure(sm.submodules, depth + 1, max_depth)
            structure.update(child_structure)
            
        elif isinstance(sm, ModuleTypeInstance):
            typ = f"Instance:{_normalize_name(sm.moduletype_name)}"
            # Add this node (instances have no submodules)
            structure.add((depth, name, typ))
    
    return structure


@dataclass
class SubmoduleDiff:
    """Comparison of submodule tree structures (full recursive)."""
    common: list[tuple[int, str, str]]  # (depth, name, type)
    only_in_variant: dict[int, list[tuple[int, str, str]]]


@dataclass
class CodeDiff:
    """Comparison of module code."""
    sequences_common: list[str]
    sequences_only_in_variant: dict[int, list[str]]
    equations_common: list[str]
    equations_only_in_variant: dict[int, list[str]]


@dataclass
class ComparisonResult:
    """Results of comparing multiple SingleModules with the same name."""
    module_name: str
    total_found: int
    unique_variants: int
    fingerprints: list[ModuleFingerprint] = field(default_factory=list)
    all_instances: list[tuple[list[str], ModuleFingerprint]] = field(default_factory=list)
    
    # Detailed diffs
    parameter_diff: VariableDiff | None = None
    localvar_diff: VariableDiff | None = None
    submodule_diff: SubmoduleDiff | None = None
    code_diff: CodeDiff | None = None
    
    def summary(self) -> str:
        lines = [
            f"Module Name: {self.module_name!r}",
            f"Total Instances Found: {self.total_found}",
            f"Unique Variants: {self.unique_variants}",
            "",
        ]
        
        if self.total_found == 0:
            lines.append("⚠ No modules found with this name")
            return "\n".join(lines)
        
        if self.unique_variants == 1:
            lines.append("✓ All instances are structurally identical (datecodes may differ)")
            lines.append("")
            lines.append("Instance locations:")
            for path, fp in self.all_instances:
                lines.append(f"  DateCode: {fp.datecode} - {' → '.join(path)}")
        else:
            lines.append(f"⚠ Found {self.unique_variants} different structural variants")
            lines.append("")
            
            # Group instances by variant FINGERPRINT (not just by id)
            variant_map = {}
            for path, fp in self.all_instances:
                # Find which unique fingerprint this instance matches
                for i, unique_fp in enumerate(self.fingerprints, 1):
                    # Check if they have the same structural hash (excluding datecode)
                    if (
                        fp.num_moduleparameters == unique_fp.num_moduleparameters
                        and fp.num_localvariables == unique_fp.num_localvariables
                        and fp.num_submodules == unique_fp.num_submodules
                        and fp.num_sequences == unique_fp.num_sequences
                        and fp.num_equations == unique_fp.num_equations
                        and fp.moduleparameters_hash == unique_fp.moduleparameters_hash
                        and fp.localvariables_hash == unique_fp.localvariables_hash
                        and fp.submodules_hash == unique_fp.submodules_hash
                        and fp.parameter_mappings_hash == unique_fp.parameter_mappings_hash
                    ):
                        if i not in variant_map:
                            variant_map[i] = []
                        variant_map[i].append((path, fp))
                        break
            
            for i, unique_fp in enumerate(self.fingerprints, 1):
                instances = variant_map.get(i, [])
                
                lines.append(f"=== Variant {i} ({len(instances)} instance(s)) ===")
                lines.append(f"Parameters: {unique_fp.num_moduleparameters}")
                lines.append(f"Local Vars: {unique_fp.num_localvariables}")
                lines.append(f"Submodules: {unique_fp.num_submodules}")
                lines.append(f"Sequences: {unique_fp.num_sequences}")
                lines.append(f"Equations: {unique_fp.num_equations}")
                lines.append(f"Locations:")
                for path, fp in instances:
                    lines.append(f"  DateCode: {fp.datecode} - {' → '.join(path)}")
                lines.append("")
            
            # Show detailed differences
            if self.parameter_diff:
                lines.append("=== Module Parameters Differences ===")
                lines.append(f"Common ({len(self.parameter_diff.common)}): {sorted(self.parameter_diff.common)}")
                for var_id, names in sorted(self.parameter_diff.only_in_variant.items()):
                    if names:
                        lines.append(f"Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                lines.append("")
            
            if self.localvar_diff:
                lines.append("=== Local Variables Differences ===")
                lines.append(f"Common ({len(self.localvar_diff.common)}): {sorted(self.localvar_diff.common)}")
                for var_id, names in sorted(self.localvar_diff.only_in_variant.items()):
                    if names:
                        lines.append(f"Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                lines.append("")
            
            if self.submodule_diff:
                lines.append("=== Submodules Differences (Recursive Tree) ===")
                
                # Group common by depth for better readability
                common_by_depth = defaultdict(list)
                for depth, name, typ in self.submodule_diff.common:
                    common_by_depth[depth].append((name, typ))
                
                lines.append(f"Common across all variants ({len(self.submodule_diff.common)} total):")
                for depth in sorted(common_by_depth.keys()):
                    indent = "  " + ("  " * depth)
                    items = common_by_depth[depth]
                    for name, typ in sorted(items):
                        lines.append(f"{indent}Depth {depth}: {name} ({typ})")
                
                # Show unique submodules per variant
                for var_id, unique_subs in sorted(self.submodule_diff.only_in_variant.items()):
                    if unique_subs:
                        lines.append(f"Only in Variant {var_id} ({len(unique_subs)} nodes):")
                        # Group by depth
                        by_depth = defaultdict(list)
                        for depth, name, typ in unique_subs:
                            by_depth[depth].append((name, typ))
                        
                        for depth in sorted(by_depth.keys()):
                            indent = "  " + ("  " * depth)
                            items = by_depth[depth]
                            for name, typ in sorted(items):
                                lines.append(f"{indent}Depth {depth}: {name} ({typ})")
                lines.append("")
            
            if self.code_diff:
                lines.append("=== Module Code Differences ===")
                if self.code_diff.sequences_common or any(self.code_diff.sequences_only_in_variant.values()):
                    lines.append(f"Sequences Common ({len(self.code_diff.sequences_common)}): {sorted(self.code_diff.sequences_common)}")
                    for var_id, names in sorted(self.code_diff.sequences_only_in_variant.items()):
                        if names:
                            lines.append(f"Sequences Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                if self.code_diff.equations_common or any(self.code_diff.equations_only_in_variant.values()):
                    lines.append(f"Equations Common ({len(self.code_diff.equations_common)}): {sorted(self.code_diff.equations_common)}")
                    for var_id, names in sorted(self.code_diff.equations_only_in_variant.items()):
                        if names:
                            lines.append(f"Equations Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                lines.append("")
        
        return "\n".join(lines)


def _normalize_name(name: str) -> str:
    """Normalize a name for case-insensitive comparison."""
    return name.lower().strip()


def _compare_variable_lists(fingerprints: list[ModuleFingerprint]) -> VariableDiff:
    """Compare module parameters or local variables across variants (case-insensitive)."""
    # Get all normalized names for each variant
    variant_names = []
    for fp in fingerprints:
        names = {_normalize_name(v.name): v.name for v in fp.moduleparameters}
        variant_names.append(names)
    
    # Find common (intersection of all)
    if variant_names:
        common_normalized = set(variant_names[0].keys())
        for names in variant_names[1:]:
            common_normalized &= set(names.keys())
        common = [variant_names[0][n] for n in sorted(common_normalized)]
    else:
        common = []
    
    # Find unique to each variant
    only_in_variant = {}
    for i, names in enumerate(variant_names, 1):
        normalized_names = set(names.keys())
        unique_normalized = normalized_names - common_normalized
        only_in_variant[i] = [names[n] for n in sorted(unique_normalized)]
    
    return VariableDiff(common=common, only_in_variant=only_in_variant)


def _compare_localvars(fingerprints: list[ModuleFingerprint]) -> VariableDiff:
    """Compare local variables across variants (case-insensitive)."""
    variant_names = []
    for fp in fingerprints:
        names = {_normalize_name(v.name): v.name for v in fp.localvariables}
        variant_names.append(names)
    
    if variant_names:
        common_normalized = set(variant_names[0].keys())
        for names in variant_names[1:]:
            common_normalized &= set(names.keys())
        common = [variant_names[0][n] for n in sorted(common_normalized)]
    else:
        common = []
    
    only_in_variant = {}
    for i, names in enumerate(variant_names, 1):
        normalized_names = set(names.keys())
        unique_normalized = normalized_names - common_normalized
        only_in_variant[i] = [names[n] for n in sorted(unique_normalized)]
    
    return VariableDiff(common=common, only_in_variant=only_in_variant)


def _compare_submodules(fingerprints: list[ModuleFingerprint]) -> SubmoduleDiff:
    """Compare complete submodule tree structures across variants (recursive)."""
    variant_structures = []
    
    for fp in fingerprints:
        # Get the full recursive tree structure
        structure = _get_submodule_tree_structure(fp.submodules)
        variant_structures.append(structure)
    
    # Find common elements (intersection of all variant structures)
    if variant_structures:
        common_set = variant_structures[0].copy()
        for structure in variant_structures[1:]:
            common_set &= structure
        common = sorted(common_set)  # Sort by depth, then name
    else:
        common = []
    
    # Find unique elements in each variant
    only_in_variant = {}
    for i, structure in enumerate(variant_structures, 1):
        unique = structure - common_set
        only_in_variant[i] = sorted(unique)
    
    return SubmoduleDiff(common=common, only_in_variant=only_in_variant)


def _compare_code(fingerprints: list[ModuleFingerprint]) -> CodeDiff:
    """Compare module code (sequences and equations) across variants."""
    variant_seqs = []
    variant_eqs = []
    
    for fp in fingerprints:
        seqs = {_normalize_name(s.name): s.name for s in fp.sequences}
        eqs = {_normalize_name(e.name): e.name for e in fp.equations}
        variant_seqs.append(seqs)
        variant_eqs.append(eqs)
    
    # Sequences
    if variant_seqs:
        common_seq_normalized = set(variant_seqs[0].keys())
        for seqs in variant_seqs[1:]:
            common_seq_normalized &= set(seqs.keys())
        common_seqs = [variant_seqs[0][n] for n in sorted(common_seq_normalized)]
    else:
        common_seqs = []
    
    only_seqs = {}
    for i, seqs in enumerate(variant_seqs, 1):
        normalized = set(seqs.keys())
        unique = normalized - common_seq_normalized
        only_seqs[i] = [seqs[n] for n in sorted(unique)]
    
    # Equations
    if variant_eqs:
        common_eq_normalized = set(variant_eqs[0].keys())
        for eqs in variant_eqs[1:]:
            common_eq_normalized &= set(eqs.keys())
        common_eqs = [variant_eqs[0][n] for n in sorted(common_eq_normalized)]
    else:
        common_eqs = []
    
    only_eqs = {}
    for i, eqs in enumerate(variant_eqs, 1):
        normalized = set(eqs.keys())
        unique = normalized - common_eq_normalized
        only_eqs[i] = [eqs[n] for n in sorted(unique)]
    
    return CodeDiff(
        sequences_common=common_seqs,
        sequences_only_in_variant=only_seqs,
        equations_common=common_eqs,
        equations_only_in_variant=only_eqs,
    )


def _hash_variable_list(variables: list[Variable]) -> int:
    """Create a hash representing the structure of a variable list."""
    parts = []
    for v in variables:
        parts.append((
            _normalize_name(v.name),  # case-insensitive
            v.datatype_text,
            v.global_var,
            v.const,
            v.state,
            v.opsave,
            v.secure,
            repr(v.init_value),
        ))
    return hash(tuple(sorted(parts)))


def _hash_parameter_mappings(mappings: list[ParameterMapping]) -> int:
    """Create a hash representing parameter mappings."""
    parts = []
    for pm in mappings:
        target_str = pm.target.get("var_name") if isinstance(pm.target, dict) else str(pm.target)
        source_str = None
        if pm.source:
            source_str = pm.source.get("var_name") if isinstance(pm.source, dict) else str(pm.source)
        parts.append((
            _normalize_name(target_str),  # case-insensitive
            pm.source_type,
            pm.is_duration,
            pm.is_source_global,
            _normalize_name(source_str) if source_str else None,
            repr(pm.source_literal),
        ))
    return hash(tuple(sorted(parts)))


def _hash_submodules(submodules: list[SingleModule | FrameModule | ModuleTypeInstance]) -> int:
    """Create a hash representing the complete recursive submodule structure."""
    structure = _get_submodule_tree_structure(submodules)
    return hash(frozenset(structure))


def _hash_code(sequences: list[Sequence], equations: list[Equation]) -> int:
    """Create a hash representing code structure."""
    seq_parts = [_normalize_name(s.name) for s in sequences]
    eq_parts = [_normalize_name(e.name) for e in equations]
    return hash((tuple(sorted(seq_parts)), tuple(sorted(eq_parts))))


def create_fingerprint(module: SingleModule, path: list[str]) -> ModuleFingerprint:
    """Create a fingerprint for a SingleModule."""
    sequences = module.modulecode.sequences if module.modulecode and module.modulecode.sequences else []
    equations = module.modulecode.equations if module.modulecode and module.modulecode.equations else []
    
    return ModuleFingerprint(
        name=module.header.name,
        datecode=module.datecode,
        num_moduleparameters=len(module.moduleparameters),
        num_localvariables=len(module.localvariables),
        num_submodules=len(module.submodules),
        has_moduledef=module.moduledef is not None,
        has_modulecode=module.modulecode is not None,
        num_sequences=len(sequences),
        num_equations=len(equations),
        num_parameter_mappings=len(module.parametermappings),
        moduleparameters=module.moduleparameters,
        localvariables=module.localvariables,
        submodules=module.submodules,
        sequences=sequences,
        equations=equations,
        moduleparameters_hash=_hash_variable_list(module.moduleparameters),
        localvariables_hash=_hash_variable_list(module.localvariables),
        submodules_hash=_hash_submodules(module.submodules),
        parameter_mappings_hash=_hash_parameter_mappings(module.parametermappings),
        module=module,
        module_path=path.copy(),
    )


def _walk_modules(node: Any, target_name: str, current_path: list[str], results: list[tuple[list[str], SingleModule]], debug: bool = False) -> None:
    """Recursively find all SingleModule instances with the target name (case-insensitive)."""
    target_name_lower = target_name.lower()
    
    if debug:
        print(f"_walk_modules: checking node type={type(node).__name__}, path={current_path}")
    
    if isinstance(node, SingleModule):
        node_name = node.header.name
        node_name_lower = node_name.lower()
        
        if debug:
            print(f"  → SingleModule found: {node_name!r}, comparing with target={target_name!r}, match={node_name_lower == target_name_lower}")
        
        path_with_current = current_path + [node_name]
        
        if node_name_lower == target_name_lower:
            if debug:
                print(f"  ✓ MATCH! Adding to results")
            results.append((path_with_current, node))
        
        if debug:
            print(f"  → Checking {len(node.submodules)} submodules of {node_name!r}")
        for i, sub in enumerate(node.submodules):
            if debug:
                print(f"  → Submodule[{i}]: {type(sub).__name__}")
            _walk_modules(sub, target_name, path_with_current, results, debug)
            
    elif isinstance(node, FrameModule):
        node_name = node.header.name
        if debug:
            print(f"  → FrameModule: {node_name!r}")
        path_with_current = current_path + [node_name]
        
        if debug:
            print(f"  → Checking {len(node.submodules)} submodules of FrameModule {node_name!r}")
        for i, sub in enumerate(node.submodules):
            if debug:
                print(f"  → Submodule[{i}]: {type(sub).__name__}")
            _walk_modules(sub, target_name, path_with_current, results, debug)
    
    elif isinstance(node, ModuleTypeDef):
        node_name = node.name
        if debug:
            print(f"  → ModuleTypeDef: {node_name!r}")
            print(f"  → Has {len(node.submodules)} submodules")
        path_with_current = current_path + [f"ModuleTypeDef:{node_name}"]
        
        for i, sub in enumerate(node.submodules):
            if debug:
                print(f"  → Submodule[{i}]: {type(sub).__name__}")
            _walk_modules(sub, target_name, path_with_current, results, debug)
            
    elif isinstance(node, BasePicture):
        if debug:
            print(f"  → BasePicture: {node.name!r}")
            print(f"  → Has {len(node.submodules)} direct submodules")
            print(f"  → Has {len(node.moduletype_defs)} moduletype_defs")
        
        for i, sub in enumerate(node.submodules):
            if debug:
                print(f"  → Submodule[{i}]: {type(sub).__name__}")
            _walk_modules(sub, target_name, current_path, results, debug)
        
        for i, mtd in enumerate(node.moduletype_defs):
            if debug:
                print(f"  → ModuleTypeDef[{i}]: {mtd.name!r}")
            _walk_modules(mtd, target_name, current_path, results, debug)
            
    elif isinstance(node, ModuleTypeInstance):
        if debug:
            print(f"  → ModuleTypeInstance: {node.header.name!r} (no submodules)")
        pass
    else:
        if debug:
            print(f"  → Unknown node type: {type(node).__name__}")


def find_modules_by_name(base_picture: BasePicture, target_name: str, debug: bool = False) -> list[tuple[list[str], SingleModule]]:
    """Find all SingleModule instances with the given name, returning path and module."""
    if debug:
        print(f"\n=== SEARCHING FOR '{target_name}' ===")
    
    results: list[tuple[list[str], SingleModule]] = []
    _walk_modules(base_picture, target_name, [base_picture.name], results, debug)
    
    if debug:
        print(f"=== SEARCH COMPLETE: Found {len(results)} matches ===\n")
    
    return results


def compare_modules(modules_with_paths: list[tuple[list[str], SingleModule]]) -> ComparisonResult:
    """Compare a list of SingleModules and identify differences."""
    if not modules_with_paths:
        return ComparisonResult(
            module_name="<none>",
            total_found=0,
            unique_variants=0,
        )
    
    module_name = modules_with_paths[0][1].header.name
    
    # Create fingerprints with paths
    instances_with_fps = [(path, create_fingerprint(m, path)) for path, m in modules_with_paths]
    
    # Group by structural similarity (EXCLUDE datecode from key)
    variant_groups: dict[tuple, list[tuple[list[str], ModuleFingerprint]]] = defaultdict(list)
    for path, fp in instances_with_fps:
        key = (
            # REMOVED: fp.datecode
            fp.num_moduleparameters,
            fp.num_localvariables,
            fp.num_submodules,
            fp.num_sequences,
            fp.num_equations,
            fp.moduleparameters_hash,
            fp.localvariables_hash,
            fp.submodules_hash,
            fp.parameter_mappings_hash,
            _hash_code(fp.sequences, fp.equations),
        )
        variant_groups[key].append((path, fp))
    
    # Get one representative fingerprint per variant
    unique_fingerprints = [group[0][1] for group in variant_groups.values()]
    
    # Compute detailed diffs if there are multiple variants
    param_diff = None
    localvar_diff = None
    submodule_diff = None
    code_diff = None
    
    if len(unique_fingerprints) > 1:
        param_diff = _compare_variable_lists(unique_fingerprints)
        localvar_diff = _compare_localvars(unique_fingerprints)
        submodule_diff = _compare_submodules(unique_fingerprints)
        code_diff = _compare_code(unique_fingerprints)
    
    return ComparisonResult(
        module_name=module_name,
        total_found=len(modules_with_paths),
        unique_variants=len(unique_fingerprints),
        fingerprints=unique_fingerprints,
        all_instances=instances_with_fps,
        parameter_diff=param_diff,
        localvar_diff=localvar_diff,
        submodule_diff=submodule_diff,
        code_diff=code_diff,
    )


def analyze_module_duplicates(base_picture: BasePicture, module_name: str, debug: bool = False) -> ComparisonResult:
    """Main entry point: find and compare all SingleModules with the given name."""
    modules_with_paths = find_modules_by_name(base_picture, module_name, debug)
    return compare_modules(modules_with_paths)