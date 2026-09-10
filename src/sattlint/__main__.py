"""Module entrypoint for `python -m sattlint`."""

from .cli.startup import cli

if __name__ == "__main__":
    raise SystemExit(cli())
