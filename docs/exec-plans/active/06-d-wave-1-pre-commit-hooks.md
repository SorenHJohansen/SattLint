# D-Wave-1: Pre-Commit Hooks

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan implements D-032 from the feature roadmap: pre-commit hooks for the SattLint repository. Before this change, a developer can commit and push code that breaks the parser, fails tests, or violates linting rules without any automated gate. After this change, running `git commit` will automatically trigger a fast local check suite that catches the most common regressions before they reach the shared branch. The full validation route is `pre-commit run --all-files` to verify all hooks pass on the current worktree, and the CI pipeline will run the same hooks on every push to confirm that bypassed local runs are caught upstream.

A "pre-commit hook" in this context means a script registered through the [pre-commit](https://pre-commit.com) framework. The framework reads a `.pre-commit-config.yaml` file at the root of the repository, downloads or locates the tools listed there, and runs each hook against the staged files (or all files when invoked with `--all-files`). The hooks run in isolated environments managed by pre-commit itself, so contributors do not need to manually install each linter or formatter tool.

The hooks chosen for this repo are scoped to fast, deterministic checks that give clear, actionable feedback. Slow checks (full test suite, full workspace analysis) are left to CI to keep the commit flow responsive.

## Context

The SattLint repository uses Python 3.x and is developed inside a virtual environment at `.venv/`. The project is built with `pyproject.toml` using a `[project]` table (PEP 517/518 layout). The main entry points are `sattlint` and `sattlint-repo-audit`, both installed into `.venv/Scripts/`. Tests live in `tests/` and are run with `pytest`. The existing CI pipeline runs `pytest` and `sattlint syntax-check` as quality gates.

The relevant files touched by this plan are:

- `.pre-commit-config.yaml`
- `pyproject.toml` (possibly add `[tool.ruff]` config if not present)
- `.github/workflows/typing.yml` (run pre-commit before the existing pytest gate)
- `CONTRIBUTING.md` (document local hook setup)

## Scope

This wave contains one roadmap item:

- **D-032**: Pre-commit hooks. Deliver a working `.pre-commit-config.yaml` that covers: trailing-whitespace and end-of-file-fixer, YAML validity, Python syntax (via ruff check), and the SattLint parser self-check (`sattlint syntax-check` on any staged `.g`, `.l`, `.s` SattLine files when they are present in the commit).

Out of scope for this wave: formatter enforcement (black/ruff format auto-fix), secrets scanning, full test suite runs, and docstring coverage checks. Those belong to D-Wave-2 quality infrastructure.

## Milestones

### Milestone 1: Install pre-commit and author the config

Install the `pre-commit` package into the project dev dependencies. Check whether `pre-commit` already appears in `pyproject.toml` under `[project.optional-dependencies]` or `[tool.poetry.dev-dependencies]` or equivalent. If not, add it.

Create `.pre-commit-config.yaml` at the repository root. The minimum set of hooks for this wave is:

    repos:
      - repo: https://github.com/pre-commit/pre-commit-hooks
        rev: v5.0.0
        hooks:
          - id: trailing-whitespace
          - id: end-of-file-fixer
          - id: check-yaml
          - id: check-toml
          - id: check-merge-conflict
          - id: mixed-line-ending
            args: [--fix=lf]

      - repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.11.0
        hooks:
          - id: ruff
            args: [--select=E,F,W,I]

      - repo: local
        hooks:
          - id: sattlint-syntax-check
            name: SattLint syntax-check (staged SattLine files)
            language: system
            entry: .venv/Scripts/python.exe -m sattlint syntax-check
            files: \.(g|l|s)$
            pass_filenames: true

Pin exact `rev` values to released tags (not `main` or `HEAD`) so the hook environment is reproducible across machines and time.

After creating the file, run `pre-commit install` to register the hooks with the local git repository. This writes a file into `.git/hooks/pre-commit`. Confirm the install with `pre-commit run --all-files` from the repository root and resolve any failures before proceeding.

### Milestone 2: Fix any hook failures on existing files

Run `pre-commit run --all-files` and read all output. Common failures on first run:

- Trailing whitespace in existing source files: accept the auto-fix and stage the changes.
- End-of-file newlines: same, accept auto-fix.
- Ruff lint errors in `src/` or `tests/`: fix the reported lines or add inline `# noqa` suppressions only when the warning is demonstrably a false positive.
- Mixed line endings: pre-commit will auto-convert; stage the result.

Do not suppress the `sattlint-syntax-check` hook if it reports real SattLine parse errors. Investigate the flagged file and either fix the syntax or remove the file from the corpus if it is an intentionally invalid fixture. Intentionally invalid fixtures must live under `tests/fixtures/invalid/` and should be excluded from the hook via the `exclude` key in `.pre-commit-config.yaml`.

After all failures are resolved, run `pre-commit run --all-files` a second time and confirm clean output (exit code 0).

### Milestone 3: Wire pre-commit into CI

Locate the GitHub Actions workflow files under `.github/workflows/`. Add a job step that runs `pre-commit run --all-files` using the `pre-commit/action` GitHub Action or an equivalent `run:` step. The step should run before the existing `pytest` step so hook failures surface early. If a dedicated `lint.yml` workflow exists, add the step there; otherwise add it to the main CI workflow.

Ensure the CI step also runs on pull requests targeting `main`, not just on push to `main`.

Validate by pushing a branch with a deliberate trailing-whitespace violation in a `.py` file and confirming CI fails at the pre-commit step rather than silently passing.

### Milestone 4: Document the developer workflow

Update `CONTRIBUTING.md` (or create it if absent) to include a "Local setup" section that tells a new contributor to run `pre-commit install` after cloning. Keep the instructions to three lines or fewer: install the venv, run `pre-commit install`, and run `pre-commit run --all-files` to confirm a clean baseline.

## Validation

The acceptance criteria for this wave are:

1. `pre-commit run --all-files` exits 0 on the current worktree from the repo root.
2. `git commit` on a file with a deliberate trailing space auto-fixes the file and either commits the fix or rejects the commit with a clear message.
3. CI passes on a clean branch and fails on a branch with a staged ruff lint error.
4. `CONTRIBUTING.md` includes the `pre-commit install` instruction.

## Progress

- [x] Milestone 1: Create `.pre-commit-config.yaml` and run `pre-commit install`.
- [ ] Milestone 2: Resolve all hook failures on existing files; confirm clean `--all-files` run.
- [ ] Milestone 3: Add CI step for pre-commit; validate with a deliberate-failure test branch.
- [x] Milestone 4: Update `CONTRIBUTING.md` with developer setup instructions.
- [ ] Move this plan to `docs/exec-plans/completed/` once all milestones are validated.

Current state: Milestone-1 setup validation was executed locally (`pre-commit install` and `pre-commit run --all-files`). Install succeeded. Full hook run failed due existing repo-wide Ruff findings (primarily `E501` line length) and stopped before a clean baseline could be confirmed. Existing CI and contributor docs already include the required D-032 wiring, but deliberate-failure CI branch validation has not been executed in this wave.

## Surprises & Discoveries

- Repo already had `.pre-commit-config.yaml` with broader checks (`ruff-format`, `pyright`, large-file guard). This wave preserves those existing hooks and adds the missing D-032 requirements instead of narrowing the repo gate.
- The existing pytest CI gate lives in `.github/workflows/typing.yml`, not `lint.yml`. The pre-commit CI step belongs there to satisfy the "before pytest" requirement.
- `pre-commit run --all-files` currently fails on pre-existing Ruff debt across the repository (many `E501` findings), so D-032 clean-baseline validation is currently blocked by unrelated lint backlog rather than hook wiring gaps.

## Decision Log

- Decision: Use the `pre-commit` framework rather than raw git hooks scripts.
  Rationale: Framework manages hook isolation, pinning, and cross-platform installation automatically. Raw shell hooks would require per-machine setup and would not pin tool versions.
  Date/Author: 2026-04-29 / Copilot (Claude Sonnet 4.6)

- Decision: Keep the `sattlint syntax-check` hook as a `local` hook using the repo venv rather than packaging it as a standalone pre-commit hook mirror.
  Rationale: The tool is not published to PyPI as a standalone package yet, so a `local` hook that delegates to the venv Python is the simplest stable path.
  Date/Author: 2026-04-29 / Copilot (Claude Sonnet 4.6)

- Decision: Exclude intentionally-invalid SattLine fixtures from the syntax-check hook via the `exclude` pattern rather than disabling the hook globally.
  Rationale: Disabling globally would let real regressions in valid SattLine files slip through. Scoped exclusion keeps protection on the production corpus.
  Date/Author: 2026-04-29 / Copilot (Claude Sonnet 4.6)

- Decision: Preserve the repo's existing `ruff-format`, `pyright`, and large-file hooks while adding the missing D-032 hooks.
  Rationale: Those hooks were already part of the repo's local/CI workflow. Removing them would be a behavior change unrelated to this exec-plan and would widen risk without helping D-032.
  Date/Author: 2026-04-29 / Copilot (GPT-5.4)

- Decision: Track D-032 implementation status separately from existing repo-wide Ruff debt.
  Rationale: The required pre-commit, CI, and contributor wiring is present, but baseline `--all-files` success cannot be claimed until existing lint violations are remediated. Marking this explicitly avoids conflating integration work with unrelated cleanup scope.
  Date/Author: 2026-04-29 / Copilot (GPT-5.3-Codex)

## Outcomes & Retrospective

- Milestone 1 is complete from a setup perspective: hooks install correctly and execute.
- Milestone 4 is complete: contributor setup already includes the required `pre-commit install` flow.
- Remaining blocker is Milestone 2 baseline cleanliness (`pre-commit run --all-files` exit 0) due existing Ruff findings not introduced by this wave.
- Milestone 3 still needs explicit deliberate-failure branch validation to close the CI-proof requirement.
