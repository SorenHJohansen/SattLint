# T-Wave-7 CodeGraph Health and Fallback Guards

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes CodeGraph usage explicit, measurable, and cheap to validate before an agent starts exploring code. Today, the repo guidance in `AGENTS.md` and `.github/skills/codegraph-routing/SKILL.md` says to use CodeGraph first when `.codegraph/` exists, but the transcript corpus shows repeated in-session failures from `callers`, `impact`, and `callees` checks. After this change lands, the repository will have one health command that tells an agent whether CodeGraph is healthy, degraded, or unavailable, and the guidance will tell agents to run that check once and fall back immediately when the result is degraded.

The observable proof is straightforward. Running the health check in a healthy repo must report `healthy` and show why. Running it in a degraded fixture or with broken MCP or CLI prerequisites must report `degraded` or `fallback_to_rg` and explain the fallback path in plain language.

## Progress

- [x] (2026-05-15) Create the ExecPlan and capture the baseline evidence: the transcript review counted 8 failed CodeGraph MCP calls across the workspace corpus, and the existing `AI: CodeGraph Health` task in `.vscode/tasks.json` only runs `codegraph status` without connecting that result to AI routing.
- [ ] Extend the repo health surface so one command can report CodeGraph health, index presence, MCP wiring, and fallback guidance.
- [ ] Add fixture-driven tests for healthy, degraded, and missing-CodeGraph scenarios.
- [ ] Update the CodeGraph task and top-level guidance so the health check becomes the required first step before CodeGraph exploration.
- [ ] Update AGENTS and the CodeGraph routing skill so repeated failed MCP calls become a documented anti-pattern rather than a silent fallback.

## Surprises & Discoveries

Observation: the repository already has a CodeGraph health task.
Evidence: `.vscode/tasks.json` defines `AI: CodeGraph Health` as `codegraph status ${workspaceFolder}`.

Observation: the task exists, but agents still attempt failing MCP calls several times in one session.
Evidence: the transcript review counted 4 failed `mcp_codegraph_codegraph_callers` calls, 3 failed `mcp_codegraph_codegraph_impact` calls, and 1 failed `mcp_codegraph_codegraph_callees` call.

Observation: guidance says to fall back when CodeGraph is unavailable, but there is no cheap repo-owned preflight step.
Evidence: `.github/skills/codegraph-routing/SKILL.md` documents fallback behavior, while representative transcript `49a27f5b-985d-4ebe-a641-47c65482866d` still tried four failing `callers` requests before switching to `grep_search`.

## Decision Log

Decision: build on the existing context-health seam rather than inventing a separate one-off script.
Rationale: `scripts/context_health.py --check` is already called out in `AGENTS.md` as a repo health command. Extending that seam keeps AI preflight behavior centralized.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: report explicit fallback guidance in the health output.
Rationale: agents should not have to infer what to do next from a failed status check. The health output should say whether to use CodeGraph, rebuild the index, or fall back to `rg` and targeted reads.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: treat MCP readiness and index readiness as separate checks.
Rationale: `.codegraph/` can exist while the CLI, MCP wiring, or current editor session is still degraded. The health output must distinguish those cases.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At creation time, no code has landed yet. The current outcome is a focused health-plan slice that addresses the repeated CodeGraph false starts visible in recent transcripts.

## Context and Orientation

CodeGraph in this repository has three moving parts. The first is the checked-in index configuration under `.codegraph/`. The second is workspace MCP wiring, which the repo guidance says lives in `.vscode/mcp.json`. The third is the local `codegraph` CLI itself, which powers the existing `AI: CodeGraph Health`, `AI: Sync CodeGraph Index`, and `AI: Rebuild CodeGraph Index` tasks in `.vscode/tasks.json`.

The current health-check seam is `scripts/context_health.py`. It already validates AI-control artifacts and repo context contracts. This plan should extend that command, or a nearby helper it calls, so CodeGraph readiness is visible in one predictable report.

The guidance surfaces that need updating are `AGENTS.md`, `.github/skills/codegraph-routing/SKILL.md`, and any nearby context-health docs or tasks. The first tests should live in a focused file such as `tests/test_context_health.py` or `tests/devtools/test_context_health_codegraph.py` using synthetic fixture directories rather than the real local MCP session.

## Plan of Work

Start by extending the context-health report builder so it can inspect CodeGraph state. At minimum, check whether `.codegraph/` exists, whether `.vscode/mcp.json` exists and mentions CodeGraph, whether the `codegraph` CLI is available on `PATH`, and whether `codegraph status <repo-root>` succeeds. Represent these as explicit fields such as `index_present`, `mcp_config_present`, `cli_available`, `status_command_ok`, and `recommended_route`.

Then make the output actionable. If all checks pass, the report should say `healthy` and recommend CodeGraph-first exploration. If the CLI or MCP checks fail, the report should say `degraded` and recommend `grep_search`, `file_search`, and targeted reads instead. If the index is stale but the CLI works, the report should recommend the existing rebuild or sync tasks instead of repeated failed symbol queries.

After the health report is stable, update `.vscode/tasks.json` so the CodeGraph health task uses the repo-owned health surface or prints the repo-owned summary directly. Update `AGENTS.md` and `.github/skills/codegraph-routing/SKILL.md` to say that agents should run the health check once, then either use CodeGraph or fall back immediately. The goal is to turn repeated failed MCP calls into a policy violation rather than a common pattern.

## Concrete Steps

Run all commands from the repository root.

Start with focused tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_context_health.py -x -q --tb=short

Run the health command directly once the CodeGraph checks exist:

    bash scripts/run_repo_python.sh scripts/context_health.py --check

If the command supports a dedicated CodeGraph-only mode, run that narrower path too:

    bash scripts/run_repo_python.sh scripts/context_health.py --check --section codegraph

If fixture-based testing needs a temporary repo root or fixture config path, exercise that mode explicitly:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_context_health.py -k codegraph -x -q --tb=short

Finish with touched-file lint and type checks:

    bash scripts/run_repo_python.sh -m ruff check scripts/context_health.py AGENTS.md .github/skills/codegraph-routing/SKILL.md .vscode/tasks.json tests/test_context_health.py
    bash scripts/run_repo_python.sh -m pyright scripts/context_health.py tests/test_context_health.py

## Validation and Acceptance

Acceptance requires a health output that changes behavior. In a healthy configuration, the command must report CodeGraph readiness and recommend CodeGraph-first exploration. In a degraded fixture, the command must report a non-healthy status and recommend the plain-text fallback path. The task and guidance surfaces must match that behavior so a novice can run one command and know which exploration route is safe.

This plan is successful when an agent no longer needs to guess whether CodeGraph is healthy and no longer retries failing MCP calls several times before falling back.

## Idempotence and Recovery

The health check must be read-only. Re-running it should be safe. It may recommend index rebuilds or sync operations, but it must not trigger them automatically. If one prerequisite is missing, the report should still emit a useful degraded result rather than aborting without guidance.

## Artifacts and Notes

Baseline evidence from the transcript review:

    failed CodeGraph callers = 4
    failed CodeGraph impact = 3
    failed CodeGraph callees = 1

Representative transcript evidence:

    49a27f5b-985d-4ebe-a641-47c65482866d says "The CodeGraph caller tool is not wired correctly in this session"

The existing fallback rule already lives in `.github/skills/codegraph-routing/SKILL.md`. This plan makes that fallback cheap and automatic to choose.

## Interfaces and Dependencies

The implementation surface is `scripts/context_health.py`, `.vscode/tasks.json`, `AGENTS.md`, and `.github/skills/codegraph-routing/SKILL.md`. The health report should expose a structured CodeGraph section with fields for index presence, MCP wiring, CLI availability, status-command success, and recommended route.

The implementation depends on `.codegraph/`, `.vscode/mcp.json`, and the local `codegraph` CLI when available. It must still produce a meaningful degraded result when one or more of those are missing.
