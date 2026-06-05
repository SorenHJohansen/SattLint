# T-Wave-10 Semantic Grounding Health and Fallback Routing

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

The AI chat observability loop can already show when transcript review sessions drift into excessive discovery, but it currently reports semantic grounding as `unavailable` without any repo-owned fix path. After this change lands, a chat review or devtools health run will make it obvious whether semantic search tooling is installed and usable, and agents will have an explicit fallback path when it is not. The user-visible result is simple: review artifacts stop reporting an unexplained search-tool outage, and the agent guidance points to a deterministic next step instead of a vague “Semble was unavailable” note.

The observable proof is that a local run of the chat observability CLI writes a `summary.json` that distinguishes “tool missing”, “tool healthy”, and “fallback in effect”, and the review prompt can cite an active plan that owns the gap instead of flagging it as uncovered.

## Progress

- [x] (2026-06-02 13:46Z) Confirm the gap from the latest transcript review: `artifacts/ai-chat/summary.json` reported `semantic_grounding.status = unavailable` and no active plan owned the fix.
- [x] (2026-06-02 13:48Z) Tighten `.github/prompts/review-ai-sessions.prompt.md` so future reviews treat semantic-grounding health as first-class evidence.
- [ ] Add a repo-owned semantic-grounding health check to the chat observability surface so the report can say whether search tooling is installed, misconfigured, or intentionally bypassed.
- [ ] Add a fallback-routing rule to agent guidance so missing semantic search tooling leads to a narrow literal-search fallback instead of repeated broad discovery.
- [ ] Add focused regression tests for the new semantic-grounding health states and fallback wording.
- [ ] Validate the observability CLI, the prompt guidance, and the touched tests.

## Surprises & Discoveries

- Observation: the repo already records semantic-grounding status in `artifacts/ai-chat/summary.json`, but only as a passive status field.
  Evidence: the latest review artifact included `semantic_grounding.status = unavailable` and `grounded_session_count = 0`, yet there was no active plan or guidance seam that translated that into a concrete repair path.

## Decision Log

- Decision: solve this as a devtools-and-guidance slice instead of expanding plan 75.
  Rationale: the missing owner is not the review workflow itself. The real work belongs to the observability summary and the routing guidance that decides what to do when semantic search is absent.
  Date/Author: 2026-06-02 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This plan starts with the gap identified but not yet repaired. Update this section once the health check and fallback routing land.

## Context and Orientation

`src/sattlint/devtools/ai_chat_observability.py` is the repo-owned command that reads Copilot transcript JSONL files and writes `artifacts/ai-chat/status.json`, `summary.json`, `sessions.json`, and `findings.json`. The `summary.json` file already contains a `semantic_grounding` block, but the current behavior collapses all missing-tool states into `unavailable` with a generic explanation.

`.github/prompts/review-ai-sessions.prompt.md` is the user-facing review prompt that interprets those artifacts. Before this plan, it focused on `findings.json` and the transcript corpus, not on the semantic-grounding block in `summary.json`, so reviewers could spot the gap but not route it consistently.

The likely implementation surface is split between the observability helpers under `src/sattlint/devtools/` and the guidance text under `.github/`. Keep the work narrow. Do not redesign transcript parsing or review output formatting beyond what is needed to make semantic-grounding health actionable.

In this repository, “semantic grounding” means using the preferred semantic code-search tool to connect a user request to the controlling source files before broad exploration begins. When that tool is unavailable, the repo still needs a deterministic fallback, usually a narrow owner-seam search using exact text or the existing observability artifacts.

## Plan of Work

Start in `src/sattlint/devtools/ai_chat_observability.py` and the nearest helper modules that populate the `semantic_grounding` section of `summary.json`. Make the health states explicit. At minimum, distinguish between “dependency missing”, “tool invocation failed”, and “fallback required”. If the current implementation hides those details inside one generic `unavailable` message, split the message generation into a helper that produces both a stable status string and a concise operator-facing explanation.

Once the observability surface can describe the failure mode precisely, update `.github/prompts/review-ai-sessions.prompt.md` so the review always reads `summary.json` and reports search-tool outages as a dedicated actionable finding. The prompt should tell the reviewer to cite this plan as the active owner until the implementation lands.

Finally, update the closest guidance seam that agents actually load during implementation or review work so a missing semantic-search tool does not trigger repeated broad discovery. Keep that change terse. The right behavior is “fail fast to a narrow literal-search fallback and continue”, not “keep retrying semantic tooling”.

## Concrete Steps

Run all commands from the repository root.

Read the current semantic-grounding code path and tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ai_chat_observability.py -x -q --tb=short

Refresh the fixture artifact to see the semantic-grounding block shape before editing:

    bash scripts/run_repo_python.sh -m sattlint.devtools.ai_chat_observability \
      --transcripts-dir tests/fixtures/ai_chat/sample_workspace/GitHub.copilot-chat/transcripts \
      --output-dir artifacts/ai-chat-fixture

After editing, rerun the focused test module and the fixture command. The expected outcome is a `summary.json` whose `semantic_grounding` section contains a stable status plus an explanation that names the exact failure mode or fallback path.

## Validation and Acceptance

Acceptance is met when the following are all true:

1. `artifacts/ai-chat/summary.json` distinguishes the semantic-grounding failure mode in plain language instead of only saying `unavailable` with no actionable next step.
2. `.github/prompts/review-ai-sessions.prompt.md` instructs reviewers to inspect the semantic-grounding block and to cite this plan while the implementation is in progress.
3. Focused tests for the observability CLI pass after the new status handling is added.
4. A human reviewer can read the updated artifact and know whether to install tooling, fix invocation wiring, or use the repo’s fallback search path.

## Idempotence and Recovery

This work is additive and read-mostly. Re-running the observability CLI should only refresh `artifacts/ai-chat/*` and should never modify source files outside the intended edits. If a semantic-grounding status split turns out to be too fine-grained, collapse the wording back into fewer stable states without removing the explanation field.

## Artifacts and Notes

The motivating evidence from the latest review was:

    semantic_grounding.status = "unavailable"
    grounded_session_count = 0
    explanation = "Semble was unavailable for every session that could have been grounded semantically."

That output proves the gap is real, but it does not yet tell the reader what to do next. This plan exists to close that loop.

## Interfaces and Dependencies

Use the existing observability command at `src/sattlint/devtools/ai_chat_observability.py` and its helpers. Do not add network dependencies or new external services. If semantic-search health depends on an optional local package or executable, detect it through the current Python environment and report the result through the existing artifact schema rather than inventing a parallel reporting path.
