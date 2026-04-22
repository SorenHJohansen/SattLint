"""Public parser-core entry points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from tempfile import gettempdir

from lark import Lark
from lark import __version__ as lark_version
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken

from .grammar import constants as const
from .grammar.parser_decode import is_compressed, preprocess_sl_text
from .models.ast_model import BasePicture
from .transformer.sl_transformer import SLTransformer
from .utils.text_processing import strip_sl_comments

GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "sattline.lark"
_PARSER_CACHE_DIR = Path(gettempdir()) / "sattlint" / "lark-cache"

if not GRAMMAR_PATH.exists():
    raise RuntimeError(f"Grammar file missing: {GRAMMAR_PATH}")


@dataclass(frozen=True, slots=True)
class ParseErrorDetails:
    message: str
    line: int | None = None
    column: int | None = None


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


def describe_parse_error(exc: Exception, source_text: str) -> ParseErrorDetails:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if isinstance(exc, UnexpectedInput):
        context = exc.get_context(source_text, span=40).rstrip()
        message = _unexpected_input_summary(exc)
        if context:
            message = f"{message}\n{context}"
        return ParseErrorDetails(message=message, line=line, column=column)
    return ParseErrorDetails(message=str(exc), line=line, column=column)


def _read_text_simple(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")


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
        src, _ = preprocess_sl_text(src)
    return src


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    cleaned = strip_sl_comments(src)
    active_parser = parser if parser is not None else _default_parser()
    active_transformer = transformer if transformer is not None else SLTransformer()
    tree = active_parser.parse(cleaned)

    if debug is not None:
        debug("Parse OK, transforming with SLTransformer")

    basepic = active_transformer.transform(tree)
    try:
        basepic.parse_tree = tree
    except Exception:
        if debug is not None:
            debug("BasePicture does not allow dynamic attributes; parse tree not attached")

    if debug is not None:
        debug(f"Transform result type: {type(basepic).__name__}")

    if not isinstance(basepic, BasePicture):
        raise RuntimeError("Transform result is not BasePicture; check transformer.start()")

    return basepic


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    src = load_source_text(code_path, debug=debug)
    return parse_source_text(src, parser=parser, transformer=transformer, debug=debug)
