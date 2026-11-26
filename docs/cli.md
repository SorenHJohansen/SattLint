# CLI Reference

Running `sattlint` with no arguments opens the interactive shell. Running
`sattlint <command>` uses the headless CLI. Headless commands never prompt,
write data to stdout, write diagnostics to stderr, and return a documented exit
code.

The compact command table also appears in [FEATURE_GUIDE.md](../FEATURE_GUIDE.md).
This page is the full reference, including selection rules and output
contracts.

## Commands at a glance

| Command | Purpose |
| --- | --- |
| `sattlint project show` | Show the resolved project settings. |
| `sattlint analyzers list` | List selectable analyzers with keys, categories, and metadata. |
| `sattlint analyze` | Run analyzers and report findings. |
| `sattlint findings` | Query findings from a stored run. |
| `sattlint show` | Show one finding by its stable ID. |
| `sattlint --version` | Print the package version. |

## Project selection

Every analysis command needs a `.slproj` project file.

- `--project PATH` accepts a file or a directory.
- A directory must contain exactly one file ending in `.slproj`.
- Without `--project`, SattLint walks upward from the current working directory
  and uses the first `.slproj` it finds.
- A blank `--project` value is a usage error instead of falling back to
  discovery.
- Project settings merge over the user configuration.

See [Project files](project-files.md) for the schema and merge rules.

## `sattlint project show`

Prints the effective project after merging project and user configuration.

Options: `--project`, `--format {json,text}`, `--output`, `--quiet`.

The JSON payload contains:

- the project path and root directory;
- the project schema version;
- the load mode;
- configured targets and the project's analyzer selection;
- the effective string capacities;
- the effective `[analysis]` settings;
- the resolved program, ABB, ICF, and additional library paths;
- the config file path and whether it exists;
- the cache directory, run-history directory, and Change Review directory.

```bash
sattlint project show --project app.slproj
sattlint project show --project ./projects --format json
```

## `sattlint analyzers list`

Lists every analyzer a run can select. The `key` value is the exact value for
`--analyzer`.

Options: `--format {json,text}`, `--output`, `--quiet`.

The listing includes each analyzer's key, display name, description, category,
scope, enablement, and delivery metadata such as acceptance tests and shared
artifact dependencies. The same catalog drives the CLI and the interactive
Analyze view.

```bash
sattlint analyzers list
sattlint analyzers list --format json
```

## `sattlint analyze`

Runs the selected analyzers against the project targets.

| Option | Effect |
| --- | --- |
| `--project PATH` | Project file or directory. |
| `--analyzer KEY` | Analyzer to run; repeatable. Overrides the project's `analyzers` list. |
| `--target NAME` | Analyze only this target; repeatable. Names must be configured. |
| `--module PREFIX` | Report only findings at or below this module path; repeatable. |
| `--fail-on {any,none}` | Exit `1` when findings exist, or always exit `0`; default `any`. |
| `--no-cache` | Ignore stored analyzer reports for this run. The parsed project graph is still reused. |
| `--no-save` | Do not store the run in run history. |
| `--refresh-ast` | Rebuild each target's parsed project graph instead of reusing the cached one. |
| `--jobs N` | Run per-target analyzers in `N` forked worker processes; `0` (default) picks a count from the CPU count. |
| `--format {json,ndjson,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

Selection rules:

- The command line wins over the project's `analyzers` list.
- If neither names an analyzer, the command fails with an error that lists every
  selectable analyzer.
- Analyzer keys are case-insensitive and support the documented compatibility
  aliases.
- Selection is exact. Nothing is added, removed, reordered, or replaced.
- Targets are matched case-insensitively against configured target names.
- An empty filter value is a usage error.

```bash
sattlint analyze --project app.slproj
sattlint analyze --project app.slproj --analyzer variables --format ndjson
sattlint analyze --project app.slproj --module Root.A --fail-on none --format json
sattlint analyze --project app.slproj --no-cache --no-save
```

### Module attribution

A full run reports a module-type problem once, at the type's declaration path.
A run limited with `--module` reports the same problem at the instance path you
asked to inspect. The two forms are alternatives, not duplicates: an
instance-level finding appears only in a scoped run.

### Datatype findings

A record datatype with no declaration or field access anywhere is reported once
as an unused datatype. Once any field is touched, the report names the fields
that stay unused instead.

### Output behavior on failure

If a target cannot be loaded, an analyzer raises, or the self-check fails, the
command writes diagnostics to stderr, removes any previous `--output` file, and
returns exit code `2`. A cancelled run returns `130` and also removes the
stale output file. This prevents a pipeline from archiving an old result as if
it were fresh.

## `sattlint findings`

Reads findings from a stored run without analyzing again.

| Option | Effect |
| --- | --- |
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest`. |
| `--analyzer KEY` | Filter by analyzer key; repeatable. |
| `--target NAME` | Filter by target name; repeatable. |
| `--module PREFIX` | Filter by module path prefix; repeatable. |
| `--exact-module` | Require an exact module path match. |
| `--kind KIND` | Filter by finding kind; repeatable. |
| `--rule RULE` | Filter by rule identifier, falling back to the finding kind when a finding has no rule identifier. |
| `--group-by {none,module,analyzer,kind}` | Also return grouped counts; default `none`. |
| `--limit N` | Return at most N findings after filtering. |
| `--format {json,ndjson,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

Rules:

- Module filters match a path prefix by default and compare case-insensitively.
- `/` in a module filter is treated like `.`.
- A `.*` suffix is accepted and removed.
- `--exact-module` requires at least one `--module`.
- The summary counts both findings and occurrences. Repeated identical findings
  collapse into one entry with an occurrence count.
- `--limit` applies after filtering and before grouping.

```bash
sattlint findings --run latest
sattlint findings --module Root.A --group-by module --format json
sattlint findings --rule <rule-id> --limit 20 --format ndjson
```

## `sattlint show`

Shows one finding, including its location and context, by its stable ID.

| Option | Effect |
| --- | --- |
| `FINDING_ID` | Stable finding ID from `analyze` or `findings`. |
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest`. |
| `--format {json,markdown,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

```bash
sattlint show f_7d3f9c1a --format markdown
```

A missing finding or an ambiguous run identifier is an error with exit code
`2`.

## Output contracts

### Streams

- Data goes to stdout.
- Diagnostics, progress, and self-check output go to stderr.
- `--quiet` suppresses progress and diagnostics.
- `--output PATH` redirects the data document to a file; diagnostics still go
  to stderr.

### JSON

- Every JSON document is a single object.
- Every document carries `schema_version: 1`.
- Every document carries a `command` field.
- Errors use a separate error envelope on stderr with an `error` object
  containing a stable code, a message, and details.

### NDJSON

NDJSON output writes one compact JSON object per line. For finding queries it
starts with one envelope record that carries the run, filters, summary, and
groups, followed by one record per finding. Records are flushed as they are
produced, so a consumer can stream them.

### Text and Markdown

Text and Markdown output use human-readable finding labels. Machine
identifiers stay in JSON and NDJSON. Text output is designed for terminals and
CI logs; Markdown output is designed for a pull request comment or a review.

### Finding identity

A finding ID is a stable hash of the target, analyzer, finding kind, optional
rule identifier, module path, site, context, message, and structured payload.
The same finding keeps the same ID across runs.

Repeated identical findings within one run collapse into one entry with an
occurrence count.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, or no blocking findings. |
| `1` | Findings were reported and `--fail-on any` is in effect. |
| `2` | Usage, configuration, project, or target-loading error. |
| `3` | Internal error. |
| `130` | Interrupted. |
| `141` | Broken pipe, such as when a downstream `head` closes the stream. |

A CI job that treats findings as failures can rely on the default `--fail-on
any` and skip parsing. A job that reports findings without failing should pass
`--fail-on none` and inspect the JSON payload.

## End-to-end example

```bash
# 1. Confirm the project resolves as expected.
sattlint project show --project app.slproj --format json

# 2. Run every selected analyzer and write findings to a file.
sattlint analyze --project app.slproj --format json --output findings.json

# 3. Keep the run for later queries, then inspect one module.
sattlint findings --run latest --module Root.A --group-by module --format json

# 4. Open one finding with its full context.
sattlint show <finding-id> --format markdown
```

## Related pages

- [Analyzers](analyzers.md) for what each key reports.
- [Configuration](configuration.md) for the effective settings behind
  `project show`.
- [Caching and runs](caching-and-runs.md) for run history.
- [Interactive UI](interactive-ui.md) for the non-headless surface.
