"""Public parser-core entry points."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from tempfile import gettempdir
from typing import Protocol, cast

from lark import Lark, Token, Tree
from lark import __version__ as lark_version
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken

__all__ = [
    "ParseErrorDetails",
    "build_lark_parser",
    "create_parser",
    "create_sl_parser",
    "describe_parse_error",
    "load_source_text",
    "parse_source_file",
    "parse_source_text",
    "read_text_with_fallback",
    "strip_sl_comments",
]

from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.transformer.sl_transformer import SLTransformer

from .grammar import constants as const
from .utils.text_processing import strip_sl_comments, strip_sl_comments_with_mapping

GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "sattline.lark"
_PARSER_CACHE_DIR = Path(gettempdir()) / "sattlint" / "lark-cache"
log = logging.getLogger("SattLint")
_LARK_LOCATION_SUFFIX_RE = re.compile(r", at line \d+ col \d+$")

if not GRAMMAR_PATH.exists():
    raise RuntimeError(f"Grammar file missing: {GRAMMAR_PATH}")


@dataclass(frozen=True, slots=True)
class ParseErrorDetails:
    message: str
    line: int | None = None
    column: int | None = None


class _ParserProtocol(Protocol):
    def parse(
        self,
        text: str,
        start: str | None = None,
        _on_error: Callable[[UnexpectedInput], bool] | None = None,
    ) -> Tree[Token]: ...


@lru_cache(maxsize=1)
def _formatted_grammar() -> str:
    grammar_text = GRAMMAR_PATH.read_text(encoding="utf-8")
    grammar_substitutions = {
        name: getattr(const, name)
        for name in dir(const)
        if name.startswith("GRAMMAR_VALUE_") or name.startswith("GRAMMAR_REGEX_")
    }
    return grammar_text.format(**grammar_substitutions)


def _parser_cache_path(
    *,
    start: str,
    propagate_positions: bool,
    strict: bool,
) -> str:
    cache_key = sha256()
    cache_key.update(_formatted_grammar().encode("utf-8"))
    cache_key.update(start.encode("utf-8"))
    cache_key.update(str(propagate_positions).encode("ascii"))
    cache_key.update(str(strict).encode("ascii"))
    cache_key.update(lark_version.encode("utf-8"))
    _PARSER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return str(_PARSER_CACHE_DIR / f"{cache_key.hexdigest()}.lark")


def build_lark_parser(
    *,
    start: str = "start",
    propagate_positions: bool = True,
    strict: bool = False,
) -> Lark:
    return Lark(
        _formatted_grammar(),
        start=start,
        parser="lalr",
        propagate_positions=propagate_positions,
        strict=strict,
        regex=True,
        cache=_parser_cache_path(
            start=start,
            propagate_positions=propagate_positions,
            strict=strict,
        ),
        cache_grammar=True,
    )


def create_parser(*, strict: bool = False) -> Lark:
    """Load and compile the SattLine grammar."""
    return build_lark_parser(strict=strict)


def create_sl_parser(*, strict: bool = False) -> Lark:
    """Compatibility alias for existing SattLint naming."""
    return create_parser(strict=strict)


@lru_cache(maxsize=1)
def _default_parser() -> Lark:
    return create_parser()


def _unexpected_input_summary(exc: UnexpectedInput) -> str:
    summary = str(exc).splitlines()[0].strip()
    expected = getattr(exc, "expected", None)
    if expected:
        expected_text = ", ".join(sorted(expected)[:12])
        if expected_text and expected_text not in summary:
            summary = f"{summary}. Expected one of: {expected_text}"
    elif isinstance(exc, UnexpectedEOF):
        expected = sorted(getattr(exc, "expected", ()) or ())
        if expected:
            summary = f"Unexpected end of input. Expected one of: {', '.join(expected[:12])}"
    elif isinstance(exc, UnexpectedToken):
        token = getattr(exc, "token", None)
        if token is not None:
            summary = f"Unexpected token {token!r}"
            expected = sorted(getattr(exc, "expected", ()) or ())
            if expected:
                summary = f"{summary}. Expected one of: {', '.join(expected[:12])}"
    elif isinstance(exc, UnexpectedCharacters):
        summary = summary.rstrip(".")
    return summary


def _render_source_context(source_text: str, *, line: int | None, column: int | None) -> str:
    if line is None or column is None or line < 1 or column < 1:
        return ""
    lines = source_text.splitlines()
    if line > len(lines):
        return ""
    context_line = lines[line - 1]
    caret_padding = max(column - 1, 0)
    return f"{context_line}\n{' ' * caret_padding}^"


def _rewrite_summary_location(summary: str, *, line: int | None, column: int | None) -> str:
    if line is None or column is None:
        return summary
    if not _LARK_LOCATION_SUFFIX_RE.search(summary):
        return summary
    return _LARK_LOCATION_SUFFIX_RE.sub(f", at line {line} col {column}", summary)


def describe_parse_error(exc: Exception, source_text: str) -> ParseErrorDetails:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if isinstance(exc, UnexpectedInput):
        message = _unexpected_input_summary(exc)
        stripped = strip_sl_comments_with_mapping(source_text)
        if stripped.text != source_text:
            line, column = stripped.map_line_column(line, column)
            message = _rewrite_summary_location(message, line=line, column=column)
            context = _render_source_context(source_text, line=line, column=column).rstrip()
        else:
            context = exc.get_context(source_text, span=40).rstrip()
        if context:
            message = f"{message}\n{context}"
        return ParseErrorDetails(message=message, line=line, column=column)
    return ParseErrorDetails(message=str(exc), line=line, column=column)


def _failure_details(exc: Exception, source_text: str | None = None) -> ParseErrorDetails:
    if source_text is not None:
        return describe_parse_error(exc, source_text)
    return ParseErrorDetails(
        message=str(exc),
        line=getattr(exc, "line", None),
        column=getattr(exc, "column", None),
    )


def _log_parser_failure(
    *,
    stage: str,
    exc: Exception,
    source_text: str | None = None,
    source_path: Path | None = None,
) -> None:
    details = _failure_details(exc, source_text)
    path_text = str(source_path) if source_path is not None else None
    location_text = ""
    if details.line is not None and details.column is not None:
        location_text = f" (line {details.line}, column {details.column})"
    elif details.line is not None:
        location_text = f" (line {details.line})"
    path_suffix = f" for {path_text}" if path_text is not None else ""
    log.error(
        "Parser %s failure%s%s: %s",
        stage,
        path_suffix,
        location_text,
        details.message,
        extra={
            "parser_stage": stage,
            "parser_path": path_text,
            "parser_line": details.line,
            "parser_column": details.column,
            "parser_context": details.message,
        },
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def read_text_with_fallback(path: Path) -> str:
    """Read a text file trying utf-8, then cp1252, then latin-1."""
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            _log_parser_failure(stage="read", exc=exc, source_path=path)
            raise
    return path.read_text(encoding="latin-1")


# Internal alias kept for callers that import the private name.
_read_text_simple = read_text_with_fallback


def load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
) -> str:
    source_path = Path(code_path)
    if debug is not None:
        debug(f"Parsing file: {source_path}")

    src = _read_text_simple(source_path)
    if is_compressed(src):
        if debug is not None:
            debug("Compressed format detected; decoding before parsing")
        try:
            src, _ = preprocess_sl_text(src)
        except Exception as exc:
            _log_parser_failure(stage="decode", exc=exc, source_text=src, source_path=source_path)
            raise
    return src


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
    source_path: Path | None = None,
    log_failures: bool = True,
) -> BasePicture:
    stripped = strip_sl_comments_with_mapping(src)
    cleaned = stripped.text
    active_parser = parser if parser is not None else _default_parser()
    active_transformer = transformer if transformer is not None else SLTransformer()
    parser_runner = cast(_ParserProtocol, active_parser)
    try:
        tree = parser_runner.parse(cleaned)
    except Exception as exc:
        if log_failures:
            _log_parser_failure(stage="parse", exc=exc, source_text=src, source_path=source_path)
        raise

    if debug is not None:
        debug("Parse OK, transforming with SLTransformer")

    try:
        transformed = active_transformer.transform(tree)
        if not isinstance(transformed, BasePicture):
            raise RuntimeError("Transform result is not BasePicture; check transformer.start()")
    except Exception as exc:
        if log_failures:
            _log_parser_failure(stage="transform", exc=exc, source_text=src, source_path=source_path)
        raise

    basepic = transformed
    try:
        basepic.parse_tree = tree
    except AttributeError:
        if debug is not None:
            debug("BasePicture does not allow dynamic attributes; parse tree not attached")

    if debug is not None:
        debug(f"Transform result type: {type(basepic).__name__}")

    return basepic


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
    log_failures: bool = True,
) -> BasePicture:
    src = load_source_text(code_path, debug=debug)
    return parse_source_text(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
        source_path=code_path,
        log_failures=log_failures,
    )
