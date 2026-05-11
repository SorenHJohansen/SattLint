"""Property-based helpers for parser and transformer invariants."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from typing import Any

from lark.exceptions import UnexpectedInput

from sattline_parser import parse_source_text as parser_core_parse_source_text


def _header_lines(program_name: str) -> str:
    return (
        '"Syntax version 2.23, date: 2026-05-04-12:00:00.000 N"\n'
        '"Original file date: ---"\n'
        f'"Program date: 2026-05-04-12:00:00.000, name: {program_name}"\n'
    )


def generate_simple_program() -> str:
    """Generate a minimal valid strict-mode SattLine program."""
    names = ["ProgramA", "TestProg", "MainProg"]
    variables = ["x", "y", "temp", "flag"]
    initial_values = ["0", "1", "3"]
    increments = ["1", "2", "3"]

    # Property helper uses non-cryptographic sampling.
    name = random.choice(names)  # nosec B311
    var = random.choice(variables)  # nosec B311
    initial_value = random.choice(initial_values)  # nosec B311
    increment = random.choice(increments)  # nosec B311

    return (
        f"{_header_lines(name)}\n"
        "BasePicture Invocation\n"
        "   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0\n"
        "    ) : MODULEDEFINITION DateCode_ 1\n\n"
        "LOCALVARIABLES\n"
        f"   {var}: integer := {initial_value};\n\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ModuleCode\n"
        "   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        f"      {var} = {var} + {increment};\n\n"
        "ENDDEF (*BasePicture*);\n"
    )


def generate_simple_module() -> str:
    """Generate a minimal valid SattLine file with one moduletype and one submodule."""
    names = ["ModuleA", "ChildMod", "Worker"]
    # Property helper uses non-cryptographic sampling.
    var = random.choice(["a", "b", "cnt"])  # nosec B311
    initial_value = random.choice(["0", "1", "3"])  # nosec B311
    module_name = random.choice(names)  # nosec B311
    moduletype_name = f"{module_name}Type"

    return (
        f"{_header_lines(module_name)}\n"
        "BasePicture Invocation\n"
        "   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0\n"
        "    ) : MODULEDEFINITION DateCode_ 1\n\n"
        "TYPEDEFINITIONS\n"
        f"   {moduletype_name} = MODULEDEFINITION DateCode_ 1\n"
        "   MODULEPARAMETERS\n"
        f"      {var}: integer ;\n"
        "   LOCALVARIABLES\n"
        "      Result: integer := 0;\n\n"
        "   ModuleDef\n"
        "   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "   ModuleCode\n"
        "   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        f"      Result = {var} + 1;\n\n"
        f"   ENDDEF (*{moduletype_name}*);\n\n"
        "LOCALVARIABLES\n"
        f"   {var}: integer := {initial_value};\n\n"
        "SUBMODULES\n"
        f"   {module_name} Invocation\n"
        "      ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8\n"
        f"       ) : {moduletype_name} (\n"
        f"      {var} => {var});\n\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n\n"
        "ENDDEF (*BasePicture*);\n"
    )


def assert_parser_deterministic(source: str) -> None:
    """Property: parsing same source twice yields equivalent ASTs."""
    bp1 = parser_core_parse_source_text(source)
    bp2 = parser_core_parse_source_text(source)

    if bp1.header.name != bp2.header.name:
        raise AssertionError("parser output changed header name across identical parses")
    if len(bp1.submodules) != len(bp2.submodules):
        raise AssertionError("parser output changed submodule count across identical parses")


def assert_valid_program_has_no_crash(source: str) -> bool:
    """Property: valid SattLine text never crashes the parser."""
    try:
        parser_core_parse_source_text(source)
        return True
    except (UnexpectedInput, SyntaxError, ValueError, AttributeError):
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
