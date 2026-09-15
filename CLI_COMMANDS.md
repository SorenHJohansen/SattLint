# SattLint CLI Commands

Authoritative reference for the `sattlint` command-line surface. This document
tracks `sattlint --help` and the per-command help; when they disagree, the CLI
is the source of truth.

The interactive Textual UI (opened by running `sattlint` with no arguments) is
described in [FEATURE_GUIDE.md](FEATURE_GUIDE.md).

## Global usage

```text
sattlint [-h] [--version] [--config PATH] [--project PATH] [--no-cache]
         [--quiet] [--debug] [--ui {textual}]
         {cache-prune,analyze} ...
```

### Global options

| Option | Description |
|--------|-------------|
| `--version` | Print the installed version and exit |
| `--config PATH` | Path to a SattLint config file |
| `--project PATH` | Path to a `.slproj` project file (default: auto-discover from CWD) |
| `--no-cache` | Skip the AST cache |
| `--quiet` | Suppress stdout output |
| `--debug` | Enable debug output |
| `--ui {textual}` | Interactive UI mode to use when no subcommand is selected (Textual only) |

## Commands

### `sattlint cache-prune`

Remove stale or unusable persistent cache artifacts from the SattLint cache
directory.

```text
sattlint cache-prune [--cache-dir CACHE_DIR] [--output-format {text,json}]
```

| Option | Description |
|--------|-------------|
| `--cache-dir CACHE_DIR` | Optional cache directory to prune instead of the default SattLint cache location |
| `--output-format`, `--format {text,json}` | Output format |

### `sattlint analyze`

Run explicitly selected analysis checks against configured targets.

```text
sattlint analyze [--check KEY] [--list-checks] [--refresh-caches]
                 [--output-format {text,json}]
```

| Option | Description |
|--------|-------------|
| `--check KEY` | Analysis check key to run (repeatable; required unless listing checks) |
| `--list-checks` | List available analysis check keys and exit |
| `--refresh-caches` | Force a full rebuild of the AST and report caches for this run |
| `--output-format`, `--format {text,json}` | Output format for analyze list commands |

At least one `--check KEY` is required to run an analysis; use
`--list-checks` to see the available keys (kebab-case, e.g.
`variables`, `dataflow`).

## Exit codes

The CLI uses two exit codes, defined in `src/sattlint/cli/_exit_codes.py`:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Invalid arguments or configuration (unknown command, missing file, missing `--check`) |

Per-command behavior:

- `analyze` reports issues in its output but exits `0` once the analysis runs.
- `cache-prune` returns `0` on success and `2` on usage or configuration errors.
