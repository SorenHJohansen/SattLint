# T-Wave-10 Observability Rewrite and CI Security Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

`src/sattlint/devtools/observability.py` currently applies destructive changes to the live source tree as a side effect of reading a metric. The `get_lint_metrics()` function passes `--fix` to `ruff`, which auto-applies code changes and silently discards the output. This means any agent workflow that invokes the observability collector is silently modifying production source files. Additionally, the module bypasses the repo venv by invoking `uvx` and `uv` directly, returns hardcoded zeros for all test metrics, and always initializes build-health flags to `False` without ever setting them to a success value. The `ruff_fixable` field is always zero and is explicitly noted in a comment as unimplemented. Every agent workflow consuming `artifacts/observability.json` therefore receives permanently incorrect data.

In CI, `bandit` (the static application security testing tool) is declared as a dev dependency in `pyproject.toml` but is never invoked in any workflow file. The `lint.yml`, `ci.yml`, and `typing.yml` workflows have no `bandit` step. Similarly, `pytest-benchmark` is declared as a dev dependency for "performance testing" but zero benchmark tests exist in the repository — it is a false dependency.

After this work lands, the observability collector produces accurate metrics using only the repo venv, does not modify source files under any circumstances, and emits correct test and build-health data sourced from already-written artifacts when they exist. `bandit` runs in CI on every push. `pytest-benchmark` is removed from `pyproject.toml`. The `write_metrics` and `read_metrics` functions specify `encoding="utf-8"` explicitly.

## Progress

- [x] Read the full current `src/sattlint/devtools/observability.py` to understand every function and the `main()` entry point before editing.
- [x] Rewrite `get_lint_metrics()` to invoke the repo venv `ruff check src --output-format=json` (read-only, never `--fix`) and parse the JSON output to count warnings and errors. Remove the `--fix` invocation entirely. Derive `ruff_fixable` from the JSON output's `fix` field if available, or omit the field rather than lying with a hardcoded zero.
- [x] Rewrite `get_build_metrics()` to replace `uv pip install --system` with a read-only check: inspect whether the package is importable in the current venv (e.g., `python -c "import sattlint"`) and set `install_success` from that exit code. Remove `uv` from the command entirely. Set `lint_success` by reusing the lint metrics result rather than leaving it hardcoded `False`. Remove `test_success` from this function — it belongs in `get_test_metrics()`.
- [x] Rewrite `get_test_metrics()` to derive real data from `coverage.xml` (already parsed by `get_coverage_metrics()`) or from a pytest `--tb=no -q` run against the test suite using the repo venv Python, not `uvx`. If a fresh run is too expensive for the observability context, read the last known test-result artifact if it exists and fall back to zeros with a `"stale": true` flag.
- [x] Replace all `run_command(["uvx", ...])` and `run_command(["uv", ...])` calls with calls that use `sys.executable` as the Python interpreter for the repo venv (e.g., `[sys.executable, "-m", "ruff", ...]`).
- [x] Add `encoding="utf-8"` to both `open()` calls in `write_metrics` and `read_metrics`.
- [x] Remove `pytest-benchmark>=4.0.0` from `pyproject.toml`'s `[dev]` dependencies. Confirm there are zero benchmark test files before removing.
- [x] Add a `bandit` CI step to `.github/workflows/lint.yml` using the repo venv Python (matching the existing `ruff` step pattern). Scope it to `src/` and use `-c pyproject.toml` so the existing `[tool.bandit]` config (or a new one) drives the run. Add `[tool.bandit]` configuration to `pyproject.toml` if it does not already exist, at minimum setting `skips` to the list of rule IDs that have already been accepted via `# nosec` comments.
- [x] Write or extend a focused test in `tests/devtools/test_observability.py` (or the nearest existing test file for this module) that asserts `get_lint_metrics()` does not modify any file in `src/` and that `write_metrics` / `read_metrics` preserve UTF-8 content round-trip.
- [ ] Run `pyright` over the touched files and confirm zero new type errors.
- [ ] Run the full test suite and confirm no regressions.

Current validation state:

- `tests/devtools/test_devtools_review_observability.py` passes after the rewrite.
- `python -m pyright src/sattlint/devtools/observability.py` passes with zero errors, but the broader touched-file invocation still reports longstanding strict-test diagnostics in `tests/devtools/test_devtools_review_observability.py`.
- The previous unrelated blocker in `tests/test_variables_submodule_helpers.py::test_framemodule_subtree_uses_repathed_context` is cleared.
- `python -m pytest --no-cov -x -q --tb=short` currently fails in unrelated pre-existing test `tests/test_analyzers_variables.py::test_graphics_format_tail_keywords_do_not_log_missing_variables`.

## Surprises & Discoveries

- The repository already emits reusable pytest artifacts at `artifacts/audit/pipeline/pytest.json` and `pytest.junit.xml`, so `get_test_metrics()` could stay read-only and still return real counts.
- `python -m bandit -r src/ -c pyproject.toml` was already clean on findings; the new `[tool.bandit]` section is primarily to make the CI contract explicit and stable.
- The active full test-suite failure is unrelated to observability or CI security work: `tests/test_analyzers_variables.py::test_graphics_format_tail_keywords_do_not_log_missing_variables` currently fails in the variables analyzer owner suite.
- Running Pyright directly on `tests/devtools/test_devtools_review_observability.py` exposes broad existing pytest-fixture typing noise that predates this slice and prevents a clean touched-files proof without a larger test-typing cleanup.

## Decision Log

- Decision: use `sys.executable` for all subprocess invocations rather than hardcoding `python` or searching PATH.
  Rationale: `sys.executable` is the Python interpreter that is currently running — i.e., the repo venv interpreter. Using it guarantees that ruff, pytest, and other dev tools installed in the venv are the ones invoked, matching AGENTS.md's explicit requirement to use repo venv commands.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: remove `--fix` from the ruff invocation and never pass it from observability code.
  Rationale: an observability function has no business mutating source files. The review classification is Critical (C-1) for exactly this reason. The fixable-issue count should come from the JSON output's fix data, not from a destructive side-effect run.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: remove `pytest-benchmark` as a false dependency rather than adding benchmark tests to justify it.
  Rationale: the repository has no benchmark tests and no active plan to add them. A false dependency introduces install-time overhead, Dependabot noise, and potential version conflicts for no benefit. Performance testing in this repo is done via custom measurement scripts in `artifacts/tmp/`, not via pytest-benchmark fixtures.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: add bandit to `lint.yml` rather than creating a new security workflow.
  Rationale: `lint.yml` already runs ruff and the doc-gardener and layer-linter scans. Bandit is a static analysis tool with the same profile. Keeping all static analysis in one workflow file reduces CI job overhead and makes the security scan visible to reviewers alongside other lint results.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: source test metrics from existing pytest artifacts rather than re-running pytest inside observability collection.
  Rationale: the repository already writes structured pytest JSON and JUnit artifacts for pipeline and audit flows. Reusing those artifacts keeps observability read-only, avoids expensive test reruns during agent workflows, and still returns accurate pass/fail counts when recent artifacts exist.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

## Outcomes & Retrospective

- `src/sattlint/devtools/observability.py` now uses repo-venv Python exclusively, parses Ruff JSON without `--fix`, reads last-known pytest artifacts with a `stale` fallback, performs a read-only import check for install health, and writes UTF-8 explicitly.
- `.github/workflows/lint.yml` now runs Bandit on `src/` in CI, and `pyproject.toml` documents the Bandit policy plus removes the unused `pytest-benchmark` dependency.
- Focused observability tests, Bandit, source-file Pyright, and a no-mutation entrypoint proof all pass. Repo-wide completion is still blocked by unrelated existing failures outside this slice.

## Context and Orientation

`src/sattlint/devtools/observability.py` is a devtools module invoked by AI agent workflows to collect health metrics about the repository. It produces `artifacts/observability.json`, which is consumed by the AI observability workflow documented in `docs/ai-workflows.md`. The module uses a `run_command(cmd)` helper that wraps `subprocess.run`.

The three critical bugs are:

1. `get_lint_metrics()` at line 89 calls `run_command(["uvx", "ruff", "check", "--fix", ...])`. The `--fix` flag tells ruff to apply auto-corrections in place. The output of this call is immediately discarded. This silently mutates source files on every observability run.

2. `get_build_metrics()` at line 97 calls `run_command(["uv", "pip", "install", "--system", "-e", ".[dev]"])`. The `--system` flag modifies the system Python environment rather than the repo venv. The `uv` binary may not exist at the PATH used by CI or agent runs. The result fields `lint_success` and `test_success` are initialized to `False` and never updated; they are always `False`.

3. `get_test_metrics()` at lines 30–42 returns a hard-coded dict of zeros with a comment acknowledging the implementation is incomplete.

The `write_metrics` and `read_metrics` functions at lines 122–130 open files without specifying `encoding=`. On non-UTF-8 systems this may produce encoding errors or silently write platform-specific encodings that differ from what downstream readers expect.

The `ruff --output-format=json` output is a JSON array of diagnostic objects. Each object has a `"code"` field, a `"message"` field, and optionally a `"fix"` field when a fix is available. Counting objects with a `"fix"` key gives `ruff_fixable`. Counting all objects gives `ruff_errors` (ruff has no warning/error distinction — all findings are "errors" in ruff's model; the `ruff_warnings` key is misleading and should be clarified or removed).

For CI: `bandit` is invoked as `python -m bandit -r src/ -c pyproject.toml`. The `[tool.bandit]` section in `pyproject.toml` controls which rules are enabled and which test IDs are skipped. Existing `# nosec B404` and `# nosec B603` comments in the codebase already accept specific subprocess-call patterns; these should be reflected in the `skips` list or kept as inline suppressions.

## Plan of Work

Start by reading the full `observability.py` and the existing test coverage (search for `test_observability` or imports of the module in tests). Understand what the module is expected to produce so the rewrite does not silently change output keys that downstream consumers expect.

Rewrite `get_lint_metrics()` first. Replace the two `run_command(["uvx", ...])` calls with a single `run_command([sys.executable, "-m", "ruff", "check", "src", "--output-format=json"])`. Parse the JSON output to count total diagnostics (assign to `ruff_errors`) and diagnostics that have a `"fix"` key (assign to `ruff_fixable`). Remove `ruff_warnings` or keep it as an alias for `ruff_errors` with a clear comment. The `--fix` call must be removed entirely — no variant of it should remain.

Rewrite `get_build_metrics()`. Replace the `uv pip install --system` call with a read-only venv check: `run_command([sys.executable, "-c", "import sattlint"])` and set `install_success = returncode == 0`. Set `lint_success` by re-invoking `get_lint_metrics()` and checking whether `ruff_errors == 0`. Remove `test_success` from this function since it duplicates `get_test_metrics()`.

Rewrite `get_test_metrics()`. Read `coverage.xml` (if it exists and is recent) and extract the test count from it (the `<testcase>` count in a JUnit XML, or derive from the coverage report's total-statements and the existing coverage metrics). If the artifact is absent, return zeros with `"stale": True` so consumers know the data is unavailable rather than incorrect.

Add `encoding="utf-8"` to the `open()` calls in `write_metrics` and `read_metrics`.

For `pyproject.toml`: remove the `pytest-benchmark>=4.0.0` line from `[project.optional-dependencies]`'s `dev` list. Then add a `[tool.bandit]` section (if absent) that excludes `tests/` from the scan scope and lists accepted rule IDs (`B404`, `B603`) as `skips` to avoid noise from the existing `# nosec` comments.

For `lint.yml`: add a `bandit` job following the same structure as the `ruff` job. Use `ubuntu-latest` only (no matrix needed for SAST). The step should run `python -m bandit -r src/ -c pyproject.toml`.

## Concrete Steps

Run all commands from the repository root.

Check for any benchmark test files before removing the dependency:

    find tests/ -name "*.py" | xargs grep -l "benchmark\|pytest_benchmark" 2>/dev/null

Expected: no output (zero benchmark test files).

After rewriting `get_lint_metrics()`, verify it does not modify source files:

    git stash -u  # save working tree state
    bash scripts/run_repo_python.sh -m sattlint.devtools.observability
    git diff --stat  # should show zero diffs in src/

Run the focused observability tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/ -k "observability" -x -q --tb=short

Run bandit manually against src/ to confirm the CI step will pass:

    bash scripts/run_repo_python.sh -m bandit -r src/ -c pyproject.toml

Expected: zero issues at HIGH or MEDIUM severity after the `# nosec` annotations and `[tool.bandit]` config are in place.

Run pyright over touched files:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools/observability.py

Run the full test suite:

    bash scripts/run_repo_python.sh -m pytest --no-cov -x -q --tb=short

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. Running `sattlint.devtools.observability` produces `artifacts/observability.json` and `git diff --stat src/` shows zero changes.
2. `get_lint_metrics()` returns a dict with `ruff_errors` based on actual ruff output, not a hardcoded zero.
3. `get_build_metrics()` returns `install_success: true` on a machine with the venv active.
4. `bandit -r src/ -c pyproject.toml` exits zero (no unaccepted HIGH or MEDIUM issues).
5. `pytest-benchmark` is not listed in `pyproject.toml` and `pip show pytest-benchmark` shows it is not installed.
6. `pyright` and `pytest --no-cov -x` both pass over all touched files.

## Idempotence and Recovery

The observability rewrite is isolated to one module. If the rewrite produces worse metrics (e.g., the ruff JSON output is harder to parse than expected), the previous implementation can be restored without affecting any other module. The `pytest-benchmark` removal is additive-in-reverse — re-adding it to `pyproject.toml` and running `pip install -e .[dev]` restores it instantly.

## Artifacts and Notes

Critical bug evidence:

    # Line 89 of observability.py — mutates source tree as side effect of reading a metric:
    _, _, _ = run_command(["uvx", "ruff", "check", "--fix", "--output-format=concise", "src"])

    # Line 98–100 — always-False flags, never set to True:
    "install_success": False,
    "lint_success": False,
    "test_success": False,

    # Line 79 — bypasses repo venv:
    _, stdout, _ = run_command(["uvx", "ruff", "check", "src"])

    # Line 103 — modifies system packages:
    returncode, _, _ = run_command(["uv", "pip", "install", "--system", "-e", ".[dev]"])

## Interfaces and Dependencies

After this plan, `observability.json` will contain:

    {
      "timestamp": "...",
      "test": { "test_count": <int>, "passed": <int>, "failed": <int>, "skipped": <int>, "stale": <bool> },
      "coverage": { "line_coverage": <float>, "branch_coverage": <float> },
      "lint": { "ruff_errors": <int>, "ruff_fixable": <int> },
      "build": { "install_success": <bool>, "lint_success": <bool> }
    }

The `ruff_warnings` key is removed (ruff has no warning category). Downstream consumers that read this field must be updated to use `ruff_errors`.
