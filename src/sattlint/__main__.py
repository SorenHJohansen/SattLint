"""Module entrypoint for `python -m sattlint`."""

from .app import cli

if __name__ == "__main__":
    raise SystemExit(cli())
