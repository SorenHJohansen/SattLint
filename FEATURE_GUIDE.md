# SattLint Feature Guide

This guide describes the headless command line surface. It is the reference
for scripts, CI jobs, and AI agents. For the interactive terminal user
interface, see [README.md](README.md).

Run `sattlint` with no arguments to open the interactive shell. Run
`sattlint <command>` to stay non-interactive. Headless commands never prompt,
write data to stdout, write diagnostics to stderr, and exit with a documented
code.

## Commands at a glance

| Command | Purpose |
|---|---|
| `sattlint project show` | Show the resolved project settings |
| `sattlint analyzers list` | List analyzer keys, categories, and rule IDs |
| `sattlint analyze` | Run analyzers and report findings |
| `sattlint findings` | Query findings from a stored run |
| `sattlint show` | Show one finding by its stable ID |

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
| `--analyzer KEY` | Run only this analyzer; repeatable, defaults to all |
| `--target NAME` | Analyze only this target; repeatable |
| `--module PREFIX` | Report only findings at or below this module path; repeatable |
| `--fail-on {any,none}` | Exit 1 when findings exist, or always exit 0; default `any` |
| `--no-cache` | Skip the analysis cache for this run |
| `--no-save` | Do not store the run in run history |
| `--format {json,ndjson,text}` | Output format; default `text` |
| `--output PATH` | Write output to a file instead of stdout |
| `--quiet` | Suppress progress and diagnostics on stderr |

```bash
sattlint analyze --project app.slproj
sattlint analyze --project app.slproj --analyzer variables --format ndjson
sattlint analyze --project app.slproj --module Root.A --fail-on none --format json
sattlint analyze --project app.slproj --no-cache --no-save
```

By default the run is stored in run history and its ID is part of the JSON
payload, so later `findings` and `show` calls can refer to it.

## `sattlint findings`

Reads findings from a stored run without analyzing again.

| Option | Effect |
|---|---|
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest` |
| `--analyzer KEY` | Filter by analyzer key; repeatable |
| `--target NAME` | Filter by target name; repeatable |
| `--module PREFIX` | Filter by module path prefix; repeatable |
| `--exact-module` | Require an exact module path match |
| `--kind KIND` | Filter by finding kind; repeatable |
| `--rule RULE` | Filter by rule ID; repeatable |
| `--group-by {none,module,analyzer,kind}` | Also return grouped counts; default `none` |
| `--limit N` | Return at most N findings after filtering |
| `--format {json,ndjson,text}` | Output format; default `text` |
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

- JSON output is a single object with `schema_version: 1` and a `command` field,
  so consumers can pin the contract.
- NDJSON output writes one JSON object per line, which suits streaming and
  `jq`.
- Text and Markdown output use human-readable finding labels. Machine IDs stay
  in JSON and NDJSON.
- Finding IDs are stable across runs for the same finding.
- Data goes to stdout. Diagnostics and progress go to stderr, and `--quiet`
  suppresses the progress portion.
- With `--format json`, failures also emit a JSON error envelope on stderr.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success, or no blocking findings |
| `1` | Findings were reported and `--fail-on any` is in effect |
| `2` | Usage, configuration, project, or target-loading error |
| `3` | Internal error |
| `130` | Interrupted |

A CI job that treats findings as failures can rely on the default `--fail-on
any` and skip parsing the output. A job that reports findings but does not fail
on them should pass `--fail-on none` and inspect the JSON payload.

## End-to-end example

```bash
# 1. Confirm the project resolves as expected.
sattlint project show --project app.slproj --format json

# 2. Run every analyzer and fail the job when findings exist.
sattlint analyze --project app.slproj --format json --output findings.json

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
