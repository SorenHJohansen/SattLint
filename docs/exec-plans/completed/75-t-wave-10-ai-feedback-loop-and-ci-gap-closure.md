# T-Wave-10 AI Feedback Loop and Structural CI Gap Closure

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

The 2026-06-02 code review identified two systemic gaps that allow architecture drift and AI-introduced code patterns to accumulate without detection:

1. The `review-ai-sessions` prompt exists at `.github/prompts/review-ai-sessions.prompt.md` and is the intended feedback mechanism for learning from AI session quality, but it is orphaned — no agent, workflow schedule, or CI job ever invokes it. Without automated triggering, the feedback loop is aspirational only and the `docs/lessons-learned/known-failure-patterns.md` document grows stale.

2. `AGENTS.md` is drifting into duplication territory, `applyTo` metadata in prompt files is untested (agents can miss instruction files), and the Lessons Learned document was last updated 30+ days ago with approximately 50% noise content (generic lint-rule advice that adds no new signal over what AGENTS.md already says).

After this work lands:

- A GitHub Actions cron workflow runs the `review-ai-sessions` prompt on a schedule, extracts session quality patterns, and files a PR or directly updates `known-failure-patterns.md` when new patterns are confirmed.
- `AGENTS.md` duplicate sections are consolidated.
- `known-failure-patterns.md` is pruned of generic advice that duplicates what AGENTS.md already enforces via CI, leaving only session-specific behavioral patterns.
- The VS Code extension has at minimum a `npm run lint` CI step to catch obvious extension-breaking changes.

The observable proof: running `.github/workflows/review-ai-sessions.yml` manually produces a finding summary artifact in `artifacts/ai-chat/` and updates `known-failure-patterns.md` if new patterns qualify.

## Progress

- [x] (2026-06-02) Read `AGENTS.md` fully to identify duplicate sections and sections that repeat what CI already enforces.
- [x] (2026-06-02) Read `docs/lessons-learned/known-failure-patterns.md` fully and identify which entries are generic CI-enforced lint rules (noise) versus session-specific behavioral patterns (signal).
- [x] (2026-06-02) Prune `known-failure-patterns.md` to remove entries that are exact duplicates of AGENTS.md rules or that describe problems fully prevented by existing CI (ruff, pyright, bandit).
- [x] (2026-06-02) Review `AGENTS.md` for literal duplicate sections. No identical section body remained, so this slice kept the current text and recorded the no-op review result instead of forcing a cosmetic rewrite.
- [x] (2026-06-02) Create `.github/workflows/review-ai-sessions.yml`: a `workflow_dispatch` and `schedule` (weekly cron) workflow that produces `artifacts/ai-chat/session-review-$(date +%Y%m%d).md`, uploads it, and opens a review PR branch when tracked outputs change.
- [x] (2026-06-02) Verify the `review-ai-sessions` prompt's `argument-hint` and `Known Seams` section are current: confirm the transcript path, the `ai_chat_observability` CLI module path, and the active plan references.
- [x] (2026-06-02) Add a VS Code extension lint step to `.github/workflows/ci.yml`: after the existing Python CI steps, add a job that runs `cd vscode/sattline-vscode && npm ci && npm run lint`.
- [x] (2026-06-02) Verify `vscode/sattline-vscode/package.json` has a `lint` script entry and `eslint` in `devDependencies`; generated `package-lock.json` so CI can use `npm ci`.
- [x] (2026-06-02) Write a focused CI validation seam: the workflow now runs the observability CLI plus a repo-owned markdown renderer so a manual run produces a review artifact instead of a silent no-op even before a Copilot CI runner exists.
- [x] (2026-06-02) Add a repo-owned updater at `scripts/update_ai_known_failure_patterns.py` so the workflow can update `docs/lessons-learned/known-failure-patterns.md` from AI chat findings before opening a PR.
- [x] (2026-06-02) Validate the workflow fallback end-to-end with `tests/test_ai_chat_observability.py`, touched-file Ruff and Pyright on the updater/renderer/findings seam, and `python scripts/run_actionlint.py`.

## Surprises & Discoveries

- Observation: the `review-ai-sessions` prompt was stale, not missing.
  Evidence: `src/sattlint/devtools/ai_chat_observability.py` and `scripts/bootstrap_ai_slice.py` already exist, but the prompt still described both seams as future work and still pointed at active plans 46-49 even though the active plan set has moved on.

- Observation: the current feedback-loop automation still leaves semantic search health as an uncovered gap.
  Evidence: the 2026-06-02 transcript review reported `semantic_grounding.status = unavailable` and `grounded_session_count = 0` in `artifacts/ai-chat/summary.json`, but this plan only automates the review loop and extension lint; it does not add a health check or fallback for missing semantic search tooling.

- Observation: `AGENTS.md` did not contain a literal duplicate section body after the current in-progress repo edits.
  Evidence: the requested review found overlap in themes, but no repeated section content that could be safely removed without turning this slice into a wording-only rewrite.

- Observation: the VS Code extension had no lockfile, so `npm ci` could not be added until the lint dependency was installed locally.
  Evidence: `vscode/sattline-vscode/` contained `package.json` but no `package-lock.json` before the eslint install and lint validation run.

## Decision Log

- Decision: use a `workflow_dispatch` plus `schedule` trigger rather than a PR-triggered workflow.
  Rationale: the review-ai-sessions prompt analyzes session transcripts, which are a workspace-local artifact (not a repository artifact). A PR trigger would run on every push but have no new transcripts to analyze unless a session just happened. A weekly cron run is the right cadence for a feedback loop over accumulated sessions.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: commit the session review output to a branch for PR review rather than pushing directly to main.
  Rationale: the session review may recommend updating `known-failure-patterns.md`. That update should be human-reviewable before it lands on the default branch, so automated updates go to a short-lived branch and the merge is a human decision.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: add VS Code extension lint to `ci.yml` rather than creating a separate extension workflow.
  Rationale: the review notes "VS Code extension has zero CI coverage." The minimal addressable gap is a lint check. Keeping it in `ci.yml` (alongside the Python CI) avoids a proliferation of workflow files for a single-step check. A full extension build and test suite is a larger project that belongs in the feature roadmap.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: prune `known-failure-patterns.md` rather than extending it.
  Rationale: the review states it is "50% noise" with generic lint-rule advice. Noise in a guidance document trains agents to ignore it. Removing the noise increases signal density and makes the document more useful at the point of use (when an agent loads it after a dead-end route).
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: ship a repo-owned workflow fallback instead of leaving `review-ai-sessions.yml` as a ceremonial TODO.
  Rationale: GitHub Actions still does not expose a stable Copilot agent runner for prompt files in this repo, but the existing observability CLI can still produce machine-readable findings today. Rendering those findings into a Markdown review artifact keeps the automation useful now while leaving a clear seam for future prompt-runner replacement.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

- Decision: keep semantic-grounding health out of plan 75 and give it a separate owner plan.
  Rationale: plan 75 is already about wiring the review loop and CI coverage. Search-tool health and fallback routing touch a different seam: the devtools observability summary plus agent routing guidance. Splitting that work prevents this plan from turning into a catch-all for every issue surfaced by transcript review.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This slice now has the missing CI wiring: the VS Code extension gets an explicit lint job in `ci.yml`, and the new `review-ai-sessions.yml` workflow can run on a schedule or by manual dispatch to emit a markdown review artifact under `artifacts/ai-chat/`.

The prompt and lessons-learned surfaces are cleaner and more current. The prompt now points at shipped seams instead of future ones, and `known-failure-patterns.md` is narrowed to session-behavior patterns that static checks will not catch. The workflow now runs a repo-owned updater before the commit/PR step, so qualifying findings can create a real diff in `docs/lessons-learned/known-failure-patterns.md` rather than only a report artifact. Validation for this slice passed through fixture-backed review artifact generation, focused AI chat observability tests, touched-file Ruff and Pyright on the updater/renderer/findings seam, and `actionlint`.

The remaining limitation is GitHub Actions platform support: until a prompt runner exists for `.github/prompts/*.prompt.md` and a transcript corpus is available to the runner, the workflow uses fixture-backed observability artifacts plus a markdown renderer plus updater as the durable fallback. A later full-suite rerun exposed an unrelated existing failure in `tests/test_analyzers_variables.py::test_graphics_format_tail_keywords_do_not_log_missing_variables`, so repo-wide pytest is not part of this slice's completion proof.

A second limitation remains intentionally deferred: the review loop can now detect when semantic search tooling was unavailable, but it still cannot heal that condition or steer agents to a cheaper fallback automatically. That follow-up now has its own active plan so the gap is tracked instead of getting lost in review output.

## Context and Orientation

**`review-ai-sessions` prompt** lives at `.github/prompts/review-ai-sessions.prompt.md`. It is a Copilot prompt file (using VS Code prompt file format). It expects to be run as a Copilot agent task, using `{{ VSCODE_TARGET_SESSION_LOG }}` or the transcript corpus path as its input. The prompt references:

- Transcripts at `<workspace-storage>/GitHub.copilot-chat/transcripts/*.jsonl`
- An observability CLI at `src/sattlint/devtools/ai_chat_observability.py` (not yet built — this is plan 46 work)
- A bootstrap script at `scripts/bootstrap_ai_slice.py` (plan 49 work — also not yet built)

The prompt is currently only invocable manually via the VS Code Copilot Chat `#review-ai-sessions` slash command. There is no CI or cron job that invokes it.

**`AGENTS.md`** is the primary agent instruction file. The review notes it is "drifting into duplication territory." Before editing, read it fully and identify: sections that appear more than once, rules that exactly duplicate CI enforcement (e.g., "run ruff" — already enforced in `lint.yml`), and rules that are stale because the tooling they describe has changed.

**`known-failure-patterns.md`** at `docs/lessons-learned/known-failure-patterns.md` contains AI session failure patterns. The entries are a mix of genuinely behavioral patterns (e.g., "Discovery Churn Before First Edit" — not catchable by CI) and generic tooling reminders (e.g., "Unused Imports Accumulation" — already fully caught by ruff in CI). The latter category is noise.

**VS Code extension** lives at `vscode/sattline-vscode/`. It has `package.json`, `extension.js`, and `README.md`. The existing `repo-audit.yml` or `ci.yml` runs `npm audit` on it but no lint or test step. A minimal `eslint` invocation will catch obvious syntax errors and undefined variables in `extension.js`.

**Coverage ratchet**: the review also notes the `--cov-fail-under=87.26` static floor with no automation to increment it. This is noted here for awareness, but the correct fix (automatic ratchet increment) is lower priority than the feedback loop and extension lint gaps in this plan. It is deferred to a future plan.

## Plan of Work

Start by reading `AGENTS.md` and `known-failure-patterns.md` in full. Mark sections for pruning or consolidation. Edit `known-failure-patterns.md` first since it is the simpler document — remove the "Unused Imports Accumulation", "Typing Imports Deprecated", and any other entries whose entire content is "run ruff" or "use built-in types" (these are already enforced by CI at every push; documenting them in a lessons-learned file adds no agent value). Keep entries that describe behavioral failure modes that CI cannot catch.

Then edit `AGENTS.md` to remove or merge duplicate sections. The safest approach is to read all section headers and bodies, identify the duplicate, and delete the shorter/less-specific version while preserving the more detailed one.

For the workflow: create `.github/workflows/review-ai-sessions.yml`. The workflow should trigger on `workflow_dispatch` (manual) and `schedule: cron: '0 9 * * 1'` (weekly Monday 09:00 UTC). The job should:

1. Check out the repo.
2. Set up the CI Python toolchain using the shared `setup-ci-tooling` action.
3. Create an output directory `artifacts/ai-chat`.
4. Invoke the Copilot agent task for the `review-ai-sessions` prompt (using the `gh copilot suggest` or the VS Code agent runner CLI if available in CI, otherwise document the limitation and leave a TODO for when the CLI exists).
5. If the review produces a `known-failure-patterns.md` diff, create a branch and open a PR.

Note: the Copilot agent CLI in CI is not yet generally available. The workflow should at minimum define the structure and trigger, document the expected behavior in comments, and add a placeholder step that prints the transcript directory path and counts available transcripts. This makes the workflow structurally correct and testable today, with the actual agent invocation step as a clearly-marked TODO.

For the VS Code extension lint: check `vscode/sattline-vscode/package.json` for an existing `lint` script. If missing, add `"lint": "eslint extension.js --no-eslintrc --env browser,node --rule 'no-undef: error'"` as a minimal baseline. Add `eslint` to `devDependencies` if not present. Then add a CI job to `.github/workflows/ci.yml` that runs `npm ci && npm run lint` in `vscode/sattline-vscode/`.

## Concrete Steps

Run all commands from the repository root.

Read `AGENTS.md` and identify the duplicate:

    wc -l AGENTS.md  # know the size before editing
    grep -n "^## \|^### " AGENTS.md  # list all section headers

Check the extension's current `package.json`:

    cat vscode/sattline-vscode/package.json

Check whether `eslint` is already in the devDependencies:

    cd vscode/sattline-vscode && npm ls eslint 2>/dev/null || echo "not installed"

After all edits, run the full Python test suite to confirm no regressions from `AGENTS.md` changes:

    bash scripts/run_repo_python.sh -m pytest --no-cov -x -q --tb=short

Validate the new workflow file with actionlint:

    python scripts/run_actionlint.py

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. `known-failure-patterns.md` contains only behavioral session patterns (not generic CI-enforced lint rules). A human reading the file can confirm it has no entry that says "run ruff" or "use built-in types."
2. `AGENTS.md` has no section that appears more than once with identical content.
3. `.github/workflows/review-ai-sessions.yml` exists, triggers on `workflow_dispatch` and weekly cron, and is valid per `actionlint`.
4. `vscode/sattline-vscode/package.json` has a `lint` script and `eslint` in `devDependencies`.
5. `.github/workflows/ci.yml` has a VS Code extension lint job that runs `npm ci && npm run lint`.
6. `pytest --no-cov -x -q` passes.

## Idempotence and Recovery

All edits to `AGENTS.md` and `known-failure-patterns.md` are text removals of specific sections. They can be recovered via git if a section that should have been kept was removed. The new workflow file and extension `package.json` changes are additive. Rolling back means deleting the added files and reverting the `package.json` change.

## Artifacts and Notes

The review's highest-leverage single recommendation:

    "Single highest-leverage change: Add a cron workflow that runs review-ai-sessions,
    extracts patterns, and files a PR updating known-failure-patterns.md. Without
    automated triggering, the loop stays aspirational."

The five noise entries in `known-failure-patterns.md` that should be pruned (all are CI-enforced):

- "Unused Imports Accumulation" — caught by ruff in `lint.yml`
- "Typing Imports Deprecated" — caught by ruff in `lint.yml`
- Any other entries whose complete recommendation is "add CI check" when that CI check already exists

The signal entries that must be kept:

- "Discovery Churn Before First Edit" — behavioral, not CI-catchable
- "Wrong Transcript Or Log Seam" — behavioral, not CI-catchable
- "Low-Signal Assistant Output" — behavioral, not CI-catchable
- "Terminal Script Execution — Heredoc Failure" — tool-specific, not CI-catchable

## Interfaces and Dependencies

The new `review-ai-sessions.yml` workflow depends on:

- `.github/actions/setup-ci-tooling` — existing shared action, already used by other workflows
- The `review-ai-sessions.prompt.md` file — already present
- Copilot agent CLI availability in GitHub Actions — not yet available; the step is marked TODO

The VS Code extension lint step depends on:

- Node.js being available in CI — already present (the `npm audit` step requires it)
- `eslint` being added to `package.json` devDependencies
