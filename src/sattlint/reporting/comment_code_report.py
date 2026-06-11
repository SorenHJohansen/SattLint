from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..analyzers.framework import Issue, empty_issues, format_report_header


@dataclass(frozen=True)
class CommentCodeHit:
    file_path: Path
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    indicators: tuple[str, ...]
    preview: str
    module_path: tuple[str, ...] = ()
    equation_name: str | None = None
    sequence_name: str | None = None
    step_name: str | None = None


def _format_module_path(module_path: tuple[str, ...]) -> str:
    if not module_path:
        return ""
    return ".".join(
        segment.removeprefix("TypeDef:") if segment.startswith("TypeDef:") else segment for segment in module_path
    )


def _format_source_location(file_path: Path, start_line: int, end_line: int) -> str:
    if start_line == end_line:
        return f"{file_path.name}:{start_line}"
    return f"{file_path.name}:{start_line}-{end_line}"


def _format_context_details(hit: CommentCodeHit) -> str:
    details: list[str] = []
    if hit.equation_name:
        details.append(f"equation={hit.equation_name}")
    if hit.sequence_name:
        details.append(f"sequence={hit.sequence_name}")
    if hit.step_name:
        details.append(f"step={hit.step_name}")
    if not details:
        return ""
    return f" [{' | '.join(details)}]"


@dataclass
class CommentCodeReport:
    basepicture_name: str
    hits: list[CommentCodeHit]
    issues: list[Issue] = field(default_factory=empty_issues)
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
                indicator_txt = ", ".join(hit.indicators) if hit.indicators else "unknown"
                source_location = _format_source_location(hit.file_path, hit.start_line, hit.end_line)
                module_location = _format_module_path(hit.module_path)
                context_details = _format_context_details(hit)
                preview = hit.preview or "<empty>"
                if module_location:
                    lines.append(
                        f"  - {module_location} ({source_location}){context_details} [{indicator_txt}] {preview}"
                    )
                else:
                    lines.append(f"  - {source_location}{context_details} [{indicator_txt}] {preview}")

        # Only show actual read errors (not duplicate comment code entries)
        read_errors = [issue for issue in self.issues if issue.kind == "comment_code_read_error"]
        if read_errors:
            lines.append("")
            lines.append("Read errors:")
            for issue in read_errors:
                lines.append(f"  - {issue.message}")

        return "\n".join(lines)
