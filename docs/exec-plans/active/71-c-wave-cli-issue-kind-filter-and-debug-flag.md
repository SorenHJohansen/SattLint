# C-Wave CLI Issue-Kind Filter and Debug Flag

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

The `sattlint analyze` command currently runs all enabled issue kinds with no way to restrict which checks run within the variables analyzer. The TUI menu already filters by `IssueKind`, but the CLI offers no equivalent — a developer who wants to check only `unused` and `shadowing` must run the full analysis and sift the output manually. There is also no `--debug` flag on the CLI; debug mode can only be enabled through the config file.

After this work lands, a developer can run:

    sattlint --debug analyze --check variables --issue-kind unused --issue-kind shadowing

and see only those two issue kinds in the report. They can also run:

    sattlint analyze --list-issue-kinds

to print all available `IssueKind` values without loading a project, which is useful for scripting and CI discovery.

The observable proof is that the command above produces output that contains only `UNUSED` and `SHADOWING` issues, and does not contain sections for other issue kinds. The `--list-issue-kinds` command exits zero and prints one kind per line. The TUI is unchanged.

## Progress

- [x] Read `src/sattlint/cli/entry.py` top-to-bottom to understand the full argument-parser setup, the debug flow, and the existing `analyze` subparser before editing.
- [x] Add `--debug` as a top-level flag in `entry.py` (before the subparsers block). Wire it so that `cfg["debug"] = True` is set before `apply_debug_fn(cfg)` is called in the config-loading block.
- [x] Add `--issue-kind` (repeatable, `action="append"`, `dest="issue_kinds"`, `default=[]`, with `choices` listing every `IssueKind` value by `ik.value` so the help text is self-documenting) and `--list-issue-kinds` (`action="store_true"`) to the `analyze` subparser in `entry.py`.
- [x] Add handling for `--list-issue-kinds` in `entry.py`: before the config-loading block, check `getattr(args, "list_issue_kinds", False)` and if set, print each `IssueKind.value` on its own line and return `exit_success` — no config load needed.
- [x] Update the `analyze` command dispatch in `entry.py` to pass `selected_issue_kinds` (derived from `args.issue_kinds`) to `run_analyze_command_fn`.
- [x] Update `run_analyze_command` in `src/sattlint/app_cli_commands.py` to accept a `selected_issue_kinds: frozenset[str] | None` keyword argument and forward it into the call to `run_checks_fn`.
- [x] Update `_run_checks` in `src/sattlint/app_analysis.py` to accept `selected_issue_kinds: AbstractSet[str] | None = None` and pass it through when constructing `AnalysisContext`.
- [x] Add `selected_issue_kinds: AbstractSet[IssueKind] | None = None` field to the `AnalysisContext` dataclass in `src/sattlint/analyzers/framework.py`. Import `AbstractSet` from `collections.abc`.
- [x] Add `"selected_issue_kinds"` to `_CONTEXT_VALUE_PROVIDERS` in `src/sattlint/analyzers/_registry_specs.py` as a lambda that returns `context.selected_issue_kinds`. Import `AbstractSet` at the top.
- [x] Add `"selected_issue_kinds"` to the `context_kwargs` tuple of the `variables` template in `src/sattlint/analyzers/_registry_spec_templates.py`.
- [x] Verify that `analyze_variables` in the variables analyzer receives and uses `selected_issue_kinds` to filter its output. If not, locate the call site and add a filter guard that restricts which `IssueKind` values are collected when `selected_issue_kinds` is not `None`.
- [x] Write a focused test in `tests/test_cli.py` (or `tests/test_app_cli_commands.py`) that verifies `--issue-kind unused` causes the result to contain only `IssueKind.UNUSED` issues and `--list-issue-kinds` prints all issue kind values.
- [x] Run `pyright` over all touched files and confirm zero new errors.
- [ ] Run the full test suite and confirm no regressions.

## Surprises & Discoveries

- `analyze_variables` already accepted `selected_issue_kinds` and normalized the filter internally. The missing behavior was limited to the non-interactive CLI chain and the registry-backed batch `AnalysisContext` path.
- The interactive variable-analysis path in `app_analysis.run_variable_analysis` already threaded the same concept through cache keys and analyzer invocation, so the CLI implementation could reuse the existing type and semantics rather than adding a second filtering mechanism.
- Python 3.14 in this repo does not expose `AbstractSet` from `collections.abc`; the new annotations had to import `AbstractSet` from `typing` instead.
- The analyzer registry tests still exercise `_CONTEXT_VALUE_PROVIDERS` with lightweight `SimpleNamespace` contexts, so the new `selected_issue_kinds` provider needed a `getattr(..., None)` fallback to remain additive.

## Decision Log

- Decision: add `--debug` as a top-level flag rather than as an `analyze`-only flag.
  Rationale: debug mode applies to config loading itself (e.g., verbose config resolution errors), not only to analysis. Making it top-level means it is available for every subcommand. The review prompt explicitly requests a top-level flag.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: use `IssueKind.value` strings as the `choices` for `--issue-kind` rather than enum names.
  Rationale: the TUI already uses `.value` strings for filtering, and the review prompt uses lowercase examples like `--issue-kind unused`. Using the lowercase `.value` strings keeps the CLI consistent with existing TUI vocabulary.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: pass `selected_issue_kinds` as a `frozenset[str]` through the CLI chain and convert to `frozenset[IssueKind]` at the `AnalysisContext` boundary.
  Rationale: the CLI argument layer works with raw strings (values from `argparse`). Converting to typed enum values at the `AnalysisContext` constructor keeps the CLI argument parsing free of enum imports while preserving type safety in the analysis layer.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: do not modify TUI paths; `selected_issue_kinds=None` in `AnalysisContext` means "run all kinds", which is the existing TUI behavior.
  Rationale: the review prompt states "The TUI is unchanged." The `None` sentinel for "no filter" is already the natural default for the `AnalysisContext` field.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

## Outcomes & Retrospective

- Added top-level `--debug`, repeatable `analyze --issue-kind`, and `analyze --list-issue-kinds` support in the non-interactive CLI path.
- Reused the existing variable-analyzer issue-kind filter by threading `selected_issue_kinds` through the app startup wrapper, CLI command owner, batch analysis runner, `AnalysisContext`, and registry context kwargs for the `variables` analyzer.
- Added focused regression coverage for CLI parsing/dispatch and command delegation.
- Validation completed.
- Focused pytest: `tests/test_cli.py tests/test_app_cli_commands.py` passed.
- Direct CLI smoke checks passed: `sattlint analyze --list-issue-kinds` printed 24 values, `sattlint --debug analyze --list-checks` exited successfully, and `sattlint analyze --issue-kind nonexistent` failed with the expected argparse error.
- Source-slice `pyright` passed with `0 errors, 0 warnings, 0 informations`.
- The previous unrelated blocker in `tests/test_variables_submodule_helpers.py::test_framemodule_subtree_uses_repathed_context` is cleared.
- The current full-suite blocker is a different unrelated existing failure in `tests/test_analyzers_variables.py::test_graphics_format_tail_keywords_do_not_log_missing_variables`.

## Context and Orientation

This repository has a layered CLI architecture. The entry point is `src/sattlint/cli/entry.py`, which builds the `argparse` parser, dispatches to command handlers, and calls a `run_analyze_command_fn` injectable. The injectable's concrete implementation is `src/sattlint/app_cli_commands.py:run_analyze_command`, which calls `run_checks_fn`. The concrete `run_checks_fn` is `src/sattlint/app_analysis.py:_run_checks`, which iterates loaded projects and constructs one `AnalysisContext` per target.

The `AnalysisContext` dataclass is defined in `src/sattlint/analyzers/framework.py`. It is a `frozen=True` dataclass; every field is an immutable keyword argument. Adding a new field is a purely additive change — callers that do not pass the field receive the default.

The `variables` analyzer spec is defined via an `AnalyzerSpecTemplate` in `src/sattlint/analyzers/_registry_spec_templates.py`. Its `context_kwargs` tuple lists which `AnalysisContext` fields the analyzer receives as keyword arguments. The `_CONTEXT_VALUE_PROVIDERS` dict in `src/sattlint/analyzers/_registry_specs.py` maps each kwarg name to a lambda that extracts the value from the context.

`IssueKind` is a plain `enum.Enum` defined in `src/sattlint/reporting/variables_report.py`. Its `.value` strings are lowercase (e.g., `IssueKind.UNUSED.value == "unused"`). All issue kinds can be enumerated with `list(IssueKind)`.

The current `analyze` dispatch in `entry.py` (around line 294) passes `selected_keys` (analyzer keys like `"variables"`) to `run_analyze_command_fn`. The new `selected_issue_kinds` argument is a different filter that operates inside the variables analyzer, not at the analyzer-key level.

The debug flow: `entry.py` calls `apply_debug_fn(cfg)` after loading the config, which mutates `cfg` to enable debug output. The `--debug` flag must set `cfg["debug"] = True` before this call so the debug function sees the CLI-supplied value.

The `--list-issue-kinds` handler must run before the config-loading block because it needs no config file and should work even on a machine where the config is broken or absent. The same pattern exists for `--list-checks` at `entry.py:268`.

## Plan of Work

Start by reading `entry.py` in full to understand the parser setup and the exact location of the config-loading block. Note that the top-level `--debug` argument must be added after `--no-cache` and before `subparsers`, so it is available to all subcommands.

In `entry.py`, add `parser.add_argument("--debug", action="store_true", help="Enable debug output")` at the top-level parser (after line 63 where `--quiet` is defined). Then in the config-loading block (line 278), add `if getattr(args, "debug", False): cfg["debug"] = True` immediately before `apply_debug_fn(cfg)`.

Add to the `analyze` subparser:

    analyze_parser.add_argument(
        "--issue-kind",
        action="append",
        dest="issue_kinds",
        default=[],
        metavar="KIND",
        choices=[ik.value for ik in IssueKind],
        help="Filter variable analysis to this issue kind (repeatable; use --list-issue-kinds to see choices)",
    )
    analyze_parser.add_argument(
        "--list-issue-kinds",
        action="store_true",
        help="List available issue kind values for --issue-kind and exit",
    )

This requires importing `IssueKind` at the top of `entry.py`; use a lazy import inside the function that builds the parser (if `IssueKind` is not already imported) to avoid a hard dependency on the reporting layer at module import time.

Add the `--list-issue-kinds` early-exit handler in the `analyze` command block, before the config-loading block (mirroring the `--list-checks` pattern at line 268):

    if command == "analyze" and getattr(args, "list_issue_kinds", False):
        from ..reporting.variables_report import IssueKind
        for ik in IssueKind:
            print(ik.value)
        return exit_success

In the `analyze` dispatch block (around line 296), derive `selected_issue_kinds` from `args.issue_kinds`:

    selected_issue_kinds = frozenset(args.issue_kinds) if args.issue_kinds else None

Pass it to `run_analyze_command_fn` as a new keyword argument.

Update `run_analyze_command` in `app_cli_commands.py` to accept `selected_issue_kinds: frozenset[str] | None = None` and forward it in the `run_checks_fn(cfg, selected_keys, use_cache, selected_issue_kinds=selected_issue_kinds)` call. Then update `_run_checks` in `app_analysis.py` to accept this argument, convert the strings to `IssueKind` values, and pass the resulting `frozenset[IssueKind] | None` to `AnalysisContext(selected_issue_kinds=...)`.

Add the `selected_issue_kinds: AbstractSet[IssueKind] | None = None` field to `AnalysisContext` in `framework.py`. Add `"selected_issue_kinds": lambda _registry_module, context: context.selected_issue_kinds` to `_CONTEXT_VALUE_PROVIDERS` in `_registry_specs.py`. Add `"selected_issue_kinds"` to the `variables` template's `context_kwargs` in `_registry_spec_templates.py`.

Finally, verify that the variables analyzer actually uses `selected_issue_kinds` to filter. Locate `analyze_variables` in the analyzer registry or the variables module and confirm there is a guard: if `selected_issue_kinds` is not None, only collect issues whose `.kind` is in the set. If no such guard exists, add one at the top-level collection point.

## Concrete Steps

Run all commands from the repository root.

Inspect the current analyze subparser and debug flow before editing:

    grep -n "debug\|issue.kind\|list_check\|apply_debug_fn\|selected_keys" src/sattlint/cli/entry.py

After all edits, verify the `--list-issue-kinds` path:

    bash scripts/run_repo_python.sh -m sattlint analyze --list-issue-kinds

Expected output: one line per `IssueKind` value, e.g.:

    unused
    unused_datatype_field
    read_only_non_const
    ...
    implicit_latch

Verify the `--debug` flag changes debug output (confirm `cfg["debug"]` is read by a real config check):

    bash scripts/run_repo_python.sh -m sattlint --debug analyze --list-checks

Run pyright over all touched files:

    bash scripts/run_repo_python.sh -m pyright \
      src/sattlint/cli/entry.py \
      src/sattlint/app_cli_commands.py \
      src/sattlint/app_analysis.py \
      src/sattlint/analyzers/framework.py \
      src/sattlint/analyzers/_registry_specs.py \
      src/sattlint/analyzers/_registry_spec_templates.py

Expected: zero errors introduced.

Run focused regression tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_cli.py tests/test_app_cli_commands.py -x -q --tb=short

Then run the full suite:

    bash scripts/run_repo_python.sh -m pytest --no-cov -x -q --tb=short

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. `sattlint analyze --list-issue-kinds` exits 0 and prints every `IssueKind.value` (verify with `| wc -l` matching `len(list(IssueKind))`).
2. `sattlint --debug analyze --check variables --issue-kind unused` produces output that does not contain sections for any issue kind other than `unused`.
3. `sattlint analyze --issue-kind nonexistent` prints an argparse error and exits non-zero.
4. Running `sattlint analyze --check variables` with no `--issue-kind` flag produces the same output as before (no regression; the full analysis still runs).
5. `pyright` and `pytest --no-cov -x` both pass over all touched files.

## Idempotence and Recovery

The `AnalysisContext` change is additive and backward-compatible — the `selected_issue_kinds=None` default means all existing callers (TUI, tests) that do not pass the field continue to work with no change. The CLI changes are isolated to argument parsing and the dispatch chain. If any step fails, reverting the individual file is safe.

## Artifacts and Notes

The 5 files to change (from the original review prompt):

1. `src/sattlint/cli/entry.py` — `--debug` top-level flag; `--issue-kind` and `--list-issue-kinds` on `analyze` subparser.
2. `src/sattlint/analyzers/framework.py` — `selected_issue_kinds: AbstractSet[IssueKind] | None = None` on `AnalysisContext`.
3. `src/sattlint/analyzers/_registry_specs.py` — `"selected_issue_kinds"` provider in `_CONTEXT_VALUE_PROVIDERS`.
4. `src/sattlint/analyzers/_registry_spec_templates.py` — `"selected_issue_kinds"` in the `variables` template's `context_kwargs`.
5. `src/sattlint/app_analysis.py` — pluck `selected_issue_kinds` from `cfg`/args and pass to `AnalysisContext`.

Additional files that require smaller changes to thread the value through:

- `src/sattlint/app_cli_commands.py` — `run_analyze_command` signature and forwarding.

## Interfaces and Dependencies

After this plan, the stable new interface is:

    AnalysisContext(
        ...,
        selected_issue_kinds=frozenset({IssueKind.UNUSED, IssueKind.SHADOWING}),  # or None for all
    )

The `--issue-kind` choices are validated by argparse before any code runs, so invalid kind values produce an error message and non-zero exit before any config file is loaded.
