"""Compatibility wrapper for the moved repo-audit facade."""

from __future__ import annotations

from .audit import repo_audit as _owner


def _export_public_owner_names() -> list[str]:
    exported_names: list[str] = []
    for name in dir(_owner):
        if name.startswith("_"):
            continue
        globals()[name] = getattr(_owner, name)
        exported_names.append(name)
    return exported_names


__all__ = _export_public_owner_names()


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


def main(argv: list[str] | None = None) -> int:
    return _owner.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
