# T-Wave-7 AI Chat Observability and Feedback Loop

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns AI chat review from a manual transcript-reading exercise into a repo-owned observability loop. Today, the only reliable source of workspace chat behavior is the raw `GitHub.copilot-chat/transcripts/*.jsonl` corpus under VS Code workspace storage, while the local session index is effectively empty for review work. After this change lands, a single repo command will read transcript JSONL files, summarize the AI's behavior into machine-readable artifacts, and highlight concrete findings such as discovery churn, empty assistant output, failed tool calls, and broken session indexing.

The observable proof is straightforward. Running the new chat observability command against a fixture corpus must write `status.json`, `summary.json`, `sessions.json`, and `findings.json` under `artifacts/ai-chat/`, and the summary must explain whether the transcript corpus is healthy, whether the session index is usable, and which task categories create the most churn.

## Progress

- [x] (2026-05-15) Create the ExecPlan and capture the baseline review evidence: 20 transcript JSONL files in the current workspace corpus, 51 rows in the local `sessions` table, 0 `turns`, 0 `session_files`, and 0 non-empty repo, cwd, branch, or agent metadata in the session index.
- [x] (2026-05-15) Implement a repo-owned transcript reader and artifact writer under `src/sattlint/devtools/` that treats transcript JSONL as the source of truth for chat behavior.
- [x] (2026-05-15) Add a session-index health probe so the report can explain whether `session_store_sql` is usable, degraded, or empty for the current workspace.
- [x] (2026-05-15) Record AI quality findings such as empty assistant output, discovery-before-action counts, failed tool calls, and repeated same-tool retries in a structured findings artifact.
- [x] (2026-05-15) Add focused tests and a small fixture transcript corpus so future chat-review work can be validated without reading real machine-local chat logs.
- [x] (2026-05-15) Add one documented refresh command or VS Code task entry so the report becomes a repeatable maintenance artifact instead of a one-off debugging script.

## Surprises & Discoveries

Observation: the transcript corpus is useful, but the indexed session database is not.
Evidence: the current workspace has 51 rows in `sessions`, but `turns` and `session_files` are both empty, and the `sessions` rows have blank repo, cwd, branch, and agent metadata.

Observation: low-signal assistant output is still a live problem rather than a historical note.
Evidence: the current transcript review counted 298 empty `assistant.message` events out of 1140 total assistant-message events.

Observation: the same report needs to help both implementation work and review-only work.
Evidence: the current corpus showed 26 to 34 discovery steps before first action for bare `Implement this plan N` prompts and 29 to 34 discovery steps before first action for broad review prompts.

Observation: the transcript JSONL seam is straightforward to normalize once the parser keys match the real workspace format.
Evidence: a live transcript sample under `GitHub.copilot-chat/transcripts/` used stable top-level `type` values such as `user.message`, `assistant.message`, `tool.execution_start`, and `tool.execution_complete`, with the useful payload under the nested `data` object.

## Decision Log

Decision: treat transcript JSONL files as the primary chat-behavior source and the session index as a supplemental health signal.
Rationale: the raw transcripts contain turn content, tool calls, and tool failures now, while the indexed store does not currently preserve the fields needed for workspace-level review.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: emit findings, not just counters.
Rationale: a self-improving repo needs actionable outputs such as `session-store-empty`, `empty-assistant-output`, and `high-discovery-before-action`, not just raw totals.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: mirror the existing `artifacts/analysis/` pattern with `status.json`, `summary.json`, and a finding inventory.
Rationale: SattLint already uses machine-readable artifact directories for code health. Reusing that shape makes chat health easier to consume in the same workflows.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implemented on 2026-05-15: `sattlint.devtools.ai_chat_observability` now reads transcript JSONL files, emits `status.json`, `summary.json`, `sessions.json`, and `findings.json`, and treats the session database as an optional health signal instead of the primary chat source.

The shipped fixture corpus exercises malformed transcript lines, empty assistant output, high discovery-before-action churn, failed CodeGraph calls, and repeated same-tool retries. `tests/test_ai_chat_observability.py` passed as the focused regression proof for both `--transcripts-dir` and `--workspace-storage` input modes.

Repeatability is now wired into the workspace through the `AI: Refresh Chat Observability` VS Code task, which prompts for the `GitHub.copilot-chat` storage root and writes the report to `artifacts/ai-chat-current`.

## Context and Orientation

In this repository, a "transcript JSONL" file is a line-oriented JSON log written by Copilot chat under VS Code workspace storage. Each line is one event such as `user.message`, `assistant.message`, `tool.execution_start`, or `tool.execution_complete`. The important corpus lives under `GitHub.copilot-chat/transcripts/`. The sibling `GitHub.copilot-chat/debug-logs/` directory is still useful for metadata, but it is not the authoritative source for chat content.

The repository already has manual lessons about chat quality in `docs/lessons-learned/known-failure-patterns.md`, AI workflow rules in `docs/ai-workflows.md`, and a context-loading policy in `docs/context-loading-order.md`. Those files describe what the AI should do, but there is no repo-owned command today that measures what the AI actually did in a workspace.

The closest existing machine-readable artifact family is `artifacts/analysis/`. This plan should reuse that style. The likely owner surface is a new CLI entry module such as `src/sattlint/devtools/ai_chat_observability.py` plus small helper modules such as `src/sattlint/devtools/_ai_chat_transcripts.py`, `src/sattlint/devtools/_ai_chat_metrics.py`, and `src/sattlint/devtools/_ai_chat_findings.py`.

The first tests should live in `tests/test_ai_chat_observability.py`, with a fixture corpus under `tests/fixtures/ai_chat/`. The fixture corpus must be small, synthetic, and safe to commit. It should contain transcript lines that exercise failed tool calls, repeated tool retries, empty assistant output, and at least one healthy session.

## Plan of Work

Start by implementing a transcript loader that reads one directory of `*.jsonl` files, parses line-oriented JSON safely, and converts each transcript into a per-session summary. The loader must accept either `--transcripts-dir` or `--workspace-storage` so the repo never hard-codes a machine-local workspace path. If `--workspace-storage` is provided, the implementation must read transcripts from the `GitHub.copilot-chat/transcripts` child directory and treat missing directories as a clean, typed error.

Build metrics from those normalized sessions next. At minimum, capture transcript count, assistant-message count, empty assistant-message count, tool-call count, failed tool-call count, discovery-before-action count, first action tool, prompt buckets such as `implement this plan`, `review`, `audit`, `validate`, and the most common tools. Add a parallel session-store health probe that reads the local session database only when a path is provided and reports whether the database contains usable turn-level data.

Then implement a finding classifier. It should flag patterns such as `session-store-empty`, `wrong-log-seam-risk`, `high-discovery-before-action`, `high-empty-assistant-output-rate`, and `codegraph-tool-failures`. Keep findings descriptive and evidence-backed so they can feed later docs, dashboards, or nightly runs.

Finish by writing artifacts under one output directory. `status.json` should say whether the run completed and whether the data source was degraded. `summary.json` should surface the top metrics and the top risky task categories. `sessions.json` should record one normalized summary per transcript. `findings.json` should contain the actionable issues. If the repo already has a health dashboard generator that can consume another JSON artifact, extend it only after the standalone command is stable.

## Concrete Steps

Run all commands from the repository root.

Create and validate the fixture-driven slice first:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ai_chat_observability.py -x -q --tb=short

Once the command exists, run it against the fixture corpus:

    bash scripts/run_repo_python.sh -m sattlint.devtools.ai_chat_observability --transcripts-dir tests/fixtures/ai_chat/sample_workspace/GitHub.copilot-chat/transcripts --output-dir artifacts/ai-chat-fixture

After the fixture run succeeds, use the same command shape on a real workspace corpus only when one is available locally:

    bash scripts/run_repo_python.sh -m sattlint.devtools.ai_chat_observability --workspace-storage <path-to-workspace-storage>/GitHub.copilot-chat --output-dir artifacts/ai-chat-current

If the session index probe is implemented as a separate optional input, re-run with that database path explicitly:

    bash scripts/run_repo_python.sh -m sattlint.devtools.ai_chat_observability --workspace-storage <path-to-workspace-storage>/GitHub.copilot-chat --session-db <path-to-session-db> --output-dir artifacts/ai-chat-current

Finish with touched-file lint and type checks after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools/ai_chat_observability.py src/sattlint/devtools/_ai_chat_transcripts.py src/sattlint/devtools/_ai_chat_metrics.py src/sattlint/devtools/_ai_chat_findings.py tests/test_ai_chat_observability.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools/ai_chat_observability.py src/sattlint/devtools/_ai_chat_transcripts.py src/sattlint/devtools/_ai_chat_metrics.py src/sattlint/devtools/_ai_chat_findings.py tests/test_ai_chat_observability.py

## Validation and Acceptance

Acceptance requires a working artifact loop, not just a parser. The fixture-driven command must complete successfully, write `status.json`, `summary.json`, `sessions.json`, and `findings.json`, and record at least one finding from the fixture corpus. The real-workspace run, when available, must explain whether transcripts were found, whether the session index was usable, and which task buckets drove the most churn.

The report must never require hand-parsing raw transcript files to understand the main result. A novice should be able to open `summary.json` and answer four questions immediately: how many transcript sessions were scanned, whether the session index can be trusted, which tasks were the most expensive, and which findings need follow-up.

## Idempotence and Recovery

This work is read-only over the transcript corpus. Re-running it must be safe. If one transcript file is malformed, the run should record that fact in findings and continue rather than aborting the whole report. If the session database path is missing or unreadable, the report should mark the session-index probe as degraded and still emit transcript-based artifacts.

## Artifacts and Notes

Baseline evidence captured during plan creation:

    transcript_count = 20
    session_rows = 51
    turn_rows = 0
    session_file_rows = 0
    empty_assistant_messages = 298
    total_assistant_messages = 1140

The current lessons-learned document already records two related chat-review smells:

    discovery churn before first edit
    wrong transcript or log seam

This plan should make those smells machine-detectable rather than manual only.

## Interfaces and Dependencies

The public interface should be a CLI entrypoint such as `sattlint.devtools.ai_chat_observability`. It must accept `--transcripts-dir` or `--workspace-storage`, an `--output-dir`, and optionally a `--session-db` for the local session index. The command must write at least `status.json`, `summary.json`, `sessions.json`, and `findings.json`.

The implementation depends on Python's JSON handling, filesystem traversal, and small pure helpers only. Do not make this feature depend on live VS Code APIs, MCP, or network access. Keep all machine-local paths as inputs, never checked-in constants.
