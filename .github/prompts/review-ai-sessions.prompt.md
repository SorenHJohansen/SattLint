---
description: "Review recent SattLint AI chat sessions for failure patterns, tool drift, and self-improvement opportunities"
name: "Review AI Sessions"
argument-hint: "GitHub.copilot-chat workspace-storage path, transcripts directory path, or 'latest-fixture'"
---

# Review AI Sessions

Analyse recent AI chat transcripts to identify failure patterns, excessive discovery steps, and missing tooling. Update `docs/lessons-learned/known-failure-patterns.md` if new patterns emerge.

## Starting Artifact

The transcript corpus is at `<workspace-storage>/GitHub.copilot-chat/transcripts/*.jsonl`. Each file is one session in newline-delimited JSON. Start with the repo-owned observability command:

    bash scripts/run_repo_python.sh -m sattlint.devtools.ai_chat_observability \
      --transcripts-dir <workspace-storage>/GitHub.copilot-chat/transcripts \
      --output-dir artifacts/ai-chat

If that command is unavailable in the current environment, read the JSONL files directly. Each line is a JSON object. Key fields: `type` (session.start | user.message | assistant.message | tool.execution_start | tool.execution_complete), `data.content`, `data.toolName`, `data.success`.

## Requirements

- Start from the transcript corpus. Do not scan the repo broadly before reading at least one transcript file.
- Identify: (1) sessions with more than 10 tool calls before the first file edit; (2) failed tool calls with three or more consecutive retries; (3) sessions whose dominant activity was discovery, not action.
- Cross-reference any new patterns against `docs/lessons-learned/known-failure-patterns.md`. Only update that file when a pattern is confirmed by two or more sessions and is not already documented.
- If `artifacts/ai-chat/findings.json` exists (plan 46 output), prefer that over manual transcript reading.
- Read `artifacts/ai-chat/summary.json` as well as `findings.json` and treat `semantic_grounding.status`, `grounded_session_count`, and the explanation text as first-class evidence when search tooling was unavailable or degraded during the reviewed sessions.
- Note which exec-plans or shipped seams address each observed gap. Prefer the completed observability plan 46 and the active automation plan 75. If an observed gap is not covered by any active plan, flag it explicitly.
- Keep the finding summary to five or fewer actionable items. Do not produce a prose summary of every session.

## Known Seams

- Transcript root: `<workspace-storage>/GitHub.copilot-chat/transcripts/`
- Observability CLI: `src/sattlint/devtools/ai_chat_observability.py`, `artifacts/ai-chat/findings.json`, and `artifacts/ai-chat/summary.json`
- Request-contract bootstrap: `scripts/bootstrap_ai_slice.py --from-request-kind chat-review`
- Failure patterns doc: `docs/lessons-learned/known-failure-patterns.md`
- Active improvement plan: `docs/exec-plans/active/75-t-wave-10-ai-feedback-loop-and-ci-gap-closure.md`
- Search-tooling follow-up plan: `docs/exec-plans/active/76-t-wave-10-semantic-grounding-health-and-fallback-routing.md`
- Completed observability plan: `docs/exec-plans/completed/46-t-wave-7-ai-chat-observability-and-feedback-loop.md`

## Output Format

Report each finding as:

    [PATTERN] <short label>
    Sessions: <session IDs or count>
    Evidence: <one-sentence description>
    Covered by plan: <plan number> or NOT COVERED
    Recommended action: <targeted next step>

End with a YES/NO answer to: "Should `known-failure-patterns.md` be updated?" If yes, apply the update directly.
