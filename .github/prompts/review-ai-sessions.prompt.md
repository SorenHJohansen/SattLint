---
description: "Review recent SattLint AI chat sessions for failure patterns, tool drift, and self-improvement opportunities"
name: "Review AI Sessions"
argument-hint: "Transcript directory path, session ID, or 'latest' to scan all recent transcripts"
---

# Review AI Sessions

Analyse recent AI chat transcripts to identify failure patterns, excessive discovery steps, and missing tooling. Update `docs/lessons-learned/known-failure-patterns.md` if new patterns emerge.

## Starting Artifact

The transcript corpus is at `<workspace-storage>/GitHub.copilot-chat/transcripts/*.jsonl`. Each file is one session in newline-delimited JSON. Use the plan-46 observability command if it exists:

    bash scripts/run_repo_python.sh -m sattlint.devtools.ai_chat_observability \
      --transcripts-dir <workspace-storage>/GitHub.copilot-chat/transcripts \
      --output-dir artifacts/ai-chat

If the observability module does not exist yet, read the JSONL files directly. Each line is a JSON object. Key fields: `type` (session.start | user.message | assistant.message | tool.execution_start | tool.execution_complete), `data.content`, `data.toolName`, `data.success`.

## Requirements

- Start from the transcript corpus. Do not scan the repo broadly before reading at least one transcript file.
- Identify: (1) sessions with more than 10 tool calls before the first file edit; (2) failed tool calls with three or more consecutive retries; (3) sessions whose dominant activity was discovery, not action.
- Cross-reference any new patterns against `docs/lessons-learned/known-failure-patterns.md`. Only update that file when a pattern is confirmed by two or more sessions and is not already documented.
- If `artifacts/ai-chat/findings.json` exists (plan 46 output), prefer that over manual transcript reading.
- Note which exec-plans (46–49) address each observed gap. If an observed gap is not covered by any active plan, flag it explicitly.
- Keep the finding summary to five or fewer actionable items. Do not produce a prose summary of every session.

## Known Seams

- Transcript root: `<VSCODE_USER_DATA>/workspaceStorage/<hash>/GitHub.copilot-chat/transcripts/`
- Observability CLI: `src/sattlint/devtools/ai_chat_observability.py` (plan 46, not yet built)
- Request-contract bootstrap: `scripts/bootstrap_ai_slice.py --from-request-kind chat-review` (plan 49, not yet built)
- Failure patterns doc: `docs/lessons-learned/known-failure-patterns.md`
- Active improvement plans: `docs/exec-plans/active/46-*.md` through `docs/exec-plans/active/49-*.md`

## Output Format

Report each finding as:

    [PATTERN] <short label>
    Sessions: <session IDs or count>
    Evidence: <one-sentence description>
    Covered by plan: <plan number> or NOT COVERED
    Recommended action: <targeted next step>

End with a YES/NO answer to: "Should `known-failure-patterns.md` be updated?" If yes, apply the update directly.
