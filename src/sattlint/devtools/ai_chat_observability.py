"""Build machine-readable observability artifacts from Copilot chat transcripts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sattlint.devtools._ai_chat_findings import build_findings
from sattlint.devtools._ai_chat_grounding import build_semantic_grounding_report
from sattlint.devtools._ai_chat_metrics import (
    build_sessions_report,
    build_status_report,
    build_summary_report,
    probe_session_store,
)
from sattlint.devtools._ai_chat_transcripts import (
    AiChatInputError,
    load_transcript_corpus,
    resolve_transcripts_input,
)
from sattlint.devtools.pipeline_artifacts import write_json_artifact

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "ai-chat"


def build_ai_chat_observability_report(
    *,
    transcripts_dir: Path | None,
    workspace_storage: Path | None,
    session_db: Path | None,
    output_dir: Path,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    resolved_input = resolve_transcripts_input(
        transcripts_dir=transcripts_dir,
        workspace_storage=workspace_storage,
        repo_root=repo_root,
    )
    transcript_report = load_transcript_corpus(resolved_input=resolved_input, repo_root=repo_root)
    session_store = probe_session_store(session_db, repo_root=repo_root)
    semantic_grounding = build_semantic_grounding_report(transcript_report=transcript_report, repo_root=repo_root)
    placeholder_summary = build_summary_report(
        transcript_report=transcript_report,
        session_store=session_store,
        semantic_grounding=semantic_grounding,
        findings=[],
        output_dir=output_dir,
        repo_root=repo_root,
    )
    findings = build_findings(
        transcript_report=transcript_report,
        session_store=session_store,
        summary=placeholder_summary,
        repo_root=repo_root,
    )
    findings_payload = findings.to_dict()
    summary = build_summary_report(
        transcript_report=transcript_report,
        session_store=session_store,
        semantic_grounding=semantic_grounding,
        findings=list(findings_payload["findings"]),
        output_dir=output_dir,
        repo_root=repo_root,
    )
    status = build_status_report(
        transcript_report=transcript_report,
        session_store=session_store,
        finding_count=int(findings_payload["finding_count"]),
        summary=summary,
        output_dir=output_dir,
        repo_root=repo_root,
    )
    sessions = build_sessions_report(transcript_report=transcript_report, semantic_grounding=semantic_grounding)
    return {
        "status": status,
        "summary": summary,
        "sessions": sessions,
        "findings": findings_payload,
    }


def write_ai_chat_observability_artifacts(
    report: dict[str, Any], *, output_dir: Path, repo_root: Path = REPO_ROOT
) -> None:
    source_paths = [report["summary"]["transcript_corpus"]["transcripts_dir"]]
    session_store_path = report["summary"]["session_store"].get("database_path")
    if session_store_path:
        source_paths.append(session_store_path)
    write_json_artifact(output_dir / "status.json", report["status"], repo_root=repo_root)
    write_json_artifact(output_dir / "summary.json", report["summary"], repo_root=repo_root)
    write_json_artifact(output_dir / "sessions.json", report["sessions"], repo_root=repo_root)
    write_json_artifact(
        output_dir / "findings.json",
        report["findings"],
        repo_root=repo_root,
        source_paths=tuple(source_paths),
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sattlint-ai-chat-observability",
        description="Read Copilot transcript JSONL files and emit machine-readable AI chat observability artifacts.",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--transcripts-dir", type=Path, help="Directory containing transcript JSONL files.")
    input_group.add_argument(
        "--workspace-storage",
        type=Path,
        help="Path to the GitHub.copilot-chat workspace storage root that contains a transcripts child directory.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory that receives JSON artifacts."
    )
    parser.add_argument(
        "--session-db", type=Path, default=None, help="Optional path to the local session-store SQLite database."
    )
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = build_ai_chat_observability_report(
            transcripts_dir=args.transcripts_dir,
            workspace_storage=args.workspace_storage,
            session_db=args.session_db,
            output_dir=args.output_dir.resolve(),
        )
    except AiChatInputError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    write_ai_chat_observability_artifacts(report, output_dir=args.output_dir.resolve())
    print(
        json.dumps(
            {
                "overall_status": report["status"]["overall_status"],
                "output_dir": report["status"]["output_dir"],
                "finding_count": report["findings"]["finding_count"],
                "transcript_count": report["summary"]["transcript_corpus"]["transcript_count"],
                "session_store_status": report["summary"]["session_store"]["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
