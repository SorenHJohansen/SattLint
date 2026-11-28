# CLI Reference

Running `sattlint` with no arguments opens the interactive shell when stdin and
stdout are terminals, and exits 2 with the usage otherwise. Running
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
| `sattlint review` | Generate Change Review JSON and Markdown artifacts. |
| `sattlint findings` | Query findings from a stored run. |
| `sattlint show` | Show one finding by its stable ID. |
| `sattlint runs list` | List stored runs with status and counts. |
| `sattlint runs show` | Show one stored run, including analyzer and failure detail. |
| `sattlint runs prune` | Remove run records this build cannot read. |
| `sattlint baseline update` | Accept the current findings as the checked-in baseline. |
| `sattlint baseline diff` | Compare a stored run with the baseline without writing it. |
| `sattlint --version` | Print the package version. |

## Project selection

Every analysis command needs a `.slproj` project file.

- `--project PATH` accepts a file or a directory.
- A directory must contain exactly one file ending in `.slproj`.
- Without `--project`, SattLint walks upward from the current working directory.
  At each directory it uses the literal `.slproj` when it exists; otherwise the
  only `*.slproj` file there. The suffix match is case-insensitive, directories
  are ignored, and the walk stops at the first directory with a candidate.
- Two or more project files in that directory is an error that lists the
  candidates; pass `--project` to choose one.
- An explicit `--project` skips discovery.
- A blank `--project` value is a usage error instead of falling back to
  discovery.
- Project settings merge over the user configuration.

`findings`, `show`, `runs list`, and `runs show` use the same discovery rule to
scope stored-run queries. `latest` resolves to the newest run recorded for the
resolved project. `runs list` with no discoverable project lists every stored
run; `runs show latest` still requires a scope.

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
- the effective `[analysis]` settings, with defaults resolved;
- the resolved program, ABB, ICF, and additional library paths;
- the config file path and whether it exists;
- the cache directory, run-history directory, and Change Review directory.

Because the analysis settings are resolved rather than copied from the file, a
setting left out of the project or user configuration appears with the value the
analyzers actually use. Configuration validation follows the same merge: an
optional ICF or library directory is checked only when a selected analyzer or a
configured target needs it, so an unused path does not block an unrelated run.

```bash
sattlint project show --project app.slproj
sattlint project show --project ./projects --format json
```

## `sattlint project targets`

Lists every target the configured roots provide, with the inferred kind
(`program` or `library`), the resolved file path, and any identity problem.

Options: `--project`, `--format {json,text}`, `--output`, `--quiet`.

- A target under `program_dir` is a program; a target under `ABB_lib_dir` or an
  `other_lib_dirs` entry is a library. The kind is inferred from the root, not
  parsed from the source.
- A duplicate name in one root is a warning.
- The same name in two roots is an error that names both files.
- A configured target that keeps a file suffix, or that is not found in any
  configured root, is an error that suggests the correction.
- The command exits `1` when it reports an error and `0` otherwise. A missing
  project is exit `2`.

```bash
sattlint project targets --project app.slproj
sattlint project targets --format json
```

## `sattlint project check`

Validates the project schema, configured roots, and target identity without
running analyzers.

Options: `--project`, `--format {json,text}`, `--output`, `--quiet`.

The check combines the conditional filesystem validation with the target scan,
so an unused optional directory does not fail it while a missing required root
or an ambiguous target does. The JSON payload carries `ok`, `errors`,
`warnings`, and `target_count`. The command exits `0` when the project is valid,
`1` when it reports an error, and `2` for a missing or unreadable project.

```bash
sattlint project check --project app.slproj
```

## `sattlint project init`

Writes a minimal valid version 2 project file. It creates parent directories and
refuses to overwrite an existing file.

Options: `PATH` (a directory or a `.slproj` path, default the current
directory), `--format {json,text}`, `--output`, `--quiet`.

```bash
sattlint project init
sattlint project init ./demo
sattlint project init ./demo/app.slproj --format json
```

A new user can go from an empty directory to a valid target list with three
commands:

```bash
sattlint project init
sattlint project targets
sattlint project check
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
| `--fail-on {error,warning,any,none}` | Exit `1` at or above this severity, or always exit `0`; default `any`. With `--baseline`, only added or changed findings are considered. |
| `--baseline PATH` | Compare the filtered findings with a checked-in baseline and fail only on new or more severe ones. |
| `--no-cache` | Ignore stored analyzer reports for this run. The parsed project graph is still reused. |
| `--no-save` | Do not store the run in run history. |
| `--refresh-ast` | Rebuild each target's parsed project graph instead of reusing the cached one. |
| `--jobs N` | Run per-target analyzers in `N` forked worker processes; `1` (default) runs them in order, `0` picks a count from the CPU count. |
| `--progress` | Emit machine-readable progress records on stderr while the run is in progress. |
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

Severity thresholds:

| `--fail-on` | Exit `1` when |
| --- | --- |
| `error` | at least one `error` finding exists |
| `warning` | at least one `warning` or `error` finding exists |
| `any` | any finding exists, regardless of severity |
| `none` | never |

Only the filtered findings decide the exit code. A value outside this set is a
usage error with exit code `2`.

With `--baseline PATH`, the same filtered findings are compared with the
baseline first, and the exit code depends only on the added and changed entries:

| `--fail-on` | Exit `1` when |
| --- | --- |
| `error` | at least one added or changed entry is `error` |
| `warning` | at least one added or changed entry is `warning` or `error` |
| `any` | any entry was added or changed, regardless of severity |
| `none` | never |

Stale, moved, and unchanged entries never fail. A severity decrease is not a
change. Without `--baseline`, the previous table applies unchanged.

A relative `--baseline` path is resolved against the project root, so
`--project sub/app.slproj --baseline .sattlint-baseline.json` reads the file next
to the project. An absolute path is used as given.

`--baseline` is the CI gate. Review new findings, accept the known ones with
`sattlint baseline update`, and commit the baseline file. The `findings` command
is a query only and never applies the baseline.

Progress records carry a `sattlint-progress` prefix followed by a space and one JSON object
per line. Each record names the phase (`start`, `loading`, `analyzing`, or
`target-complete`) plus the target and analyzer positions, so a supervising
process can show live progress without parsing human diagnostics. `--quiet`
suppresses them together with the rest of the stderr output.

```bash
sattlint analyze --project app.slproj
sattlint analyze --project app.slproj --analyzer variables --format ndjson
sattlint analyze --project app.slproj --module Root.A --fail-on none --format json
sattlint analyze --project app.slproj --fail-on warning
sattlint analyze --project app.slproj --no-cache --no-save
sattlint analyze --project app.slproj --baseline .sattlint-baseline.json --fail-on warning
```

The analyze summary carries `fail_on` with the chosen threshold and
`by_severity` with the finding count in each bucket.

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

If one or more targets cannot be loaded but at least one target succeeds, the
command still writes the successful targets' findings, adds a `failures` array
and a `failed_targets` count to the document, marks the failed targets in the
text summary, and returns exit code `2`. A partial run is never written to run
history, so `findings --run latest` cannot present it as a complete result.

Each failure entry names the target, its `kind` (`load`, `read`, or `parse`),
a message, and the file, line, and column when the parser reported them; absent
positions are `null`. An unreadable file is reported as a `read` failure with
its path, not as a parse failure. Failure lists are capped at 12 entries and the
remainder is summarized as a count.

If every target fails, an analyzer raises, or the self-check fails, the command
writes diagnostics to stderr, removes any previous `--output` file, and returns
exit code `2`. The run is stored with a `failed` status and its failure detail,
so it becomes `latest` instead of an older successful run. `findings --run
latest` then exits `2` and names the failed run. A cancelled run returns `130`
and removes the stale output file; it is not stored. This prevents a pipeline
from archiving an old result as if it were fresh.

`--quiet` suppresses the unknown-project-key warning and the human summary, but
never the final error line.

## `sattlint review`

Generates Change Review artifacts without the interactive UI. It reuses the
same review engine as the TUI, so the JSON and Markdown content is identical for
the same project and target.

| Option | Effect |
| --- | --- |
| `--project PATH` | Project file or directory. |
| `--target NAME` | Review only this target; repeatable. Defaults to every configured target. Names are matched case-insensitively. |
| `--output-dir PATH` | Directory for the artifacts. Defaults to the configured review directory. A missing directory is created. |
| `--format {json,text}` | Report format; default `text`. |
| `--output PATH` | Write the report to a file instead of stdout. The artifacts still go to the review output directory. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

For each reviewed target the command writes two artifacts into the review
output directory:

- `<project>-change-review-<timestamp>.json`
- `<project>-change-review-<timestamp>.md`

The timestamp is UTC and comes from the review metadata. A relative
`--output-dir` resolves against the current working directory. The JSON report
names the resolved project, the resolved output directory, every generated
artifact, and every failed target:

```json
{
  "schema_version": 2,
  "command": "review",
  "project": "/workspace/app.slproj",
  "output_dir": "/workspace/change-review",
  "targets": [
    {
      "target": "Demo",
      "json": "/workspace/change-review/Demo-change-review-20261119T102030.123456Z.json",
      "markdown": "/workspace/change-review/Demo-change-review-20261119T102030.123456Z.md"
    }
  ],
  "failures": [],
  "generated_targets": 1,
  "failed_targets": 0
}
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Every selected target generated both artifacts. |
| `1` | At least one target generated artifacts and at least one failed (partial). |
| `2` | Missing project, no configured or selected target, unusable output directory, or a usage error. Nothing was generated. |

The command never returns `0` when it generated no artifact. A partial review
still writes the successful targets' artifacts and returns `1`. A full failure
uses the CLI error envelope, names each failed target, and returns `2`.

```bash
sattlint review --project app.slproj
sattlint review --project app.slproj --target Demo --output-dir change-review
sattlint review --project app.slproj --format json --quiet
sattlint review --project app.slproj --format text --output review-report.txt
```

## `sattlint findings`

Reads findings from a stored run without analyzing again.

| Option | Effect |
| --- | --- |
| `--project PATH` | Project file or directory that scopes the run lookup. |
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest`. |
| `--analyzer KEY` | Filter by analyzer key; repeatable. |
| `--target NAME` | Filter by target name; repeatable. |
| `--module PREFIX` | Filter by module path prefix; repeatable. |
| `--exact-module` | Require an exact module path match. |
| `--kind KIND` | Filter by finding kind or its documented label; repeatable. |
| `--rule RULE` | Filter by rule identifier, finding kind, or documented label; repeatable. |
| `--group-by {none,module,analyzer,target,kind}` | Also return grouped counts; default `none`. |
| `--limit N` | Return at most N findings after filtering. |
| `--format {json,ndjson,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

Rules:

- Module filters match a path prefix by default and compare case-insensitively.
- `/` in a module filter is treated like `.`.
- A `.*` suffix is accepted and removed.
- `--exact-module` requires at least one `--module`.
- `--kind` accepts either the kind key (for example `unused`) or its documented
  label (for example `Unused variable`). `--rule` accepts a rule ID that the
  selected run contains, a kind key, or a documented label. An unknown value
  exits `2`; it never returns an empty result with exit `0`.
- The summary counts both findings and occurrences, and reports `by_severity`.
  Repeated identical findings collapse into one entry with an occurrence count.
- `--limit` applies after filtering and before grouping.
- Each finding line starts with its severity tag, for example `[warning]`, then
  the target name, then the source location the analyzer recorded when it knows
  one, for example `[warning] Demo  /work/app/programs/Demo.s:12:4`. The CLI does
  not rewrite that path to a repository-relative form; it shows what the
  analyzer recorded. The baseline file stores a project-relative file instead.
  A finding with only a line, or no location, stays readable without
  placeholders.
- `latest` resolves within the project: discovery from the current directory,
  or an explicit `--project`. A run recorded for another project is never
  returned.
- With no discoverable project, `latest` is refused with exit code `2` and a
  message that asks for `--project` or an explicit `--run`. An explicit run ID
  needs no project.
- `latest` includes a failed run. When the newest record failed, the command
  exits `2` with the `run_failed` code and a message that names the run and
  points at `sattlint runs show`; it never returns an older run's findings. An
  explicit `--run ID` naming a failed run is refused the same way.
- When a record newer than the resolved run cannot be read, `latest` exits `2`
  with the `run_unreadable` code instead of falling back to an older record.
  `sattlint runs list` names the skipped record and `sattlint runs prune`
  removes it.
- Text and NDJSON output name the resolved project next to the run.

```bash
sattlint findings --run latest
sattlint findings --project app.slproj --run latest
sattlint findings --run 2026-11-26T10-00-00 --format json
sattlint findings --module Root.A --group-by module --format json
sattlint findings --group-by target --format text
sattlint findings --kind "Unused variable" --format json
sattlint findings --rule <rule-id> --limit 20 --format ndjson
```

`--quiet` drops the progress and diagnostic lines on stderr, including the
unknown-project-key warning. It never suppresses the final error line or the
document on stdout, so `--format json --quiet` writes only the JSON document to
stdout and nothing to stderr on success.

## `sattlint show`

Shows one finding, including its location and context, by its stable ID.

| Option | Effect |
| --- | --- |
| `FINDING_ID` | Stable finding ID from `analyze` or `findings`. |
| `--project PATH` | Project file or directory that scopes the run lookup. |
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest`. |
| `--format {json,markdown,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

```bash
sattlint show f_7d3f9c1a --format markdown
```

Text output adds a `Severity:` line and `File:`, `Line:`, and `Column:` lines
when the finding records them. Markdown output adds `Severity` and `Location`
bullets. A location the analyzer does not know is omitted rather than shown as
zero.

A missing finding, an ambiguous run identifier, an unscoped `latest`, or a
newest run that failed is an error with exit code `2`.

## `sattlint runs`

Run-history commands read the stored records without analyzing again.

### `sattlint runs list`

Lists stored runs newest first. Each row shows the run ID, start time, target
count, finding count, status, and project.

| Option | Effect |
| --- | --- |
| `--project PATH` | Project file or directory that scopes the listing. |
| `--limit N` | Show at most N runs. |
| `--format {json,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

- With `--project`, only runs recorded for that project are listed.
- Without it, discovery walks up from the current directory. When no project is
  found, every stored run is listed.
- Records this build cannot read are counted and named after the table, with
  the reason. They are never silently dropped.
- The JSON document carries `project`, `runs`, `skipped`, and `skipped_count`.
  Each run carries `run_id`, `started_at`, `finished_at`, `project_tag`,
  `project_path`, `target_count`, `analyzer_count`, `finding_count`,
  `failure_count`, and `status`.

```bash
sattlint runs list --project app.slproj
sattlint runs list --format json --limit 5
```

### `sattlint runs show`

Shows one stored run: the same summary as `runs list`, plus the selected
analyzers, one line per analyzer result, and every recorded failure.

| Option | Effect |
| --- | --- |
| `RUN_ID` | Run ID, unique prefix, or `latest`; default `latest`. |
| `--project PATH` | Project file or directory that scopes `latest`. |
| `--format {json,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

`runs show` always displays a failed run; it does not apply the refusal
`findings` uses. The JSON document adds `cancelled`, `selected_analyzers`,
`truncated`, `truncation_note`, `failure_message`, `failure_reason`,
`analyzers`, `failures`, and `output_line_count`. An analyzer entry names its
target, key, name, status, finding count, duration, summary, and skip reason. A
failure entry carries `kind`, the `target` and `analyzer` it belongs to, a
message, and the file, line, and column when known.

```bash
sattlint runs show latest --project app.slproj
sattlint runs show 20261128T101500000000Z-abc123 --format json
```

`latest` resolves within the project and refuses with exit code `2` when no
project can be discovered, when a newer record cannot be read, or when the run
does not exist.

### `sattlint runs prune`

Removes run records this build cannot load, such as a record from another
schema version or a corrupt file, together with their sidecars.

| Option | Effect |
| --- | --- |
| `--keep N` | Also delete readable records older than the newest N. |
| `--format {json,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

A plain prune deletes only records it cannot read. A readable record is deleted
only when `--keep N` asks for a bounded history. The JSON document carries
`removed`, `unreadable`, `over_limit`, `kept`, and `removed_run_ids`.

```bash
sattlint runs prune
sattlint runs prune --keep 20
```

## `sattlint baseline`

The baseline is a checked-in JSON document that records findings a team has
accepted. By default it is `.sattlint-baseline.json` next to the project file.
The document carries a schema version, the generator and creation time, and an
`entries` array sorted by stable finding identity. Each entry stores the
identity, analyzer, kind, severity, module path, project-relative file, line,
and message. It never stores an absolute path, a source snippet, or an
occurrence count.

A reader rejects an unknown schema version instead of treating the document as
empty.

### `sattlint baseline update`

Rewrites the baseline from a stored run. This is the command that accepts known
findings and prunes entries that no longer occur.

| Option | Effect |
| --- | --- |
| `--project PATH` | Project file or directory. |
| `--run ID` | Run ID, unique prefix, or `latest`; default `latest`. |
| `--path PATH` | Baseline file. Defaults to `.sattlint-baseline.json` next to the project file. |
| `--format {json,text}` | Output format; default `text`. |
| `--output PATH` | Write output to a file instead of stdout. |
| `--quiet` | Suppress progress and diagnostics on stderr. |

When a baseline already exists, the command compares it with the rewritten
entries and reports how many entries were added and pruned. A new baseline
reports the entry count only.

A run that failed is refused with exit code `2`, so an incomplete run never
becomes the accepted baseline.

The JSON payload carries `path`, `entry_count`, `generated_by`, `created`, and
the `added` and `pruned` counts when a previous baseline existed.

### `sattlint baseline diff`

Compares a stored run with the baseline and never writes. It exits `0`
regardless of added or changed entries, because the CI gate is
`analyze --baseline`. The run resolution and options are the same as for
`baseline update`. The JSON payload carries `path`, the resolved run, and a
`baseline` object with the same counts and records as the analyze document.

```bash
sattlint baseline update --project app.slproj
sattlint baseline diff --project app.slproj --run latest --format json
sattlint analyze --project app.slproj --baseline .sattlint-baseline.json --fail-on warning
```

### Baseline matching

- Identity comes first. The stable finding ID is the same in the baseline and
  the run.
- Unchanged: same identity, same severity, same file, and same line.
- Moved: same identity with a different file or line, or an identity that
  disappeared while exactly one unmatched baseline entry shares its analyzer,
  kind, module path, and message. The secondary match ignores a leading source
  position such as `Program.icf:12: ` or `Demo.s:12-14 `, so a line shift is
  still recognized as the same site. A moved entry is reported, never fatal.
- Changed: same identity with a higher severity. This is the only change that
  can fail a run.
- Added: a current finding with no identity match and no unique secondary
  match.
- Stale: a baseline entry with no current match. Stale entries are advisory and
  are pruned by `baseline update`.
- If several baseline entries or several current findings share the secondary
  fields, the current findings are reported as added and the baseline entries as
  stale. The tool never guesses.

A severity decrease is not a change. It is reported as moved when the site also
moved, otherwise as unchanged.

The `findings` command remains a query over stored runs. It never applies the
baseline, so `findings --run latest` reports the same findings with or without
one.

## Output contracts

### Streams

- Data goes to stdout.
- Diagnostics, progress, and self-check output go to stderr.
- `--quiet` suppresses progress and diagnostics.
- `--output PATH` redirects the data document to a file; diagnostics still go
  to stderr.

### JSON

- Every JSON document is a single object.
- Every document carries `schema_version: 2`.
- Every document carries a `command` field.
- Errors use a separate error envelope on stderr with an `error` object
  containing a stable code, a message, and details.
- A partial analyze document adds a `failures` array and a `failed_targets`
  count. Successful runs keep the same shape without those fields.
- An `analyze --baseline` document adds a `baseline` object with `path`, the
  `added`, `moved`, `changed`, `stale`, and `unchanged` counts, and an `entries`
  array for every non-unchanged entry. A moved record adds `previous_file` and
  `previous_line`; a changed record adds `previous_severity`.
- A `baseline update` document carries `path`, `entry_count`, `generated_by`,
  `created`, and `added` and `pruned` when a previous baseline existed.
- A `baseline diff` document carries `path`, the resolved `run`, and a
  `baseline` object with the same counts and records as the analyze document.
- A `runs list` document carries `project`, `runs`, `skipped`, and
  `skipped_count`. A `runs show` document carries the run summary plus
  `selected_analyzers`, `analyzers`, `failures`, and the failure reason. A
  `runs prune` document carries `removed`, `unreadable`, `over_limit`, `kept`,
  and `removed_run_ids`.
- A `review` document carries `project`, `output_dir`, `targets`, `failures`,
  `generated_targets`, and `failed_targets`. Each target entry carries its
  target, JSON artifact path, and Markdown artifact path. Each failure entry
  carries the target and a message. A partial review keeps this shape and adds
  failure entries.
- Every finding carries `severity` (`error`, `warning`, or `info`) and optional
  `file`, `line`, `column`, and `end_line` fields. Positions are one-based. A
  position the analyzer does not know is `null`, never zero.

### NDJSON

NDJSON output writes one compact JSON object per line. For finding queries it
starts with one envelope record that carries the run, filters, summary, and
groups, followed by one record per finding. Records are flushed as they are
produced, so a consumer can stream them.

### Text and Markdown

Text and Markdown output use human-readable finding labels. Machine
identifiers stay in JSON and NDJSON. Text output is designed for terminals and
CI logs; Markdown output is designed for a pull request comment or a review.
When a finding records a source location, text finding lines start with it and
`show` lists it, while Markdown carries it as a `Location` bullet.

### Finding identity

A finding ID is a stable hash of the target, analyzer, finding kind, optional
rule identifier, module path, site, context, message, and structured payload.
The encoded parts are an array, so separator-like text inside one part cannot
shift a boundary into another part. The same finding keeps the same ID across
runs. The location fields are presentation metadata and are not part of the
identity hash.

Repeated identical findings within one run collapse into one entry with an
occurrence count.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, or no finding at or above the `--fail-on` threshold. For `review`, every selected target generated artifacts. |
| `1` | At least one filtered finding is at or above the `--fail-on` threshold. With `--baseline`, at least one added or changed entry is. For `review`, a partial review: some targets generated artifacts and some failed. For `project check` and `project targets`, at least one reported validation error. |
| `2` | Usage, configuration, project, or target-loading error. A stored run that failed or could not be read is also exit `2`. For `review`, missing input, no selected target, an unusable output directory, or no artifact generated. |
| `3` | Internal error. |
| `130` | Interrupted. |
| `141` | Broken pipe, such as when a downstream `head` closes the stream. |

A query against a failed or unreadable run reports a stable error code:
`run_failed` when the resolved run did not complete, and `run_unreadable` when a
newer record for the scope cannot be loaded. Both exit `2`, so a pipeline can
tell a refusal apart from an empty result.

A CI job that treats every finding as a failure can rely on the default
`--fail-on any` and skip parsing. A job that reports findings without failing
should pass `--fail-on none` and inspect the JSON payload.

The recommended CI setting is `--fail-on warning`. It fails the build on
correctness defects and on risky patterns, while naming, comment, complexity,
and design advice remains visible as `info` without breaking the pipeline. A
strict correctness gate can use `--fail-on error` instead.

A team that has accepted known findings can commit `.sattlint-baseline.json`
and gate only on new or more severe findings:

```bash
sattlint analyze --project app.slproj --baseline .sattlint-baseline.json --fail-on warning
```

The baseline gate ignores unchanged, moved, and stale entries, so only added or
changed findings at or above the threshold fail the job.

```bash
sattlint analyze --project app.slproj --fail-on warning --format json
```

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

# 5. Accept reviewed findings and commit the baseline.
sattlint baseline update --project app.slproj

# 6. Make CI fail only on new or more severe findings.
sattlint analyze --project app.slproj --baseline .sattlint-baseline.json --fail-on warning
```

## Related pages

- [Analyzers](analyzers.md) for what each key reports.
- [Configuration](configuration.md) for the effective settings behind
  `project show`.
- [Caching and runs](caching-and-runs.md) for run history.
- [Interactive UI](interactive-ui.md) for the non-headless surface.
