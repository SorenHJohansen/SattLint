# T-Wave-8 Maintainer Blind-Spot Reconciliation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the 2026-05-19 repository review for "what maintainers forgot to review themselves" into one executable artifact. After this work lands, a maintainer or coding agent should be able to open one plan and see which suspicious findings are already owned by active plans, which paths were truly committed residue rather than local noise, and which live seams still had no clear owner when the review finished. The goal is not to reopen every adjacent slice. The goal is to make the review durable, remove duplicate ownership, and close the remaining uncovered gap so future maintainers do not have to rediscover the same blind spots.

This plan also becomes the checked-in routing home for AI-generated-repo maintainability audits: duplicate abstractions, unused sophistication, disconnected or ceremonial systems, architecture entropy, hallucination residue, and the question of whether documented architecture matches the actual runtime architecture. It should record which active plan owns each category and which checks, if any, still have no correct owner.

The observable proof is straightforward. The review findings around version drift, root clutter, workflow duplication, release rehearsal, and security hardening will each point at one explicit owner plan instead of living only in a chat transcript. The canonical tech-debt tracker will reference this plan directly. The `doc_gardener` source-ledger scan will stop depending on a second hard-coded list of retired `TODO_*.md` files and will instead treat the consolidation source ledger in `docs/exec-plans/tech-debt-tracker.md` as the only authority for those retired sources.

## Progress

- [x] (2026-05-19 00:00Z) Create this ExecPlan from the blind-spot review and confirm the main routing fact pattern: release-version drift is already owned by plan 50, root-layout and architecture drift are already owned by the two plan 58 slices, workflow and release-path hardening are already owned by plans 58 and 61, and CLI truthfulness is already owned by plan 63.
- [x] (2026-05-19 00:00Z) Confirm the remaining live uncovered seam from the review: `src/sattlint/devtools/doc_gardener.py` still hard-codes `AI_FIRST_SOURCE_FILES` even though `docs/exec-plans/tech-debt-tracker.md` marks all four legacy `TODO_*.md` sources retired.
- [x] (2026-05-20 10:13Z) Expand the routing map so duplicate abstractions, unused sophistication, disconnected systems, architecture entropy, hallucination residue, and runtime-architecture mapping all point to explicit active owners or are recorded here as genuinely uncovered.
- [x] (2026-05-20 10:13Z) Add a durable routing section to this plan and to `docs/exec-plans/tech-debt-tracker.md` so the blind-spot review no longer depends on chat history.
- [x] (2026-05-20 10:13Z) Remove the duplicated retired-TODO source list from the doc-gardener path and make the source ledger the single source of truth for `scan_ai_first_source_drift`.
- [x] (2026-05-20 10:13Z) Update the focused source-ledger drift tests so retired-source behavior remains enforced without implying that root `TODO_*.md` files are still a live repo surface.
- [x] (2026-05-20 10:13Z) Re-ran focused doc-gardener and repo-audit validation and recorded the result here: `python scripts\run_repo_python.py -m pytest --no-cov tests\_repo_audit_part5.py tests\_repo_audit_part6.py -x -q --tb=short`, `python scripts\run_repo_python.py -m sattlint.devtools.doc_gardener --check-only`, `python scripts\context_health.py --check`, `.\.venv\Scripts\python.exe -m ruff check src\sattlint\devtools\doc_gardener.py src\sattlint\devtools\_doc_gardener_scan.py tests\_repo_audit_part5.py tests\_repo_audit_part6.py`, `.\.venv\Scripts\python.exe -m pyright src\sattlint\devtools\doc_gardener.py src\sattlint\devtools\_doc_gardener_scan.py`, and `.\.venv\Scripts\python.exe -m pre_commit run --files docs\exec-plans\completed\64-t-wave-8-maintainer-blind-spot-reconciliation.md docs\exec-plans\tech-debt-tracker.md`.

## Surprises & Discoveries

- Observation: most of the suspicious findings from the review were real, but they were not actually ownerless.
  Evidence: `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` already owns version drift and release-smoke gaps; `docs/exec-plans/completed/58-t-wave-8-repo-structure-and-architecture-alignment.md` already owns the root-clutter, GUI and editor-facade doc drift, and stale `arch_linter` naming; `docs/exec-plans/active/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md` already owns the duplicate Ubuntu full-audit leg, repeated raw `actionlint` installation, and publish rehearsal wiring; `docs/exec-plans/active/61-t-wave-8-repo-security-and-supply-chain-hardening.md` already owns the supply-chain and legacy helper-script removal seams.

- Observation: the blind-spot review still surfaced one live source-of-truth duplication that no active plan named directly.
  Evidence: `src/sattlint/devtools/doc_gardener.py` defines `AI_FIRST_SOURCE_FILES` as `TODO_GUI.md`, `TODO_REFACTOR.md`, `TODO_SATTLINT.md`, and `TODO_TOOLS.md`, while `docs/exec-plans/tech-debt-tracker.md` marks all four as retired and `src/sattlint/devtools/_doc_gardener_scan.py` still iterates the hard-coded sequence rather than the parsed ledger rows.

- Observation: the active plan set covered many concrete defects, but it did not yet name the AI-maintainability review lenses explicitly.
  Evidence: current plans already own release drift, root clutter, CI duplication, supply-chain hardening, parser rule wiring, and test helper coupling, but none of them originally framed duplicate abstractions, unused sophistication, ceremonial systems, architecture entropy, or hallucination residue as first-class recurring audit categories.

- Observation: several suspicious paths from the review are genuinely committed residue, not only local ignored output.
  Evidence: the review confirmed that `package.json`, `package-lock.json`, `node_modules/`, `compare.py`, `process_pyright.py`, `pyright_audit.py`, `artifacts/generated/repo-health.json`, and `artifacts/audit-full-current.tmp-g_ap8njm/` are tracked in git.

- Observation: the root helper and artifact clutter review is now actionable because the repo already has a canonical policy seam for it.
  Evidence: `src/sattlint/devtools/repo_audit_shared.py` defines `TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST`, and plan 58 already captures the concrete out-of-policy root paths from the same review.

## Decision Log

- Decision: do not reopen version alignment, workflow duplication, root-layout cleanup, or release-rehearsal work under a third implementation plan.
  Rationale: those findings already have active owners in plans 50, 58, and 61. Creating another implementation owner would increase drift rather than reduce it.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: use this plan as the durable routing artifact for the review and keep its direct implementation scope narrow.
  Rationale: the value of the blind-spot review is that it connected several suspicious paths at once. The repo needs one checked-in place that records those connections, even if most fixes land in neighboring plans.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: treat the tech-debt tracker's consolidation source ledger as the single source of truth for retired TODO-source status.
  Rationale: the four legacy `TODO_*.md` files were already retired by the completed AI-first hardening work. Keeping a second hard-coded list in `doc_gardener.py` recreates the split-brain source-of-truth problem that the retirement work was meant to remove.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: keep the existing temporary-file and restored-file regression tests, but make them prove ledger-driven behavior instead of hard-coded file-list behavior.
  Rationale: the repo still needs to catch accidental resurrection of retired TODO files. The fix is to derive the source names from the ledger, not to stop checking the behavior entirely.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: use this plan as the routing owner for AI-maintainability audits rather than creating parallel implementation plans for each review pass.
  Rationale: the value of these audits is in making ownership explicit. The implementation work should still land in the nearest active owner plan instead of duplicating scope here.
  Date/Author: 2026-05-20 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The routing artifact is now explicit in both this plan and `docs/exec-plans/tech-debt-tracker.md`, and the doc-gardener source-ledger scan no longer depends on a second hard-coded tuple of retired `TODO_*.md` names. The direct implementation gap from the blind-spot review is now narrower: source-ledger behavior is owned by the ledger rows themselves, while the surrounding suspicious-path findings keep their existing owner plans.

The remaining risk is accidental re-duplication. If future edits reintroduce another canonical retired-source list or start copying the same root-clutter, version-drift, or workflow findings into this plan as if it were a second implementation owner, the review surface will become noisy again. The durable rule after this slice is simple: fix the ledger first, then let doc-gardener derive behavior from it.

Focused validation for this slice stayed narrow and behavior-first. The repo-audit shard tests passed, `sattlint.devtools.doc_gardener --check-only` reported zero findings on the updated tree, context health stayed clean, the touched production files passed Ruff and Pyright, and the touched routing docs passed the targeted pre-commit hooks. Running Pyright on the full legacy repo-audit shard test modules still reports inherited strict-typing debt outside the scope of this routing slice, so the typed proof for this change stayed anchored to the production seam it actually changed.

## Context and Orientation

The 2026-05-19 blind-spot review covered four broad categories: suspicious inconsistencies, abandoned-looking surfaces, duplicated workflows or artifacts, and manual human-review candidates. The review named exact paths rather than abstract themes. The most important paths were `src/sattlint/__version__.py`, `src/sattlint_lsp/server.py`, `vscode/sattline-vscode/package.json`, `ARCHITECTURE.md`, `docs/repo-map.md`, `docs/architecture.md`, `AGENTS.md`, `.github/workflows/ci.yml`, `.github/workflows/repo-audit.yml`, `.github/workflows/publish.yml`, `package.json`, `package-lock.json`, `node_modules/`, `compare.py`, `process_pyright.py`, `pyright_audit.py`, `artifacts/generated/repo-health.json`, and `artifacts/audit-full-current.tmp-g_ap8njm/`.

The broader AI-maintainability audit uses the same evidence style but groups the findings differently. In this plan, `duplicate abstractions` means multiple systems solving the same problem with different seams or conventions. `unused sophistication` means complexity whose payoff is unclear, such as extension points with one implementation or metrics and automation that nobody consumes. `looks real but is never used` means commands, scripts, docs, or workflows that read as official but do not connect to an actual execution path. `architecture entropy` means additive growth where several generations of design coexist. `hallucination residue` means authoritative-looking files, TODOs, config keys, imports, or classes that imply systems which are deleted, disconnected, or never shipped. Concrete examples to route through this lens include duplicate config or logging seams, repeated subprocess or file wrappers, unused configuration keys, TODOs that refer to removed systems, commands with no real callers, classes with no callers, and files that look authoritative but are disconnected from the live execution paths.

Most of those paths are already owned by active plans. `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` owns public version alignment, support classification, release rehearsal, and the missing `release_smoke` seam. `docs/exec-plans/completed/58-t-wave-8-repo-structure-and-architecture-alignment.md` owns root-layout cleanup, root helper-script triage, stale long- and short-doc names, and the GUI plus editor-facade documentation gap. `docs/exec-plans/active/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md` owns duplicate full-audit workflow work, repeated `actionlint` setup logic, and publish-workflow rehearsal wiring. `docs/exec-plans/active/61-t-wave-8-repo-security-and-supply-chain-hardening.md` owns the supply-chain and workflow-trust concerns around legacy helper removal, publish permissions, and Node dependency monitoring. `docs/exec-plans/completed/63-t-wave-8-cli-ux-and-documentation-trustworthiness.md` owns the user-facing CLI and command-doc drift that the broader review touched only indirectly.

At planning time, the one live seam that still lacked a dedicated owner was the retired-TODO source-ledger wiring inside doc-gardener. `docs/exec-plans/tech-debt-tracker.md` is the canonical consolidation source ledger for the retired files `TODO_GUI.md`, `TODO_REFACTOR.md`, `TODO_SATTLINT.md`, and `TODO_TOOLS.md`. The completed plan `docs/exec-plans/completed/ai-first-repo-hardening.md` explicitly retired those files and moved their state into the ledger. Before this slice landed, `src/sattlint/devtools/doc_gardener.py` still defined `AI_FIRST_SOURCE_FILES`, and `src/sattlint/devtools/_doc_gardener_scan.py` took that explicit list as an argument to `scan_ai_first_source_drift`.

In this plan, a `routing artifact` means a checked-in plan that tells a future maintainer where each review finding belongs so the same scan does not need to be repeated from scratch. A `source ledger` means the Markdown table under `## Consolidation Source Ledger` in `docs/exec-plans/tech-debt-tracker.md`. A `retired TODO source` means one of the earlier root-level `TODO_*.md` backlog files that was removed from the repository and replaced by the canonical ledger. A `blind-spot finding` means a path or mismatch that looked intentionally added but incompletely reviewed, for example a committed scratch helper or a doc that still uses an old module name.

The focused tests for the source-ledger seam already exist. `tests/_repo_audit_part5.py` and `tests/_repo_audit_part6.py` create temporary restored `TODO_*.md` files and assert the drift messages produced by the current source-ledger checks. Those tests are the nearest executable proof for any change in `scan_ai_first_source_drift`. The doc-gardener CLI entrypoint lives in `src/sattlint/devtools/doc_gardener.py`, and `docs/exec-plans/tech-debt-tracker.md` is the canonical data source it should trust.

## Plan of Work

Start by making the review routing explicit. Update `docs/exec-plans/tech-debt-tracker.md` so it points at this plan as the follow-on artifact from the 2026-05-19 blind-spot review. In this plan itself, keep a concise path-to-owner map for the major findings so a future executor can see immediately which active plan owns which suspicious path. Expand that routing so the broader AI-maintainability categories also have explicit owners: actual-runtime-architecture and doc-versus-runtime drift go to the repo-structure plan, stale or ceremonial automation goes to the CI plan, implementation-coupled or high-count low-confidence tests go to the test-hardening plan, public-doc and command truthfulness go to the release-readiness plan, parser or error-reporting style drift goes to the parser hardening plan, security-only automation drift goes to the security plan, and performance-only sophistication goes to the performance plan. If a concrete finding still has no correct owner after that pass, record it here as uncovered instead of forcing it into the wrong slice.

Then fix the uncovered source-of-truth duplication in doc-gardener. Edit `src/sattlint/devtools/doc_gardener.py` and `src/sattlint/devtools/_doc_gardener_scan.py` so `scan_ai_first_source_drift` derives the relevant source names from the parsed consolidation source ledger instead of from the separate `AI_FIRST_SOURCE_FILES` constant. The important behavior is not the constant itself. The important behavior is that the source-ledger scan should report three cases correctly: a retired source file was accidentally restored, an active source file is missing when the ledger says it should exist, and a ledger row is malformed or missing.

Keep the current user-visible behavior of the scan, but change what owns the truth. If the ledger marks `TODO_GUI.md` retired and a temporary file with that name exists, the scan should still emit the same drift finding. If the ledger ever marks a source file active in the future, the scan should still catch its absence. What must disappear is the second canonical list in `doc_gardener.py` that can drift from the ledger. If some compatibility wrapper is still useful, move that knowledge next to the ledger-parsing seam rather than leaving it as an independently curated top-level tuple.

After the source-ledger seam is repaired, update the focused tests. `tests/_repo_audit_part5.py` and `tests/_repo_audit_part6.py` should continue to cover retired-source resurrection and malformed-ledger behavior, but they should no longer imply that the hard-coded `AI_FIRST_SOURCE_FILES` tuple is an independently maintained input. Add or adjust assertions so the tests prove that the ledger rows drive the behavior. Keep the message text stable when possible because the messages already explain the drift clearly.

Finish by recording the review-to-owner routing and validation evidence back into this plan. The finished state of this plan should say explicitly that version drift remains owned by plan 50, root clutter and doc alignment remain owned by the two plan 58 slices, security and supply-chain hardening remain owned by plan 61, and the retired-TODO source-ledger seam was the only direct implementation gap this reconciliation slice closed.

## Concrete Steps

Run all commands from the repository root.

First, restate the routing facts and the uncovered seam before editing anything:

    rg -n "0\.1\.1|0\.1\.0|TODO_GUI\.md|TODO_REFACTOR\.md|TODO_SATTLINT\.md|TODO_TOOLS\.md|compare\.py|process_pyright\.py|pyright_audit\.py|artifacts/generated/repo-health\.json|audit-full-current\.tmp" docs/exec-plans/active docs/exec-plans/tech-debt-tracker.md src/sattlint/devtools tests

Then edit the plan and tracker files so the blind-spot review becomes a durable artifact:

    docs/exec-plans/completed/64-t-wave-8-maintainer-blind-spot-reconciliation.md
    docs/exec-plans/tech-debt-tracker.md

After that, repair the source-ledger seam in the doc-gardener path:

    src/sattlint/devtools/doc_gardener.py
    src/sattlint/devtools/_doc_gardener_scan.py

Update the nearest regression tests for the same seam:

    tests/_repo_audit_part5.py
    tests/_repo_audit_part6.py

Run the first focused executable proof immediately after the code change:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/_repo_audit_part5.py tests/_repo_audit_part6.py -x -q --tb=short

If that passes, run the narrow doc-gardener proof and the repo health check for the touched docs:

    bash scripts/run_repo_python.sh -m sattlint.devtools.doc_gardener --check-only
    python scripts/context_health.py --check

If the executor also touches the tracker or plan routing text substantially, finish with a targeted Markdown or pre-commit pass for the changed docs:

    python -m pre_commit run --files docs/exec-plans/completed/64-t-wave-8-maintainer-blind-spot-reconciliation.md docs/exec-plans/tech-debt-tracker.md

## Validation and Acceptance

Acceptance is behavior and routing clarity together. A maintainer should be able to open this plan and `docs/exec-plans/tech-debt-tracker.md` and learn, without re-running the original broad review, which active plan owns each substantive blind-spot finding. The plan should explicitly route at least these categories: version drift, root-clutter and fast-doc drift, workflow duplication and release rehearsal, supply-chain hardening, the retired-TODO source-ledger seam, duplicate abstractions, unused sophistication, disconnected or ceremonial systems, architecture entropy, hallucination residue, and the actual-runtime-architecture map.

The doc-gardener acceptance bar is that the consolidation source ledger becomes the only source of truth for the retired `TODO_*.md` files. The implementation may still detect restored retired files and malformed rows, but it must do so from the parsed ledger rather than from a separate top-level tuple. A grep of `src/sattlint/devtools/doc_gardener.py` after the slice should no longer show a second authoritative hard-coded list of retired `TODO_*.md` source names.

The executable acceptance bar is that `bash scripts/run_repo_python.sh -m pytest --no-cov tests/_repo_audit_part5.py tests/_repo_audit_part6.py -x -q --tb=short` passes, `bash scripts/run_repo_python.sh -m sattlint.devtools.doc_gardener --check-only` passes on the updated tree, and `python scripts/context_health.py --check` still succeeds after the tracker and plan routing updates.

## Idempotence and Recovery

The routing-doc edits are safe to repeat. If a neighboring active plan changes scope later, update the routing text in this plan and the tech-debt tracker rather than creating a second reconciliation artifact. This plan should stay the single checked-in answer to "where did the 2026-05-19 blind-spot review go?"

The doc-gardener change should also be safe to retry. If the first implementation attempt breaks the source-ledger scan, recover by restoring the previous passing behavior and then reapplying the change with the parsed ledger rows as the only input. Do not reintroduce a second hard-coded canonical list just to make the tests pass quickly.

If an unexpected future need arises for a live TODO source outside the retired four-file set, add or edit the row in `docs/exec-plans/tech-debt-tracker.md` first and let the scan derive behavior from that ledger row. The recovery path is to fix the ledger, not to patch around it in code.

## Artifacts and Notes

Blind-spot finding to active owner routing captured at plan creation:

    - public version drift, release-smoke gap, VS Code preview labeling -> plan 50
    - root Node surface, committed scratch helpers, stale repo-health artifact, fast-doc alignment, stale `arch_linter` naming -> repo-structure plan 58
    - duplicate Ubuntu full audit, repeated raw `actionlint` installation, publish rehearsal wiring -> CI workflow plan 58
    - legacy helper-script removal, workflow trust boundary, npm monitoring -> plan 61
    - CLI doc and command-trust drift -> plan 63
    - retired TODO-source ledger duplication in doc-gardener -> this plan
    - actual runtime architecture map, documented-versus-actual architecture drift, additive-versus-cohesive structure review -> repo-structure plan 58
    - implementation-coupled or high-count low-confidence test areas -> plan 59
    - parser-rule, warning, and diagnostic-style duplication -> plan 60
    - unused sophistication or ceremonial automation in workflows -> CI workflow plan 58
    - unused sophistication or ceremonial release-facing docs and commands -> plan 50
    - unused sophistication that is only performance or scaling complexity -> plan 62

Committed paths confirmed by the review that made plan 58's root-clutter cleanup concrete rather than hypothetical:

    - package.json
    - package-lock.json
    - node_modules/
    - compare.py
    - process_pyright.py
    - pyright_audit.py
    - artifacts/generated/repo-health.json
    - artifacts/audit-full-current.tmp-g_ap8njm/

## Interfaces and Dependencies

The direct implementation seam for this plan is the doc-gardener source-ledger path. `src/sattlint/devtools/doc_gardener.py` now calls `scan_ai_first_source_drift` without a second canonical file list, and `src/sattlint/devtools/_doc_gardener_scan.py` now derives retired-source checks directly from the parsed rows in `docs/exec-plans/tech-debt-tracker.md`. The authoritative inputs are the ledger rows plus the repository root path used to test file presence and active-file digests.

The test interfaces that must remain green are `tests/_repo_audit_part5.py` and `tests/_repo_audit_part6.py`, because they already exercise the source-ledger drift behavior with temporary restored `TODO_*.md` files and malformed rows. The documentation interfaces that must stay aligned are `docs/exec-plans/tech-debt-tracker.md` and this plan file itself. No new external dependencies are needed for this slice.
