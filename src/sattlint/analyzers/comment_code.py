from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, cast

from sattlint.parser_api import (
    BasePicture,
    CodeComment,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    is_compressed,
    preprocess_sl_text,
)

from ..analyzers.framework import AnalysisContext, Issue
from ..models.project_graph import program_identity
from ..reporting.comment_code_report import CommentCodeHit, CommentCodeReport
from ..utils.text_processing import find_comments_with_code

_SOURCE_SUFFIXES = {".s", ".x"}
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


def _iter_code_comments(value: object) -> Iterator[CodeComment]:
    if isinstance(value, CodeComment):
        yield value
        return
    if isinstance(value, (list, tuple)):
        for item in cast(Sequence[object], value):
            yield from _iter_code_comments(item)
        return
    if not is_dataclass(value) or isinstance(value, type):
        return
    for field in fields(cast(Any, value)):
        yield from _iter_code_comments(cast(object, getattr(value, field.name)))


def _comment_module_paths(base_picture: BasePicture) -> dict[int, tuple[str, ...]]:
    """Map every comment's starting line to its declared module path.

    The parser keeps ``CodeComment`` nodes with source spans, so ownership comes
    from the AST instead of a text-level module stack that can drift on record
    typedefs, commented headers, or ``Name = value`` clauses in invocation
    headers. Paths use the ``TypeDef:`` marker for moduletype-owned code; the
    checks pipeline rewrites those to a real invocation before display.
    """
    paths: dict[int, tuple[str, ...]] = {}
    root_name = base_picture.header.name
    if not root_name:
        return paths

    def walk(node: BasePicture | SingleModule | FrameModule | ModuleTypeDef, path: tuple[str, ...]) -> None:
        modulecode = node.modulecode
        if modulecode is not None:
            for comment in _iter_code_comments(modulecode):
                span = comment.span
                if span is not None:
                    paths.setdefault(span.line, path)
        for child in node.submodules or ():
            if isinstance(child, ModuleTypeInstance):
                continue
            walk(child, (*path, child.header.name))

    for moduletype in base_picture.moduletype_defs or ():
        walk(moduletype, (root_name, f"TypeDef:{moduletype.name}"))
    walk(base_picture, (root_name,))
    return paths


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
    *,
    module_paths_by_line: Mapping[int, tuple[str, ...]] | None = None,
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
        except (OSError, UnicodeError, ValueError):
            continue

        for hit in find_comments_with_code(text):
            module_path = (
                module_paths_by_line.get(hit.start_line, hit.module_path)
                if module_paths_by_line is not None
                else hit.module_path
            )
            hits.append(
                CommentCodeHit(
                    file_path=path,
                    start_line=hit.start_line,
                    end_line=hit.end_line,
                    start_col=hit.start_col,
                    end_col=hit.end_col,
                    indicators=hit.indicators,
                    module_path=module_path,
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
                    module_path=list(module_path) if module_path else None,
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


def _source_base_picture(context: AnalysisContext) -> BasePicture:
    """Return the target's own parsed picture, not the merged project view.

    The merged picture also carries moduletype definitions from dependency
    libraries, and their source line numbers collide with the target file's.
    Comment ownership must come from the target's own AST only.
    """
    base_picture = context.base_picture
    graph = context.graph
    if graph is None:
        return base_picture
    ast_by_name = getattr(graph, "ast_by_name", None)
    if not isinstance(ast_by_name, Mapping):
        return base_picture
    root = cast(Mapping[str, object], ast_by_name).get(program_identity(base_picture))
    if isinstance(root, BasePicture):
        return root
    return base_picture


def analyze_comment_code(context: AnalysisContext) -> CommentCodeReport:
    paths = _target_source_paths(context)
    return analyze_comment_code_files(
        paths,
        context.base_picture.header.name,
        module_paths_by_line=_comment_module_paths(_source_base_picture(context)),
    )
