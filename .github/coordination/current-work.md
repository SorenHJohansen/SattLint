# Current Work

Shared ledger for concurrent chats and agents in SattLint.

## Rules

- Read this file before first edit when parallel work is active.
- Claim exact files before editing them.
- Update first validation command when scope changes.
- Mark workstream `done` and release claims when finished.

## Active Workstreams

### Workstream repo-verify-fixes-008

- Owner: current chat
- Goal: fix current pre-commit and repo-audit blockers in tests/test_app.py
- Claims: none
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py`
- Status: done
- Notes: fixed test-only typing and lint cleanup in `tests/test_app.py`; isolated `config_menu` tests with `deepcopy` so list mutations no longer leak through shallow `DEFAULT_CONFIG.copy()`. Final validation passed: focused `pytest tests/test_app.py tests/test_app_menus.py`, `pre-commit --all-files`, and `sattlint-repo-audit --profile full --output-dir artifacts/audit`.

## Recent Handoffs

### Workstream validation-gaps-doc-007

- Owner: current chat
- Goal: add confirmed validation gaps to remaining-refactor notes
- Claims: `.github/coordination/current-work.md`, `docs/refactor-remaining.md`
- First validation: markdown-only edit; workspace diagnostics on touched markdown files
- Status: done
- Notes: added a dedicated "Validation gaps to add" section in `docs/refactor-remaining.md` covering operator/type enforcement gaps, :OLD/:NEW assignment semantics, missing CONST/STATE rules, missing SFC execution semantics, and missing library/dependency validation.

### Workstream ai-validation-architecture-006

- Owner: current chat
- Goal: add direct Repo Verify prompt and collapse repeated validation routing into canonical map plus light references
- Claims: `.github/coordination/current-work.md`, `.github/prompts/`, `.github/instructions/`, `.github/agents/`, `.github/skills/validation-routing/`
- First validation: workspace diagnostics on touched customization files
- Status: done
- Notes: added a dedicated `Repo Verify` prompt, promoted `validation-map.md` to canonical first-check command source, and trimmed repeated validation command blocks from prompts, instructions, and specialist agents.

### Workstream ai-prompt-coverage-005

- Owner: current chat
- Goal: add direct slash-command prompts for remaining specialist agents so prompt coverage matches agent coverage
- Claims: `.github/coordination/current-work.md`, `.github/prompts/`, `.github/agents/`
- First validation: workspace diagnostics on new prompt and agent files
- Status: done
- Notes: added `CLI App Change` and `Documentation Generation Change` prompts, then exposed specialist agents as user-invocable so prompt frontmatter resolves cleanly for every specialist route.

### Workstream icf-draft-resolution-001

- Owner: current chat
- Goal: make draft-mode moduletype resolution prefer `.s` definitions over `.x` fallbacks within same library/name bucket
- Claims: `.github/coordination/current-work.md`, `src/sattlint/resolution/common.py`, `tests/test_moduletype_resolution_scoped.py`
- First validation: `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_moduletype_resolution_scoped.py`
- Status: done
- Notes: strict resolver now keeps same-library duplicates distinct by origin file, prefers source suffix matching current context, and carries enclosing definition file context while traversing nested `ModuleTypeInstance` paths. Follow-up ICF lookup now reuses that effective context when resolving variables under a moduletype instance, which clears the real `KaHAApplZ3` `Transfer.Dilute.*` failures. Validated with `tests/test_moduletype_resolution_scoped.py`, `tests/test_icf_validation.py`, and real draft-mode `KaHAApplZ3` counts.

### Workstream ai-routing-004

- Owner: current chat
- Goal: add test and fixture scoped instructions plus specialist workflow prompts for common AI repair paths
- Claims: `.github/coordination/current-work.md`, `.github/instructions/`, `.github/prompts/`
- First validation: workspace diagnostics on new instruction and prompt files
- Status: done
- Notes: added targeted test and fixture instruction files plus `Parser Fix`, `Workspace LSP Fix`, and `Repo Audit Change` prompts so common AI work enters the correct specialist flow faster.

### Workstream ai-efficiency-003

- Owner: current chat
- Goal: add subsystem-scoped instructions and lightweight session-start context for AI-only repo workflows
- Claims: `AGENTS.md`, `.github/instructions/`, `.github/hooks/`, `.github/coordination/current-work.md`
- First validation: `& ".venv/Scripts/python.exe" -m py_compile .github/hooks/scripts/session_context.py`
- Status: done
- Notes: added six subsystem-scoped instruction files to reduce context waste and a SessionStart hook that only injects coordination context when active workstreams exist.

### Workstream extend-agents-002

- Owner: current chat
- Goal: add claimed-file hook guard, more specialist agents, and repo-verify merge prompt
- Claims: `AGENTS.md`, `.github/coordination/current-work.md`, `.github/agents/`, `.github/prompts/`, `.github/skills/concurrent-work/SKILL.md`, `.github/hooks/`
- First validation: `& ".venv/Scripts/python.exe" -m py_compile .github/hooks/scripts/claimed_files_guard.py`
- Status: done
- Notes: hook guard now warns on active claims, asks on `ready-for-merge`, and denies on `blocked`; orchestrator can delegate to repo-audit, CLI/app-menu, and docgen specialists; use `Merge Workstreams` before final repo verification when multiple streams converge.

### Workstream bootstrap-agents-001

- Owner: current chat
- Goal: add initial repo-scoped agent, skill, prompt, and coordination scaffold
- Claims: `AGENTS.md`, `.github/agents/`, `.github/prompts/`, `.github/skills/`, `.github/coordination/current-work.md`
- First validation: workspace diagnostics on changed markdown files
- Status: done
- Notes: initial scaffold landed; next chats should create a new active entry instead of editing this handoff unless they are extending agent customization.

## Template

See `.github/skills/concurrent-work/assets/workstream-template.md`.
