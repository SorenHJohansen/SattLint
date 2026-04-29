"""Property-based helpers for parser and transformer invariants."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from typing import Any

from sattline_parser import parse_source_text as parser_core_parse_source_text


def generate_simple_program() -> str:
    """Generate a minimal valid SattLine program."""
    names = ["ProgramA", "TestProg", "MainProg"]
    variables = ["x", "y", "temp", "flag"]
    values = ["1", "0", "TRUE", "FALSE", "3.14"]

    name = random.choice(names)
    var = random.choice(variables)
    val = random.choice(values)

    return f"""
PROGRAM {name}
    VAR
        {var} : INT;
    END_VAR
    {var} := {val};
END_PROGRAM
"""


def generate_simple_module() -> str:
    """Generate a minimal valid SattLine module."""
    names = ["ModuleA", "ChildMod", "Worker"]
    var = random.choice(["a", "b", "cnt"])

    return f"""
MODULE {names[0]}
    VAR
        {var} : INT;
    END_VAR
END_MODULE
"""


def assert_parser_deterministic(source: str) -> None:
    """Property: parsing same source twice yields equivalent ASTs."""
    bp1 = parser_core_parse_source_text(source)
    bp2 = parser_core_parse_source_text(source)

    assert bp1.header.name == bp2.header.name
    assert len(bp1.submodules) == len(bp2.submodules)


def assert_valid_program_has_no_crash(source: str) -> bool:
    """Property: valid SattLine text never crashes the parser."""
    try:
        parser_core_parse_source_text(source)
        return True
    except (SyntaxError, ValueError, AttributeError):
        return False


def iter_generated_programs(
    count: int = 10,
    seed: int | None = None,
) -> Iterable[str]:
    """Yield generated SattLine program texts."""
    if seed is not None:
        random.seed(seed)
    for _ in range(count):
        yield generate_simple_program()


def iter_generated_modules(
    count: int = 10,
    seed: int | None = None,
) -> Iterable[str]:
    """Yield generated SattLine module texts."""
    if seed is not None:
        random.seed(seed)
    for _ in range(count):
        yield generate_simple_module()


def check_parser_property(
    property_fn: Callable[[str], Any],
    *,
    count: int = 20,
    seed: int = 42,
) -> list[tuple[str, Exception | None]]:
    """Run a property against generated programs; return failures."""
    failures: list[tuple[str, Exception | None]] = []
    if seed is not None:
        random.seed(seed)

    for _ in range(count):
        source = generate_simple_program()
        try:
            result = property_fn(source)
            if result is False:
                failures.append((source[:60], None))
        except Exception as exc:
            failures.append((source[:60], exc))

    return failures


__all__ = [
    "assert_parser_deterministic",
    "assert_valid_program_has_no_crash",
    "check_parser_property",
    "generate_simple_module",
    "generate_simple_program",
    "iter_generated_modules",
    "iter_generated_programs",
]
