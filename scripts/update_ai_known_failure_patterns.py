from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts._repo_paths import repo_root_from
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    from _repo_paths import repo_root_from

REPO_ROOT = repo_root_from(Path(__file__))
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sattlint.devtools._ai_chat_findings import known_failure_pattern_updates  # noqa: E402

AUTOMATED_SECTION_HEADING = "## Automated AI Chat Review"
_AUTOMATED_SECTION_RE = re.compile(rf"(?ms)^({re.escape(AUTOMATED_SECTION_HEADING)}\n.*?)(?=^## |\Z)")


def _render_automated_section(*, review_date: str, findings: list[dict[str, Any]]) -> str | None:
    updates = known_failure_pattern_updates(findings)
    if not updates:
        return None

    lines = [
        AUTOMATED_SECTION_HEADING,
        "",
        f"Generated from AI chat observability findings on {review_date}.",
        "",
    ]
    for update in updates:
        lines.extend(
            [
                f"### {update.title}",
                "",
                f"- **Finding ID**: {update.finding_id}",
                f"- **Review Date**: {review_date}",
                f"- **Pattern**: {update.pattern}",
                f"- **Root Cause**: {update.root_cause}",
                f"- **Fix**: {update.fix}",
                f"- **Prevention**: {update.prevention}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _strip_automated_sections(document_text: str) -> str:
    stripped = _AUTOMATED_SECTION_RE.sub("", document_text)
    return stripped.rstrip()


def update_known_failure_patterns_doc(
    doc_path: Path,
    findings: list[dict[str, Any]],
    review_date: str,
) -> bool:
    rendered_section = _render_automated_section(review_date=review_date, findings=findings)
    if rendered_section is None:
        return False

    existing_text = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    base_text = _strip_automated_sections(existing_text)
    updated_text = rendered_section if not base_text else f"{base_text}\n\n{rendered_section}"
    if updated_text == existing_text:
        return False

    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(updated_text, encoding="utf-8", newline="\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update the generated AI known-failure section in a markdown doc.")
    parser.add_argument("doc_path", type=Path)
    parser.add_argument("findings_path", type=Path, help="JSON file containing observability findings.")
    parser.add_argument("review_date", help="Review date to stamp into the generated section.")
    args = parser.parse_args(argv)

    findings_payload = json.loads(args.findings_path.read_text(encoding="utf-8"))
    if not isinstance(findings_payload, list):
        raise ValueError("findings JSON must be a list of finding objects")

    update_known_failure_patterns_doc(
        doc_path=args.doc_path,
        findings=[item for item in findings_payload if isinstance(item, dict)],
        review_date=args.review_date,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
