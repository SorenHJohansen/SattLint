"""Compatibility shim for the active devtools pipeline package."""

from __future__ import annotations

from sattlint.devtools import pipeline as _pipeline_package

# Re-export the active package surface for legacy module-path consumers.
globals().update(
    {
        name: getattr(_pipeline_package, name)
        for name in dir(_pipeline_package)
        if not (name.startswith("__") and name not in {"__all__"})
    }
)

if __name__ == "__main__":
    raise SystemExit(_pipeline_package.main())
