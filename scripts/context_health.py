from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
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


def _first_nonempty_line(*chunks: str) -> str | None:
    for chunk in chunks:
        for line in chunk.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
    return None


def _collect_codegraph_health() -> dict[str, Any]:
    codegraph_dir = REPO_ROOT / ".codegraph"
    codegraph_config_path = codegraph_dir / "config.json"
    mcp_config_path = REPO_ROOT / ".vscode" / "mcp.json"

    index_present = codegraph_dir.exists()
    index_config_present = codegraph_config_path.exists()
    mcp_config_present = mcp_config_path.exists()
    mcp_server_configured = False
    mcp_uses_codegraph_cli = False
    mcp_command: str | None = None
    mcp_error: str | None = None

    if mcp_config_present:
        try:
            mcp_payload = _read_jsonc(mcp_config_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            mcp_error = f"{type(exc).__name__}: {exc}"
        else:
            servers = mcp_payload.get("servers", {})
            if isinstance(servers, dict):
                server_payload = servers.get("codegraph")
                if isinstance(server_payload, dict):
                    mcp_server_configured = True
                    raw_command = server_payload.get("command")
                    if isinstance(raw_command, str):
                        mcp_command = raw_command.strip() or None
                        mcp_uses_codegraph_cli = mcp_command == "codegraph"

    cli_path = shutil.which("codegraph")
    cli_available = cli_path is not None
    status_command_ok = False
    status_command_exit_code: int | None = None
    status_summary: str | None = None
    status_error: str | None = None
    status_command = ["codegraph", "status", str(REPO_ROOT)]

    if cli_available:
        try:
            result = subprocess.run(
                status_command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            status_error = f"{type(exc).__name__}: {exc}"
        else:
            status_command_exit_code = result.returncode
            status_command_ok = result.returncode == 0
            status_summary = _first_nonempty_line(result.stdout, result.stderr)

    if not index_present or not index_config_present:
        status = "degraded"
        recommended_route = "rebuild_codegraph"
        guidance = (
            "CodeGraph index files are missing. Rebuild or sync the index before using MCP queries; "
            "if that is not possible, fall back to grep_search, file_search, and targeted read_file calls."
        )
    elif not mcp_config_present or mcp_error is not None or not mcp_server_configured or not mcp_uses_codegraph_cli:
        status = "fallback_to_rg"
        recommended_route = "fallback_to_rg"
        guidance = (
            "CodeGraph MCP wiring is unavailable in this workspace. Skip MCP queries in this session and use "
            "grep_search, file_search, semantic_search, and targeted read_file calls instead."
        )
    elif not cli_available or status_error is not None:
        status = "fallback_to_rg"
        recommended_route = "fallback_to_rg"
        guidance = (
            "The local codegraph CLI is unavailable, so CodeGraph-first routing is unsafe here. Use grep_search, "
            "file_search, semantic_search, and targeted read_file calls instead."
        )
    elif not status_command_ok:
        status = "degraded"
        recommended_route = "sync_or_rebuild_codegraph"
        guidance = (
            "CodeGraph prerequisites are present, but `codegraph status` failed. Run the sync or rebuild task once, "
            "then recheck health before using MCP queries."
        )
    else:
        status = "healthy"
        recommended_route = "codegraph_first"
        guidance = "CodeGraph is ready. Run the health check once, then prefer CodeGraph tools before text search."

    recommended_commands = ["python scripts/context_health.py --check --section codegraph"]
    if recommended_route == "codegraph_first":
        recommended_commands.append(f"codegraph status {REPO_ROOT}")
    elif recommended_route in {"sync_or_rebuild_codegraph", "rebuild_codegraph"}:
        recommended_commands.extend([f"codegraph sync {REPO_ROOT}", f"codegraph index {REPO_ROOT}"])
    else:
        recommended_commands.extend(
            [
                "rg --files src tests scripts .github",
                'rg -n "symbol|class|def" src tests scripts .github',
            ]
        )

    return {
        "status": status,
        "recommended_route": recommended_route,
        "guidance": guidance,
        "index_present": index_present,
        "index_config_present": index_config_present,
        "mcp_config_present": mcp_config_present,
        "mcp_server_configured": mcp_server_configured,
        "mcp_uses_codegraph_cli": mcp_uses_codegraph_cli,
        "mcp_command": mcp_command,
        "mcp_error": mcp_error,
        "cli_available": cli_available,
        "cli_path": cli_path,
        "status_command": status_command,
        "status_command_ok": status_command_ok,
        "status_command_exit_code": status_command_exit_code,
        "status_summary": status_summary,
        "status_error": status_error,
        "recommended_commands": recommended_commands,
    }


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


def build_report(*, section: str | None = None) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    codegraph = _collect_codegraph_health()
    codegraph_issues: list[dict[str, Any]] = []
    if codegraph["status"] != "healthy":
        issue_path: str | None
        if codegraph["status"] == "degraded" and not codegraph["index_config_present"]:
            issue_path = ".codegraph/config.json"
        elif not codegraph["mcp_config_present"] or codegraph["mcp_error"] is not None:
            issue_path = ".vscode/mcp.json"
        else:
            issue_path = None
        summary_suffix = f" Detail: {codegraph['status_summary']}" if codegraph["status_summary"] else ""
        error_suffix = f" Detail: {codegraph['status_error']}" if codegraph["status_error"] else ""
        codegraph_issues.append(
            {
                "id": "codegraph-not-ready",
                "severity": "error",
                "path": issue_path,
                "message": f"{codegraph['guidance']}{summary_suffix}{error_suffix}",
            }
        )

    if section == "codegraph":
        return {
            "kind": "sattlint.context_health.codegraph",
            "schema_version": 1,
            "generated_at": generated_at,
            "status": codegraph["status"],
            "sections": {"codegraph": codegraph},
            "issues": codegraph_issues,
            "recommended_commands": codegraph["recommended_commands"],
        }

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
    issues.extend(codegraph_issues)

    status = "pass" if not issues else "fail"
    return {
        "kind": "sattlint.context_health",
        "schema_version": 1,
        "generated_at": generated_at,
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
            "codegraph_status": codegraph["status"],
            "codegraph_recommended_route": codegraph["recommended_route"],
        },
        "inventory": {
            "auto_loaded": auto_loaded_inventory,
            "recommended_extensions": sorted(recommended_extensions),
        },
        "sections": {
            "codegraph": codegraph,
        },
        "issues": issues,
        "recommended_commands": [
            "python scripts/context_health.py --check",
            "python scripts/context_health.py --check --section codegraph",
            "python scripts/repo_health.py --check --audit-dir artifacts/audit",
            "@context-optimizer /audit",
            "@context-optimizer /compare",
            *[
                command
                for command in codegraph["recommended_commands"]
                if command != "python scripts/context_health.py --check --section codegraph"
            ],
        ],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    if report["kind"] == "sattlint.context_health.codegraph":
        codegraph = report["sections"]["codegraph"]
        lines = [
            "# CodeGraph Health",
            "",
            f"- Status: {codegraph['status']}",
            f"- Generated: {report['generated_at']}",
            f"- Recommended route: {codegraph['recommended_route']}",
            f"- Index present: {'yes' if codegraph['index_present'] else 'no'}",
            f"- MCP configured: {'yes' if codegraph['mcp_server_configured'] else 'no'}",
            f"- CLI available: {'yes' if codegraph['cli_available'] else 'no'}",
            f"- Status command ok: {'yes' if codegraph['status_command_ok'] else 'no'}",
            f"- Guidance: {codegraph['guidance']}",
            "",
            "## Issues",
            "",
        ]
        if not report["issues"]:
            lines.append("- none")
        else:
            for issue in report["issues"]:
                path_text = issue["path"] if issue["path"] is not None else "(repo)"
                lines.append(f"- {issue['id']}: {path_text} - {issue['message']}")
        lines.extend(["", "## Recommended Commands", ""])
        for command in report["recommended_commands"]:
            lines.append(f"- {command}")
        lines.append("")
        return "\n".join(lines)

    metrics = report["metrics"]
    codegraph = report["sections"]["codegraph"]
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
        f"- CodeGraph: {codegraph['status']} via {codegraph['recommended_route']}",
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
    parser.add_argument(
        "--section",
        choices=["codegraph"],
        help="Emit a focused health report for one section.",
    )
    parser.add_argument("--json-output", type=Path, help="Write the JSON report to a file.")
    parser.add_argument("--markdown-output", type=Path, help="Write the Markdown report to a file.")
    parser.add_argument("--stdout-json", action="store_true", help="Print the JSON report instead of the text summary.")
    return parser


def _is_failing_report(report: dict[str, Any]) -> bool:
    if report["kind"] == "sattlint.context_health.codegraph":
        return report["status"] != "healthy"
    return report["status"] != "pass"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = build_report(section=args.section)

    if args.json_output is not None:
        _write_text(args.json_output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.markdown_output is not None:
        _write_text(args.markdown_output, _render_markdown(report))

    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if report["kind"] == "sattlint.context_health.codegraph":
            codegraph = report["sections"]["codegraph"]
            print(f"CodeGraph health: {codegraph['status']}")
            print(f"Recommended route: {codegraph['recommended_route']}")
            print(f"Index present: {'yes' if codegraph['index_present'] else 'no'}")
            print(f"MCP configured: {'yes' if codegraph['mcp_server_configured'] else 'no'}")
            print(f"CLI available: {'yes' if codegraph['cli_available'] else 'no'}")
            print(f"Status command ok: {'yes' if codegraph['status_command_ok'] else 'no'}")
            print(f"Guidance: {codegraph['guidance']}")
        else:
            metrics = report["metrics"]
            codegraph = report["sections"]["codegraph"]
            print(f"Context health: {report['status']}")
            print(f"Required paths: {metrics['required_path_present_count']}/{metrics['required_path_count']}")
            print(
                f"Auto-loaded context: {metrics['auto_loaded_context_lines']}/{metrics['auto_loaded_context_budget']} lines"
            )
            print(f"Scoped context files: {metrics['scoped_context_file_count']}")
            print(f"CodeGraph: {codegraph['status']} ({codegraph['recommended_route']})")
            print(f"Issues: {len(report['issues'])}")
        for issue in report["issues"]:
            path_text = issue["path"] if issue["path"] is not None else "(repo)"
            print(f"- {issue['id']}: {path_text}: {issue['message']}")

    return 1 if args.check and _is_failing_report(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
