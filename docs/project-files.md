# Project Files

A `.slproj` file is the portable, checked-in description of one SattLint
project. It captures everything needed to reproduce an analysis: targets,
source roots, load mode, string capacities, analyzer selection, and
analyzer-specific settings.

Prefer a `.slproj` file over editing the user configuration directly. The user
configuration is machine-local defaults; the project file travels with the
code.

## A complete example

```toml
slproj_version = 2

mode = "official"
analyzed_programs_and_libraries = ["LineController", "CommonLib"]
analyzers = ["variables", "sfc", "dataflow"]

program_dir = "src/programs"
ABB_lib_dir = "src/abb"
icf_dir = "src/icf"
other_lib_dirs = ["src/vendor", "src/shared"]

[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140

[analysis]
cyclomatic_module_threshold = 20
cyclomatic_step_threshold = 10
cyclomatic_equation_block_threshold = 10
fan_in_out_threshold = 3
unsafe_default_tokens = ["bypass", "enable"]
```

All keys except `[string_capacities]` have defaults, so a sparse project file is
valid. The string capacity table is required.

## Top-level keys

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `slproj_version` | integer | `2` | Project file schema version. |
| `mode` | string | `"official"` | `"official"` reads official files; `"draft"` reads draft files. |
| `analyzed_programs_and_libraries` | list of strings | `[]` | Bare unit names to analyze. |
| `analyzers` | list of strings | `[]` | Analyzer keys this project selects. No default set. |
| `program_dir` | string | `""` | Primary program source directory. |
| `ABB_lib_dir` | string | `""` | Primary ABB library directory. |
| `icf_dir` | string | `""` | Directory containing `.icf` configuration files. |
| `other_lib_dirs` | list of strings | `[]` | Additional library roots searched after the primary roots. |
| `string_capacities` | table | required | Capacity of every SattLine string datatype. |
| `analysis` | table | `{}` | Analyzer-specific settings; see [Configuration](configuration.md). |

Unit names never include a file extension. Write `LineController`, not
`LineController.s`.

## Path rules

Every path value resolves relative to the directory that contains the
`.slproj` file:

- empty `program_dir` means an empty path, not the current directory;
- `program_dir = "."` means the project directory;
- absolute paths are used as written;
- `other_lib_dirs` entries are resolved individually, and blank entries are
  dropped.

The project remains valid when the whole directory is moved or checked out on
another machine, as long as the relative layout is preserved.

## Discovery

- `--project PATH` accepts a project file or a directory.
- A directory must contain exactly one file ending in `.slproj`. If it contains
  several, pass the file explicitly.
- Without `--project`, SattLint walks upward from the current working directory
  and uses the first `.slproj` it finds.
- The interactive shell does not auto-discover a project; open or create one
  from the **File** menu.

## String capacities

Version 2 requires a top-level `[string_capacities]` table so every project
states the capacity of each SattLine string datatype instead of inheriting a
hidden default:

```toml
[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140
```

All five keys are required, every value must be a positive integer, and no
other key is accepted. A missing table, a missing key, an unknown key, or a
non-positive value is a load error that names the problem. A version 1 project
is rejected with a message that names the required table and the standard
values.

The values are behavioral, not cosmetic. They drive:

- **String inference**: literal, copy, and concatenation results are sized
  against the configured capacity.
- **String validation**: assignments and variable-to-parameter mappings are
  checked against the capacity of the destination type.
- **PictureDisplay path resolution**: display-path literals are sized from the
  same capacities as the destination.
- **Cache invalidation**: the table is part of the project cache key, so
  changing a capacity invalidates cached results.

## Analyzer selection

Every run names its analyzers. There is no default set.

```toml
analyzers = ["variables", "sfc", "dataflow"]
```

- `sattlint analyzers list` prints the selectable keys.
- `--analyzer KEY` on the command line overrides the project list for that run.
- A run with no selection, on the command line or in the project file, fails
  with an error that lists every selectable analyzer.
- The interactive Analyze view preselects the project list when a project is
  opened.

Choosing analyzers is exact. Nothing is added, removed, reordered, or folded
into another analyzer. See [Analyzers](analyzers.md).

## Merging with user configuration

Project settings merge over the machine-local user configuration:

1. Built-in defaults.
2. User configuration (`config.toml`).
3. The project file.

The project always wins for keys it defines. Application settings such as run
history retention, output retention, debug logging, and the Change Review output
directory live in the user configuration, so opening a project does not reset
them to built-in defaults.

The analyzer settings table is merged field by field, so a project can override
one threshold and inherit the rest.

## Validation and warnings

Loading a `.slproj`:

- rejects an unsupported version;
- rejects a missing or malformed `[string_capacities]` table;
- rejects a wrong type for a known key;
- rejects an invalid `mode`;
- ignores unknown keys with a warning instead of reading them by accident;
- accepts missing known keys by applying project defaults.

Configuration paths are not required to exist at load time. The analysis
self-check reports missing directories and missing targets when a run starts,
so a project can be opened while a share is temporarily unavailable.

## Version history

- Version 1 predates the required string capacity table.
- Version 2 requires `[string_capacities]` and is the only version current
  SattLint loads.

## Related pages

- [Configuration](configuration.md) for the user configuration and every
  analyzer setting.
- [Project loading](project-loading.md) for how the loader consumes these
  values.
- [CLI reference](cli.md) for `project show` output and project resolution
  errors.
