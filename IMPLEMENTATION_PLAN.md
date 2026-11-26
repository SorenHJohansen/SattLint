# SattLint implementation plan, November 2026

Status: proposed. Consolidated from the security, packaging, workflow, and performance
reviews of tree `feature/parser-2026.11.5` at `46e41ebe`.

This plan is ordered by risk and dependency, not by review area. It is written to be
executed by subagents in waves, with at most two builders and one reviewer active at a
time. Each package is one coherent change with its own files, tests, and acceptance
criteria. A wave is complete only when its gate passes.

## Priority model

| Level | Meaning | Release rule |
| --- | --- | --- |
| P0 | Trust boundary, release correctness, or data integrity | Blocks any tag or publish |
| P1 | CI adoption, untrusted input, or the finding contract | Required before recommending SattLint to another team |
| P2 | Workflow, release engineering, and performance | Required for a complete release, can follow P0 and P1 |
| P3 | Truth and hygiene | Continuous, never allowed to block a fix |

The first tag after this plan must include every P0 package. A release that claims CI
readiness must include P0 and P1. Do not start Wave 5 before Wave 1 lands, because the
benchmark gate needs the finding contract.

## How to execute with subagents

Roles:

- **Orchestrator.** One session owns the branch, file ownership, commits, and the full
  verification ladder. It writes the package prompt, launches builders, resolves
  questions, runs the gate, and requests the reviewer pass.
- **Builder.** One fresh subagent per package. It may edit only the files listed under
  Owns, runs focused tests, and reports what changed. It does not commit, push, tag, or
  publish.
- **Reviewer.** The existing `sattlint-reviewer` subagent, read-only, one pass per wave.
  Apply its findings, re-run the gate, and stop. Do not loop reviews.

Concurrency rule: never more than two builders and one reviewer at once. A wave table
below names the batches. Start the next batch only after the previous batch reports and
the orchestrator has run the focused tests.

Every builder prompt must contain:

1. Package id and goal.
2. The exact files it owns and the files it must not touch.
3. The behavior to add or fix, with the failure the change must prevent.
4. Acceptance tests that fail before the change and pass after it.
5. The focused validation command.
6. Documentation and changelog obligations.
7. The rule to stop and report if a change is required outside its file list.

File ownership rule: two builders may never edit the same file in one batch. If a package
needs a file owned by another, it waits for the next batch or becomes a sequential step in
the same track. Do not let a builder "just fix" a neighboring file.

Commit protocol: one commit per package, conventional message, no history rewrite, no
push, no tag. The orchestrator commits after the focused test passes and the diff is
reviewed for scope. A wave commit lands only after the wave gate passes.

Verification ladder, run from the repository virtual environment:

```bash
.venv/bin/python -m pytest tests/<focused path> -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pyright src/sattlint tests
.venv/bin/python -m pytest -q --tb=short
.venv/bin/python scripts/check_docs.py
```

For packaging changes also run `python -m build` and `twine check dist/*`. For Markdown
changes run the pre-commit hooks. A wave gate is the full ladder plus one reviewer pass.

Guardrails for every builder: do not edit SattLine source outside this repository, do not
read or copy the local reference corpus, do not add customer names or private paths, do not
add dash punctuation to prose, and do not run a global install.

## Wave overview

| Wave | Theme | Packages | Gate |
| --- | --- | --- | --- |
| 0 | Release blockers and trust boundary | 6 | Working tree is safe to tag |
| 1 | Finding contract and CI gate | 3 | A CI job can fail on new or severe findings |
| 2 | Untrusted input and reliability | 6 | Hostile projects cannot exhaust or escape the tool |
| 3 | Release engineering | 2 | Wheel and sdist are built, installed, and reproducible |
| 4 | Workflow and product surface | 9 | A user can install, open, triage, export, and compare |
| 5 | Performance and scalability | 4 | A ratio gate protects the load path and the pool |
| 6 | Truth and cleanup | 3 | No public claim lacks an implementation |

## Wave 0: release blockers and trust boundary

Batch 1: W0-1, W0-2, W0-3. Batch 2: W0-4, W0-5. Batch 3: W0-6.

### W0-1 Child process import safety (P0)

Goal: the analysis child must never import a module from the analyzed project.

Owns: `src/sattlint/application/subprocess_analysis.py`,
`tests/app/test_subprocess_analysis.py`.

Steps:

1. Add `-P` to the child command and `PYTHONSAFEPATH=1` to the child environment.
2. Add a regression test with a project-local `sattlint.py` that writes a marker, run the
   child from that directory, and assert the marker is absent.
3. Record the isolation guarantee in the module docstring and in `docs/architecture.md`.

Acceptance: the shadow module does not execute; analysis still works from the repository
and from an installed wheel.

Validate: `.venv/bin/python -m pytest tests/app/test_subprocess_analysis.py -q`.

### W0-2 Non-interactive entry guard (P0)

Goal: bare `sattlint` must not enter the Textual shell when stdin is not a terminal.

Owns: `src/sattlint/cli/startup.py`, `tests/app/test_app_textual_startup.py`.

Steps:

1. Check `sys.stdin.isatty()` and `sys.stdout.isatty()` before starting the shell.
2. Exit 2 with the existing usage text and a one-line explanation when either is false.
3. Add a test that runs the entry point with a pipe and asserts a fast, clean exit.

Acceptance: `timeout 5 sattlint </dev/null` exits 2 with no escape output.

Validate: the focused test plus the timeout command above.

### W0-3 Sequential analysis default (P0)

Goal: stop paying for a worker pool that is slower than the sequential loop.

Owns: `src/sattlint/cli/entry.py`, `src/sattlint/application/analyzer_workers.py`,
`docs/cli.md`, `tests/app/test_analyzer_workers.py`.

Steps:

1. Change the effective default for `--jobs` to 1. Keep `--jobs 0` and explicit values
   available for the later fix and for measurement.
2. Update the help text so the default is not described as automatic.
3. Add a test that pins the default and a warm run comparison in the package report.

Acceptance: a default run uses one worker; `--jobs 4` still selects four.

Validate: focused worker tests plus a manual timing note in the package report. The
benchmark decision is W5-1.

### W0-4 Release state reconciliation (P0)

Goal: version, changelog, tag, artifacts, and PyPI agree before anything is published.

Owns: `src/sattlint/__version__.py`, `CHANGELOG.md`, `.github/workflows/ci.yml`,
`tests/test_release_state.py` (new, if a test is the right seam), `dist/` (remove with
`trash-put`).

Steps:

1. Choose the next version, recommended 2026.11.6, and move the current unreleased entries
   into a dated section for it. Fold or renumber the stale 2026.11.5 section so one version
   describes one code state.
2. Add a CI check that fails when the package version has an entry that is already dated,
   when `[Unreleased]` is empty at tag time, or when the tag and package version differ.
3. Remove the stale `dist/` artifacts. They are not a source of truth and one differs from
   the published wheel.
4. Confirm the metadata documentation URL resolves before the next publish.

Acceptance: `sattlint --version` matches the changelog top section, the tag check fails on
a deliberate mismatch, and `dist/` no longer exists.

Validate: the new check, `python -m build`, `twine check dist/*`.

### W0-5 Project discovery and run scoping (P0)

Goal: a project file is found predictably, and `findings` never silently reads another
project's run.

Owns: `src/sattlint/project/io.py`, `src/sattlint/cli/_findings.py`,
`src/sattlint/cli/commands.py`, `docs/project-files.md`, `docs/cli.md`,
`tests/project/test_project_io.py`, `tests/app/test_analysis_findings.py`.

Adopted rule: at each ancestor, use `.slproj` if it exists; otherwise use the only
`*.slproj` file in that directory. If two or more exist, fail with the candidate list and
tell the user to pass `--project`. Stop at the first ancestor with a candidate and never
merge candidates across directories. Match the suffix case-insensitively, ignore
directories, and let an explicit `--project` bypass discovery entirely.

Steps:

1. Implement the rule once and use it from `project show`, `analyze`, `findings`, and
   `show`.
2. Make `findings --run latest` resolve within the discovered project. When no project is
   discoverable, refuse the implicit lookup and require `--run` or `--project`. When a
   project is used, name it in the run header.
3. Add `--project` to `findings` and `show` if that is the cheapest way to make the scope
   explicit.
4. Add tests for: literal wins over a named file, one named file, two named files, none
   found, and a run from another project.

Acceptance: from a directory with a named project, `findings --run latest` either reports
that project or exits with a clear error. It never prints another project's findings.

Validate: the two focused test modules plus a manual two-project probe.

### W0-6 Load failure UX and partial results (P0)

Goal: a user sees one actionable error, and one bad target does not erase the good ones.

Owns: `src/sattlint/core/debug.py`, `src/sattlint/project/loading.py`,
`src/sattlint/cli/commands.py`, `src/sattlint/project/support.py`,
`tests/project/`, `tests/app/test_subprocess_analysis.py` only if the envelope is shared.

Steps:

1. Log the traceback only when debug is enabled. Otherwise log one line and emit the
   structured error that JSON mode already produces.
2. Cap the number of failure entries in one message and truncate with a count.
3. Keep successful target results when another target fails. Exit 2, mark the failed target
   in the summary, and keep the run out of history.
4. Make `--quiet` suppress the unknown-key warning and the human summary, but never the
   final error line.
5. Report an unreadable file as a read error, not a parse error.
6. Include the parser line and column in the machine-readable diagnostic.

Acceptance: text mode produces at most a few lines for a missing dependency; a two-target
project with one failure still reports the successful target; JSON keeps the same shape
with a new fields-only addition.

Validate: focused project and CLI tests, plus the mixed-project probe.

## Wave 1: finding contract and CI gate

Sequential, one builder track. W1-2 starts after W1-1, W1-3 after W1-2. This wave touches
the same files and must not be parallelized.

### W1-1 Source location on findings (P1)

Goal: every finding can point at a file, line, column, and end position.

Owns: `src/sattlint/application/findings.py`, `src/sattlint/models/_variable_issues.py`
only if the span needs a richer type, `src/sattlint/cli/_findings.py`,
`src/sattlint/cli/_payloads.py`, `src/sattlint/cli/commands.py`,
`src/sattlint/ui/_app_textual_results.py`, `docs/cli.md`, `tests/app/test_analysis_findings.py`.

Steps:

1. Add optional `file`, `line`, `column`, and `end_line` to the finding model and its
   serialized payload. Keep them optional so analyzers can migrate incrementally.
2. Propagate the span that the variables analyzer already records. Audit the other
   analyzers and fill spans where the data is already available; record the rest as
   follow-ups rather than inventing positions.
3. Show the location in text and Markdown output and in the Results view. Do not add an
   editor launch in this package.
4. Document the JSON schema addition and bump the CLI schema version if the project treats
   added fields as a schema change.

Acceptance: `show` and `findings` include a real file and line for the analyzers that have
spans; missing spans serialize as null and do not break consumers.

Validate: focused finding and CLI tests plus a snapshot of one text and one JSON finding.

### W1-2 Severity and fail-on policy (P1)

Goal: CI can fail on correctness defects without failing on style advice.

Owns: `src/sattlint/analyzers/registry/_registry_delivery.py`,
`src/sattlint/application/findings.py`, `src/sattlint/cli/entry.py`,
`src/sattlint/cli/commands.py`, `src/sattlint/cli/_payloads.py`, `docs/analyzers.md`,
`docs/cli.md`, `tests/analyzers/suites/test_registry_catalog.py`,
`tests/app/test_analysis_findings.py`.

Steps:

1. Add `error`, `warning`, and `info` to the finding payload. Assign the default per
   finding kind, with analyzer metadata as the fallback for kinds that do not set one. Do
   not classify by analyzer category.
2. Reserve `error` for near-certain defects, such as a read of an overwritten value, an
   SFC contract violation, or a capacity overflow. Use `warning` for risky patterns and
   any heuristic whose classification is uncertain. Use `info` for naming, comment, and
   complexity advice.
3. Add `--fail-on error|warning|any|none` and include the chosen threshold in the summary
   and JSON envelope. Keep `any` as the compatibility default and document
   `--fail-on warning` as the CI setting.
4. Show severity in text and JSON; keep the UI grouping unchanged unless it is free.

Acceptance: a project with only info findings exits 0 under `--fail-on warning` and 1 under
`--fail-on any`; one warning exits 1 under `--fail-on warning`.

Validate: focused registry, finding, and CLI tests.

### W1-3 Baseline file and run diff (P1)

Goal: a team can accept known findings and fail only on new ones.

Owns: `src/sattlint/runs/` (new baseline module), `src/sattlint/cli/entry.py`,
`src/sattlint/cli/commands.py`, `src/sattlint/cli/_findings.py`, `docs/cli.md`,
`docs/caching-and-runs.md`, `README.md`, `tests/runs/test_run_store.py`, new baseline tests.

Steps:

1. Define `.sattlint-baseline.json` next to the project file, with `schema_version`,
   `generated_by`, `created`, and a sorted `entries` array. Each entry stores the stable
   finding identity plus analyzer, kind, severity, module path, relative file, line, and
   message. Do not store absolute paths or source snippets.
2. Add `analyze --baseline PATH`, `baseline update`, and `findings --diff`, or a single
   `baseline` command if that keeps the CLI smaller. Report added, moved, changed, stale,
   and unchanged counts.
3. Match by identity first. When an identity disappears, use the secondary fields to
   recognize a moved site; if several candidates match, report removed and added rather
   than guessing. A severity increase re-surfaces the finding and is subject to the
   current threshold. Stale entries are reported, not fatal, and `baseline update` prunes
   them.
4. Replace the per-run TUI acknowledgement with a baseline entry. Keep the UI action if it
   can write the baseline; otherwise remove it and document the command.
5. Harden the finding identity so quoted identifiers cannot collide. Prefer length
   prefixes or a hash over ad hoc delimiters.

Acceptance: a moved line is reported as moved, a severity increase fails under
`--fail-on warning`, stale entries are listed without failing, and a new finding exits 1
only under the baseline gate.

Validate: focused run-store, baseline, and CLI tests plus a two-run probe.

## Wave 2: untrusted input and reliability

Batch 1: W2-1, W2-2, W2-5. Batch 2: W2-3, W2-4, W2-6.

### W2-1 ICF linear parsing and input caps (P1)

Goal: a hostile file cannot spend minutes in a regex or allocate gigabytes.

Owns: `src/sattlint/analyzers/icf/_icf_file_io.py`,
`src/sattlint/analyzers/icf/analyzer.py`, `src/sattlint/config/`,
`src/sattlint/project/loading.py`, `docs/configuration.md`, `tests/analyzers/test_icf*.py`.

Steps:

1. Replace the reference regex with a linear prefix strip and `partition(":")`, preserving
   the current accepted forms.
2. Add configurable limits for source bytes, ICF bytes, and project bytes, with documented
   defaults that fit real projects.
3. Enforce the limits with a per-target load failure that names the file and the limit. Do
   not abort the whole project when only one target is oversized.
4. Hash and read large files in chunks so a rejected file is not loaded whole first.
5. Add regression tests for a long colon-free ICF line and an oversized source.

Acceptance: a 1 MB colon-free ICF line parses in linear time; a file over the limit fails
with a clear message and bounded memory.

Validate: focused ICF and project tests plus a timing probe on the long-line fixture.

### W2-2 Terminal and Markdown sanitization (P1)

Goal: project text cannot control the terminal, the Rich markup, or the report structure.

Owns: new `src/sattlint/utils/terminal_text.py`,
`src/sattlint/cli/_output.py`, `src/sattlint/cli/commands.py`,
`src/sattlint/ui/_app_textual_results.py`,
`src/sattlint/change_review/serialization/markdown_serializer.py`,
`tests/core/`, `tests/change_review/test_change_review.py`.

Steps:

1. Add one sanitizer for C0, C1, and Unicode format characters, with a mode that keeps
   tabs and newlines only where the sink expects them.
2. Apply it to every terminal sink: project show, finding text, error text, tree labels,
   and status messages. JSON and NDJSON stay byte-exact.
3. Pass `Text(label)` or an explicit no-markup path to Textual so a name cannot raise a
   markup error or hide text.
4. Choose a Markdown fence longer than any backtick run in the snippet, or indent the
   block by four spaces. Add a test with an indented fence and a fake heading.
5. Keep the sanitizer out of the parser and the data model; this is a presentation concern.

Acceptance: an escape sequence, a newline, and a markup tag in a target name render as
visible text; a comment with a fence cannot create a heading.

Validate: focused core, CLI, UI, and change-review tests plus a probe project with hostile
names.

### W2-3 Cache trust hardening (P1)

Goal: write access to the cache directory is not enough to control what the next run reads.

Owns: `src/sattlint/cache/__init__.py`, `src/sattlint/cache/classes.py`,
`tests/cache/test_cache_integrity.py`, `tests/cache/test_cache_classes.py`.

Steps:

1. Authenticate the manifest, either by signing it or by including its digest in the signed
   payload. Reject a mismatch as a cache miss, not a crash.
2. Add a model version to the cache key so a format change cannot be replayed.
3. Read the signing key with an ownership and mode check and refuse a symlink. Fall back to
   a cache miss when the key cannot be trusted.
4. Replace the unrestricted unpickler with a restricted one, or move to a non-executable
   format. If a format change is too large for this package, document the residual risk and
   open a follow-up with a size estimate.
5. Call the over-budget prune after save, and add a test that proves the budget is enforced.

Acceptance: a tampered manifest is rejected; a symlinked or wrong-mode key is rejected; the
AST budget actually removes the oldest entries.

Validate: focused cache tests plus a tamper probe.

### W2-4 Artifact permissions, profile log, and history bounds (P1)

Goal: no source excerpt is world-readable by default, and history cannot grow forever.

Owns: `src/sattlint/change_review/artifacts.py`, `src/sattlint/core/profiling.py`,
`src/sattlint/runs/io.py`, `docs/change-review.md`, `docs/caching-and-runs.md`,
`tests/change_review/`, `tests/runs/test_run_store.py`.

Steps:

1. Write Change Review artifacts 0600 and create the review directory 0700.
2. Write the profile log 0600, cap its size, and rotate or truncate it.
3. Cap stored diagnostics and the run record size. Report truncation in the record.
4. Add tests for the file modes and for the cap behavior on each surface.

Acceptance: generated artifacts are 0600, the profile log is 0600 and bounded, and an
oversized record is truncated with a visible marker.

Validate: focused change-review, profiling, and run tests.

### W2-5 Project root containment policy (P2)

Goal: a `.slproj` cannot silently point the tool at an unrelated directory.

Owns: `src/sattlint/project/models.py`, `src/sattlint/project/io.py`,
`docs/project-files.md`, `tests/project/test_project_io.py`.

Steps:

1. Decide and document the policy: roots must resolve under the project directory unless an
   explicit opt-in is set.
2. Warn on `..` and absolute roots with the resolved path, and require the opt-in for
   loading. Keep the error actionable.
3. Add tests for `..`, an absolute root, a symlink, and a legitimate nested root.

Acceptance: an unrelated root is refused or requires an explicit opt-in; a nested root and
a symlink inside the project still work.

Validate: focused project tests.

### W2-6 Worker liveness watchdog (P2)

Goal: a killed analyzer worker fails the run instead of hanging it.

Owns: `src/sattlint/application/analyzer_workers.py`,
`tests/app/test_analyzer_workers.py`.

Steps:

1. Replace the bare `imap_unordered` wait with a loop that detects a dead worker or uses an
   executor that surfaces a broken pool.
2. Terminate the pool, record a failed analyzer result, and let the run finish with a
   diagnostic.
3. Add a test that kills a worker and asserts a bounded failure.

Acceptance: a killed worker produces a failed analyzer entry within a few seconds.

Validate: focused worker tests plus a kill probe.

## Wave 3: release engineering

Batch 1: W3-1 and W3-2 in parallel. They touch different files.

### W3-1 CI artifacts, matrix, and provenance (P2)

Goal: CI proves both distributions install, on every supported interpreter.

Owns: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`,
`.github/workflows/scorecard.yml`, `docs/ci-and-release.md`.

Steps:

1. Build both the wheel and the sdist in CI, install each into a clean environment, and
   smoke the same commands for both.
2. Add a Python 3.14 job. Add macOS or drop the OS-independent claim.
3. Set `SOURCE_DATE_EPOCH` for the build, and verify two builds produce the same wheel.
4. Add a tag ancestry check and a publish concurrency group.
5. Refresh the CodeQL pin so the merge does not regress it.
6. Add a sdist manifest policy: prune `src/*.egg-info`, include the changelog and the
   license, and state what is intentionally excluded.

Acceptance: a release-candidate build installs from both artifacts on 3.13 and 3.14; two
builds with the same epoch hash identically; a tag on a non-main commit fails the ancestry
check.

Validate: workflow syntax check plus a local `python -m build` and install of both artifacts.

### W3-2 Install docs, assets, and dependency bounds (P2)

Goal: the documented install path works on a current distribution.

Owns: `README.md`, `docs/getting-started.md`, `docs/ci-and-release.md`, `pyproject.toml`,
`src/sattlint/ui/_app_textual_shared.py`, new `MANIFEST.in`.

Steps:

1. Make `pipx install sattlint` the primary instruction and keep a virtual environment
   fallback. Remove the bare `pip install --user` recommendation.
2. Load the `.tcss` lazily or degrade to a default stylesheet when it is missing. Add a test
   for a missing asset.
3. Add an upper bound for `rich` that matches the tested major.
4. Keep the sdist contents intentional and documented.

Acceptance: a fresh pipx-style isolated environment runs `sattlint --version` and
`analyzers list`; deleting the stylesheet does not break the import.

Validate: package build, clean-environment smoke, and the asset test.

## Wave 4: workflow and product surface

Tracks:

- Track A, CLI surface, sequential: W4-2, W4-3, W4-4, W4-7, W4-9.
- Track B, UI, parallel with Track A: W4-1.
- Track C, config, after Track A: W4-5, W4-6.
- Track D, docs, last: W4-8.

Batch 1: W4-1 and W4-2. Batch 2: W4-3. Batch 3: W4-4. Batch 4: W4-5 and W4-7 (different
files). Batch 5: W4-6. Batch 6: W4-9 and W4-8.

### W4-1 TUI project open and navigation truth (P2)

Goal: a checked-in project can be opened from the shell, and the guidance matches the UI.

Owns: `src/sattlint/ui/_app_textual_actions.py`,
`src/sattlint/ui/_app_textual_widgets.py`, `src/sattlint/ui/_app_textual_shared.py`,
`src/sattlint/ui/_app_textual_app.py`, `src/sattlint/cli/menu.py`, `README.md`,
`docs/interactive-ui.md`, `tests/app/`.

Steps:

1. Add Browse and a path field to Open Configuration. Default New Configuration to the
   current directory, or ask, instead of always writing to the config directory.
2. Rename the "File menu" wording to match the flat bar, or add a real menu. Renaming is
   cheaper and is the recommendation.
3. Rename the Output view to Change Review, or label it so the artifact name is obvious.
4. Add a UI test for opening a project outside the config directory.

Acceptance: a repository `.slproj` opens from the shell in two actions; no doc names a menu
that does not exist.

Validate: focused UI tests plus a scripted pilot open.

### W4-2 CLI query and quiet semantics (P2)

Goal: filters, grouping, and text output match what the tool prints.

Owns: `src/sattlint/cli/entry.py`, `src/sattlint/cli/_findings.py`,
`src/sattlint/cli/commands.py`, `src/sattlint/cli/_output.py`,
`src/sattlint/cli/_project.py`, `docs/cli.md`, `tests/app/`.

Steps:

1. Accept the human labels in `--kind` and `--rule`, or remove those filters until rule ids
   exist. A typo must exit 2, not return zero findings at exit 0.
2. Add `--group-by target`.
3. Include the target name in text finding lines.
4. Make `--quiet` suppress the human report on stderr in JSON mode and suppress the
   unknown-key warning. Never suppress the final error line.
5. Document the defaults and the exact exit codes.

Acceptance: filters accept documented labels; a typo exits 2; text lines identify the
target; `--format json --quiet` writes only the JSON document.

Validate: focused CLI tests plus an output snapshot.

### W4-3 Run history commands and failure visibility (P2)

Goal: a user can see what runs exist, what failed, and which run is current.

Owns: `src/sattlint/runs/`, `src/sattlint/cli/entry.py`,
`src/sattlint/cli/commands.py`, `docs/caching-and-runs.md`, `docs/cli.md`,
`tests/runs/test_run_store.py`.

Steps:

1. Add `runs list` and `runs show` with id, time, project, target count, finding count, and
   status.
2. Record failed runs or a failure marker so `findings --run latest` does not present the
   previous success as current.
3. Report records skipped because of an unknown schema version, and offer a prune command.

Acceptance: after a failed analysis, `runs list` shows the failure and `findings --run
latest` does not silently return old data.

Validate: focused run-store and CLI tests.

### W4-4 Headless Change Review (P2)

Goal: Change Review is reachable without the TUI.

Owns: `src/sattlint/cli/entry.py`, new `src/sattlint/cli/commands/` module if the CLI is
split, `src/sattlint/application/change_review.py`, `docs/change-review.md`,
`docs/cli.md`, `tests/app/`, `tests/change_review/`.

Steps:

1. Add a `review` command that takes a project, optional targets, and an output directory,
   and writes the existing JSON and Markdown artifacts.
2. Reuse the application seam; do not duplicate the review engine.
3. Define exit codes for a successful review, a missing input, and a partial target
   failure.
4. Document the artifact contract and one CI example.

Acceptance: a headless review on the synthetic project produces the same artifacts as the
TUI path.

Validate: a golden artifact comparison plus the focused tests.

### W4-5 Config validation and effective settings (P2)

Goal: optional directories do not block unrelated analyzers, and `project show` tells the
truth.

Owns: `src/sattlint/config/validation.py`, `src/sattlint/cli/commands.py`,
`src/sattlint/cli/_project.py`, `docs/configuration.md`, `docs/cli.md`,
`tests/project/`.

Steps:

1. Validate `icf_dir`, `ABB_lib_dir`, and `other_lib_dirs` only when a selected analyzer or
   target needs them.
2. Make `project show` render the merged effective analysis settings, not defaults, in text
   and JSON.
3. Add tests for an unselected ICF analyzer with a missing directory, and for a merged
   setting that differs from the default.

Acceptance: missing optional directories do not abort unrelated work; `project show`
matches the values used by `analyze`.

Validate: focused config and CLI tests.

### W4-6 Config and run schema versioning (P2)

Goal: a downgrade does not delete settings or hide history.

Owns: `src/sattlint/config/io.py`, `src/sattlint/runs/io.py`,
`docs/configuration.md`, `docs/caching-and-runs.md`, `tests/project/`, `tests/runs/`.

Steps:

1. Add a schema version to the user config. Preserve unknown keys on read and write.
2. Refuse to save over a config written by a newer version, with an actionable message.
3. Version run records and report skipped versions to the caller instead of returning
   nothing.
4. Add migration tests for one older and one newer file.

Acceptance: an unknown key survives a read and write; a newer config is not overwritten;
an old run is reported as skipped, not missing.

Validate: focused config and run tests.

### W4-7 Project targets, init, and check (P2)

Goal: a user can discover valid unit names, create a project, and validate it without
running analyzers.

Owns: `src/sattlint/cli/entry.py`, new project command modules,
`src/sattlint/project/`, `docs/cli.md`, `docs/project-files.md`, `tests/project/`.

Steps:

1. Add `project targets` with name, kind, and resolved path, scanning the configured roots.
2. Add `project init` that writes a minimal valid version 2 file in the current directory.
3. Add `project check` that validates schema, roots, and targets without analysis.
4. Fix target identity: warn on duplicate names, error on ambiguous stems across roots, and
   suggest stripping a known suffix or correcting a directory.
5. Decide whether library versus program is declarable. If not, show the inferred kind.

Acceptance: a new user can go from an empty directory to a valid target list with three
commands, and ambiguous targets are reported.

Validate: focused project and CLI tests.

### W4-8 Consumer CI and workflow docs (P2)

Goal: a team can adopt SattLint in its own pipeline from the documentation alone.

Owns: `docs/`, `README.md`, `FEATURE_GUIDE.md`.

Steps:

1. Add a consumer CI page with a minimal workflow, install, analyze, baseline, and artifact
   upload. Use the discovery and baseline behavior that actually shipped.
2. Document automatic creation of a missing output directory.
3. Update the getting-started path after W4-1 and W4-7 so the first ten minutes work.
4. Link every new page from `docs/README.md`.

Acceptance: the documented workflow runs verbatim in a scratch repository.

Validate: `scripts/check_docs.py` plus a transcript of the example.

### W4-9 SARIF and CI annotations (P2, after W1-1)

Goal: findings reach code scanning and pull request annotations.

Owns: `src/sattlint/cli/_output.py`, new exporter module,
`src/sattlint/cli/entry.py`, `docs/cli.md`, `tests/app/`.

Steps:

1. Add `--format sarif` with SARIF 2.1.0, using the location and severity added in Wave 1.
2. Map rule ids from the public analyzer catalogue; if rule ids still do not exist, use a
   stable analyzer key plus kind and document it.
3. Include a GitHub Actions example in the consumer CI page.
4. Keep the JSON schema versioned and tested.

Acceptance: a SARIF consumer accepts the file, and a finding without a location is omitted
or emitted with a document-level location, never with a fake position.

Validate: schema validation plus a snapshot test.

## Wave 5: performance and scalability

Batch 1: W5-1, W5-3, W5-4. Batch 2: W5-2 (owns the loading seam).

### W5-1 Parallel analysis decision and fix (P2)

Goal: keep the pool only if it beats sequential with the full analyzer set.

Owns: `src/sattlint/application/analyzer_workers.py`,
`src/sattlint/application/checks_execution.py`, `docs/cli.md`,
`tests/app/test_analyzer_workers.py`.

Steps:

1. Profile one pooled job against the sequential loop and find the repeated setup that
   doubles CPU.
2. Fix the duplication or remove the pool. Do not keep a pool that is within noise of
   sequential.
3. If it stays, enable it only above a measured target count and analyzer count, and pin
   the threshold in the benchmark suite.
4. Record the decision and the numbers in the package report.

Acceptance: the default is never slower than sequential on the benchmark fixtures. A pool
that cannot beat sequential is removed.

Validate: the benchmark harness from W5-4 plus the worker tests.

### W5-2 Parser discovery reuse and warm fast path (P2)

Goal: stop rebuilding the parser index per target and reloading graphs that the cache
already covers.

Owns: `src/sattlint/project/loading.py`, `src/sattlint/project/parser_adapter.py`,
`src/sattlint/application/checks_execution.py`,
`src/sattlint/parser_api.py` only if the parser needs a new seam, `tests/project/`.

Steps:

1. Build the parser discovery index once per project load and reuse it across targets.
2. Validate cached analyzer reports before loading and converting the graph for a warm run.
3. Keep a correctness fallback: if the cache cannot prove coverage, load as today.
4. Add tests for a warm run with one changed target and one unchanged target.

Acceptance: the cold `stat` count drops substantially, and a warm 200-unit run avoids the
graph conversion it does today. Correctness is unchanged.

Validate: the benchmark harness plus focused loading and checks tests.

### W5-3 Lazy startup imports (P2)

Goal: a one-unit run does not pay for Change Review and UI imports.

Owns: `src/sattlint/cli/startup.py`, `src/sattlint/cli/entry.py`, `tests/app/`.

Steps:

1. Move optional command and UI imports inside the branch that needs them.
2. Keep `--version`, `--help`, `analyzers list`, and `project show` on the light path.
3. Measure import time before and after; keep the change only if it saves at least 50 ms.

Acceptance: startup drops by the target amount with no new import cycle.

Validate: the import-time probe plus focused CLI tests.

### W5-4 Benchmark harness and ratio gate (P2)

Goal: a repeatable benchmark that catches regressions without flaking on shared runners.

Owns: new `bench/` directory, `scripts/` if the team prefers it, `.github/workflows/ci.yml`,
`docs/development.md`.

Steps:

1. Commit a deterministic generator and one pinned minimal unit template. Generate project
   size and lines per unit at run time; do not commit large fixtures.
2. Measure cold, warm, and `--no-cache`, with isolated XDG directories and a timeout.
3. Store a JSON baseline with medians. Add a correctness assertion and within-run ratios to
   CI: warm over cold, 200 over 50, and per-line cost.
4. Add a nightly job on one fixed runner for absolute budgets, with a 25 percent tolerance.
5. Document how to refresh the baseline and why ratios are the merge gate.

Acceptance: the harness runs in CI in under five minutes, fails on a deliberate regression,
and passes on a normal run.

Validate: run it twice locally and once in the pull request.

## Wave 6: truth and cleanup

Batch 1: W6-1, W6-2, W6-3. These touch different files.

### W6-1 Remove dead modules (P3)

Goal: the wheel contains only code that can run.

Owns: `src/sattlint/utils/repo_paths.py` and any module confirmed dead by import analysis,
`tests/`.

Steps: confirm no caller, remove the module, and run the full ladder. Do not remove a module
that is a documented public API without a deprecation note.

Acceptance: no unreachable module remains in the wheel.

### W6-2 Remove unimplemented claims and internal JSON detail (P3)

Goal: public metadata describes only shipped behavior.

Owns: `src/sattlint/analyzers/registry/_registry_delivery.py`,
`src/sattlint/cli/entry.py`, `docs/analyzers.md`, `docs/cli.md`,
`tests/analyzers/suites/test_registry_catalog.py`.

Steps:

1. Remove `--rule` and the rule-id promise until rule ids exist, or add rule ids as part of
   W1-2 and keep the flag.
2. Remove baseline and incremental capability flags until the features exist.
3. Remove acceptance paths, fixture paths, and implementation buckets from the public
   analyzer payload; keep them behind a developer flag if needed.

Acceptance: every field in the public analyzer payload is backed by behavior.

### W6-3 Corpus diff and acknowledgement disposition (P3)

Goal: no half-wired feature stays in the tree.

Owns: `src/sattlint/reporting/corpus_diff.py`,
`tests/corpus/test_corpus_differential_reporting.py`, `src/sattlint/ui/_app_textual_results.py`,
`docs/`.

Steps:

1. If the baseline in W1-3 and the review in W4-4 cover run comparison, delete the corpus
   diff module and its test.
2. Otherwise wire it into a documented command and add an integration test.
3. Remove the per-run acknowledgement path after the baseline replaces it.

Acceptance: no module is reachable only from tests, and no acknowledgement state survives a
run without a baseline.

## Decisions

Locked on 2026-11-26.

1. Discovery. At each ancestor, use `.slproj` if it exists; otherwise use a unique
   `*.slproj`. Two or more candidates is an error listing them. Stop at the first ancestor
   with a candidate. `--project` bypasses discovery. `findings` never falls back to a
   machine-wide latest run.
2. Severity. Three levels, `error`, `warning`, and `info`, assigned per finding kind with
   analyzer metadata as a fallback. `error` is reserved for near-certain defects, `info`
   for style and convention, and `warning` for everything uncertain. `--fail-on` defaults
   to `any`; the documented CI setting is `warning`.
3. Baseline. One checked-in `.sattlint-baseline.json` per project, schema versioned and
   sorted. Keyed by the stable finding identity, with a human-readable match record. No
   content hash and no absolute paths. Diff reports added, moved, changed, stale, and
   unchanged; `baseline update` rewrites the file.

Settled in the package body: sequential jobs until W5-1 proves a win; keep Python 3.13 and
add 3.14 in W3-1.

Still open, decide at package start:

1. SARIF rule identity: public rule ids if W1-2 adds them, otherwise the analyzer key plus
   the finding kind. This can wait until W4-9.
2. Plugin API: entry-point loading or internal only. Recommendation: internal only, and
   remove it from the public feature list in W6-2.

## Deliberately not doing

- No new analyzers until location, severity, and baseline exist.
- No SARIF before locations exist.
- No File menu. Rename the label instead.
- No absolute CI timing gate. Use ratios on shared runners.
- No entry-point plugin system without a user request.
- No large committed benchmark fixtures. Generate them.
- No compatibility shim for a feature that never shipped.

## Traceability

| Review area | Package |
| --- | --- |
| Child process imports from the project directory | W0-1 |
| Non-TTY entry hang | W0-2 |
| Parallel pool regression | W0-3, W5-1 |
| Version, tag, changelog, stale artifacts, docs URL | W0-4 |
| Project discovery and wrong-project latest run | W0-5 |
| Tracebacks, quiet, partial results, parse diagnostics | W0-6, W4-2 |
| Finding location and source navigation | W1-1, W4-9 |
| Severity and fail-on policy | W1-2 |
| Baseline, diff, acknowledgement, finding identity | W1-3, W6-3 |
| ICF regex and input size limits | W2-1 |
| Terminal, Textual, and Markdown injection | W2-2 |
| Cache manifest, pickle, key, budget | W2-3 |
| Artifact modes, profile log, run bounds | W2-4 |
| Project root containment | W2-5 |
| Worker killed during analysis | W2-6 |
| sdist, CI matrix, reproducibility, tag ancestry | W3-1 |
| Install docs, stylesheet asset, dependency bounds | W3-2 |
| TUI project open, menu wording, view naming | W4-1 |
| CLI filters, grouping, target names, quiet | W4-2 |
| Run history commands and failed-run visibility | W4-3 |
| Headless Change Review | W4-4 |
| Optional directory validation and effective settings | W4-5 |
| Config and run schema versions | W4-6 |
| Target inventory, project init and check, edge cases | W4-7 |
| Consumer CI documentation | W4-8 |
| SARIF and annotations | W4-9 |
| Parser index reuse and warm fast path | W5-2 |
| Lazy startup imports | W5-3 |
| Benchmark harness and ratio gate | W5-4 |
| Dead modules, unimplemented claims, corpus diff, plugin API | W6-1, W6-2, W6-3 |

## Execution checklist

For each package:

- [ ] The prompt names the package, owns, forbidden files, acceptance, and validation.
- [ ] The builder adds a test that fails without the change.
- [ ] Focused tests pass.
- [ ] Documentation and `CHANGELOG.md` are updated when behavior changes.
- [ ] The diff contains no unrelated edits.
- [ ] The orchestrator commits one package.

For each wave:

- [ ] All packages in the wave are merged.
- [ ] The full verification ladder passes.
- [ ] One reviewer pass is complete and its findings are applied.
- [ ] The wave gate passes and the next wave starts.

For the release:

- [ ] Every P0 package is in the tag.
- [ ] P1 is complete before any CI-readiness claim.
- [ ] The wheel and sdist both install on the supported interpreters.
- [ ] The changelog, version, tag, and published metadata agree.
