# T-Wave-8 CI Workflow Consolidation And Release Rehearsal

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes SattLint's GitHub Actions behavior match the repository's AI-only operating model instead of forcing contributors to infer which workflows are intentionally layered and which ones are accidentally duplicated. After this work lands, pull requests and `main` pushes will still get the integrated full-trust gate described in `AGENTS.md`, but the heaviest repo-audit work will run in one authoritative place instead of twice. The owner workflows in `.github/workflows/lint.yml`, `.github/workflows/typing.yml`, and `.github/workflows/repo-audit.yml` will remain, but each will own a narrower and clearer slice. The review question for this plan is not only "does CI run?" but also "does this automation still represent the real repository and release path, or is it ceremonial drift?"

This plan also closes the largest release-automation gap found in the CI review. Maintainers will be able to run the same build and smoke-validation path that the publish workflow uses without actually publishing to PyPI. The observable proof is simple: a draft pull request shows one integrated audit path plus the owner workflows, a `main` push no longer runs two Ubuntu full-audit legs, and a manual `publish.yml` run builds distributions, runs the release smoke checks, uploads artifacts, and stops before publication.

## Progress

- [x] (2026-05-19 00:00Z) Created this ExecPlan and captured the current workflow inventory: `.github/workflows/ci.yml`, `.github/workflows/lint.yml`, `.github/workflows/typing.yml`, `.github/workflows/repo-audit.yml`, and `.github/workflows/publish.yml`.
- [x] (2026-05-19 00:00Z) Confirmed that SattLint is intentionally AI-only and already documents a layered workflow model: `ci.yml` is the integrated full-trust and nightly workflow, while `lint.yml`, `typing.yml`, and `repo-audit.yml` are owner workflows.
- [x] (2026-05-19 00:00Z) Captured the highest-value workflow defects: duplicate Ubuntu full-audit work on `main`, repeated raw `actionlint` download logic, missing publish rehearsal, and naming or doc drift around `typing.yml`, nightly outputs, and advisory review.
- [ ] Add one shared CI setup surface and one checksum-verified `actionlint` installer so the workflow files stop repeating setup and stop downloading the binary without verification.
- [ ] Refactor `ci.yml`, `lint.yml`, `typing.yml`, and `repo-audit.yml` to use the shared setup surface, keep the AI-only layered model, and remove the duplicate Ubuntu full-audit leg.
- [ ] Review workflow jobs, uploads, and quality gates against the current repo architecture so stale or ceremonial automation is removed instead of merely kept green.
- [ ] Align `AGENTS.md`, `docs/quality-gates.md`, and any nearby CLI or workflow docs with the actual workflow names, triggers, ownership, and advisory-versus-blocking behavior.
- [ ] Extend `publish.yml` with a safe release rehearsal path that runs the same build and smoke checks without publishing, reusing the repo-owned release-smoke seam instead of inventing a second release validator.
- [ ] Run focused local validation, then run one GitHub Actions rehearsal through `workflow_dispatch` and record the result in this plan.

## Surprises & Discoveries

Observation: the repo already has a deliberate workflow architecture for an AI-only project; the problem is drift and duplication inside that architecture, not the absence of structure.
Evidence: `AGENTS.md` says `ci.yml` is the integrated full-trust and nightly workflow while `lint.yml`, `typing.yml`, and `repo-audit.yml` remain owner workflows, and `docs/quality-gates.md` repeats the same split.

Observation: the clearest accidental duplication is the Ubuntu full repo audit on `main`.
Evidence: `.github/workflows/ci.yml` job `full-trust` runs `python -m sattlint.devtools.repo_audit --profile full --output-dir artifacts/audit-ci --fail-on high` on non-PR events, and `.github/workflows/repo-audit.yml` job `audit` also runs `python -m sattlint.devtools.repo_audit --profile full --output-dir artifacts/audit --fail-on high` for the Ubuntu matrix entry on pushes to `main`.

Observation: the most concrete workflow security issue is not an unpinned GitHub Action, because the Actions are already pinned to full commit SHAs.
Evidence: every `uses:` entry in the checked-in workflow files is SHA-pinned, but three workflows still download `actionlint` with `curl` and install it with `sudo` without a checksum or signature check.

Observation: the publish flow still lacks the rehearseable artifact path that the active public-release plan already calls for.
Evidence: `.github/workflows/publish.yml` builds distributions, runs `twine check`, uploads the artifacts, and publishes to PyPI on `v*` tags, but it has no `workflow_dispatch` dry-run path and no smoke-install or boot check before publication.

Observation: `typing.yml` is the least clear owner surface for a novice because its filename implies typing only while the workflow also owns tests, dependency audit, and ratchet policy.
Evidence: `.github/workflows/typing.yml` contains jobs `pyright`, `tests`, `pip-audit`, and `ratchet_policy`, while the workflow display name is currently `Quality`.

Observation: workflow-only tool management is inconsistent today.
Evidence: `.github/dependabot.yml` updates `pip` and `github-actions`, `package.json` only contains `better-sqlite3`, `scripts/run_markdownlint.py` can use `npx` when available, and the workflow files still pin `markdownlint-cli2` and the `actionlint` release directly in YAML.

## Decision Log

- Decision: keep the AI-only layered workflow model instead of collapsing everything into one monolithic workflow.
  Rationale: `AGENTS.md` and `docs/quality-gates.md` already define `ci.yml` as the integrated gate and the other workflow files as owner workflows. The review found waste and drift inside that model, not evidence that the model itself is wrong.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: make `ci.yml` the only workflow that runs the authoritative Ubuntu full repo audit on pull requests, `main` pushes, manual CI runs, and nightly health.
  Rationale: that removes the most expensive duplicate work without weakening the owner-workflow split.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: keep `repo-audit.yml` as an owner workflow, but narrow it to checks that `ci.yml` does not already own.
  Rationale: packaging validation, public-readiness or leak checks, and a Windows quick audit are still useful owner checks, while a second Ubuntu full audit on `main` is not.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: judge the workflow cleanup by representational accuracy, not by whether old YAML can still execute.
  Rationale: AI-generated repositories often keep dead uploads, obsolete gates, and duplicated jobs that remain syntactically valid. This slice should remove or narrow those ceremonial paths instead of preserving them for appearance.
  Date/Author: 2026-05-20 / Copilot (GPT-5.4)

- Decision: keep `Agent Review (Advisory)` non-blocking in this slice unless the repository explicitly raises reviewer-agent output to a required gate later.
  Rationale: the AI-only workflow docs describe reviewer work as a distinct role, but the checked-in CLI docs already say `sattlint-review` is advisory in CI. Reclassifying it as blocking would be a policy change, not just a cleanup.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: preserve the file path `.github/workflows/typing.yml` in this slice, but align its display name and documentation with its broader responsibility.
  Rationale: the current file path is already referenced in docs and may be referenced in repository settings outside the worktree. Updating the display name and nearby docs is lower risk than renaming the file while this slice is still about consolidation.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: add release rehearsal to `publish.yml` itself through `workflow_dispatch` instead of creating a second publish-adjacent workflow.
  Rationale: a single workflow with one build path is easier to keep honest than a separate release-candidate workflow that can drift from the real publish path.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: reuse the repo-owned release-smoke seam already required by `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md`.
  Rationale: the release review found a missing workflow path, not a reason to invent a second artifact validator. This plan should wire the workflow side to the same smoke contract instead of duplicating release logic.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At creation time, this plan records a concrete, implementable workflow cleanup without changing repository behavior yet. The intended outcome is a smaller and more trustworthy GitHub Actions surface: one full-audit owner, one rehearseable release path, one shared setup surface, and documentation that explains the AI-only workflow split honestly.

The largest execution risk is scope creep. It would be easy to widen this plan into a full release-management redesign or a general dependency-management overhaul. This plan should stay focused on the checked-in GitHub Actions files, the CI helper surface they need, the repo-owned release-smoke path they already depend on, and the docs that explain those workflows.

## Context and Orientation

SattLint is an AI-only repository. In this repository, `AI-only` means the development workflow is designed around planner, executor, test, and reviewer agents rather than around a single manual contributor path. `AGENTS.md` says the integrated CI workflow is `.github/workflows/ci.yml`, while `.github/workflows/lint.yml`, `.github/workflows/typing.yml`, and `.github/workflows/repo-audit.yml` are owner workflows that each cover a narrower surface. `docs/quality-gates.md` repeats that contract and also says nightly health should come from `ci.yml`.

The current workflow files are small enough to reason about directly. `.github/workflows/ci.yml` has job `full-trust` with display name `Full Trust Gate` and job `nightly-health` with display name `Nightly Health`. `full-trust` runs on pull requests, pushes to `main`, and `workflow_dispatch`; it installs Python, `uv`, Node, `markdownlint-cli2`, and `actionlint`, then runs context health, actionlint, pre-commit, doc gardener, and either `--check-my-changes` or a full repo audit. `.github/workflows/lint.yml` owns job `actionlint`, job `ruff`, job `doc-gardener`, job `layer-lint`, and job `review`. `.github/workflows/typing.yml` owns job `pyright`, job `tests`, job `pip-audit`, and job `ratchet_policy`. `.github/workflows/repo-audit.yml` currently owns one matrix job `audit` that runs a full Ubuntu repo audit plus build and leak checks and a Windows quick audit on pushes to `main`. `.github/workflows/publish.yml` owns jobs `build` and `publish` and publishes to PyPI on `v*` tag pushes.

Two helper scripts matter immediately. `scripts/run_actionlint.py` does not install `actionlint`; it only finds an existing binary on `PATH` or in a few common locations and executes it. `scripts/run_markdownlint.py` can use a locally installed `markdownlint-cli2`, WSL, or `npx`, which means the repo already has a good wrapper around Node-based Markdown linting and does not need a second custom frontend.

In this plan, an `integrated gate` means one workflow that runs the repo-wide trust checks expected before merge or on `main`. An `owner workflow` means a separate workflow file that covers one narrower concern, such as lint, typing, or repo-audit-specific checks. A `release rehearsal` means running the build and smoke-validation steps that a real publish uses, but stopping before any upload to PyPI. A `full repo audit` means the `sattlint.devtools.repo_audit --profile full` path that already aggregates many quality signals. A `quick audit` means the lighter audit profile used for faster or secondary coverage.

This plan intentionally touches one already-active release plan. `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` already requires a repo-owned release smoke validator and a rehearseable publish path. This plan does not redefine the release-smoke contract. It owns the workflow wiring, the CI setup cleanup, and the docs alignment needed to make that release-smoke contract usable from GitHub Actions.

## Plan of Work

Begin by centralizing repeated setup and the repeated `actionlint` install logic. Add one checked-in composite action at `.github/actions/setup-ci-tooling/action.yml` that handles the common Python and `uv` bootstrap and can optionally add Node, `markdownlint-cli2`, and `actionlint`. Do not leave `actionlint` download logic inline in three workflow files. Add a repo-owned installer at `scripts/install_actionlint.py` so the binary download, archive extraction, and SHA-256 verification live in one testable place. The script should accept at least `--version`, `--sha256`, and `--bin-dir`; it should download the named release tarball for the current runner, verify the checksum before extraction, and write the executable into the caller-provided directory. Add focused regression coverage in `tests/test_install_actionlint.py` for checksum mismatch, successful install into a temporary directory, and unsupported-platform handling.

Next, refactor the workflow files to consume that shared setup surface without changing their high-level roles. `.github/workflows/ci.yml` should keep jobs `full-trust` and `nightly-health`, keep actionlint and doc-gardener inside the integrated gate, and remain the only place that runs the authoritative Ubuntu full audit. `.github/workflows/lint.yml` should keep job `actionlint`, job `ruff`, job `doc-gardener`, job `layer-lint`, and job `review`, but it should stop duplicating setup logic and should clearly document that `review` remains advisory. `.github/workflows/typing.yml` should keep its existing jobs but change its displayed workflow name to something truthful such as `Typing And Quality`, because it owns typing, tests, dependency audit, and ratchet policy. Do not rename the file path in this slice.

Then narrow `.github/workflows/repo-audit.yml` so it owns checks that are still valuable after `ci.yml` becomes the sole full-audit owner. The Windows matrix leg should keep a quick audit because it gives platform coverage that `ci.yml` does not provide. The Ubuntu leg should stop running the full audit and should instead own packaging and release-adjacent checks such as `python -m build`, `python -m twine check dist/*`, the leak-only audit, and the public-readiness audit if that check is already cheap and deterministic enough to run there. If the public-readiness check is not yet reliable enough, leave it in the release-smoke or release-readiness slice and keep this workflow focused on packaging plus leaks. In the same pass, challenge every uploaded artifact, duplicate status check, and legacy quality gate: if it no longer feeds a real maintainer, reviewer, or release workflow, remove it rather than keeping a ceremonial upload or job.

After the owner workflows are narrowed, wire the release rehearsal path into `.github/workflows/publish.yml`. Add `workflow_dispatch` so maintainers can trigger a build and smoke run manually. The `build` job should run for both tag pushes and manual dispatches, and it should do more than `python -m build` plus `twine check`: it must also invoke `src/sattlint/devtools/release_smoke.py` or the same CLI wrapper provided by the release-readiness slice, then upload the smoke artifacts. The `publish` job must only run on real `v*` tag pushes after the build and smoke checks succeed. The manual dispatch path must never publish.

Finish by making the docs tell the truth about the cleaned-up workflow surface. Update `AGENTS.md` and `docs/quality-gates.md` so they describe the post-cleanup ownership split precisely. Update `docs/references/cli-commands.md` where it mentions the advisory `sattlint-review` behavior and any new release-smoke CLI entry point or publish rehearsal instructions. If the nightly workflow still does not emit all the outputs currently listed in `docs/quality-gates.md`, either wire those outputs in through existing scripts or narrow the docs to the outputs that the workflow really produces. Choose one truth and make the code and docs agree.

## Concrete Steps

Run all commands from the repository root.

Start by validating the baseline workflow files before any edits:

    python scripts/run_actionlint.py

Add the shared setup action and the verified `actionlint` installer, then run the focused tests for that seam:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_install_actionlint.py -x -q --tb=short

Refactor the workflow files and validate them immediately with actionlint and the Markdown or policy docs touched by the slice:

    python scripts/run_actionlint.py
    python -m pre_commit run --files .github/workflows/ci.yml .github/workflows/lint.yml .github/workflows/typing.yml .github/workflows/repo-audit.yml .github/workflows/publish.yml AGENTS.md docs/quality-gates.md docs/references/cli-commands.md

If this slice also lands the release-smoke owner seam from the active public-release plan, validate that seam locally before relying on the workflow:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_release_smoke.py tests/test_repo_audit.py tests/test_repo_audit_cli.py -x -q --tb=short

If new Python files are added in `scripts/` or `src/sattlint/devtools/`, run focused typing on those exact files:

    bash scripts/run_repo_python.sh -m pyright scripts/install_actionlint.py src/sattlint/devtools/release_smoke.py tests/test_install_actionlint.py tests/test_release_smoke.py

Once the YAML and local helper surfaces are green, run one manual release rehearsal in GitHub Actions:

    - open the `Publish` workflow in GitHub Actions
    - trigger `workflow_dispatch`
    - confirm the run performs build, `twine check`, and release-smoke validation
    - confirm the run uploads distributions and smoke artifacts
    - confirm the run does not publish to PyPI

For the final workflow-shape proof, inspect one draft pull request and one `main` push after the change lands:

    - the draft pull request should show the integrated `CI` workflow plus the owner workflows
    - `repo-audit.yml` should no longer contribute a second Ubuntu full-audit leg
    - the `main` push should still show packaging or Windows audit owner checks from `repo-audit.yml`

## Validation and Acceptance

Acceptance is behavioral. After this plan is implemented, a pull request must still trigger the integrated `CI` workflow and the owner workflows, but only one workflow may own the authoritative Ubuntu full repo audit. A `main` push must no longer schedule both `ci.yml` and `repo-audit.yml` to run equivalent full-audit commands on Ubuntu. The remaining workflow jobs, uploads, and gates must also correspond to real maintainer or release paths rather than stale ceremonial automation.

The workflow setup surface must be smaller and safer. There must be one checked-in place that installs `actionlint`, and that installer must verify the expected SHA-256 checksum before extracting the binary. Local `python scripts/run_actionlint.py` must still pass after the refactor.

The release path must be rehearseable. A manual `workflow_dispatch` run of `publish.yml` must build distributions, pass `twine check`, run the repo-owned release smoke validation, upload artifacts, and exit without publishing. A real `v*` tag push must reuse that same build-and-smoke path and only then enter the publish job.

The documentation must match the shipped workflow behavior. `AGENTS.md`, `docs/quality-gates.md`, and any nearby workflow CLI docs must describe the same ownership split, the same advisory-versus-blocking review stance, and the same release rehearsal path that the workflow files actually implement.

## Idempotence and Recovery

The shared setup action and the `actionlint` installer must be safe to rerun. Installing the same `actionlint` version into a temporary or caller-owned bin directory should overwrite or replace the existing binary without corrupting the runner state. A checksum mismatch must fail before extraction and must not leave a half-installed executable on disk.

The manual release rehearsal path must be safe by default. `workflow_dispatch` on `publish.yml` must never publish to PyPI. If a rehearsal fails, rerunning it after a fix should use the same workflow entry point and should not require a new version tag.

Do not widen this slice into a general release-policy rewrite. If `src/sattlint/devtools/release_smoke.py` does not exist yet when implementation begins, land the smallest version that satisfies the already-active public-release plan and this workflow wiring. If release policy questions remain, keep them in `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` instead of inventing a third release design.

## Artifacts and Notes

Baseline workflow inventory captured when this plan was created:

    - `.github/workflows/ci.yml`: jobs `full-trust` (`Full Trust Gate`) and `nightly-health` (`Nightly Health`)
    - `.github/workflows/lint.yml`: jobs `actionlint`, `ruff`, `doc-gardener`, `layer-lint`, and `review` (`Agent Review (Advisory)`)
    - `.github/workflows/typing.yml`: jobs `pyright`, `tests`, `pip-audit`, and `ratchet_policy`
    - `.github/workflows/repo-audit.yml`: one matrix job `audit` with Ubuntu full audit plus build and leak checks and Windows quick audit
    - `.github/workflows/publish.yml`: jobs `build` and `publish` on `v*` tags

Key review findings captured at plan creation:

    - duplicate Ubuntu full-audit work exists in both `ci.yml` and `repo-audit.yml` on `main`
    - `actionlint` is downloaded in multiple workflows without checksum verification
    - `publish.yml` has no dry-run or rehearsal path
    - `typing.yml` owns broader quality checks than its filename suggests
    - `.github/dependabot.yml` covers `pip` and `github-actions`, but workflow-only tool versions are still scattered through workflow YAML

This plan intentionally depends on the existing release-readiness direction already written in:

    - `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md`

That plan remains the source of truth for the release-smoke contract itself. This plan owns the GitHub Actions and shared-setup side of the same work.

## Interfaces and Dependencies

Add one composite action at `.github/actions/setup-ci-tooling/action.yml`. It should accept explicit inputs for the Python version and for optional Node, Markdown lint, and `actionlint` installation so the workflow files can stay declarative instead of embedding long shell blocks. The composite action may call SHA-pinned third-party setup actions, but it must delegate binary download verification to the repo-owned installer instead of repeating `curl` logic inline.

Add one repo-owned installer at `scripts/install_actionlint.py`. At the end of this slice, it must expose a command-line interface that accepts at least `--version`, `--sha256`, and `--bin-dir`, detects the current platform or accepts an override for tests, downloads the matching release asset, verifies the checksum, extracts the `actionlint` binary, and exits non-zero on mismatch or unsupported platform.

Reuse the release-smoke interface already required by `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md`. At the end of this slice, the publish workflow must be able to call a repo-owned command in `src/sattlint/devtools/release_smoke.py` or an equivalent checked-in CLI surface that accepts a built wheel, a sample file, and an output directory and emits machine-readable results.

The main workflow files that must stay aligned are `.github/workflows/ci.yml`, `.github/workflows/lint.yml`, `.github/workflows/typing.yml`, `.github/workflows/repo-audit.yml`, `.github/workflows/publish.yml`, `AGENTS.md`, and `docs/quality-gates.md`. If this slice changes how advisory review or release rehearsal is invoked, also update `docs/references/cli-commands.md` so the human-facing CLI docs stay honest.
