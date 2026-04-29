"""Architecture linter: enforces layered domain architecture and dependency rules."""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

# Define the layers based on SattLint architecture from AGENTS.md
# We define layers such that dependencies should only go from higher layer number to lower (or same)
# Layer 0: Foundational (parser)
# Layer 1: Core semantics
# Layer 2: CLI and tools
# Layer 3: LSP
# Layer 4: VS Code client

LAYER_MAP = {
    "sattline_parser": 0,
    "sattlint.core": 1,
    "sattlint": 2,
    "sattlint_lsp": 3,
    "vscode": 4,
}

# Allowed dependencies: a layer can depend on same layer or lower layers (lower number)
# We'll compute allowed dependencies dynamically from LAYER_MAP

# Also define some specific known good dependencies that might cross layers in a controlled way
# For now, we rely on the layer numbering.


@dataclass
class ArchViolation:
    file: str
    line: int
    message: str


def get_layer_for_module(module_name: str) -> int:
    """Get the layer number for a given module name."""
    # Check for exact matches first
    if module_name in LAYER_MAP:
        return LAYER_MAP[module_name]

    # Check for parent package matches
    for prefix, layer in LAYER_MAP.items():
        if module_name.startswith(prefix + ".") or module_name == prefix:
            return layer

    # If not found, assume it's an external or unknown layer (we'll treat as layer -1 for safety)
    return -1


def check_file_for_arch_violations(file_path: Path) -> list[ArchViolation]:
    """Check a single Python file for architecture violations."""
    violations = []
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        # Get the module name of the current file
        # We'll compute relative to src/ or vscode/ root
        try:
            rel_path = file_path.relative_to(Path.cwd())
            # Convert path to module name
            parts = list(rel_path.parts)
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]  # Remove .py
            # If it's __init__.py, we remove it and use the directory as module
            if parts[-1] == "__init__":
                parts = parts[:-1]
            current_module = ".".join(parts)
            # If the module is empty (e.g., file is at root), we skip
            if not current_module:
                current_module = "."  # placeholder
        except ValueError:
            # File is not under current working directory, skip
            return violations

        current_layer = get_layer_for_module(current_module.split(".")[0] if "." in current_module else current_module)

        # Visit all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    # Skip external modules (not starting with our packages)
                    if not any(module_name.startswith(pkg) for pkg in LAYER_MAP):
                        continue
                    imported_layer = get_layer_for_module(
                        module_name.split(".")[0] if "." in module_name else module_name
                    )
                    if imported_layer != -1 and current_layer != -1 and imported_layer > current_layer:
                        violations.append(
                            ArchViolation(
                                file=str(file_path),
                                line=node.lineno,
                                message=f"Invalid dependency: {current_module} (layer {current_layer}) imports {module_name} (layer {imported_layer}). Fix: move code to same or lower layer, or introduce interface in Providers layer.",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    # Relative import, we'll assume it's okay for now (same layer or parent)
                    continue
                module_name = node.module
                # Skip external modules
                if not any(module_name.startswith(pkg) for pkg in LAYER_MAP):
                    continue
                imported_layer = get_layer_for_module(module_name.split(".")[0] if "." in module_name else module_name)
                if imported_layer != -1 and current_layer != -1 and imported_layer > current_layer:
                    violations.append(
                        ArchViolation(
                            file=str(file_path),
                            line=node.lineno,
                            message=f"Invalid dependency: {current_module} (layer {current_layer}) imports from {module_name} (layer {imported_layer}). Fix: move code to same or lower layer, or introduce interface in Providers layer.",
                        )
                    )
    except Exception:
        # If we can't parse the file, skip it (but we might want to log this)
        pass

    return violations


def find_python_files(root_dirs: list[Path]) -> list[Path]:
    """Find all Python files in the given root directories."""
    python_files = []
    for root in root_dirs:
        if root.exists():
            python_files.extend(root.rglob("*.py"))
    return python_files


def main() -> None:
    """Run architecture linting on the codebase."""
    # Define the roots of our source code
    roots = [
        Path("src"),
        Path("vscode"),
    ]

    python_files = find_python_files(roots)

    all_violations = []
    for file_path in python_files:
        violations = check_file_for_arch_violations(file_path)
        all_violations.extend(violations)

    if all_violations:
        print(f"Found {len(all_violations)} architecture violations:")
        for v in all_violations:
            print(f"  {v.file}:{v.line} - {v.message}")
        sys.exit(1)
    else:
        print("No architecture violations found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
