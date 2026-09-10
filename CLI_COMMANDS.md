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
         {init,syntax-check,validate-config,cache-prune,analyze} ...
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

### `sattlint init`

Scaffold a new `.slproj` project file.

```text
sattlint init [--dir DIR] [--name NAME] [--program-dir PROGRAM_DIR]
              [--abb-lib-dir ABB_LIB_DIR] [--icf-dir ICF_DIR]
              [--other-lib-dirs OTHER_LIB_DIRS]
```

| Option | Description |
|--------|-------------|
| `--dir DIR` | Directory to create the project file in (default: current directory) |
| `--name NAME` | Optional project display name |
| `--program-dir PROGRAM_DIR` | Path to program source files (relative to project) |
| `--abb-lib-dir ABB_LIB_DIR` | Path to ABB library files (relative to project) |
| `--icf-dir ICF_DIR` | Path to ICF files (relative to project) |
| `--other-lib-dirs OTHER_LIB_DIRS` | Additional library directories (repeatable, relative to project) |

### `sattlint syntax-check`

Validate one SattLine source file and report a compact syntax or validation
error.

```text
sattlint syntax-check FILE [--output-format {text,json}]
```

| Option | Description |
|--------|-------------|
| `FILE` | Path to the SattLine source file |
| `--output-format`, `--format {text,json}` | Output format |

### `sattlint validate-config`

Validate and report any issues with the current configuration.

```text
sattlint validate-config [--output-format {text,json}]
```

| Option | Description |
|--------|-------------|
| `--output-format`, `--format {text,json}` | Output format |

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
sattlint analyze [--check KEY] [--list-checks] [--issue-kind KIND]
                 [--list-issue-kinds] [--output-format {text,json}]
```

| Option | Description |
|--------|-------------|
| `--check KEY` | Analysis check key to run (repeatable; required unless listing checks or issue kinds) |
| `--list-checks` | List available analysis check keys and exit |
| `--issue-kind KIND` | Filter variable analysis to this issue kind (repeatable; use `--list-issue-kinds` to see choices) |
| `--list-issue-kinds` | List available issue kind values for `--issue-kind` and exit |
| `--output-format`, `--format {text,json}` | Output format for analyze list commands |

At least one `--check KEY` is required to run an analysis; use
`--list-checks` to see the available keys (kebab-case, e.g.
`naming-consistency`, `dataflow`).

## Exit codes

The CLI uses three exit codes, defined in `src/sattlint/cli/_exit_codes.py`:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | A real problem was found (for example `syntax-check` found a syntax error) |
| `2` | Invalid arguments or configuration (unknown command, missing file, missing `--check`) |

Per-command behavior:

- `syntax-check` returns `1` when the file fails to parse or validate.
- `analyze` reports issues in its output but exits `0` once the analysis runs.
- `validate-config` returns `2` on invalid configuration.
- `init`, `cache-prune` return `0` on success and `2` on usage or configuration
  errors.
