from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..analyzers.framework import Issue, format_report_header


@dataclass(frozen=True)
class CommentCodeHit:
    file_path: Path
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    indicators: tuple[str, ...]
    preview: str


@dataclass
class CommentCodeReport:
    basepicture_name: str
    hits: list[CommentCodeHit]
    issues: list[Issue] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def name(self) -> str:
        return self.basepicture_name

    def summary(self) -> str:
        if not self.hits and not self.issues:
            lines = format_report_header(
                "Commented-out code",
                self.basepicture_name,
                status="ok",
            )
            lines.append("No code-like comments found.")
            return "\n".join(lines)

        status = "issues" if self.hits else "info"
        lines = format_report_header(
            "Commented-out code",
            self.basepicture_name,
            status=status,
        )
        lines.append(f"Files scanned: {self.files_scanned}")
        lines.append(f"Comment blocks with code: {len(self.hits)}")

        if self.hits:
            lines.append("")
            lines.append("Findings:")
            for hit in self.hits:
                indicator_txt = (
                    ", ".join(hit.indicators) if hit.indicators else "unknown"
                )
                if hit.start_line == hit.end_line:
                    location = f"{hit.file_path.name}:{hit.start_line}"
                else:
                    location = f"{hit.file_path.name}:{hit.start_line}-{hit.end_line}"
                preview = hit.preview or "<empty>"
                lines.append(f"  - {location} [{indicator_txt}] {preview}")

        # Only show actual read errors (not duplicate comment code entries)
        read_errors = [
            issue for issue in self.issues if issue.kind == "comment_code_read_error"
        ]
        if read_errors:
            lines.append("")
            lines.append("Read errors:")
            for issue in read_errors:
                lines.append(f"  - {issue.message}")

        return "\n".join(lines)
