# Interactive UI

Run `sattlint` with no arguments to open the interactive shell. The shell is
built with Textual and is the primary surface for configuring a project, running
analyzers, browsing results, and generating a Change Review.

The headless CLI is documented in [CLI reference](cli.md). Both surfaces share
the same application layer, so they produce the same findings and run records.

## Startup

The shell always starts with no project loaded.

- **File → Open Configuration** opens an existing `.slproj`.
- **File → New Configuration** scaffolds a new project file.
- **File → Help** shows first-run guidance and keyboard shortcuts.
- **File → Quit** exits.

If no project is open, analysis, results, settings, and review actions explain
that a configuration is required instead of silently doing nothing.

The shell requires Textual. Interactive startup fails with a clear message when
Textual is unavailable; the headless commands still work.

## Views

Switch views with `Ctrl+1` through `Ctrl+5`, the navigation tabs, or the menu.

| View | Key | Purpose |
| --- | --- | --- |
| Analyze | `Ctrl+1` | Select analyzers, run them, and watch session output. |
| Results | `Ctrl+2` | Browse stored runs, modules, and findings. |
| Configuration Settings | `Ctrl+3` | Edit targets, directories, and load mode for the open project. |
| App Settings | `Ctrl+4` | Edit user-level settings such as run history and output retention. |
| Output | `Ctrl+5` | Generate Change Review artifacts. |

The footer shows the active bindings. `Ctrl+C` copies the current output, and
`Tab` / `Shift+Tab` move focus between controls.

## Status bar

The status bar sits above the footer and has three segments:

- the open project's name, or `No configuration`;
- live work: during an analysis it shows percentage complete, an estimated
  time left, the current target and analyzer, and elapsed time; other jobs show
  their label and elapsed time;
- project state: the configured target count and whether there are unsaved
  changes.

The analysis percentage advances per analyzer step, so it holds at `0%` while
the first target is loading. The time-left estimate averages the targets that
already finished and falls back to the fraction of the current target's
analyzers while the first target is still running. It reads `estimating…` until
it has something to measure, and it can move when analyzers differ in cost.

## Analyze view

The Analyze view lists the selectable analyzers from the registry.

- The project's `analyzers` list is preselected when a project is opened.
- Every analyzer shows its name, key, and description.
- **Select all** and **Clear selection** operate on the visible list.
- A filter narrows the visible analyzers.
- **Run selected analyses** starts the run.
- **Cancel run** or `Esc` stops a run in progress.
- Session output streams into the output pane.
- **Clear output** clears the session pane, not run history.

If nothing is selected, the view reports the same guidance as the CLI: name at
least one analyzer in the project file or in the selection list.

During a run the active view shows progress. A failed target or analyzer is
reported in the session output and does not silently disappear. The UI runs the
analysis in a short-lived child process, then loads the stored run record, so
repeated runs do not accumulate parsed project graphs in the shell process.

Cancelling stops the child and the analyzer workers it forked; the app does not
wait for the current analyzer to finish. A cancelled run is discarded; a run
that had already finished saving when the cancel arrived can still appear in
Results. Quit also cancels a running analysis before leaving, so the shell never
waits on an analyzer. Other actions such as Change Review also stop being waited
on when the app quits, so a review that was still being written can be left
partially finished.

## Results view

The Results view lists stored runs, newest first.

- Select a run to load its target and module tree.
- The left pane lists runs; the right pane shows the module tree and the
  selected module's findings.
- **Expand all** and **Collapse all** control the tree.
- Modules that own findings are marked.
- Module-parameter findings are separated from local-variable findings.
- Selecting a module shows its findings without collapsing the tree.
- A finding can be acknowledged for the selected run; acknowledged findings are
  dimmed and marked.
- **Delete run** removes the selected run and its sidecars.

Findings use the human-readable labels, sites, explanations, and suggestions from
the normalized finding model. A run that cannot be read is skipped instead of
breaking the list.

Run retention is controlled by `run_history.limit` in App Settings. A run with
no stored record cannot be opened; the view reports that state.

## Configuration Settings view

This view edits the open project file.

- **Analysis Targets**: add or remove configured programs and libraries.
  Candidates are discovered from the configured roots.
- **Program Folder**: the primary program root.
- **ABB Library**: the ABB library root.
- **Other Libraries**: additional library roots.
- **ICF Folder**: the ICF configuration directory.
- **Mode & Config**: switch between official and draft source resolution.

Directory and target changes are saved back to the project file. A change that
requires the parsed project to be refreshed marks the AST cache for refresh.

The view does not rewrite the user configuration. Application settings belong to
App Settings.

## App Settings view

This view edits user-level settings and writes only the application sections of
the user configuration:

- **Run history**: enable or disable storage and set the retention limit.
- **Debug logging**: enable verbose diagnostics.
- **Session output retention**: how many lines the output pane keeps.
- **Change Review output folder**: where review artifacts are written.

Saving app settings preserves project keys in the same file and strips unknown
or stale keys, so an out-of-date file does not block the save.

## Output view

The Output view generates Change Review artifacts for the configured project.

- **Generate Change Review** runs the review for every configured target.
- Each successful target writes one JSON and one Markdown artifact.
- A failed target is reported, and the remaining targets still run.
- The generated file names are shown in the result message.

Change Review is independent of analyzers. See [Change Review](change-review.md).

## Interaction model

The Textual shell runs an asynchronous application but exposes a synchronous
interaction bridge to the shared application layer. When a workflow asks a
question, pauses, or requests a confirmation, the bridge forwards the request to
the UI thread and waits for the response.

This lets the same workflow code serve the CLI and the UI without branching on
the terminal implementation.

## Failure behavior

- A configuration or project that cannot be loaded is reported in the UI.
- A failed run leaves already produced results intact and records the failure.
- A cancelled run stops immediately and reports cancellation; a run that had
  already finished saving can still appear in Results.
- A modal error view is used for failures that need attention.
- Plain text is rendered as plain text, so a bracketed message in a path or
  exception cannot be interpreted as markup.

## Related pages

- [Getting started](getting-started.md)
- [CLI reference](cli.md)
- [Change Review](change-review.md)
- [Troubleshooting](troubleshooting.md)
