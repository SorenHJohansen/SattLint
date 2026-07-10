"""Compatibility shim for the active configgen package."""

from __future__ import annotations

from sattlint.docgenerator import configgen as _configgen_package

# Re-export the active package surface for legacy module-path consumers.
globals().update(
    {
        name: getattr(_configgen_package, name)
        for name in dir(_configgen_package)
        if not (name.startswith("__") and name not in {"__all__"})
    }
)

if __name__ == "__main__":
    raise SystemExit(_configgen_package.main())
