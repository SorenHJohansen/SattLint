# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportAttributeAccessIssue=false
"""AST/import-graph dependency guard for the layered ownership rules.

Forbids the cross-layer edges listed in the architecture-upgrade plan
(mechanical enforcement): layer code may only depend on the allowed layers.
A violation fails the suite via plain ``assert``, independent of grep.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "sattlint"

# Maps a source layer directory to the root-level import targets it must never use.
# Targets without a dot are matched as the first dotted segment (e.g. "cli" also
# bans "cli.app_commands"); "app_"/"_app_" ban the legacy flat facade modules.
_FORBIDDEN_LAYER_LINKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("application", ("app", "app_", "_app_")),
    ("core", ("application", "cli")),
    ("project", ("application", "cli")),
    ("resolution", ("application", "project")),
    ("analyzers", ("application",)),
)


def _module_dotted_name(path: Path) -> str:
    rel = path.relative_to(SRC_DIR)
    return ".".join(rel.with_suffix("").parts)


def _resolve_imports(node: ast.AST, base_dotted: str) -> set[str]:
    resolved: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            resolved.add(alias.name)
    elif isinstance(node, ast.ImportFrom):
        prefix_parts = base_dotted.split(".")
        root = ".".join(prefix_parts[: -node.level]) if node.level > 0 and node.level <= len(prefix_parts) else ""
        if node.module:
            resolved.add(node.module)
            if root:
                resolved.add(f"{root}.{node.module}")
        elif root:
            resolved.add(root)
        for alias in node.names:
            if node.module:
                resolved.add(f"{node.module}.{alias.name}")
                if root:
                    resolved.add(f"{root}.{node.module}.{alias.name}")
            elif root:
                resolved.add(f"{root}.{alias.name}")
    return resolved


def _hits_target(module_name: str, target: str) -> bool:
    if not module_name.startswith("sattlint."):
        return False
    rest = module_name[len("sattlint.") :]
    return rest == target or rest.startswith(f"{target}.")


def test_forbidden_layer_links_are_absent() -> None:
    violations: list[str] = []
    for layer_dir, forbidden_targets in _FORBIDDEN_LAYER_LINKS:
        layer_root = SRC_DIR / layer_dir
        for path in sorted(layer_root.rglob("*.py")):
            base_dotted = _module_dotted_name(path)
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in module.body:
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                for imported in _resolve_imports(node, base_dotted):
                    for target in forbidden_targets:
                        if _hits_target(imported, target):
                            violations.append(f"{path.relative_to(SRC_DIR)}: imports {imported} (forbidden: {target})")

    assert violations == []


def test_analyzers_use_only_the_public_reporting_surface() -> None:
    violations: list[str] = []
    analyzers_root = SRC_DIR / "analyzers"
    for path in sorted(analyzers_root.rglob("*.py")):
        base_dotted = _module_dotted_name(path)
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in module.body:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for imported in _resolve_imports(node, base_dotted):
                if imported.startswith("sattlint.reporting._"):
                    violations.append(f"{path.relative_to(SRC_DIR)}: imports reporting internals {imported}")

    assert violations == []
