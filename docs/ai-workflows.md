# AI Workflows

This repository supports four explicit AI working roles: planner, executor, test, and reviewer.
`Planner` is a thin planning alias over `SattLint Orchestrator`, and executor work stays split across surface-specific agents rather than one generic executor.
Each role works from a scoped contract and hands off through machine-readable artifacts.

## Branch Strategy

- `main`: protected release branch.
- `develop/integration`: optional integration branch for multi-slice staging.
- `ai/task-<id>`: executor implementation branch.
- `test/task-<id>`: test-agent validation branch.
- `review/task-<id>`: reviewer or merge-prep branch.

## Worktree Strategy

Preferred flow for parallel work:

1. Use `Planner` or `SattLint Orchestrator` to choose the owning surface, claims, and first validation command.
2. `git worktree add ../SattLint-ai-<id> -b ai/task-<id> main`
3. Implement the executor slice and emit `.ai/tasks/<id>.json`.
4. Handoff with `.ai/handoffs/<id>.json`.
5. Create the test or review worktree from the handoff branch when isolation is needed.

## Agent Set

- `Planner`: scopes broad requests, keeps work in one slice when possible, and escalates to multi-stream orchestration only when needed.
- Executor role: `CLI App Menu`, `Documentation Generation`, `Parser Analysis`, `Repo Audit`, and `Workspace LSP`.
- `Test Agent`: validates executor handoffs, adds focused regression coverage, and updates handoff validation state.
- `Reviewer Agent`: checks the diff, handoff, and finish-gate evidence before merge.
- `Repo Verify`: optional repo-wide gate runner after slice-level validation; not a substitute for the slice test or review roles.

## Planner -> Executor -> Test -> Reviewer Pipeline

### Planner

- Reads `.github/coordination/current-work.md` first.
- Chooses the owning surface, file claims, and first validation command.
- Keeps work in one scoped slice when possible.
- Escalates to `SattLint Orchestrator` only for parallel lanes or shared-file coordination.

### Executor

- Claims files in `.github/coordination/current-work.md`.
- Works from one task contract in `.ai/tasks/`.
- Runs focused validation immediately after the first substantive edit.
- Emits a handoff with changed files, known risks, and required tests.

### Test Agent

- Reads the executor handoff.
- Adds regression or edge-case coverage.
- Verifies coverage and finish-gate evidence.
- Updates the handoff validation state.

### Reviewer Agent

- Reviews the diff and handoff contract.
- Checks architectural compliance, security notes, and unresolved risks.
- Approves only when the finish gate and handoff are both green.

## Handoff Contracts

- `.ai/tasks/task-contract.schema.json` defines task scope, branch, worktree, files, and validations.
- `.ai/handoffs/handoff.schema.json` defines the executor to test to reviewer handoff artifact.
- `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` are the canonical starter shapes for new slice artifacts.
- Keep one task file and one handoff file per scoped unit of work.

## Debt-Driven Entry Points

- Use the `debt-id-routing` skill when a request starts from `docs/exec-plans/tech-debt-tracker.md` instead of a file path or failing test.
- `Plan Debt Slice` wraps `Planner` for debt ID to owner surface, claims, first validation, finish gate, and task or handoff path selection.
- `Implement Debt Slice` wraps `SattLint Orchestrator`, keeps one slice when possible, and routes execution to the closest specialist agent when ownership is clear.
- `Validate Slice` wraps `Test Agent`, and `Review Slice` wraps `Reviewer Agent`, so the debt workflow has user-facing entry points for the full planner to executor to test to reviewer path.
- The debt prompts use `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json` as the consistent artifact shapes to target.
- Keep blocker work explicit. Do not silently absorb a listed blocker into the same slice unless the user asked for that broader scope.

## Required Handoff Fields

- task ID
- branch
- commit
- files changed
- summary
- known risks
- required tests
- validation status

## Context Optimization Workflow

Use the VS Code chat participant from `wanderleyferreiradealbuquerque.context-optimizer` before expanding AI control files.

- `@context-optimizer /audit` to inventory current context cost.
- `@context-optimizer /compare` to preview reductions.
- `@context-optimizer /optimize` to propose extractions or deduplication.
- `@context-optimizer /init` only for missing starter files.

## Merge Thresholds

Merge only when all of the following are true:

- file claims are resolved
- handoff validation is green
- pre-commit and finish gate passed
- reviewer found no unresolved high-risk issue
- context health still passes after the change
