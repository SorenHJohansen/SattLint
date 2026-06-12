"""Architecture linter: enforces layered domain architecture and dependency rules."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattlint import cli_output

from ..repo_paths import repo_root_from
from .artifact_registry import LAYER_LINT_POLICY_FILENAME, POLICY_KIND, POLICY_SCHEMA_VERSION

# Define the layers based on SattLint architecture from AGENTS.md and docs/public/architecture.md
# Dependencies must only flow from higher layer number to lower (or same).
# Layer 0: sattline_parser  - grammar, AST, transformer
# Layer 1: sattlint.models / types - pure data containers, enums, semantic aliases
# Layer 4: sattlint runtime        - semantic core, resolution, analyzers, app orchestration,
#                                    reporting, and shared helpers
# Layer 5: reserved
# Layer 6: reserved
# Layer 7: sattlint_lsp        - language server
# Layer 8: vscode              - VS Code extension client
# Layer 9: sattlint.devtools   - tooling-only; must not be imported by layers 0-7

LAYER_MAP = {
    "sattline_parser": 0,
    "sattlint.models": 1,
    "sattlint.types": 1,
    "sattlint.core": 4,
    "sattlint.resolution": 4,
    "sattlint.analyzers": 4,
    "sattlint.reporting": 4,
    "sattlint": 4,
    "sattlint_lsp": 7,
    "vscode": 8,
    "sattlint.devtools": 9,
}

REPO_ROOT = repo_root_from(Path(__file__))
POLICY_PATH = REPO_ROOT / "metrics" / LAYER_LINT_POLICY_FILENAME

# Allowed dependencies: a layer can depend on same layer or lower layers (lower number)
# We'll compute allowed dependencies dynamically from LAYER_MAP

# Also define some specific known good dependencies that might cross layers in a controlled way
# For now, we rely on the layer numbering.


@dataclass
class ArchViolation:
    file: str
    line: int
    message: str
    current_module: str = ""
    imported_module: str = ""
    violation_kind: str = ""
    policy_owner: str | None = None
    forbidden_import: str | None = None


@dataclass(frozen=True)
class LayerLintPolicy:
    forbidden_imports: dict[str, tuple[str, ...]]
    path: str


def _matches_module_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(prefix + ".")


def load_policy(policy_path: Path = POLICY_PATH) -> LayerLintPolicy:
    if not policy_path.exists():
        return LayerLintPolicy(forbidden_imports={}, path=str(policy_path))

    payload_obj = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise ValueError(f"{policy_path} must contain a JSON object.")
    payload = cast(dict[str, object], payload_obj)
    if payload.get("kind") != POLICY_KIND:
        raise ValueError(f"{policy_path} kind must be {POLICY_KIND!r}.")
    if payload.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError(f"{policy_path} schema_version must be {POLICY_SCHEMA_VERSION}.")

    raw_rules_obj = payload.get("forbidden_imports")
    if not isinstance(raw_rules_obj, dict):
        raise ValueError(f"{policy_path} forbidden_imports must be a JSON object.")
    raw_rules = cast(dict[object, object], raw_rules_obj)

    normalized_rules: dict[str, tuple[str, ...]] = {}
    for raw_owner, raw_rule_obj in raw_rules.items():
        if not isinstance(raw_owner, str) or not raw_owner.strip():
            raise ValueError(f"{policy_path} forbidden_imports keys must be non-empty strings.")
        if not isinstance(raw_rule_obj, dict):
            raise ValueError(f"{policy_path} rule for {raw_owner!r} must be a JSON object.")
        raw_rule = cast(dict[str, object], raw_rule_obj)
        cannot_import_obj = raw_rule.get("cannot_import")
        if not isinstance(cannot_import_obj, list):
            raise ValueError(f"{policy_path} rule for {raw_owner!r} must include a cannot_import list.")
        normalized_forbidden: list[str] = []
        cannot_import = cast(list[object], cannot_import_obj)
        for entry in cannot_import:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(f"{policy_path} cannot_import entries for {raw_owner!r} must be non-empty strings.")
            normalized_forbidden.append(entry.strip())
        normalized_rules[raw_owner.strip()] = tuple(normalized_forbidden)

    return LayerLintPolicy(forbidden_imports=normalized_rules, path=str(policy_path))


def _resolve_current_module(file_path: Path, *, repo_root: Path | None = None) -> tuple[str, int]:
    """Resolve the current module name and owning layer from a repo-relative file path."""
    rel_path = file_path.relative_to(Path.cwd() if repo_root is None else repo_root)
    parts = list(rel_path.parts)
    if not parts:
        return ".", -1

    source_root = parts[0]
    if source_root == "src" and len(parts) > 1:
        module_parts = parts[1:]
    elif source_root == "vscode":
        module_parts = parts[1:] if len(parts) > 1 else []
    else:
        module_parts = parts

    if module_parts and module_parts[-1].endswith(".py"):
        module_parts[-1] = module_parts[-1][:-3]
    if module_parts and module_parts[-1] == "__init__":
        module_parts = module_parts[:-1]

    current_module = ".".join(module_parts) or "."
    current_layer_key = current_module if source_root == "src" else source_root
    return current_module, get_layer_for_module(current_layer_key)


def get_layer_for_module(module_name: str) -> int:
    """Get the layer number for a given module name."""
    # Check for exact matches first
    if module_name in LAYER_MAP:
        return LAYER_MAP[module_name]

    # Sort by prefix length descending so the most specific prefix wins
    # (e.g. sattlint.devtools before sattlint)
    for prefix, layer in sorted(LAYER_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if module_name.startswith(prefix + ".") or module_name == prefix:
            return layer

    # Unknown/external module
    return -1


def _resolve_import_from_base(
    current_module: str,
    *,
    module_name: str | None,
    level: int,
    current_is_package: bool,
) -> str | None:
    if level == 0:
        return module_name

    if current_module in {"", "."}:
        return None

    package_parts = current_module.split(".") if current_is_package else current_module.split(".")[:-1]
    parent_hops = level - 1
    if parent_hops > len(package_parts):
        return None

    base_parts = package_parts[: len(package_parts) - parent_hops]
    if module_name:
        base_parts.extend(module_name.split("."))
    return ".".join(base_parts)


def _import_target_candidates(
    current_module: str,
    node: ast.ImportFrom,
    imported_name: str,
    *,
    current_is_package: bool,
) -> tuple[str, ...]:
    base_module = _resolve_import_from_base(
        current_module,
        module_name=node.module,
        level=node.level,
        current_is_package=current_is_package,
    )
    if not base_module:
        return ()

    candidates: list[str] = []
    if imported_name != "*":
        candidates.append(f"{base_module}.{imported_name}")
    candidates.append(base_module)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return tuple(deduped)


def _policy_violation(
    *,
    file_path: Path,
    line: int,
    current_module: str,
    imported_module: str,
    owner_prefix: str,
    forbidden_prefix: str,
) -> ArchViolation:
    return ArchViolation(
        file=str(file_path),
        line=line,
        message=(
            "Forbidden import policy violation: "
            f"{current_module} imports {imported_module} "
            f"(matched rule {owner_prefix} cannot import {forbidden_prefix})."
        ),
        current_module=current_module,
        imported_module=imported_module,
        violation_kind="policy",
        policy_owner=owner_prefix,
        forbidden_import=forbidden_prefix,
    )


def _layer_violation(
    *,
    file_path: Path,
    line: int,
    current_module: str,
    current_layer: int,
    imported_module: str,
    imported_layer: int,
) -> ArchViolation:
    return ArchViolation(
        file=str(file_path),
        line=line,
        message=(
            "Layer violation: "
            f"{current_module} (layer {current_layer}) imports {imported_module} (layer {imported_layer})."
        ),
        current_module=current_module,
        imported_module=imported_module,
        violation_kind="layer",
    )


def _check_import_target(
    *,
    file_path: Path,
    line: int,
    current_module: str,
    current_layer: int,
    imported_module: str,
    policy: LayerLintPolicy,
) -> ArchViolation | None:
    for owner_prefix, forbidden_prefixes in policy.forbidden_imports.items():
        if not _matches_module_prefix(current_module, owner_prefix):
            continue
        for forbidden_prefix in forbidden_prefixes:
            if _matches_module_prefix(imported_module, forbidden_prefix):
                return _policy_violation(
                    file_path=file_path,
                    line=line,
                    current_module=current_module,
                    imported_module=imported_module,
                    owner_prefix=owner_prefix,
                    forbidden_prefix=forbidden_prefix,
                )

    imported_layer = get_layer_for_module(imported_module)
    if imported_layer != -1 and current_layer != -1 and imported_layer > current_layer:
        return _layer_violation(
            file_path=file_path,
            line=line,
            current_module=current_module,
            current_layer=current_layer,
            imported_module=imported_module,
            imported_layer=imported_layer,
        )

    return None


def check_file_for_arch_violations(
    file_path: Path,
    *,
    repo_root: Path | None = None,
    content: str | None = None,
    tree: ast.AST | None = None,
    policy: LayerLintPolicy | None = None,
) -> list[ArchViolation]:
    """Check a single Python file for architecture violations."""
    violations: list[ArchViolation] = []
    try:
        resolved_policy = load_policy() if policy is None else policy
        source_text = content
        if source_text is None:
            with open(file_path, encoding="utf-8") as f:
                source_text = f.read()

        parsed_tree = ast.parse(source_text) if tree is None else tree

        # Get the module name of the current file
        # We'll compute relative to src/ or vscode/ root
        try:
            if repo_root is None:
                current_module, current_layer = _resolve_current_module(file_path)
            else:
                current_module, current_layer = _resolve_current_module(file_path, repo_root=repo_root)
        except ValueError:
            # File is not under current working directory, skip
            return violations

        current_is_package = file_path.name == "__init__.py"

        # Visit all imports
        for node in ast.walk(parsed_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    violation = _check_import_target(
                        file_path=file_path,
                        line=node.lineno,
                        current_module=current_module,
                        current_layer=current_layer,
                        imported_module=alias.name,
                        policy=resolved_policy,
                    )
                    if violation is not None:
                        violations.append(violation)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    for imported_module in _import_target_candidates(
                        current_module,
                        node,
                        alias.name,
                        current_is_package=current_is_package,
                    ):
                        violation = _check_import_target(
                            file_path=file_path,
                            line=node.lineno,
                            current_module=current_module,
                            current_layer=current_layer,
                            imported_module=imported_module,
                            policy=resolved_policy,
                        )
                        if violation is not None:
                            violations.append(violation)
                            break
    except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
        violations.append(
            ArchViolation(
                file=str(file_path),
                line=0,
                message=f"Failed to parse file for architecture check: {exc}",
            )
        )
        return violations

    return violations


def find_python_files(root_dirs: list[Path]) -> list[Path]:
    """Find all Python files in the given root directories."""
    python_files: list[Path] = []
    for root in root_dirs:
        if root.exists():
            python_files.extend(root.rglob("*.py"))
    return python_files


def collect_architecture_violations(
    root_dirs: list[Path],
    *,
    repo_root: Path | None = None,
    policy_path: Path | None = None,
) -> list[ArchViolation]:
    try:
        policy = load_policy(POLICY_PATH if policy_path is None else policy_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        failed_policy_path = POLICY_PATH if policy_path is None else policy_path
        return [
            ArchViolation(
                file=str(failed_policy_path),
                line=0,
                message=f"Failed to load layer-lint policy: {type(exc).__name__}: {exc}",
                violation_kind="policy-load-error",
            )
        ]

    all_violations: list[ArchViolation] = []
    for file_path in find_python_files(root_dirs):
        all_violations.extend(
            check_file_for_arch_violations(
                file_path,
                repo_root=repo_root,
                policy=policy,
            )
        )
    return all_violations


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run architecture linting on the codebase.")
    cli_output.add_output_format_argument(
        parser,
        help_text="Output format for stdout summary.",
    )
    return parser


def _build_cli_report(violations: list[ArchViolation]) -> dict[str, Any]:
    return {
        "status": "fail" if violations else "pass",
        "violation_count": len(violations),
        "violations": [
            {
                "file": violation.file,
                "line": violation.line,
                "message": violation.message,
                "current_module": violation.current_module,
                "imported_module": violation.imported_module,
                "violation_kind": violation.violation_kind,
                "policy_owner": violation.policy_owner,
                "forbidden_import": violation.forbidden_import,
            }
            for violation in violations
        ],
    }


def _render_cli_summary(report: dict[str, Any]) -> str:
    if report["violation_count"] == 0:
        return "No architecture violations found."
    lines = [f"Found {report['violation_count']} architecture violations:"]
    for violation in cast(list[dict[str, Any]], report["violations"]):
        lines.append(f"  {violation['file']}:{violation['line']} - {violation['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """Run architecture linting on the codebase."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    output_format = cli_output.resolve_output_format(args)
    # Define the roots of our source code
    roots = [
        Path("src"),
        Path("vscode"),
    ]

    all_violations = collect_architecture_violations(roots, repo_root=REPO_ROOT)
    report = _build_cli_report(all_violations)
    cli_output.emit_text_or_json(
        text=_render_cli_summary(report),
        json_payload=report,
        output_format=output_format,
        emit_text_fn=print,
    )
    sys.exit(1 if all_violations else 0)


if __name__ == "__main__":
    main()
