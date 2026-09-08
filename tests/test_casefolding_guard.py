# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportAttributeAccessIssue=false
"""AST guard enforcing casefold-only normalization for SattLine identifiers.

SattLine identifiers (variable / module-type / datatype / program names) must be
normalized with ``casefold`` (via ``utils.casefolding.casefold_key`` or
``.casefold()``), never ``.lower()`` — ``casefold`` is the only normalization that
handles non-ASCII names uniformly. ``.lower()`` is reserved for genuinely
non-identifier strings (file suffixes, mode/config strings, CLI prompts).

Mechanical enforcement, mirroring ``tests/test_dependency_guard.py``: walks the
AST of every ``src/sattlint`` module and fails via plain ``assert`` if a
``.lower()`` call is found on an identifier-carrying attribute receiver or on a
bare name that is not in the documented non-identifier allowlist.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "sattlint"

# Attribute names that carry SattLine identifiers on AST nodes. A ``.lower()`` on
# any of these receivers is an identifier normalization and must use casefold.
_IDENTIFIER_CARRYING_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "datatype_text",
        "moduletype_name",
        "moduletype",
        "datatype",
    }
)

# Bare-name receivers of ``.lower()`` that are NOT SattLine identifiers. These are
# documented, non-identifier uses (file extensions, mode/config strings) that stay
# as-is. Any other bare-name receiver is treated as an identifier carry.
_ALLOWED_NON_IDENTIFIER_NAMES: frozenset[str] = frozenset({"extension"})


def _lower_call_sites(module: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "lower"
    ]


def _violation_for(call: ast.Call) -> str | None:
    receiver = call.func.value
    if isinstance(receiver, ast.Attribute):
        if receiver.attr in _IDENTIFIER_CARRYING_ATTRS:
            return f"'.{receiver.attr}.lower()' normalizes a SattLine identifier; use casefold_key()/.casefold()"
        return None
    if isinstance(receiver, ast.Name):
        if receiver.id in _ALLOWED_NON_IDENTIFIER_NAMES:
            return None
        return (
            f"'.lower()' on bare name '{receiver.id}' looks like identifier normalization; "
            "use casefold_key()/.casefold() (add to allowlist only if it is a non-identifier)"
        )
    return None


def test_no_lower_on_sattline_identifiers() -> None:
    violations: list[str] = []
    for path in sorted(SRC_DIR.rglob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _lower_call_sites(module):
            violation = _violation_for(call)
            if violation is not None:
                violations.append(f"{path.relative_to(SRC_DIR)}:{call.lineno}: {violation}")

    assert violations == [], "SattLine identifier normalization must use casefold:\n" + "\n".join(violations)
