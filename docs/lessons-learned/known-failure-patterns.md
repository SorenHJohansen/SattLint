# Known Failure Patterns

Agents should learn from prior mistakes. Update after each root-cause analysis.

## 2026-05-01 Chat Review

### Discovery Churn Before First Edit

- **Pattern**: Sessions burned 42-89 discovery calls before the first edit, with today dominated by `read_file`, `run_in_terminal`, `grep_search`, and `file_search`.
- **Root cause**: Failing to anchor on the controlling file, artifact, or failing test quickly enough, then continuing to widen search after the first dead-end path.
- **Fix**: Cap initial discovery to the smallest seam that can falsify one local hypothesis, then edit or run the cheapest discriminating check.
- **Prevention**: For repeated-file reviews, use one compact aggregation step instead of many ad hoc reads and searches.

### Wrong Transcript Or Log Seam

- **Pattern**: Chat-review work started in `debug-logs/main.jsonl`, even though useful conversation data lived in `GitHub.copilot-chat/transcripts/*.jsonl`.
- **Root cause**: Reaching for the most visible log folder instead of validating the controlling artifact format first.
- **Fix**: Use transcript JSONL files first for chat content. Treat debug logs as session-start metadata only.
- **Prevention**: Add the transcript-path rule to `AGENTS.md` so the default routing starts at the right seam.

### Low-Signal Assistant Output

- **Pattern**: Several sessions emitted empty assistant messages or `<final_answer>` blocks that were only file-path dumps.
- **Root cause**: Passing through incomplete subagent or intermediate tool output instead of summarizing the actionable result.
- **Fix**: If a tool or subagent returns incomplete context, continue the investigation or summarize the confirmed finding in plain language.
- **Prevention**: Treat empty messages and path-only close-outs as invalid output shapes.

### Broad Exploration On Review Tasks

- **Pattern**: Question-only review tasks still loaded unrelated repo surfaces before touching the requested artifact or the narrowest guidance seam.
- **Root cause**: Applying implementation-style repo exploration to tasks that first need evidence synthesis.
- **Fix**: Start review tasks from the user-named artifact, then update the smallest persistent guidance surface that can change future behavior.
- **Prevention**: Do not open unrelated `ai_*` devtools or broad docs unless the task explicitly requires tooling changes.

### Terminal Script Execution — Heredoc Failure

- **Pattern**: `python3 - << 'PY' ... PY` heredoc syntax fails silently or inconsistently in the VS Code integrated terminal, causing 3-4 retries before the agent finds a working command.
- **Root cause**: The VS Code terminal does not reliably handle multi-line heredoc blocks sent through the agent's `run_in_terminal` or `send_to_terminal` tools.
- **Fix**: Write the script content to a file first (`/tmp/script.py` or a named temp file), then run `python3 /tmp/script.py`. Never use heredoc syntax for Python execution in VS Code terminal.
- **Prevention**: Add a tool-use note to any agent that needs to run a short analysis script: write file then execute. Never inline Python in a heredoc.
