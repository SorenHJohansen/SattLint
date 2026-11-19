# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportAttributeAccessIssue=false
"""AST/import-graph dependency guard for the layered ownership rules.

Forbids the cross-layer edges listed in the architecture-upgrade plan
(mechanical enforcement): layer code may only depend on the allowed layers.
A violation fails the suite via plain ``assert``, independent of grep.
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Iterator
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "sattlint"

# Maps a source layer directory to the root-level import targets it must never use.
# Targets without a dot are matched as the first dotted segment (e.g. "cli" also
# bans "cli.app_commands"); "app_"/"_app_" ban the legacy flat facade modules.
_FORBIDDEN_LAYER_LINKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("application", ("app", "app_", "_app_")),
    ("core", ("analyzers", "application", "cli")),
    ("project", ("application", "cli")),
    ("resolution", ("application", "project")),
    ("analyzers", ("application",)),
)


def _module_dotted_name(path: Path) -> str:
    """Absolute dotted module name, so relative imports resolve to ``sattlint.*``."""
    rel = path.relative_to(SRC_DIR)
    return ".".join(("sattlint", *rel.with_suffix("").parts))


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


def _import_nodes(module: ast.Module) -> Iterator[ast.Import | ast.ImportFrom]:
    """Every import in the module, including nested and ``TYPE_CHECKING`` ones."""
    for node in ast.walk(module):
        if isinstance(node, ast.Import | ast.ImportFrom):
            yield node


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
            for node in _import_nodes(module):
                for imported in _resolve_imports(node, base_dotted):
                    for target in forbidden_targets:
                        if _hits_target(imported, target):
                            violations.append(f"{path.relative_to(SRC_DIR)}: imports {imported} (forbidden: {target})")

    assert violations == []


def test_guard_resolves_multi_level_relative_imports() -> None:
    module = ast.parse(
        textwrap.dedent(
            """
            from ...project.loading import load_program_ast
            from ..project.loading_support import record_project_warning
            """
        )
    )

    nested = {
        name for node in _import_nodes(module) for name in _resolve_imports(node, "sattlint.analyzers.icf.analyzer")
    }
    sibling = {
        name for node in _import_nodes(module) for name in _resolve_imports(node, "sattlint.graphics.graphics_helpers")
    }

    assert "sattlint.project.loading.load_program_ast" in nested
    assert "sattlint.project.loading_support.record_project_warning" in sibling


def test_guard_sees_imports_nested_in_type_checking_and_functions() -> None:
    module = ast.parse(
        textwrap.dedent(
            """
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from sattlint.cli import startup

            def load() -> None:
                from sattlint.core.syntax import parse_source_file
            """
        )
    )
    imported = {name for node in _import_nodes(module) for name in _resolve_imports(node, "sattlint.core.example")}
    assert "sattlint.cli.startup" in imported
    assert "sattlint.core.syntax.parse_source_file" in imported


_PROJECT_LOADER_LAYERS = ("core", "models", "resolution", "graphics", "analyzers")
_PROJECT_LOADER_TARGETS = (
    "project.loading",
    "project.loader_config",
    "project.loading_support",
    "project.parser_adapter",
)
#: Non-loader layers that still reach the loader today. Any new edge fails this
#: test instead of slipping past the layer table above.
_PROJECT_LOADER_EDGE_EXCEPTIONS = {
    "analyzers/icf/analyzer.py",
    "graphics/graphics_helpers.py",
}


def test_only_the_documented_layers_reach_the_project_loader() -> None:
    found: set[str] = set()
    for layer_dir in _PROJECT_LOADER_LAYERS:
        for path in sorted((SRC_DIR / layer_dir).rglob("*.py")):
            base_dotted = _module_dotted_name(path)
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in _import_nodes(module):
                for imported in _resolve_imports(node, base_dotted):
                    if any(_hits_target(imported, target) for target in _PROJECT_LOADER_TARGETS):
                        found.add(path.relative_to(SRC_DIR).as_posix())
                        break
                else:
                    continue
                break

    assert found == _PROJECT_LOADER_EDGE_EXCEPTIONS


def test_analyzers_use_only_the_public_reporting_surface() -> None:
    violations: list[str] = []
    analyzers_root = SRC_DIR / "analyzers"
    for path in sorted(analyzers_root.rglob("*.py")):
        base_dotted = _module_dotted_name(path)
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _import_nodes(module):
            for imported in _resolve_imports(node, base_dotted):
                if imported.startswith("sattlint.reporting._"):
                    violations.append(f"{path.relative_to(SRC_DIR)}: imports reporting internals {imported}")

    assert violations == []


def test_engine_is_not_imported_below_the_top_layers() -> None:
    # The project loader is the only path into the parser. A second top-level
    # orchestration module must not reappear; every layer reaches the loader
    # through ``project`` instead.
    violations: list[str] = []
    for path in sorted(SRC_DIR.rglob("*.py")):
        if path.name in {"__init__.py"}:
            continue
        base_dotted = _module_dotted_name(path)
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _import_nodes(module):
            for imported in _resolve_imports(node, base_dotted):
                if _hits_target(imported, "engine"):
                    violations.append(f"{path.relative_to(SRC_DIR)}: imports {imported} (forbidden: engine)")

    assert violations == []
