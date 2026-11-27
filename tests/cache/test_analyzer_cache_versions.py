# pyright: reportPrivateUsage=false
"""The report cache version must change when an analyzer's code changes.

A cached report is keyed by the analyzer's version marker, so a behavior change
without a marker bump silently replays the old findings for the whole team.
That has gone wrong repeatedly, so this test pins a fingerprint of each
analyzer's implementation: edit the code and it fails until the marker is
bumped and the pin updated.

The fingerprint covers the modules the analyzer imports inside
``sattlint.analyzers``. Wiring that only names, lists, or describes analyzers is
excluded, so a documentation change does not force a version bump. Changes
outside the analyzer layer (resolution, reporting, models) are not covered here;
the existing report-layout fingerprint test guards the issue shapes.
"""

from __future__ import annotations

import ast
import hashlib
from importlib import import_module
from pathlib import Path

from sattlint import cache as cache_module
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers._registry_spec_templates import default_spec_templates

_ANALYZERS_ROOT = Path(__file__).resolve().parents[2] / "src" / "sattlint" / "analyzers"

#: Modules that only wire analyzers together. Rewriting a description or adding
#: a template entry does not change what an analyzer reports.
_WIRING_FILES = frozenset(
    {
        "_registry_dispatch.py",
        "_registry_spec_templates.py",
        "_registry_specs.py",
        "_registry_delivery.py",
        "catalog.py",
        "dispatch.py",
        "plugin.py",
    }
)


def _is_wiring(path: Path) -> bool:
    relative = path.relative_to(_ANALYZERS_ROOT).as_posix()
    return relative.startswith("registry/") or relative in _WIRING_FILES


#: Fingerprint pins: ``analyzer key -> (version marker, implementation digest)``.
#:
#: The version marker lives in ``sattlint/cache/__init__.py``. Bump it in the
#: same change that edits the analyzer, then replace the digest here with the
#: one the failure message reports.
PINS: dict[str, tuple[str, str]] = {
    "alarm-integrity": (
        "2026-11-26-language-identity",
        "481e47d82f01321defff82864632d3fce0cd9af38f29a69f700c8c36372e93f9",
    ),
    "comment-code": (
        "2026-11-25-file-line-ownership",
        "8d05d49511f9c8dda96310005792829c44919e8aaa5236791ed2cc797502d72e",
    ),
    "cyclomatic-complexity": (
        "2026-11-26-language-identity",
        "eaa213d36a7d6221a5937b2c2118e137300df85e6b4b961d9f69d795d543d69a",
    ),
    "dataflow": ("2026-11-26-language-identity", "d6d18b35afdb8f36afbbadb526eb00e49932380b7124f24a077a814804bedda4"),
    "datatype-fields": (
        "2026-11-26-language-identity",
        "54e6aa724cbbe86dfadfb3e70ce7ce28121c9315abc4e40625182636c74bde4d",
    ),
    "icf": ("2026-11-27-input-limits", "b00e575f7ba06d549e9aaf88fcaca3db556748228e97ac501e02baa4d5816e77"),
    "module-layout": (
        "2026-11-26-language-identity",
        "edc32d620ca001cfbd6e56b9b128eeb986ac31651c53051eefeca4654140f12d",
    ),
    "moduletype-usage": (
        "2026-11-26-language-identity",
        "645fc93d08d5bbea648783375f0b84d1a58738f9e90f23f93b8c4ba18df2b373",
    ),
    "picture-display-paths": (
        "2026-11-25-stable-string-pass",
        "098f64db66b810fce9dede5e7205a2f8c14837ea5cef1c8ec6810c8b381e21bc",
    ),
    "same-cycle": (
        "2026-11-26-language-identity",
        "16d2ff5425420d71d3fad31d3496761f2a61c602f0b63518aafa593baf81567a",
    ),
    "sfc": ("2026-11-26-language-identity", "5f97ac17c04491319dfe067dd0105b7bc92af5c5b98a496c9733a7628306fa9b"),
    "string-capacity": (
        "2026-11-26-language-identity",
        "cd4ac0799e7acd467b006b1ba184096b9596182d0928d8a58dddf56745259fd0",
    ),
    "string-style": (
        "2026-11-26-language-identity",
        "cd4ac0799e7acd467b006b1ba184096b9596182d0928d8a58dddf56745259fd0",
    ),
    "variables": (
        "2026-11-26-language-identity",
        "a6cab84c7775da1920e1de25325a400300120370e6cb76c7d36305cc2c6578ee",
    ),
}


def _analyzer_module_names() -> dict[str, str]:
    """Map each selectable analyzer key to the module that implements it."""
    lazy_exports = vars(registry_module)["_LAZY_ANALYZER_EXPORTS"]
    modules: dict[str, str] = {}
    for template in default_spec_templates():
        entry = lazy_exports.get(template.analyzer_attr)
        if entry is None:
            continue
        modules[template.key] = entry[0]
    return modules


def _module_path(module_name: str) -> Path | None:
    try:
        module = import_module(module_name)
    except ImportError:
        return None
    origin = getattr(module, "__file__", None)
    if origin is None:
        return None
    path = Path(origin).resolve()
    return path if path.is_relative_to(_ANALYZERS_ROOT) else None


def _imported_modules(path: Path) -> set[Path]:
    """The analyzer-layer modules *path* imports, from its own package outward."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    package = path.parent
    found: set[Path] = set()
    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.ImportFrom):
            base = _resolve_relative(package, node.level, node.module)
            if base is None:
                continue
            targets.append(base)
            for alias in node.names:
                targets.append(f"{base}.{alias.name}")
        elif isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        for target in targets:
            resolved = _module_file(target)
            if resolved is not None:
                found.add(resolved)
    return found


def _resolve_relative(package: Path, level: int, module: str | None) -> str | None:
    if level == 0:
        return module
    anchor = package
    for _ in range(level - 1):
        anchor = anchor.parent
    relative = anchor.relative_to(_ANALYZERS_ROOT.parent).as_posix().replace("/", ".")
    return relative if module is None else f"{relative}.{module}"


def _module_file(dotted: str) -> Path | None:
    relative = Path(*dotted.split("."))
    root = _ANALYZERS_ROOT.parent
    candidates = (root / relative.with_suffix(".py"), root / relative / "__init__.py")
    for candidate in candidates:
        if candidate.is_file() and candidate.is_relative_to(_ANALYZERS_ROOT):
            return candidate.resolve()
    return None


def implementation_digest(module_name: str) -> str | None:
    """Hash of every analyzer module the implementation reaches."""
    start = _module_path(module_name)
    if start is None:
        return None
    pending = [start]
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen or _is_wiring(path):
            continue
        seen.add(path)
        pending.extend(_imported_modules(path) - seen)
    digest = hashlib.sha256()
    for path in sorted(seen):
        digest.update(path.relative_to(_ANALYZERS_ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_every_analyzer_has_a_report_cache_version_and_a_pin() -> None:
    modules = _analyzer_module_names()
    versions = cache_module._ANALYSIS_REPORT_ANALYZER_VERSIONS

    assert set(modules) == set(versions), (
        "Every selectable analyzer needs a report cache version in sattlint/cache/__init__.py and a pin here."
    )
    assert set(PINS) == set(modules), "Every analyzer needs a fingerprint pin; run this test to see the digest."


def test_an_analyzer_change_requires_a_report_cache_version_bump() -> None:
    changed: list[str] = []
    for key, module_name in sorted(_analyzer_module_names().items()):
        pinned = PINS.get(key)
        version = cache_module._ANALYSIS_REPORT_ANALYZER_VERSIONS.get(key)
        digest = implementation_digest(module_name)
        if pinned is None or digest is None:
            changed.append(f"{key}: no pin or module")
            continue
        if (version, digest) != pinned:
            changed.append(f'{key}: ({version!r}, "{digest}")')

    assert not changed, (
        "An analyzer's implementation changed without a report cache version bump. "
        "Bump its marker in src/sattlint/cache/__init__.py, then pin:\n  " + "\n  ".join(changed)
    )
