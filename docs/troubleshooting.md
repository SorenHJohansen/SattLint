# Troubleshooting

Start with the effective project, not with assumptions:

```bash
sattlint project show --format text
sattlint analyzers list
```

`project show` prints the resolved paths, targets, mode, capacities, and
analyzer selection. Most "it cannot find my code" problems are visible there.

## Installation

### `sattlint` is not found

The pipx or virtual environment scripts directory is not on `PATH`.

- With pipx: run `pipx ensurepath`, then restart the terminal.
- pipx commands live under `~/.local/bin` on Linux and
  `%USERPROFILE%\.local\bin` on Windows.
- In a virtual environment, call `.venv/bin/sattlint` or
  `.venv\Scripts\sattlint` directly.

Confirm with:

```bash
sattlint --version
```

### Python version error

SattLint requires Python 3.13 or newer. Check the interpreter used by the
installer, install a current Python, then point the pipx environment at it.
`pipx upgrade` and `pipx reinstall` keep the interpreter they were created
with unless you name a new one:

```bash
pipx reinstall --python 3.14 sattlint
```

Use the interpreter version you installed. If pipx reports that SattLint is
already installed, run `pipx install --python 3.14 --force sattlint` instead.

### Interactive shell fails to start

The shell requires Textual. Confirm the package is installed and that the
environment can import it:

```bash
python -c "import sattlint.ui; print('ok')"
```

Headless commands still work without a working interactive terminal.

## Project and configuration

### `No .slproj found`

No `.slproj` exists in the current directory or any ancestor. Either create one
or pass it explicitly:

```bash
sattlint analyze --project path/to/.slproj
```

A directory argument must contain exactly one file ending in `.slproj`.

### `Missing required [string_capacities]`

The project is version 1 or incomplete. Add the required table:

```toml
[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140
```

All five keys are required, and every value must be a positive integer.

### Unknown configuration key

A typo was ignored with a warning. Compare the key with
[Configuration](configuration.md). Unknown keys are stripped deliberately so a
misspelled key does not silently change behavior in an unpredictable way.

### Configuration value error

A known key has the wrong type. Typical causes:

- a boolean written as a quoted string (`debug = "false"`);
- a list written as a string (`other_lib_dirs = "lib"`);
- a non-positive retention or threshold value;
- an invalid `mode`.

Fix the value and rerun.

### Self-check fails before analysis

The self-check reports missing directories, missing targets, or invalid analyzer
settings. Fix each reported item. A run does not start with a failed self-check.

## Targets and loading

### Target not found

Check all of these:

- the target is a bare unit name with no file extension;
- `program_dir`, `ABB_lib_dir`, and `other_lib_dirs` point at the real roots;
- the selected mode matches the available files (`official` or `draft`);
- the target actually exists in one of those roots.

### Missing libraries

Add the root that contains the library to `ABB_lib_dir` or `other_lib_dirs`.
Order matters: earlier roots are searched first.

### A target fails to load

A load is all or nothing. The error names the target and usually the missing
dependency or the parser diagnostic that stopped it. Enable debug logging for
more detail, then rerun the focused load. If the failure is in the grammar or
parser-owned syntax, report it to the `sattline-parser` project.

When other targets loaded, the command still reports their findings and marks
the failed target, then exits `2` without saving the partial run. A failure
reported as a read error names the file and its path, and the fix is usually a
missing file, a directory in its place, or a permission problem. A parse
failure carries the parser's line and column when it reported one.

Failure lists are capped at 12 entries per section and the remainder is shown
as a count, so a broken dependency graph does not turn one error into pages of
output.

### Results look outdated

- The AST cache is validated against file manifests; changing a source file or a
  companion file invalidates the entry.
- The analysis report cache also depends on analyzer settings and analyzer
  behavior versions.
- If a stored analyzer report is suspect, delete the cache directory or run
  with `--no-cache` to ignore reports for one run. Add `--refresh-ast` only
  when the parsed project graph itself is suspect.
- In the UI, opening a project refreshes the parsed project; rerun the analysis
  after a large change.

See [Caching and runs](caching-and-runs.md).

## Analyzer selection

### `No analyzers selected`

Neither the command line nor the project names an analyzer. Add an `analyzers`
list to the project or pass `--analyzer`:

```bash
sattlint analyze --project app.slproj --analyzer variables
```

### `Unknown analyzer key`

Run `sattlint analyzers list` and use the exact key. Keys are
case-insensitive, but the spelling must match an available analyzer.

### An analyzer failed

The run reports which analyzer failed and on which target. A failure does not
stop other analyzers, but the headless command treats the run as failed because
a partial result is misleading.

Enable debug logging to include the full exception text. In normal mode the
message names the exception type only so internal paths and values do not leak
into shared output.

## Findings and run history

### `findings` cannot find the run

- A run is stored only when run history is enabled, `--no-save` was not passed,
  and every selected target loaded.
- `--run latest` uses the newest stored run for the project discovered from the
  current directory, or named with `--project`.
- Without a discoverable project, `latest` is refused; pass `--project` or an
  explicit run ID.
- A run ID prefix must be unique.
- A corrupt run record is ignored rather than partially read.

### `show` cannot find the finding

The finding ID belongs to the selected run. Pass the same `--run` value that
produced the ID, or use `latest`.

### Acknowledged findings disappeared

Acknowledgements belong to one stored run. Deleting or pruning the run removes
its acknowledgement sidecar.

## Interactive UI

### A view says no configuration is open

Open or create a project from the **File** menu. The shell does not
auto-discover a project.

### Changes are not saved

Configuration Settings edits the open project file. App Settings edits the user
configuration. Confirm which view you are in.

### Change Review produces no files

- Configure at least one target.
- Confirm the review output directory is writable.
- Check the per-target failure message. One failing target does not stop the
  others, but a review fails entirely when every target fails.

## Documentation checks

### `check_docs.py` reports a missing link target

The linked file does not exist relative to the page. Fix the path or remove the
link. Paths are relative to the Markdown file, not to the repository root.

### `check_docs.py` reports a missing anchor

The heading does not exist, or its slug differs. Heading anchors are lowercase,
punctuation is removed, spaces become hyphens, and duplicate headings get a
numeric suffix.

### `check_docs.py` reports an unindexed page

Add a link to the page from `docs/README.md` in the appropriate table.

### markdownlint reports style

Use dash bullets, ATX headings, fenced code blocks with a language, and blank
lines around headings, lists, and fences. See
[Documentation maintenance](documentation.md).

## Performance

Analysis is CPU-bound. To understand a slow run:

- enable `SATTLINT_PROFILE=1`;
- inspect the profiling log under the cache directory;
- compare the target load stages with analyzer durations;
- try a focused analyzer selection to isolate the cost;
- run with `--no-cache` once to tell a stale analyzer report from an analyzer
  that is genuinely slow, and with `--refresh-ast` only if the parsed graph is
  in question.

A first run is slower because it builds the cache. Later runs reuse the parsed
project graph when its manifest is still valid.

## Getting help

- Usage and bug reports: GitHub issues.
- Security vulnerabilities: follow [SECURITY.md](../SECURITY.md).
- Parser grammar and parser-owned syntax: the `sattline-parser` project.

Include the SattLint version, operating system, exact command, and a minimal
safe reproduction.
