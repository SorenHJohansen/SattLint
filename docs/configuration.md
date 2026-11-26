# Configuration

SattLint has two configuration layers:

- a machine-local user configuration that supplies defaults and application
  settings;
- a portable `.slproj` project file that describes one analysis project.

The project file is documented in [Project files](project-files.md). This page
documents the user configuration, the shared settings, and the merge and
validation rules.

## Location

| Platform | Configuration file |
| --- | --- |
| Linux | `$XDG_CONFIG_HOME/sattlint/config.toml`, or `~/.config/sattlint/config.toml` |
| Windows | `%APPDATA%\sattlint\config.toml` |

On first interactive launch SattLint creates the file from built-in defaults.
The file is TOML.

The same directory contains:

- `projects/`, a location the interactive shell can use for project files;
- `change-review/`, the default Change Review output directory.

The cache and run history live under the platform cache directory, not the
configuration directory. See [Caching and runs](caching-and-runs.md).

## Defaults

The built-in configuration is the base layer for every merge.

```toml
analyzed_programs_and_libraries = []
mode = "official"
debug = false
program_dir = ""
ABB_lib_dir = ""
icf_dir = ""
other_lib_dirs = []

[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140

[run_history]
enabled = true
limit = 50

[output]
retention_lines = 4000

[review]
output_dir = ""

[analysis]
```

An empty `[analysis]` table means every analyzer setting uses its own default.
See [Analyzer settings](#analyzer-settings).

## Top-level keys

| Key | Type | Purpose |
| --- | --- | --- |
| `analyzed_programs_and_libraries` | list of strings | Default analysis targets. A project file normally supplies these. |
| `mode` | `"official"` or `"draft"` | Which file variant the loader resolves. |
| `debug` | boolean | Enables verbose diagnostics and debug-level logging. |
| `program_dir` | path string | Primary program root. |
| `ABB_lib_dir` | path string | Primary ABB library root. |
| `icf_dir` | path string | ICF configuration directory. |
| `other_lib_dirs` | list of path strings | Additional library roots. |
| `string_capacities` | table | Capacity of each string datatype. |
| `run_history` | table | Whether runs are stored and how many are retained. |
| `output` | table | Session output retention for the interactive shell. |
| `review` | table | Change Review output location. |
| `analysis` | table | Analyzer-specific settings. |

## Application settings

Four sections are application-level and are written back by the interactive
**App Settings** view without touching project keys:

- `debug`
- `run_history`
- `output`
- `review`

`run_history` controls whether completed runs are saved and how many recent
runs are kept:

```toml
[run_history]
enabled = true
limit = 50
```

`output.retention_lines` controls how many lines the interactive session output
pane keeps.

`review.output_dir` selects the Change Review output directory. An empty value
uses `<config dir>/change-review`. A relative value resolves against the
configuration directory, not against the current working directory, so the
location is independent of where the shell was started.

## Analyzer settings

Analyzer settings live under `[analysis]`. The same table can appear in the user
configuration and in a project file. Project values win.

| Key | Default | Used by |
| --- | --- | --- |
| `unsafe_default_tokens` | `["bypass", "enable"]` | Variable analysis: flags initialized to true whose names contain one of these tokens. |
| `cyclomatic_module_threshold` | `20` | Cyclomatic complexity: worst scope in a program or module. |
| `cyclomatic_step_threshold` | `10` | Cyclomatic complexity: an SFC step. |
| `cyclomatic_equation_block_threshold` | `10` | Cyclomatic complexity: an equation block. |
| `fan_in_out_threshold` | `3` | Variable analysis: high fan-in or fan-out of a root-level variable. |
| `module_grid` | `0.02` | Module layout: drawing grid used when a module writes no `Grid` clause. |
| `module_grid_tolerance` | `0.00001` | Module layout: distance below which a value counts as exactly on the grid. The same distance decides when an object is fully outside a clipping rectangle. |

Rules:

- An empty list for `unsafe_default_tokens` is treated as the default list.
- A threshold must be a positive integer; an invalid value falls back to the
  default when read, and configuration validation reports it as an error.
- A module-layout distance must be a finite positive number; an invalid value
  falls back to the default when read, and configuration validation reports it
  as an error.
- The analyzer settings are part of the analysis report cache key. Changing one
  invalidates cached analyzer reports even though the parsed project is
  unchanged.

## Load and merge order

Every effective configuration is built in this order:

1. Built-in defaults.
2. The user `config.toml`.
3. The `.slproj` project file.

Nested tables merge field by field. A project that sets one analyzer threshold
inherits the rest. Application sections from the user configuration survive a
project load.

The resulting configuration is what the loader, analyzers, run store, and
Change Review receive.

## Validation

Configuration validation has two levels.

**Value validation** checks shape and allowed keys:

- unknown top-level or section keys are reported and stripped;
- wrong types are load errors, for example `debug = "false"` or a string where
  a list is expected;
- `mode` must be `official` or `draft`;
- `run_history.limit` and `output.retention_lines` must be positive integers;
- `review.output_dir` must be a path string;
- every string capacity must be a positive integer;
- every analyzer threshold must be a positive integer;
- a module-layout distance must be a finite positive number.

**Filesystem validation** checks configured paths and targets:

- `program_dir`, `ABB_lib_dir`, and `icf_dir` must exist and be readable when
  set;
- every `other_lib_dirs` entry must exist;
- every configured target must resolve in one of the configured roots under the
  selected mode.

A missing path is a warning at configuration load time and an error at analysis
self-check time. This lets settings be edited while a directory is temporarily
unavailable.

Saving settings performs value validation only. It never fails because a
configured directory is temporarily missing.

## Self-check before analysis

Before an analysis run starts, SattLint prints a self-check:

- the Python version;
- every required top-level configuration key;
- each configured directory;
- each configured target;
- the analyzer settings namespace.

A failed self-check aborts the run before targets are loaded. The run result
carries no target results, and the headless CLI reports a preflight failure
with exit code `2`.

## Warnings

Unknown project keys are ignored with a warning:

```text
Warning: Ignoring unknown .slproj key 'programdir' in my-project/.
```

Unknown configuration keys are also reported before they are stripped, so a
typo does not silently disable a setting. With `--format json` or `--format
ndjson`, configuration warnings are attached to the CLI error envelope's
`details` when a command fails.

## Environment variables

| Variable | Effect |
| --- | --- |
| `XDG_CONFIG_HOME` | Relocates the Linux configuration directory. |
| `XDG_CACHE_HOME` | Relocates the Linux cache directory. |
| `APPDATA` | Relocates the Windows configuration and cache roots. |
| `SATTLINT_UI` | Selects the interactive UI. Only `textual` is accepted. |
| `SATTLINT_PROFILE` | Enables the profiler-gated diagnostics log. |
| `SATTLINT_PROFILE_ANALYZERS` | Enables analyzer reuse diagnostics and timings. |

Profiling writes a JSONL log under the cache directory. It never changes
analysis results.

## Related pages

- [Project files](project-files.md) for the portable project schema.
- [Caching and runs](caching-and-runs.md) for cache and run-history locations.
- [Troubleshooting](troubleshooting.md) for configuration errors.
