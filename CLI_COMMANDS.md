# SattLint CLI Commands

The `sattlint` command has a single behavior: running it with no arguments
launches the interactive Textual UI.

```text
sattlint
```

Any supplied arguments are rejected with a usage error (exit code `2`). All
CLI subcommands and flags (`analyze`, `cache-prune`, `--config`, `--project`,
`--no-cache`, `--quiet`, `--debug`, `--version`, `--ui`, and the rest) have
been removed; every capability is reachable from the Textual UI instead.

The interactive Textual UI is described in [FEATURE_GUIDE.md](FEATURE_GUIDE.md).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | TUI launch succeeded (or the session quit cleanly) |
| `2` | Arguments were supplied to `sattlint` |
