# SattLint Feature Guide

This guide describes the headless command line surface. It is the reference
for scripts, CI jobs, and AI agents. The full documentation set is indexed at
[docs/README.md](docs/README.md). For the interactive terminal user interface,
see [README.md](README.md).

Run `sattlint` with no arguments to open the interactive shell. Run
`sattlint <command>` to stay non-interactive. Headless commands never prompt,
write data to stdout, write diagnostics to stderr, and exit with a documented
code.

## Commands at a glance

| Command | Purpose |
|---|---|
| `sattlint project show` | Show the resolved project settings |
| `sattlint project targets` | List configured targets with kind and path |
| `sattlint project init` | Create a minimal version 2 project file |
| `sattlint project check` | Validate schema, roots, and targets without analysis |
| `sattlint analyzers list` | List analyzer keys, categories, and rule IDs |
| `sattlint analyze` | Run analyzers and report findings |
| `sattlint review` | Generate Change Review JSON and Markdown artifacts |
| `sattlint findings` | Query findings from a stored run |
| `sattlint show` | Show one finding by its stable ID |
| `sattlint runs list` | List stored runs with status and counts |
| `sattlint runs show` | Show one stored run with analyzer and failure detail |
| `sattlint runs prune` | Remove run records this build cannot read |
| `sattlint baseline update` | Accept the current findings as the checked-in baseline |
| `sattlint baseline diff` | Compare a stored run with the baseline without writing it |

`sattlint --version` prints the package version.

## Selecting a project

Every analysis command needs a `.slproj` project file.

- `--project PATH` accepts a project file or a directory. A directory must
  contain exactly one `.slproj` file, otherwise pass the file explicitly.
- Without `--project`, SattLint walks up from the current directory looking for
  a `.slproj` file.
- Paths inside the project file are relative to the file, so the project is
  portable across machines.
- Project settings merge over the user configuration in
  `~/.config/sattlint/config.toml` on Linux, or `%APPDATA%\sattlint\config.toml`
  on Windows.

```bash
sattlint project show --project app.slproj --format json
sattlint project show --project ./projects --format text
```

## `sattlint project show`

Prints the effective settings after project and user configuration are merged.

Options: `--project`, `--format {json,text}`, `--output`, `--quiet`.

Use it to confirm which directories, targets, and mode an analysis will use.

## `sattlint project targets`, `init`, and `check`

- `project targets` scans the configured roots and lists each unit name with its
  inferred kind and resolved path. Duplicate names in one root are warnings; a
  name provided by two roots, a name that keeps a file suffix, and a missing
  target are errors.
- `project init` writes a minimal version 2 file at a directory or `.slproj`
  path and refuses to overwrite.
- `project check` validates the schema, the conditional filesystem rules, and
  target identity. It exits `0` for a valid project and `1` for a reported
  error.

```bash
sattlint project init
sattlint project targets
sattlint project check
```

## `sattlint analyzers list`

Lists every analyzer that can be selected, with its key, category, and rule
IDs. Analyzer keys from this command are the valid values for
`analyze --analyzer`.

Options: `--format {json,text}`, `--output`, `--quiet`.

```bash
sattlint analyzers list
sattlint analyzers list --format json
```

## `sattlint analyze`

Runs the selected analyzers against the project targets and reports findings.

| Option | Effect |
|---|---|
| `--project PATH` | Project file or directory |
| `--analyzer KEY` | Run only this analyzer; repeatable, overrides the project's `analyzers` list |
| `--target NAME` | Analyze only this target; repeatable |
| `--module PREFIX` | Report only findings at or below this module path; repeatable |
| `--fail-on {error,warning,any,none}` | Exit 1 at or above this severity, or always exit 0; default `any` |
| `--baseline PATH` | Compare with a checked-in baseline and fail only on new or more severe findings |
| `--no-cache` | Skip the analysis cache for this run |
| `--no-save` | Do not store the run in run history |
| `--format {json,ndjson,sarif,text}` | Output format; default `text` |
| `--output PATH` | Write output to a file instead of stdout |
| `--quiet` | Suppress progress and diagnostics on stderr |

```bash
sattlint analyze --project app.slproj
sattlint analyze --project app.slproj --analyzer variables --format ndjson
sattlint analyze --project app.slproj --module Root.A --fail-on none --format json
sattlint analyze --project app.slproj --fail-on warning
sattlint analyze --project app.slproj --no-cache --no-save
sattlint analyze --project app.slproj --format sarif --output build/sattlint.sarif
```

Every finding carries a severity of `error`, `warning`, or `info`. A proven
defect is `error`, a risky pattern or uncertain heuristic is `warning`, and
naming, comment, complexity, or design advice is `info`. The recommended CI
setting is `--fail-on warning`, which fails on `warning` and `error` findings
while leaving `info` findings visible. Use `--fail-on error` for a strict
correctness gate, or `--fail-on none` to report without failing.

By default the run is stored in run history and its ID is part of the JSON
payload, so later `findings` and `show` calls can refer to it. Findings can also
carry a source file and line, shown in text, Markdown, and JSON output.

### Module attribution

A full run reports a module-type problem once, at the type's declaration
path (`TypeDef:Name`). A run limited with `--module` reports the same
problem at the instance path you asked to inspect. The two forms are
alternatives, not duplicates: an instance-level finding appears only in a
scoped run.

### Datatype findings

A record datatype that has no declaration or field access anywhere is
reported once, as an unused datatype. Once any field is touched, the
report names the fields that stay unused instead.

## `sattlint review`

Generates the Change Review JSON and Markdown artifacts without the TUI.

```bash
sattlint review --project app.slproj --output-dir change-review --format json --quiet
```

Exit `0` when every selected target generated artifacts, `1` for a partial
review, and `2` when nothing was generated or the input is unusable. A missing
output directory is created. See [Change Review](docs/change-review.md).

## `sattlint runs list`, `show`, and `prune`

List stored runs with their status and counts, inspect one run's analyzers and
failure detail, and remove records this build cannot read.

```bash
sattlint runs list --format json
sattlint runs show latest
sattlint runs prune
```

`findings --run latest` refuses a failed or unreadable newest record with exit
`2` instead of returning an older success. A plain prune removes only unreadable
records; `--keep N` adds a bounded retention cut.

## `sattlint findings`

Reads findings from a stored run without analyzing again.

| Option | Effect |
|---|---|
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest` |
| `--analyzer KEY` | Filter by analyzer key; repeatable |
| `--target NAME` | Filter by target name; repeatable |
| `--module PREFIX` | Filter by module path prefix; repeatable |
| `--exact-module` | Require an exact module path match |
| `--kind KIND` | Filter by finding kind or documented label; repeatable |
| `--rule RULE` | Filter by rule ID, finding kind, or documented label; repeatable |
| `--group-by {none,module,analyzer,target,kind}` | Also return grouped counts; default `none` |
| `--limit N` | Return at most N findings after filtering |
| `--format {json,ndjson,sarif,text}` | Output format; default `text` |
| `--output PATH` | Write output to a file instead of stdout |
| `--quiet` | Suppress progress and diagnostics on stderr |

```bash
sattlint findings --run latest
sattlint findings --module Root.A --group-by module --format json
sattlint findings --rule <rule-id> --limit 20 --format ndjson
```

## `sattlint show`

Shows one finding, including its location and context, by its stable ID.

| Option | Effect |
|---|---|
| `FINDING_ID` | Stable finding ID from `analyze` or `findings` |
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest` |
| `--format {json,markdown,text}` | Output format; default `text` |
| `--output PATH` | Write output to a file instead of stdout |
| `--quiet` | Suppress progress and diagnostics on stderr |

```bash
sattlint show 7d3f9c1a --format markdown
```

## Output contracts

- JSON output is a single object with `schema_version: 2` and a `command` field,
  so consumers can pin the contract.
- NDJSON output writes one JSON object per line, which suits streaming and
  `jq`.
- Text and Markdown output use human-readable finding labels. Machine IDs stay
  in JSON and NDJSON.
- Finding payloads carry `severity` and optional `file`, `line`, `column`, and
  `end_line` fields. Text finding lines start with a severity tag such as
  `[warning]`, and `show` reports the severity and location.
- Finding IDs are stable across runs for the same finding.
- Data goes to stdout. Diagnostics and progress go to stderr, and `--quiet`
  suppresses the progress portion.
- With `--format json`, failures also emit a JSON error envelope on stderr.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success, or no finding at or above the `--fail-on` threshold |
| `1` | At least one filtered finding is at or above the `--fail-on` threshold |
| `2` | Usage, configuration, project, or target-loading error |
| `3` | Internal error |
| `130` | Interrupted |

A CI job that treats every finding as a failure can rely on the default
`--fail-on any` and skip parsing the output. The recommended CI gate is
`--fail-on warning`. A job that reports findings but does not fail on them
should pass `--fail-on none` and inspect the JSON payload.

`analyze --baseline` is the stricter gate for an existing project: only findings
that are new or more severe than the checked-in baseline can fail the run.
Review new findings, accept the known ones with `sattlint baseline update`, and
commit the baseline file. The `findings` command is a query only and never
applies the baseline.

## End-to-end example

```bash
# 1. Confirm the project resolves as expected.
sattlint project show --project app.slproj --format json

# 2. Run every analyzer and fail the job at the recommended threshold.
sattlint analyze --project app.slproj --fail-on warning --format json --output findings.json

# 3. Keep the run for later queries, then inspect one module.
sattlint findings --run latest --module Root.A --group-by module --format json

# 4. Open one finding with its full context.
sattlint show <finding-id> --format markdown
```

## Related surfaces

- Interactive shell views, configuration workflow, and troubleshooting:
  [README.md](README.md).
- Scriptable command definitions and shareable support policy:
  [SUPPORT.md](SUPPORT.md).
- Language parsing and parser-owned syntax validation: the external
  [sattline-parser](https://github.com/SorenHJohansen/sattline-parser) project.
