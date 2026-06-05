# T-Wave-7 Audit Runner and Artifact Freshness

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes long-running repo audits reliable for both humans and AI agents. Today, the repository already exposes named audit tasks, but the common `Audit: Full Repo Audit` task writes directly into a reused `artifacts/audit-full-current/` directory, and transcript evidence shows agents reading `status.json`, `summary.json`, and `pytest.json` while the run is still in progress. After this change lands, full and quick audit runs will go through a repo-owned driver that writes into a fresh temporary directory, publishes a complete result atomically, and exposes a readiness check so readers can tell whether an artifact directory is final.

The observable proof is straightforward. Running the new audit driver in quick mode must leave a fully populated output directory that the readiness checker reports as complete. If a caller points the readiness checker at a missing or incomplete run directory, it must fail with a clear message instead of inviting optimistic `read_file` calls against partial artifacts.

## Progress

- [x] (2026-05-15) Create the ExecPlan and capture the baseline evidence: transcript review counted `run_in_terminal` 369 times and `run_task` 13 times, while the current `Audit: Full Repo Audit` task in `.vscode/tasks.json` writes directly to `artifacts/audit-full-current`.
- [x] (2026-05-15) Add a repo-owned audit driver that runs quick or full audits in a fresh temporary directory and publishes the final output atomically.
- [x] (2026-05-15) Add an artifact-readiness command that can validate whether an audit output directory is complete and safe to read.
- [x] (2026-05-15) Repoint the VS Code audit tasks in `.vscode/tasks.json` to the driver so common AI workflows use the stable path by default.
- [x] (2026-05-15) Add a repo-owned findings-comparison command so agents can diff two audit output directories without reading both `findings.json` files manually.
- [x] (2026-05-15) Add focused tests for temporary output staging, incomplete-run detection, final-directory publication, and findings comparison.
- [x] (2026-05-15) Update the quality-gate docs so the stable audit runner becomes the canonical path for long-running repo checks.

## Surprises & Discoveries

Observation: the task surface exists already, but it still writes to a reused directory.
Evidence: `.vscode/tasks.json` defines `Audit: Full Repo Audit` with `--output-dir artifacts/audit-full-current`.

Observation: the current failure mode is artifact freshness, not just long runtime.
Evidence: transcript `4a386d4b-6803-4395-8c4b-37fa61665e7d` shows repeated `read_file` failures while the agent read `pytest.json`, `progress.json`, `status.json`, and a fresh recheck directory that was not complete yet.

Observation: raw terminal control is the default even when named tasks exist.
Evidence: the transcript corpus counted 369 `run_in_terminal` calls versus 13 `run_task` calls.

Observation: the emitted pipeline artifact registry is the cleanest readiness contract for nested audit outputs.
Evidence: `artifacts/audit-full-current/summary.json` already records `pipeline_summary.artifact_registry.artifacts` with enabled and blocking flags for `progress.json`, `ruff.json`, `pyright.json`, `pytest.json`, and the other pipeline reports.

Observation: a completed audit can still exit non-zero and remain safe to publish.
Evidence: the quick smoke run published `artifacts/audit-quick-current` successfully while preserving the audit exit code `1` for pre-existing repo findings, and the readiness checker still reported the directory as complete.

## Decision Log

Decision: add a findings-comparison command alongside the readiness checker.
Rationale: the transcript corpus shows agents reading `findings.json` and `summary.json` both before and after each fix to confirm resolution. A diff command removes those repeated reads and gives the agent a single deterministic answer: N findings resolved, M new, K unchanged.
Date/Author: 2026-05-15 / Copilot (Claude Sonnet 4.6)

Decision: solve this with a repo-owned audit driver rather than more warning text.
Rationale: the repo already has tasks and docs, but the transcripts still show stale-read failures. A stable execution surface is more reliable than asking every agent to remember the caveat.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: stage runs in a temporary sibling directory and publish the final output atomically.
Rationale: atomically replacing the final directory avoids the misleading state where `*-current` exists but only half of its artifacts are present.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: expose artifact readiness as an explicit check.
Rationale: a self-improving repo should let tools and agents ask "is this directory safe to read yet?" instead of assuming directory existence means completion.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: derive nested pipeline readiness from the emitted artifact registry instead of a second hard-coded file list.
Rationale: the pipeline summary already records which reports were enabled for that run, so the readiness checker can stay exact for quick, full, and skip-path variants without duplicating another registry.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The repo now has a staged runner in `src/sattlint/devtools/repo_audit_runs.py`, a readiness checker in `src/sattlint/devtools/artifact_readiness.py`, and a findings diff CLI in `src/sattlint/devtools/compare_audit_findings.py`. The common VS Code quick and full audit tasks now publish through the staged runner, and focused regression tests cover publication, incomplete-run rejection, and before/after findings comparison.

Validation landed in three layers. Focused tests passed with `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_repo_audit_runs.py tests/test_artifact_readiness.py -x -q --tb=short`. Ruff and Pyright both passed on the touched Python files. The end-to-end quick smoke run published `artifacts/audit-quick-current` through the new task surface, archived the previous quick snapshot under `artifacts/audit-history/`, and `bash scripts/run_repo_python.sh -m sattlint.devtools.artifact_readiness --artifact-dir artifacts/audit-quick-current` reported the published directory as complete and safe to read.

## Context and Orientation

The current full audit entrypoint is `src/sattlint/devtools/repo_audit.py`. Repo-wide quality-gate policy lives in `docs/quality-gates.md`. VS Code task wiring lives in `.vscode/tasks.json`, which already defines `Audit: Quick Repo Audit`, `Audit: Full Repo Audit`, and related AI tasks.

In this repository, an "artifact directory" is the folder produced by a long-running analysis or audit command. Files such as `status.json`, `summary.json`, `progress.json`, `pytest.json`, and `findings.json` are meant to describe the result. The problem is not that those files are missing forever; the problem is that they can be absent or stale while the audit is still running. This plan must make that state explicit.

The likely implementation seam is a new driver module such as `src/sattlint/devtools/repo_audit_runs.py` plus a helper module such as `src/sattlint/devtools/artifact_readiness.py`. The first focused tests should live in `tests/test_repo_audit_runs.py` and `tests/test_artifact_readiness.py`. Keep the existing `src/sattlint/devtools/repo_audit.py` CLI behavior intact; the new driver should wrap it rather than replacing the public audit command.

## Plan of Work

Start by adding an audit-run driver that accepts the same profile concepts as the existing audit CLI, but stages the run in a temporary output directory first. The driver should create a temporary sibling directory such as `<final-output-dir>.tmp-<timestamp>`, invoke the existing repo-audit CLI against that temporary path, and then rename the completed directory into the requested final path only after the run has finished. If a previous final directory exists, archive it or replace it only after the new directory is complete.

Add a readiness checker next. The readiness checker should inspect an artifact directory and answer whether it is complete, missing, or still unsafe to read. It should check for the expected files for that workflow, ensure `progress.json` is not still pending when that file exists, and return a non-zero exit code with a human-readable message when the directory is incomplete. Keep the readiness rules local and explicit rather than spread across multiple ad hoc readers.

Then rewire `.vscode/tasks.json` to call the driver for the quick and full repo audit tasks. That keeps the developer surface stable while moving the freshness contract into one repo-owned place. If a helper task for `artifact_readiness` is useful, add it next to the existing audit tasks so an AI can select a named task instead of probing raw JSON files by hand.

Add a findings-comparison command next. The comparison command should accept two artifact directories — a before and an after — and output three sets: resolved finding IDs, new finding IDs, and unchanged finding IDs. Agents should be able to run this immediately after a targeted fix and get a deterministic single-read answer on whether the finding was resolved. Implement it as `src/sattlint/devtools/compare_audit_findings.py` or as an `--compare <before-dir>` flag on the readiness checker, whichever keeps the surface area smaller. The output should be compact JSON so an agent can parse it in one tool call.

Finish by updating `docs/quality-gates.md` and any nearby devtools docs to tell readers that long-running audits should be launched through the driver and inspected through the readiness checker.

## Concrete Steps

Run all commands from the repository root.

Start with focused tests for the new driver and readiness checker:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_repo_audit_runs.py tests/test_artifact_readiness.py -x -q --tb=short

Once the driver exists, run a quick-profile smoke check through the staged runner:

    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit_runs --profile quick --final-output-dir artifacts/audit-quick-current

Validate the finished directory explicitly:

    bash scripts/run_repo_python.sh -m sattlint.devtools.artifact_readiness --artifact-dir artifacts/audit-quick-current

If the driver supports separate temporary and history controls, exercise that path too:

    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit_runs --profile full --final-output-dir artifacts/audit-full-current --keep-history artifacts/audit-history

After applying a targeted fix, validate findings resolution via the comparison command:

    bash scripts/run_repo_python.sh -m sattlint.devtools.compare_audit_findings --before artifacts/audit-full-current --after artifacts/audit-full-after-fix

After focused tests pass, run touched-file lint and type checks:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools/repo_audit_runs.py src/sattlint/devtools/artifact_readiness.py .vscode/tasks.json tests/test_repo_audit_runs.py tests/test_artifact_readiness.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools/repo_audit_runs.py src/sattlint/devtools/artifact_readiness.py tests/test_repo_audit_runs.py tests/test_artifact_readiness.py

## Validation and Acceptance

Acceptance requires a stable long-running execution surface. A quick-profile run through the driver must produce a complete final artifact directory, and the readiness checker must return success for that directory. A test fixture or synthetic incomplete directory must cause the readiness checker to fail with a clear message such as "progress pending" or "required file missing".

The VS Code audit tasks must still be easy to run, but they should now inherit the stable publish behavior from the driver. A novice should be able to run the task, wait for completion, and trust that `artifacts/audit-quick-current/` or `artifacts/audit-full-current/` is safe to read only after the driver publishes it.

## Idempotence and Recovery

The driver must be safe to re-run. If a previous completed output directory exists, the new run should either replace it atomically at the end or archive it first. If the audit process fails halfway, the temporary directory may remain for debugging, but the final output directory must never be replaced with a half-written run.

The readiness checker must be safe to run repeatedly against the same directory. It should never mutate artifacts. It should only report status.

## Artifacts and Notes

Baseline evidence from the transcript review:

    run_in_terminal calls = 369
    run_task calls = 13
    audit-heavy sessions = 154, 181, 288, and 568 tool calls
    representative stale-read session = 4a386d4b-6803-4395-8c4b-37fa61665e7d

The current task wiring already points to the right audit command family. The stability problem is publication timing, not the absence of tasks.

## Interfaces and Dependencies

The public driver should be a CLI such as `sattlint.devtools.repo_audit_runs` with flags like `--profile`, `--final-output-dir`, and optional history controls. The readiness checker should be a CLI such as `sattlint.devtools.artifact_readiness` with a required `--artifact-dir` input. Both commands should remain local-only and should build on the existing repo-audit CLI rather than duplicating its analysis logic.

The implementation depends on `src/sattlint/devtools/repo_audit.py`, `.vscode/tasks.json`, and the existing audit artifact shape defined by `status.json`, `summary.json`, `progress.json`, and related JSON outputs.
