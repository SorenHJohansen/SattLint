"""Semantic grounding helpers for AI chat observability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sattlint.devtools._semble_adapter import search_local_repo

GROUNDING_TOP_K = 3


def build_semantic_grounding_report(*, transcript_report: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    session_reports: list[dict[str, Any]] = []
    queryable_session_count = 0
    searchable_session_count = 0
    grounded_session_count = 0
    average_match_ratios: list[float] = []
    backend: str | None = None
    ungrounded_session_ids: list[str] = []

    for session in list(transcript_report["sessions"]):
        session_id = str(session.get("session_id", ""))
        prompt_preview = str(session.get("prompt_preview") or "").strip()
        file_reference_paths = [
            str(path).strip() for path in list(session.get("file_reference_paths", [])) if str(path).strip()
        ]

        if not prompt_preview:
            session_reports.append(
                {
                    "session_id": session_id,
                    "status": "no-query",
                    "query": None,
                    "candidate_file_paths": [],
                    "matched_file_paths": [],
                    "match_ratio": 0.0,
                    "explanation": "No prompt preview was available for semantic grounding.",
                }
            )
            continue
        if not file_reference_paths:
            session_reports.append(
                {
                    "session_id": session_id,
                    "status": "no-file-references",
                    "query": prompt_preview,
                    "candidate_file_paths": [],
                    "matched_file_paths": [],
                    "match_ratio": 0.0,
                    "explanation": "The session did not record any file-referencing tool calls to compare against search hits.",
                }
            )
            continue

        queryable_session_count += 1
        search_report = search_local_repo(prompt_preview, repo_root=repo_root, top_k=GROUNDING_TOP_K)
        if backend is None:
            backend = search_report.backend
        if not search_report.available:
            session_reports.append(
                {
                    "session_id": session_id,
                    "status": "unavailable",
                    "query": prompt_preview,
                    "candidate_file_paths": [],
                    "matched_file_paths": [],
                    "match_ratio": 0.0,
                    "explanation": search_report.explanation,
                    "error": search_report.error,
                }
            )
            continue

        searchable_session_count += 1
        candidate_file_paths: list[str] = []
        matched_file_paths: list[str] = []
        referenced_lookup = {path.casefold() for path in file_reference_paths}
        for match in search_report.results:
            if match.file_path not in candidate_file_paths:
                candidate_file_paths.append(match.file_path)
            if match.file_path.casefold() in referenced_lookup and match.file_path not in matched_file_paths:
                matched_file_paths.append(match.file_path)

        if candidate_file_paths:
            match_ratio = float(len(matched_file_paths) / len(candidate_file_paths))
            average_match_ratios.append(match_ratio)
        else:
            match_ratio = 0.0

        status = "ok"
        explanation = "Prompt search hits overlap with file-referencing tool calls from the session."
        if not candidate_file_paths:
            status = "no-results"
            explanation = "Semble returned no semantic search hits for the prompt preview."
        elif not matched_file_paths:
            status = "ungrounded"
            explanation = "Prompt search hits did not overlap with the session's file-referencing tool calls."

        if matched_file_paths:
            grounded_session_count += 1
        else:
            ungrounded_session_ids.append(session_id)

        session_reports.append(
            {
                "session_id": session_id,
                "status": status,
                "query": prompt_preview,
                "candidate_file_paths": candidate_file_paths,
                "matched_file_paths": matched_file_paths,
                "match_ratio": match_ratio,
                "explanation": explanation,
            }
        )

    overall_status = "no-queryable-sessions"
    explanation = "No sessions had both a prompt preview and file-referencing tool calls."
    if queryable_session_count > 0 and searchable_session_count == 0:
        overall_status = "unavailable"
        explanation = "Semble was unavailable for every session that could have been grounded semantically."
    elif searchable_session_count > 0 and grounded_session_count == 0:
        overall_status = "low-grounding"
        explanation = (
            "Semble returned prompt hits, but none overlapped with the files referenced during those sessions."
        )
    elif grounded_session_count > 0:
        overall_status = "ok"
        explanation = "At least one grounded session showed overlap between prompt search hits and referenced files."

    grounding_match_rate = (
        float(grounded_session_count / searchable_session_count) if searchable_session_count > 0 else 0.0
    )
    average_candidate_match_ratio = (
        float(sum(average_match_ratios) / len(average_match_ratios)) if average_match_ratios else 0.0
    )
    return {
        "status": overall_status,
        "backend": backend,
        "queryable_session_count": queryable_session_count,
        "searchable_session_count": searchable_session_count,
        "grounded_session_count": grounded_session_count,
        "grounding_match_rate": grounding_match_rate,
        "average_candidate_match_ratio": average_candidate_match_ratio,
        "ungrounded_session_ids": ungrounded_session_ids[:5],
        "explanation": explanation,
        "sessions": session_reports,
    }


__all__ = ["build_semantic_grounding_report"]
