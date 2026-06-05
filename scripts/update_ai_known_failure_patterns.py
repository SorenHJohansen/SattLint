from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from sattlint.devtools._ai_chat_findings import known_failure_pattern_updates

JsonObject = dict[str, Any]
AUTO_SECTION_START = "<!-- BEGIN AUTO-UPDATED AI CHAT REVIEW -->"
AUTO_SECTION_END = "<!-- END AUTO-UPDATED AI CHAT REVIEW -->"
INTRO_LINE = "Agents should learn from prior mistakes. Update after each root-cause analysis.\n"


def _load_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(JsonObject, payload)


def _render_auto_section(*, review_date: str, findings: list[JsonObject]) -> str:
    updates = known_failure_pattern_updates(findings)
    if not updates:
        return ""

    lines = [
        AUTO_SECTION_START,
        "## Automated AI Chat Review",
        "",
        "This section is updated by the AI session review workflow when behavioral thresholds are met.",
        "",
    ]
    for update in updates:
        lines.extend(
            [
                f"### {update.title}",
                "",
                f"- **Observed**: {review_date}",
                f"- **Pattern**: {update.pattern}",
                f"- **Root cause**: {update.root_cause}",
                f"- **Fix**: {update.fix}",
                f"- **Prevention**: {update.prevention}",
                "",
            ]
        )
    lines.append(AUTO_SECTION_END)
    return "\n".join(lines) + "\n"


def update_known_failure_patterns_doc(*, doc_path: Path, findings: list[JsonObject], review_date: str) -> bool:
    auto_section = _render_auto_section(review_date=review_date, findings=findings)
    if not auto_section:
        return False

    original = doc_path.read_text(encoding="utf-8")
    if AUTO_SECTION_START in original and AUTO_SECTION_END in original:
        start = original.index(AUTO_SECTION_START)
        end = original.index(AUTO_SECTION_END) + len(AUTO_SECTION_END)
        updated = original[:start] + auto_section + original[end:]
    else:
        insertion = f"{INTRO_LINE}\n{auto_section}\n"
        if INTRO_LINE not in original:
            raise ValueError(f"Could not locate intro line in {doc_path}")
        updated = original.replace(INTRO_LINE, insertion, 1)

    if updated == original:
        return False

    doc_path.write_text(updated, encoding="utf-8")
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update known-failure-patterns.md from AI chat observability findings when thresholds are met."
    )
    parser.add_argument("--findings-json", type=Path, required=True)
    parser.add_argument("--known-failure-patterns-path", type=Path, required=True)
    parser.add_argument("--review-date", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    findings_payload = _load_json(args.findings_json)
    findings_value = findings_payload.get("findings")
    if not isinstance(findings_value, list):
        raise ValueError("findings.json must contain a findings list")
    findings_list = cast(list[Any], findings_value)
    findings = [cast(JsonObject, entry) for entry in findings_list if isinstance(entry, dict)]
    updated = update_known_failure_patterns_doc(
        doc_path=args.known_failure_patterns_path,
        findings=findings,
        review_date=args.review_date,
    )
    print(json.dumps({"updated": updated, "path": str(args.known_failure_patterns_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
