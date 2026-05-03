from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RATCHET_PATH = REPO_ROOT / "metrics" / "ratchet.json"
SETTINGS_PATH = REPO_ROOT / ".vscode" / "settings.json"
EXTENSIONS_PATH = REPO_ROOT / ".vscode" / "extensions.json"
TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.MULTILINE)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _read_jsonc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    text = LINE_COMMENT_RE.sub("", text)
    text = TRAILING_COMMA_RE.sub(r"\1", text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _json_path(location: str, segment: str) -> str:
    if location == "$":
        return f"$.{segment}"
    return f"{location}.{segment}"


def _normalize_rel_path(path_text: str) -> str:
    return path_text.replace("\\", "/").strip().strip("/")


def _path_payloads(grouped_paths: dict[str, Any]) -> list[tuple[str, str]]:
    payloads: list[tuple[str, str]] = []
    for group_name, raw_paths in grouped_paths.items():
        if not isinstance(raw_paths, list):
            continue
        for path_text in raw_paths:
            if isinstance(path_text, str) and path_text.strip():
                payloads.append((group_name, _normalize_rel_path(path_text)))
    return payloads


def _collect_scoped_file_count(globs: Sequence[str]) -> int:
    seen: set[str] = set()
    for pattern in globs:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                seen.add(path.relative_to(REPO_ROOT).as_posix())
    return len(seen)


def _validate_against_schema(instance: Any, schema: dict[str, Any], *, location: str = "$") -> list[str]:
    errors: list[str] = []
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(instance, dict):
            return [f"{location}: expected object"]
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in instance:
                    errors.append(f"{location}: missing required property {key!r}")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{location}: unexpected property {key!r}")
        for key, value in instance.items():
            subschema = properties.get(key)
            if isinstance(key, str) and isinstance(subschema, dict):
                errors.extend(_validate_against_schema(value, subschema, location=_json_path(location, key)))
        return errors

    if schema_type == "array":
        if not isinstance(instance, list):
            return [f"{location}: expected array"]
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            errors.append(f"{location}: expected at least {min_items} item(s)")
        if schema.get("uniqueItems"):
            seen_items: set[str] = set()
            for item in instance:
                marker = json.dumps(item, sort_keys=True)
                if marker in seen_items:
                    errors.append(f"{location}: array items must be unique")
                    break
                seen_items.add(marker)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(_validate_against_schema(item, item_schema, location=f"{location}[{index}]"))
        return errors

    if schema_type == "string":
        if not isinstance(instance, str):
            return [f"{location}: expected string"]
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(f"{location}: expected minimum length {min_length}")
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and instance not in enum_values:
            errors.append(f"{location}: expected one of {enum_values!r}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{location}: value does not match pattern {pattern!r}")
        return errors

    return errors


def _ai_schema_targets() -> list[tuple[str, Path, Path]]:
    return [
        ("task contract", REPO_ROOT / ".ai" / "tasks" / "task-contract.schema.json", REPO_ROOT / ".ai" / "tasks"),
        ("handoff", REPO_ROOT / ".ai" / "handoffs" / "handoff.schema.json", REPO_ROOT / ".ai" / "handoffs"),
    ]


def _validate_ai_artifacts() -> tuple[list[dict[str, Any]], int]:
    issues: list[dict[str, Any]] = []
    validated_count = 0
    for label, schema_path, artifact_dir in _ai_schema_targets():
        if not schema_path.exists() or not artifact_dir.exists():
            continue
        try:
            schema = _read_json(schema_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(
                {
                    "id": "invalid-ai-schema-json",
                    "severity": "error",
                    "path": schema_path.relative_to(REPO_ROOT).as_posix(),
                    "message": f"{label.title()} schema could not be read: {type(exc).__name__}: {exc}",
                }
            )
            continue

        for artifact_path in sorted(artifact_dir.glob("*.json")):
            if artifact_path == schema_path:
                continue
            rel_path = artifact_path.relative_to(REPO_ROOT).as_posix()
            try:
                payload = _read_json(artifact_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(
                    {
                        "id": "invalid-ai-artifact-json",
                        "severity": "error",
                        "path": rel_path,
                        "message": f"{label.title()} artifact is not valid JSON: {type(exc).__name__}: {exc}",
                    }
                )
                continue

            validated_count += 1
            errors = _validate_against_schema(payload, schema)
            if errors:
                issues.append(
                    {
                        "id": "invalid-ai-artifact-schema",
                        "severity": "error",
                        "path": rel_path,
                        "message": f"{label.title()} artifact failed schema validation: {'; '.join(errors[:3])}",
                    }
                )
    return issues, validated_count


def build_report() -> dict[str, Any]:
    ratchet = _read_json(RATCHET_PATH)
    thresholds = ratchet.get("thresholds", {})
    required_paths = ratchet.get("required_paths", {})
    context_files = ratchet.get("context_files", {})
    optimizer = ratchet.get("context_optimizer", {})

    issues: list[dict[str, Any]] = []
    existing_required = 0
    required_payloads = _path_payloads(required_paths)
    for group_name, rel_path in required_payloads:
        path = REPO_ROOT / rel_path
        if path.exists():
            existing_required += 1
            continue
        issues.append(
            {
                "id": "missing-required-path",
                "severity": "error",
                "path": rel_path,
                "message": f"Required {group_name} path is missing.",
            }
        )

    auto_loaded_paths = [
        REPO_ROOT / _normalize_rel_path(path_text)
        for path_text in context_files.get("auto_loaded", [])
        if isinstance(path_text, str) and path_text.strip()
    ]
    auto_loaded_inventory: list[dict[str, Any]] = []
    auto_loaded_lines = 0
    for path in auto_loaded_paths:
        if not path.exists():
            issues.append(
                {
                    "id": "missing-auto-loaded-context",
                    "severity": "error",
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "message": "Configured auto-loaded context file is missing.",
                }
            )
            continue
        line_count = _line_count(path)
        auto_loaded_inventory.append(
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "lines": line_count,
            }
        )
        auto_loaded_lines += line_count

    auto_loaded_budget = int(thresholds.get("auto_loaded_context_max_lines", 180))
    if auto_loaded_lines > auto_loaded_budget:
        issues.append(
            {
                "id": "auto-loaded-context-over-budget",
                "severity": "error",
                "path": None,
                "message": (f"Auto-loaded context is {auto_loaded_lines} lines; budget is {auto_loaded_budget}."),
            }
        )

    agents_path = REPO_ROOT / "AGENTS.md"
    agents_max_lines = int(thresholds.get("agents_max_lines", 100))
    agents_lines = _line_count(agents_path) if agents_path.exists() else 0
    if agents_path.exists() and agents_lines > agents_max_lines:
        issues.append(
            {
                "id": "agents-over-budget",
                "severity": "error",
                "path": "AGENTS.md",
                "message": f"AGENTS.md is {agents_lines} lines; budget is {agents_max_lines}.",
            }
        )

    repo_map_path = REPO_ROOT / "docs" / "repo-map.md"
    repo_map_max_lines = int(thresholds.get("repo_map_max_lines", 220))
    repo_map_lines = _line_count(repo_map_path) if repo_map_path.exists() else 0
    if repo_map_path.exists() and repo_map_lines > repo_map_max_lines:
        issues.append(
            {
                "id": "repo-map-over-budget",
                "severity": "error",
                "path": "docs/repo-map.md",
                "message": f"docs/repo-map.md is {repo_map_lines} lines; budget is {repo_map_max_lines}.",
            }
        )

    settings = _read_jsonc(SETTINGS_PATH) if SETTINGS_PATH.exists() else {}
    extensions = _read_json(EXTENSIONS_PATH) if EXTENSIONS_PATH.exists() else {}
    recommended_extensions = {
        item for item in extensions.get("recommendations", []) if isinstance(item, str) and item.strip()
    }
    expected_extension = str(optimizer.get("extension_id", "")).strip()
    if expected_extension and expected_extension not in recommended_extensions:
        issues.append(
            {
                "id": "missing-context-optimizer-recommendation",
                "severity": "error",
                "path": ".vscode/extensions.json",
                "message": f"VS Code recommendations do not include {expected_extension}.",
            }
        )

    expected_threshold = int(thresholds.get("context_optimizer_auto_loaded_line_threshold", 80))
    actual_threshold = settings.get("contextOptimizer.autoLoadedLineThreshold")
    if actual_threshold != expected_threshold:
        issues.append(
            {
                "id": "context-optimizer-threshold-drift",
                "severity": "error",
                "path": ".vscode/settings.json",
                "message": ("VS Code context optimizer threshold does not match metrics/ratchet.json."),
            }
        )

    scoped_globs = [
        pattern for pattern in context_files.get("scoped_globs", []) if isinstance(pattern, str) and pattern.strip()
    ]
    scoped_file_count = _collect_scoped_file_count(scoped_globs)
    ai_artifact_issues, validated_ai_artifact_count = _validate_ai_artifacts()
    issues.extend(ai_artifact_issues)

    status = "pass" if not issues else "fail"
    return {
        "kind": "sattlint.context_health",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "metrics": {
            "required_path_count": len(required_payloads),
            "required_path_present_count": existing_required,
            "auto_loaded_context_lines": auto_loaded_lines,
            "auto_loaded_context_budget": auto_loaded_budget,
            "agents_lines": agents_lines,
            "agents_max_lines": agents_max_lines,
            "repo_map_lines": repo_map_lines,
            "repo_map_max_lines": repo_map_max_lines,
            "scoped_context_file_count": scoped_file_count,
            "validated_ai_artifact_count": validated_ai_artifact_count,
            "context_optimizer_recommended": expected_extension in recommended_extensions,
            "context_optimizer_auto_loaded_line_threshold": actual_threshold,
            "context_optimizer_expected_threshold": expected_threshold,
        },
        "inventory": {
            "auto_loaded": auto_loaded_inventory,
            "recommended_extensions": sorted(recommended_extensions),
        },
        "issues": issues,
        "recommended_commands": [
            "python scripts/context_health.py --check",
            "python scripts/repo_health.py --check --audit-dir artifacts/audit",
            "@context-optimizer /audit",
            "@context-optimizer /compare",
        ],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Context Health",
        "",
        f"- Status: {report['status']}",
        f"- Generated: {report['generated_at']}",
        f"- Required paths: {metrics['required_path_present_count']}/{metrics['required_path_count']}",
        (
            f"- Auto-loaded context: {metrics['auto_loaded_context_lines']}/"
            f"{metrics['auto_loaded_context_budget']} lines"
        ),
        f"- AGENTS.md: {metrics['agents_lines']}/{metrics['agents_max_lines']} lines",
        f"- docs/repo-map.md: {metrics['repo_map_lines']}/{metrics['repo_map_max_lines']} lines",
        f"- Scoped context files: {metrics['scoped_context_file_count']}",
        (f"- Context optimizer recommended: {'yes' if metrics['context_optimizer_recommended'] else 'no'}"),
        "",
        "## Issues",
        "",
    ]
    issues = report["issues"]
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            path_text = issue["path"] if issue["path"] is not None else "(repo)"
            lines.append(f"- {issue['id']}: {path_text} - {issue['message']}")
    lines.extend(["", "## Recommended Commands", ""])
    for command in report["recommended_commands"]:
        lines.append(f"- {command}")
    lines.append("")
    return "\n".join(lines)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AI-first context surfaces for SattLint.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when context health fails.")
    parser.add_argument("--json-output", type=Path, help="Write the JSON report to a file.")
    parser.add_argument("--markdown-output", type=Path, help="Write the Markdown report to a file.")
    parser.add_argument("--stdout-json", action="store_true", help="Print the JSON report instead of the text summary.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = build_report()

    if args.json_output is not None:
        _write_text(args.json_output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.markdown_output is not None:
        _write_text(args.markdown_output, _render_markdown(report))

    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        metrics = report["metrics"]
        print(f"Context health: {report['status']}")
        print(f"Required paths: {metrics['required_path_present_count']}/{metrics['required_path_count']}")
        print(
            f"Auto-loaded context: {metrics['auto_loaded_context_lines']}/{metrics['auto_loaded_context_budget']} lines"
        )
        print(f"Scoped context files: {metrics['scoped_context_file_count']}")
        print(f"Issues: {len(report['issues'])}")
        for issue in report["issues"]:
            path_text = issue["path"] if issue["path"] is not None else "(repo)"
            print(f"- {issue['id']}: {path_text}: {issue['message']}")

    return 1 if args.check and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
