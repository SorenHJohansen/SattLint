# T-Wave-8 CLI UX and Documentation Trustworthiness

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the 2026-05-19 CLI UX review into a concrete repair slice for the command-line surface that first-time users actually touch. After this work lands, a new user should be able to trust `sattlint --help`, `sattlint repo-audit --help`, the command examples in `README.md` and `docs/references/cli-commands.md`, and the exit codes returned by the main CLI. They should not hit documented flags that do not exist, silent success when docs promise a success marker, or alias help that hides the real options.

The observable proof is straightforward. `sattlint analyze --list-checks` must work and list real analyzer keys, `sattlint docgen --help` must show the output flags that the implementation already supports, `sattlint syntax-check` must have a stable success and failure contract, `sattlint repo-audit --help` must expose the same meaningful options as the dedicated repo-audit entrypoint, and the README plus CLI reference must only show commands that a user can run exactly as written.

## Progress

- [x] (2026-05-19) Create this ExecPlan from the CLI UX review and capture the current baseline: `README.md` and `docs/references/cli-commands.md` document `sattlint analyze --list-checks`, `sattlint docgen --output-dir`, and `--verbose`, but the top-level parser in `src/sattlint/cli/entry.py` does not expose those flags.
- [x] (2026-05-19) Confirm the main user-visible mismatches by probing the real commands: `sattlint analyze --list-checks` fails with unrecognized arguments, `sattlint docgen --output-dir docs-out` fails with unrecognized arguments, `sattlint syntax-check` succeeds silently on a valid file even though the README promises `OK`, and `sattlint repo-audit --help` shows only the shallow alias wrapper.
- [x] (2026-05-19) Confirm the current exit-code drift: `src/sattlint/cli/entry.py` and `src/sattlint/app_base.py` define `EXIT_USAGE_ERROR = 1`, the docs claim code `2` means invalid arguments or configuration, and raw argparse failures still surface as `2` in `tests/test_cli.py`.
- [x] (2026-05-19) Repair the top-level `sattlint` parser so its discoverability features and accepted flags match the documented user workflows. `analyze --list-checks` now lists shipped analyzer keys, `docgen --help` exposes `--output-dir` and `--output-path`, and the top-level help description reflects the real non-interactive surface.
- [x] (2026-05-19) Standardize the user-visible success, failure, and exit-code contract across `syntax-check`, config-driven commands, and the repo-audit alias. The main CLI now uses `0` for success, `1` for real command failures such as invalid SattLine input, and `2` for invalid arguments or invalid configuration inputs.
- [x] (2026-05-19) Make `sattlint repo-audit` expose trustworthy help and consistent `--quiet` behavior instead of acting like a thin forwarding trap. The nested alias now reuses the dedicated repo-audit parser definitions, and `--quiet repo-audit --list-checks` suppresses normal stdout while still exiting `0`.
- [x] (2026-05-19) Rewrite the affected sections of `README.md` and `docs/references/cli-commands.md` so every published example is reproducible from the current tree. Stale `--verbose` examples were removed, global flag ordering was corrected, and the exit-code wording now matches shipped behavior.
- [x] (2026-05-19) Add or update focused CLI tests so parser flags, help output, quiet mode, and exit codes stop drifting again. `tests/test_cli.py` now covers analyzer key listing, docgen flag threading, repo-audit alias option parity, quiet repo-audit suppression, and syntax-check success and failure contracts; `tests/test_repo_audit_cli.py` now covers reusable alias-parser construction.
- [x] (2026-05-19) Run focused CLI, repo-audit, and documentation validation and record the results in this file. Focused pytest passed for `tests/test_cli.py tests/test_app_cli_commands.py tests/test_repo_audit_cli.py`, `sattlint.devtools.doc_gardener` reported `0 findings`, touched-file Ruff passed, direct diagnostics on edited files were clean, and the user-visible command probes matched the documented behavior.

## Surprises & Discoveries

- Observation: the docs have drifted farther than the implementation in one important place.
  Evidence: `src/sattlint/app_cli_commands.py` already supports `output_dir` and `output_path` for DOCX generation, but the public parser in `src/sattlint/cli/entry.py` does not expose those options, so the docs describe real lower-level capability that users cannot actually reach.

- Observation: the nested repo-audit alias is much less discoverable than the dedicated repo-audit entrypoint.
  Evidence: `sattlint repo-audit --help` currently prints only the alias wrapper usage, while `bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --help` lists `--profile`, `--fail-on`, `--list-checks`, `--recommend-checks`, `--run-recommended-finish-gate`, `--check-my-changes`, and `--planning-context`.

- Observation: the current docs over-promise success output for `syntax-check`.
  Evidence: `README.md` says a valid file prints `OK`, but probing `bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s` returned exit code `0` with empty stdout, which matches the silent success path in `src/sattlint/cli/entry.py`.

- Observation: exit-code drift already exists between the parser, helper commands, and the docs.
  Evidence: `src/sattlint/cli/entry.py` defines `EXIT_USAGE_ERROR = 1`, `tests/test_cli.py` still asserts raw argparse `SystemExit(2)` behavior for parser failures, and `docs/references/cli-commands.md` claims code `2` covers invalid arguments or configuration.

- Observation: `--quiet` is currently narrower than its help text implies.
  Evidence: the parser text in `src/sattlint/cli/entry.py` says `Suppress stdout output`, but the implementation only wraps the built-in `syntax-check` command; probing `sattlint --quiet repo-audit --profile quick` still emitted repo-audit output before failing on live repo findings.

- Observation: the `syntax-check` success marker had already been restored in the current tree before the main parser and docs were repaired.
  Evidence: after the exit-code cleanup landed, probing `bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s` printed `OK` and exited `0`, so the remaining user-facing drift was the parser surface, alias help, quiet handling, and documentation rather than the success marker itself.

## Decision Log

- Decision: keep this repair as its own active plan instead of folding it into `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md`.
  Rationale: release-readiness is broader than the immediate command-trust problem. This slice is small, testable, and directly tied to concrete CLI review findings.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: treat `--verbose` as documentation drift, not as a feature that must be implemented in this slice.
  Rationale: there is no corresponding parser or command implementation, and adding new global verbosity behavior would widen scope beyond the review findings. The first fix is to stop documenting nonexistent behavior.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: standardize the main CLI contract to `0` for success, `1` for domain failures such as invalid SattLine source or repo-audit findings, and `2` for invocation mistakes or invalid configuration inputs.
  Rationale: this matches common CLI expectations, explains the current raw argparse behavior, and gives users a consistent scripting model.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: keep `sattlint repo-audit` as a supported alias, but make its help and flag behavior genuinely useful.
  Rationale: the alias is already shipped and documented. First-time users should not need to discover a second command name just to get meaningful help for a supported subcommand.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: prefer fixing parser and command behavior when the implementation already has the needed seam, and prefer fixing docs when the docs invented a feature.
  Rationale: `docgen` output flags and analyzer-key discovery are real UX improvements worth exposing, while `--verbose` has no shipped behavior to rescue.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Completed 2026-05-19.

The top-level parser now exposes `analyze --list-checks`, `docgen --output-dir`, and `docgen --output-path`, and the nested `repo-audit` alias now reuses the dedicated repo-audit parser so `sattlint repo-audit --help` shows the real audit options. No `--verbose` CLI feature was added; instead, the stale `--verbose` examples were removed from the public docs.

The shipped exit-code contract is now `0` for success, `1` for real command failures such as invalid SattLine input or repo-audit findings, and `2` for invalid arguments or invalid configuration inputs. `syntax-check` prints `OK` on success, prints validation errors on stderr for invalid input, and returns `1` for invalid source files.

Updated docs: `README.md` and `docs/references/cli-commands.md` now match the real flag surface, correct global-flag ordering, and document the new exit-code meanings.

Proof captured in this slice:

  bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_cli.py tests/test_app_cli_commands.py tests/test_repo_audit_cli.py -x -q --tb=short
  bash scripts/run_repo_python.sh -m sattlint.devtools.doc_gardener
  bash scripts/run_repo_python.sh -m ruff check src/sattlint/app.py src/sattlint/app_base.py src/sattlint/cli/entry.py src/sattlint/devtools/repo_audit_cli.py tests/test_cli.py tests/test_repo_audit_cli.py
  bash scripts/run_repo_python.sh -m sattlint --help
  bash scripts/run_repo_python.sh -m sattlint analyze --list-checks
  bash scripts/run_repo_python.sh -m sattlint docgen --help
  bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
  bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/invalid/BuiltinWrongArity.s
  bash scripts/run_repo_python.sh -m sattlint repo-audit --help
  bash scripts/run_repo_python.sh -m sattlint --quiet repo-audit --list-checks

## Context and Orientation

The top-level user CLI lives in `src/sattlint/cli/entry.py`. That file builds the `sattlint` parser, defines the global flags, and dispatches subcommands such as `syntax-check`, `validate-config`, `analyze`, `simulate`, `docgen`, `format-icf`, and `repo-audit`. `src/sattlint/app_base.py` and `src/sattlint/app.py` are compatibility layers that still expose the same entrypoint and constants to the rest of the package. `src/sattlint/app_cli_commands.py` contains the concrete user-facing behaviors for config validation, analysis, simulation, and DOCX generation.

The dedicated repository-audit CLI lives under `src/sattlint/devtools/repo_audit_cli.py`, with compatibility entrypoints in `src/sattlint/devtools/repo_audit.py`. That split matters because the nested alias `sattlint repo-audit` should feel like a trustworthy front door, but today it only exposes a shallow forwarding parser while the dedicated command owns the real help text and option definitions.

The public command docs that users see first are `README.md` and `docs/references/cli-commands.md`. The earlier completed plan `docs/exec-plans/completed/03-cli-doc-parity.md` established a canonical command reference, but the current parser drift reopened the same gap: the docs again describe flags and examples that the parser does not actually accept.

In this plan, an `invocation mistake` means the user called the command with unsupported flags, wrong flag ordering, or missing required arguments. A `domain failure` means the command ran correctly but reported a real problem in the target input or repository, such as a SattLine validation error or repo-audit findings above the chosen threshold. A `success marker` means a short, stable human-readable output such as `OK` that lets a first-time user see success without having to infer it from silence alone.

Contributor validation in this repository uses the repo venv wrapper, not globally installed console scripts. From the repository root, `bash scripts/run_repo_python.sh -m sattlint ...` exercises the main CLI, and `bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit ...` exercises the dedicated repo-audit entrypoint. The installed script names such as `sattlint` and `sattlint-repo-audit` are still the user-facing contract, but the in-repo proof path must use the module form above.

The checked-in files that make good reproducible CLI examples are already present. Use `tests/fixtures/corpus/valid/VariableModifiers.s` as the known-valid syntax-check sample and `tests/fixtures/corpus/invalid/BuiltinWrongArity.s` as the known-invalid sample unless a better checked-in invalid fixture becomes necessary during implementation.

## Plan of Work

Start with the parser surface in `src/sattlint/cli/entry.py`. Add analyzer-key discovery as an actual supported subcommand option instead of leaving `--check KEY` as a guess-only interface. Expose the DOCX output flags that `src/sattlint/app_cli_commands.py` already supports so the parser, handler, and docs all describe the same command. Remove or reword any top-level help text that still frames the CLI as interactive plus one non-interactive `syntax-check` command.

Next, repair the exit and message contract. Introduce a clear distinction between success, invocation mistakes, and domain failures in the top-level CLI constants and in the command handlers. `syntax-check` should emit a stable success marker on valid input and continue to emit a clear validation message on invalid input. Config-driven command failures such as unreadable config files, missing configured targets, or invalid config content should become actionable by naming the next command or setting the user needs to inspect. The docs must then describe the same exit contract the code returns.

After that, fix the repo-audit alias. Reuse the dedicated repo-audit parser definitions, or otherwise clone their option surface into the nested alias, so `sattlint repo-audit --help` stops hiding the actual flags. Also make `--quiet` behave consistently for forwarded commands, not only for the built-in `syntax-check` path. Quiet mode should suppress normal stdout while still allowing stderr diagnostics and nonzero exits.

Then align the docs. Update only the command sections of `README.md` and `docs/references/cli-commands.md` that talk about supported flags, output behavior, exit codes, and reproducible examples. Keep public-user commands and contributor validation commands distinct. The public docs should show installed command names such as `sattlint` and `sattlint-repo-audit`; the plan validation steps should keep using `bash scripts/run_repo_python.sh -m ...` from the repo root.

Finish by locking the behavior down in tests. `tests/test_cli.py` should cover parser flags, exit codes, `syntax-check` output, and quiet behavior. `tests/test_app_cli_commands.py` should cover the actionable message changes for config and DOCX workflows. `tests/test_repo_audit_cli.py` should cover repo-audit help and alias parity where that behavior lives. If the existing repo-audit command-gap checks can enforce any doc truthfulness here, extend them instead of adding a second overlapping guard.

## Concrete Steps

Run all commands from the repository root.

First, re-establish the current behavior before editing:

    bash scripts/run_repo_python.sh -m sattlint --help
    bash scripts/run_repo_python.sh -m sattlint analyze --help
    bash scripts/run_repo_python.sh -m sattlint analyze --list-checks
    bash scripts/run_repo_python.sh -m sattlint docgen --help
    bash scripts/run_repo_python.sh -m sattlint docgen --output-dir docs-out
    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/invalid/BuiltinWrongArity.s
    bash scripts/run_repo_python.sh -m sattlint repo-audit --help
    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --help

Implement the parser, handler, and doc changes described above. Keep the edits focused to the CLI and documentation surfaces named in this plan.

After each behavior slice lands, run the focused automated validation:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_cli.py tests/test_app_cli_commands.py tests/test_repo_audit_cli.py -x -q --tb=short

After the docs are updated, run the narrow documentation validation:

    bash scripts/run_repo_python.sh -m sattlint.devtools.doc_gardener

Finish with the user-visible command probes that must now work as documented:

    bash scripts/run_repo_python.sh -m sattlint analyze --list-checks
    bash scripts/run_repo_python.sh -m sattlint docgen --help
    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s
    bash scripts/run_repo_python.sh -m sattlint syntax-check tests/fixtures/corpus/invalid/BuiltinWrongArity.s
    bash scripts/run_repo_python.sh -m sattlint repo-audit --help
    bash scripts/run_repo_python.sh -m sattlint --quiet repo-audit --list-checks

Expected outcomes after the slice is complete:

    - `analyze --list-checks` exits `0` and prints real analyzer keys such as `variables` and other shipped checks.
    - `docgen --help` lists `--output-dir` and any other shipped output-shaping flags.
    - valid `syntax-check` prints `OK` and exits `0`.
    - invalid `syntax-check` prints a validation error on stderr and exits `1`.
    - `sattlint repo-audit --help` includes real repo-audit flags such as `--profile`, `--fail-on`, `--list-checks`, and `--planning-context`.
    - `--quiet` suppresses normal stdout for the repo-audit list-checks path and still returns exit `0`.

## Validation and Acceptance

Acceptance is behavior, not only documentation edits. A first-time user must be able to copy the command examples from `README.md` and `docs/references/cli-commands.md` and run them without discovering undocumented caveats. The top-level `sattlint` help output must describe the real non-interactive command surface, not a stale subset.

`sattlint analyze --list-checks` must exist as a discoverability feature, because `--check KEY` is not an intuitive first-run interface without a way to list valid keys. `sattlint docgen --help` must expose the output-path flags that the command implementation supports. `sattlint syntax-check` must have a visible success contract and a predictable failure contract. `sattlint repo-audit --help` must stop acting like a dead-end alias and instead show the real repo-audit options.

The exit-code contract must become coherent enough for scripting. After this slice, users should be able to rely on `0` for success, `1` for domain failures such as invalid SattLine input or blocking repo-audit findings, and `2` for unsupported flags, missing required arguments, or invalid configuration inputs. The docs must say exactly that, and the tests must lock it down.

The focused pytest command in this plan and the doc-gardener run must pass. The final command probes must match the documented behavior exactly.

## Idempotence and Recovery

This slice is safe to implement incrementally. The parser and docs can be updated in small passes as long as the focused CLI tests are rerun after each pass. If one attempted improvement widens scope too far, recover by keeping the smallest change that makes code and docs agree, then defer any extra polish to a later plan instead of leaving half-implemented flags behind.

If exposing the dedicated repo-audit parser wholesale inside `sattlint repo-audit` proves too invasive, fall back to a smaller compatibility step that still satisfies the acceptance bar: the nested alias help must at least enumerate the real repo-audit flags and point to the dedicated command unambiguously. Do not keep the current shallow help text once the slice is done.

If the final exit-code cleanup risks breaking unrelated callers, add compatibility tests first, then change one command family at a time. Do not update the docs until the new exit codes and messages are actually in place.

## Artifacts and Notes

Baseline facts captured at plan creation time:

    README.md currently documents:
      sattlint analyze --list-checks
      sattlint docgen --output-dir docs-out
      sattlint --config path/to/config.toml --verbose validate-config
      sattlint --quiet repo-audit --profile quick

    docs/references/cli-commands.md currently documents:
      sattlint analyze --list-checks
      sattlint validate-config --config path/to/config.toml --verbose
      sattlint docgen --output-dir docs-out
      sattlint --verbose [subcommand]

    src/sattlint/cli/entry.py currently exposes only these global flags:
      --version
      --config
      --no-cache
      --quiet

    Current observed mismatches:
      analyze --list-checks -> unrecognized arguments
      docgen --output-dir docs-out -> unrecognized arguments
      valid syntax-check -> exit 0 with empty stdout
      invalid syntax-check -> exit 1 with ERROR [validation] ... on stderr
      sattlint repo-audit --help -> shallow alias help only

    Current documented exit-code table says:
      0 success
      1 execution error
      2 invalid arguments or configuration

    Current code constants say:
      src/sattlint/cli/entry.py -> EXIT_USAGE_ERROR = 1
      src/sattlint/app_base.py -> EXIT_USAGE_ERROR = 1

## Interfaces and Dependencies

The controlling top-level parser interface is `src/sattlint/cli/entry.py`. The controlling command-helper interface is `src/sattlint/app_cli_commands.py`. The controlling repo-audit parser interface is `src/sattlint/devtools/repo_audit_cli.py`. The controlling public-doc interfaces are `README.md` and `docs/references/cli-commands.md`. The nearest focused tests are `tests/test_cli.py`, `tests/test_app_cli_commands.py`, and `tests/test_repo_audit_cli.py`.

Do not add new external dependencies for this slice. Reuse the existing parser and handler seams, the existing repo-audit parser, and the current test modules. If analyzer-key listing needs a data source, reuse the existing analyzer registry and the same key names already accepted by `--check`. If DOCX output flags are added to the parser, thread them into the existing `run_docgen_command` interface rather than creating a second output path.
