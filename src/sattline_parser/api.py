"""Public parser-core entry points."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from lark import Lark

from .grammar import constants as const
from .grammar.parser_decode import is_compressed, preprocess_sl_text
from .models.ast_model import BasePicture
from .transformer.sl_transformer import SLTransformer
from .utils.text_processing import strip_sl_comments

GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "sattline.lark"

if not GRAMMAR_PATH.exists():
    raise RuntimeError(f"Grammar file missing: {GRAMMAR_PATH}")


def create_parser() -> Lark:
    """Load and compile the SattLine grammar."""
    grammar_text = GRAMMAR_PATH.read_text(encoding="utf-8")
    grammar_substitutions = {
        name: getattr(const, name)
        for name in dir(const)
        if name.startswith("GRAMMAR_VALUE_") or name.startswith("GRAMMAR_REGEX_")
    }
    formatted_grammar = grammar_text.format(**grammar_substitutions)
    return Lark(formatted_grammar, start="start", parser="lalr", propagate_positions=True)


def create_sl_parser() -> Lark:
    """Compatibility alias for existing SattLint naming."""
    return create_parser()


@lru_cache(maxsize=1)
def _default_parser() -> Lark:
    return create_parser()


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
        setattr(basepic, "parse_tree", tree)
    except Exception:
        if debug is not None:
            debug("BasePicture does not allow dynamic attributes; parse tree not attached")

    if debug is not None:
        debug(f"Transform result type: {type(basepic).__name__}")

    if not isinstance(basepic, BasePicture):
        raise RuntimeError(
            "Transform result is not BasePicture; check transformer.start()"
        )

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
