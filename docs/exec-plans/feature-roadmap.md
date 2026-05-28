# Feature Roadmap

Planned GUI capabilities for SattLint. Non-GUI feature work now lives in exec plans instead of this roadmap.

For actual code quality and architecture debt, see `docs/exec-plans/tech-debt-tracker.md`.

Last updated: 2026-05-13

## Quick Reference

| Check | Command |
|-------|---------|
| Parser | `sattlint syntax-check <file>` |
| All tests | `pytest tests/` |
| Quick audit | `sattlint-repo-audit --profile quick --output-dir artifacts/audit` |
| Type check | `mypy src/` |
| Lint | `ruff check src/` |
| Format | `ruff format src/` |

---

## Priority Model

- P1: high value, should be scheduled in the next planning cycle
- P2: valuable but can wait for a later cycle or external demand

## Non-GUI ExecPlan Routing

Non-GUI feature work is now tracked in exec plans instead of this roadmap.

Active non-GUI ExecPlans:

- `docs/exec-plans/completed/28-c-wave-1-semantic-core-follow-ons.md`
- `docs/exec-plans/completed/29-c-wave-2-analyzer-roadmap-follow-ons.md`
- `docs/exec-plans/completed/30-c-wave-backlog-s88-scope-lock.md`
- `docs/exec-plans/completed/31-c-wave-3-dependency-resource-follow-ons.md`
- `docs/exec-plans/completed/32-d-wave-2-devtools-follow-ons.md`
- `docs/exec-plans/active/33-d-wave-backlog-promotion-decision.md`

Completed or already shipped non-GUI coverage:

- `docs/exec-plans/completed/20-d-038-sfc-scan-cycle-simulation.md`
- `docs/exec-plans/completed/21-c-022-state-inference.md`
- `docs/exec-plans/completed/22-d-041-impact-analysis-tool.md`
- `C-021` Safety Path Depth is already live in `src/sattlint/analyzers/safety_paths.py` with focused coverage in `tests/_analyzers_suites_part5.py`, so it no longer belongs in planned feature tracking.

---

## Feature Implementation Template

Use this template when adding new features.

### Feature ID

**Feature ID:** F-XXX

**Status:** Open

**Priority:** P1 or P2

**Owner:** Owner team

**Target Window:** Quarter or "Backlog"

**Wave:** Program wave

**Purpose:** One-paragraph description.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Component A | `path/to/file.py` | What it does |

**Input:** Input format/description

**Output:** Output format/description

**Reuses:**

- Existing component (path)

**Validation:** Command to validate

**See also:** Related features

---

## Common Reusable Components

| Component | Path | Purpose |
|-----------|------|---------|
| Workspace snapshot | `core/semantic.py:load_workspace_snapshot()` | Load workspace |
| Parser | `engine.py:parse_source_file()` | Parse file |
| Expression evaluator | `analyzers/dataflow.py:_evaluate_expression()` | Evaluate |
| Module resolver | `resolution/common.py:resolve_*()` | Resolve refs |
| AST models | `sattline_parser/models/ast_model.py` | Data structures |
| Grammar | `sattline_parser/grammar/sattline.lark` | Parser grammar |
