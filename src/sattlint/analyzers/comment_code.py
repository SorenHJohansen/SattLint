from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from sattline_parser.preprocessing import is_compressed, preprocess_sl_text

from ..analyzers.framework import AnalysisContext, Issue
from ..reporting.comment_code_report import CommentCodeHit, CommentCodeReport
from ..utils.text_processing import find_comments_with_code

_SOURCE_SUFFIXES = {".s", ".x", ".l", ".z"}
_COMMENT_PREVIEW_MAX_LEN = 120


def _read_source_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if is_compressed(text):
        text, _meta = preprocess_sl_text(text)
    return text


def _comment_preview(text: str, max_len: int = _COMMENT_PREVIEW_MAX_LEN) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            preview = stripped
            break
    else:
        preview = ""

    if len(preview) > max_len:
        return preview[: max_len - 3] + "..."
    return preview


def _format_line_range(start_line: int, end_line: int) -> str:
    if start_line == end_line:
        return str(start_line)
    return f"{start_line}-{end_line}"


def _comment_code_site(hit: object, path: Path) -> str:
    equation_name = getattr(hit, "equation_name", None)
    sequence_name = getattr(hit, "sequence_name", None)
    step_name = getattr(hit, "step_name", None)
    if equation_name:
        return f"EQ:{equation_name}"
    if sequence_name:
        site = f"SQ:{sequence_name}"
        if step_name:
            return f"{site} > STEP:{step_name}"
        return site
    return str(path)


def analyze_comment_code_files(
    paths: Iterable[Path],
    basepicture_name: str,
) -> CommentCodeReport:
    hits: list[CommentCodeHit] = []
    issues: list[Issue] = []
    files_scanned = 0

    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        files_scanned += 1
        try:
            text = _read_source_text(path)
        except (OSError, UnicodeError, ValueError) as exc:
            issues.append(
                Issue(
                    kind="comment_code_read_error",
                    message=f"{path.name}: {exc}",
                    data={"path": str(path), "site": str(path), "context": str(exc)},
                )
            )
            continue

        for hit in find_comments_with_code(text):
            hits.append(
                CommentCodeHit(
                    file_path=path,
                    start_line=hit.start_line,
                    end_line=hit.end_line,
                    start_col=hit.start_col,
                    end_col=hit.end_col,
                    indicators=hit.indicators,
                    module_path=hit.module_path,
                    equation_name=hit.equation_name,
                    sequence_name=hit.sequence_name,
                    step_name=hit.step_name,
                    preview=_comment_preview(hit.text),
                )
            )
            issues.append(
                Issue(
                    kind="comment_code",
                    message=f"{path.name}:{_format_line_range(hit.start_line, hit.end_line)} "
                    f"{', '.join(hit.indicators) if hit.indicators else 'code'}",
                    module_path=list(hit.module_path) if hit.module_path else None,
                    data={
                        "path": str(path),
                        "start_line": hit.start_line,
                        "end_line": hit.end_line,
                        "start_col": hit.start_col,
                        "end_col": hit.end_col,
                        "indicators": hit.indicators,
                        "equation_name": hit.equation_name,
                        "sequence_name": hit.sequence_name,
                        "step_name": hit.step_name,
                        "site": _comment_code_site(hit, path),
                        "context": _comment_preview(hit.text),
                    },
                )
            )

    hits.sort(key=lambda h: (h.module_path, h.file_path.name.casefold(), h.start_line, h.start_col))

    return CommentCodeReport(
        basepicture_name=basepicture_name,
        hits=hits,
        issues=issues,
        files_scanned=files_scanned,
    )


def _target_source_paths(context: AnalysisContext) -> set[Path]:
    graph = context.graph
    if graph is None:
        return set()
    root_source_path_for_basepicture = getattr(graph, "root_source_path_for_basepicture", None)
    if callable(root_source_path_for_basepicture):
        root_source_path = root_source_path_for_basepicture(context.base_picture)
        if isinstance(root_source_path, Path):
            return {root_source_path}
    return set(getattr(graph, "source_files", set()) or set())


def analyze_comment_code(context: AnalysisContext) -> CommentCodeReport:
    paths = _target_source_paths(context)
    return analyze_comment_code_files(paths, context.base_picture.header.name)
