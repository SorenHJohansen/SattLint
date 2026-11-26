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
        "2026-11-25-structural-never-cleared",
        "7ddf8355946bd3d5e4b382ffbcf0bfcdbc39f69db2c7f9efa58c5c984a2be39d",
    ),
    "comment-code": (
        "2026-11-25-file-line-ownership",
        "8d05d49511f9c8dda96310005792829c44919e8aaa5236791ed2cc797502d72e",
    ),
    "cyclomatic-complexity": (
        "2026-11-21-worst-scope",
        "d2277e844005e006f5e5c848e3cb12f70b9e51560e777a6b248a280db4a7e1f0",
    ),
    "dataflow": ("2026-11-25-sfc-guard-and-state", "614a5a8e5eda532804c7ab7b2c5701306e631b5ed2d9915dfbd2f78eebd5314b"),
    "datatype-fields": (
        "2026-11-26-sweep-keeps-findings",
        "417d31ef0c9b51ba5ae2dc9b3b7a045483684990e6dcf6652ac6bb2e93b61fee",
    ),
    "icf": ("2026-11-25-partial-project", "b57a15fb535e1a1d8a6990ab24e3b4cd0f305675f8e95b5183fe1afc465d7844"),
    "module-layout": (
        "2026-11-26-grid-origo-visibility",
        "b8ee532feff0def2ed8a068a8115b9eb777c6385ed2014862f8aaf922197a752",
    ),
    "moduletype-usage": (
        "2026-11-21-consumer-closure",
        "d03db7cb4e19b2c61fc4fd61006b6f892c3fba6a62e9622825216ec8b1ca6133",
    ),
    "picture-display-paths": (
        "2026-11-25-stable-string-pass",
        "098f64db66b810fce9dede5e7205a2f8c14837ea5cef1c8ec6810c8b381e21bc",
    ),
    "same-cycle": (
        "2026-11-26-sweep-keeps-findings",
        "394162a16007af43e2bc5d12de03064bea8da2ca2be2f87cb9fe7003b76b7744",
    ),
    "sfc": ("2026-11-26-fork-targets", "dfca64ae045ca499d2bc8c26cca60602b0f9a84c25f7a972f9652446f5018376"),
    "string-capacity": (
        "2026-11-26-analyzed-origin",
        "beeb51cc17ac37adc7cea687c9fc29c84e69338e96762fa56ef6dfecf8c541fd",
    ),
    "string-style": ("2026-11-26-analyzed-origin", "beeb51cc17ac37adc7cea687c9fc29c84e69338e96762fa56ef6dfecf8c541fd"),
    "variables": (
        "2026-11-26-sweep-keeps-findings",
        "fac2f32f8bc14b3e97871db425f0f553c72523e0a69c69be1ee977f4780bb6e0",
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
