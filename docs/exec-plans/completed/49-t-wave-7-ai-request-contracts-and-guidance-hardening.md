# T-Wave-7 AI Request Contracts and Guidance Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan reduces ambiguous AI requests by turning common request shapes into explicit contracts and by tightening the repo's top-level routing guidance. Today, the transcript corpus shows repeated bare prompts such as `Implement this plan 37` and broad review prompts that trigger 26 to 34 discovery steps before first action. The repository already has `scripts/bootstrap_ai_slice.py`, `.ai/tasks/`, `.ai/handoffs/`, and strong workflow docs, but those surfaces are not yet the default answer to ambiguous requests. After this change lands, the repo will have a request-contract builder built on the existing bootstrap seam, and the top-level guidance will direct chat-review work to transcript JSONL files instead of letting agents rediscover that rule.

The observable proof is straightforward. Running the new request-contract flow for an implement-plan request must create a task contract or prompt payload that names the plan file, the requested files, the validation command, and the expected outcome. Running the same flow for a review request must create a contract that points at the controlling artifact or transcript corpus instead of a broad repo scan.

## Progress

- [x] (2026-05-15) Create the ExecPlan and capture the baseline evidence: 7 `Implement this plan N` sessions in the current transcript corpus, with several taking 26 to 34 discovery steps before first action, plus review sessions that also spent 29 to 34 discovery steps before action.
- [x] (2026-05-15) Extend `scripts/bootstrap_ai_slice.py` so common request kinds can be turned into explicit machine-readable request contracts and prompt text.
- [x] (2026-05-15) Add a contract path for `implement-plan`, `review-artifact`, and `chat-review` requests that points the agent at the narrowest controlling artifact first.
- [x] (2026-05-15) Add the missing transcript-path rule to `AGENTS.md` and align the nearby workflow docs with the new contract flow.
- [x] (2026-05-15) Embed the most-read instruction content directly in the relevant specialist `.agent.md` files so agents do not need redundant `read_file` calls at session start.
- [x] (2026-05-15) Add focused tests for the new bootstrap modes and the generated contract payloads.

## Surprises & Discoveries

Observation: the repository already has the right bootstrap seam.
Evidence: `scripts/bootstrap_ai_slice.py` already knows how to create `.ai/tasks/*.json` and `.ai/handoffs/*.json` from a scoped task id, files, validation command, and stage.

Observation: the missing piece is not a lack of structure, but a failure to route ambiguous requests through that structure.
Evidence: the transcript review found multiple sessions prompted only with `Implement this plan N` and broad review requests that still spent 26 to 34 discovery steps before the first edit or action.

Observation: one documented transcript rule is still missing from the top-level guide.
Evidence: `docs/lessons-learned/known-failure-patterns.md` says chat review should start from `GitHub.copilot-chat/transcripts/*.jsonl` and recommends adding that rule to `AGENTS.md`, but `AGENTS.md` does not currently mention the transcript path.

Observation: the specialist agent files do not expose a separate `system` frontmatter field.
Evidence: the current `.github/agents/*.agent.md` files rely on frontmatter plus markdown body content, so the compact invariant summaries had to be embedded in the body section that already renders at session start.

## Decision Log

Decision: extend the existing bootstrap flow instead of creating a second independent contract generator.
Rationale: `scripts/bootstrap_ai_slice.py` already owns task-id validation, branch defaults, template loading, and task-contract output. Reusing it keeps request bootstrapping in one place.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: treat `implement-plan`, `review-artifact`, and `chat-review` as first-class request kinds.
Rationale: those were the most expensive request categories in the transcript review, and each has a predictable controlling artifact that can be expressed in a contract.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: update `AGENTS.md` at the same time as the bootstrap flow.
Rationale: the repository already knows the transcript-path rule and review-task anti-patterns. The top-level guide should stop making agents rediscover them in each session.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: emit the request contract and prompt payload from the bootstrap CLI without introducing a second committed schema.
Rationale: the existing task and handoff schemas stay stable, while the bootstrap command can still produce explicit request-kind metadata, prompt text, and seeded acceptance criteria for novice-facing flows.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: embed the most-read instruction content directly in specialist `.agent.md` system prompts.
Rationale: transcript corpus analysis found that 5 of 18 sessions each read the same 3 to 6 instruction files (sattline-invariants, python-tests, validation-routing SKILL, codegraph-routing SKILL) in their first 10 tool calls before doing any useful work. The agent files have a `system` field that renders at session start without a tool call. Embedding a compact summary of each specialist agent's key invariants there eliminates those redundant reads. The full instruction files remain the authoritative source; the agent body holds a stable summary that the executor reads before the source of truth has loaded.
Date/Author: 2026-05-15 / Copilot (Claude Sonnet 4.6)

## Outcomes & Retrospective

The bootstrap seam now accepts `--from-request-kind implement-plan|review-artifact|chat-review` plus the required path flags, resolves chat-review requests to transcript JSONL directories, seeds request-specific acceptance criteria, and prints a paste-ready prompt payload alongside the normal task and handoff JSON paths. `AGENTS.md`, `docs/ai-workflows.md`, and the relevant specialist `.agent.md` files now reinforce the same routing rules so future sessions do not need to rediscover them.

## Context and Orientation

The main bootstrap seam is `scripts/bootstrap_ai_slice.py`. It already validates task ids, stages, worktree defaults, and task and handoff template paths. The machine-readable task templates live in `.ai/tasks/task-contract.example.json` and `.ai/handoffs/handoff.example.json`. Workflow policy lives in `docs/ai-workflows.md`, while top-level AI routing rules live in `AGENTS.md`.

In this repository, a "request contract" means a machine-readable or generated payload that tells an agent exactly what artifact to start from, what files are in scope, what validation command to run first, and what success looks like. This plan must make that contract explicit for the request kinds that caused the most drift in the transcript review.

The first focused tests should live next to the bootstrap script's existing test coverage or in a new file such as `tests/test_bootstrap_ai_slice.py` if one does not exist yet. Keep the implementation additive: ambiguous user prompts should still be possible, but the repo should offer a better default path.

## Plan of Work

Start by extending `scripts/bootstrap_ai_slice.py` so it can generate contracts from explicit request kinds. For `implement-plan`, accept a required `--plan-file` path and store it in the generated task contract or companion prompt output. For `review-artifact`, accept a required `--artifact-path` and make that artifact the controlling entrypoint. For `chat-review`, accept a transcript root or workspace-storage path and default the controlling seam to `GitHub.copilot-chat/transcripts/` rather than `debug-logs/`.

Then make the output useful. The bootstrap flow should still emit the normal task and handoff JSON when that makes sense, but it should also be able to emit a short prompt payload or Markdown snippet that a human can paste directly into chat. That output must include the starting artifact, files in scope, first validation command, and success criteria. Keep the prompt text short and machine-friendly rather than prose-heavy.

After the bootstrap path works, update `AGENTS.md` and `docs/ai-workflows.md` so the repo guidance matches it. Add the missing transcript-path rule to `AGENTS.md`, and document that chat-review and artifact-review requests should start from the named artifact rather than broad repo exploration. If the bootstrap script introduces new flags, document them where a novice will find them.

Finish by embedding a compact instruction summary in each relevant specialist `.agent.md` file. The target files are `.github/agents/parser-analysis.agent.md`, `.github/agents/workspace-lsp.agent.md`, `.github/agents/cli-app-menu.agent.md`, `.github/agents/documentation-generation.agent.md`, and `.github/agents/test-agent.agent.md`. For each file, review which instruction files its sessions most frequently read in the first 10 tool calls (as reported by the plan 46 findings output once that exists, or from the current transcript corpus), then embed a compact bullet list of those invariants in the agent's `system` field. Do not duplicate every word from the source; embed only the rules that agents have repeatedly re-read at session start. The authoritative source remains the instruction file; the agent body entry is a session-start summary that prevents the redundant reads.

## Concrete Steps

Run all commands from the repository root.

Start with focused bootstrap tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_bootstrap_ai_slice.py -x -q --tb=short

Once the new modes exist, exercise an implement-plan contract:

    bash scripts/run_repo_python.sh scripts/bootstrap_ai_slice.py --task-id ai-chat-observability --stage executor --from-request-kind implement-plan --plan-file docs/exec-plans/completed/46-t-wave-7-ai-chat-observability-and-feedback-loop.md --file src/sattlint/devtools/ai_chat_observability.py --validation "bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ai_chat_observability.py -x -q --tb=short"

Exercise an artifact-review contract:

    bash scripts/run_repo_python.sh scripts/bootstrap_ai_slice.py --task-id audit-summary-review --stage review --from-request-kind review-artifact --artifact-path artifacts/analysis/summary.json --validation "bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_pipeline_run_recommendations.py -x -q --tb=short"

Exercise a chat-review contract that targets transcripts explicitly:

    bash scripts/run_repo_python.sh scripts/bootstrap_ai_slice.py --task-id chat-review-current --stage executor --from-request-kind chat-review --artifact-path <path-to-workspace-storage>/GitHub.copilot-chat/transcripts --validation "bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ai_chat_observability.py -x -q --tb=short"

Finish with touched-file lint and type checks:

    bash scripts/run_repo_python.sh -m ruff check scripts/bootstrap_ai_slice.py AGENTS.md docs/ai-workflows.md tests/test_bootstrap_ai_slice.py
    bash scripts/run_repo_python.sh -m pyright scripts/bootstrap_ai_slice.py tests/test_bootstrap_ai_slice.py

## Validation and Acceptance

Acceptance requires more than new flags. The bootstrap flow must produce a contract or prompt payload that a novice can use without re-deriving the starting seam. The `implement-plan` flow must point at the plan file. The `review-artifact` flow must point at the named artifact. The `chat-review` flow must point at transcripts rather than debug logs.

The generated output must include the controlling artifact, requested files, first validation command, and success criteria. A novice should be able to run the bootstrap command and start a chat from the generated payload without guessing what to load first.

## Idempotence and Recovery

This flow must stay safe to re-run. If a task id already exists, the script should fail cleanly or require an explicit overwrite flag. The new request-kind modes should remain additive and should not break existing bootstrap usage. If a request-kind input is incomplete, the script should fail with a typed error that explains which artifact path or plan file is missing.

## Artifacts and Notes

Baseline evidence from the transcript review:

    implement-plan sessions in corpus = 7
    common discovery-before-action range for bare implement-plan prompts = 26 to 34
    common discovery-before-action range for broad review prompts = 29 to 34

The current repo already has the right raw materials:

    scripts/bootstrap_ai_slice.py
    .ai/tasks/task-contract.example.json
    .ai/handoffs/handoff.example.json
    docs/ai-workflows.md

This plan turns those pieces into the default answer to ambiguous requests.

## Interfaces and Dependencies

The main interface is `scripts/bootstrap_ai_slice.py`. The implementation should add explicit request-kind inputs such as `--from-request-kind implement-plan`, `--from-request-kind review-artifact`, and `--from-request-kind chat-review`, plus the required path flags that make each contract unambiguous.

The guidance surfaces that must stay aligned are `AGENTS.md` and `docs/ai-workflows.md`. The implementation depends on the existing task and handoff templates in `.ai/tasks/` and `.ai/handoffs/`, and it should keep those schemas stable unless a schema change is essential and validated in the same slice.
