"""Module-invocation entry point for the moved repo-audit facade."""

from __future__ import annotations

from .audit import repo_audit as _owner


def main(argv: list[str] | None = None) -> int:
    return _owner.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
