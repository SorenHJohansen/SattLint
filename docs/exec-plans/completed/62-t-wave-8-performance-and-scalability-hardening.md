# T-Wave-8 Performance and Scalability Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the 2026-05-19 performance and scalability review into an execution slice that protects SattLint from slowing down or falling over on large workspaces. After this work lands, the AST cache path will stop doing expensive file-manifest validation when the user explicitly asked for the fast path, workspace discovery and LSP background diagnostics will stop traversing irrelevant large directories or rebuilding more entry snapshots than necessary, and the structural-report plus repo-audit pipelines will stop paying repeated full-scan costs that do not scale with thousands of files.

The visible proof is behavioral. `ensure_ast_cache` will stop turning "fast cache validation" into a full `stat()` sweep, LSP workspace refreshes will avoid obvious non-source trees and limit rebuild work to affected entries, structural graph reporting will stop rebuilding or retaining unnecessary per-entry snapshots, and repo-audit or pipeline inventory checks will stop walking large generated or vendor trees that this repository already knows are irrelevant.

## Progress

- [x] (2026-05-19) Create this ExecPlan from the performance and scalability review. Capture the current hot paths in AST cache validation, workspace discovery, LSP snapshot refresh, structural graph reporting, and repo-wide inventory scans.
- [x] Fix the inverted fast-cache-validation branch so the fast path stays cheap and the slow path remains opt-in.
- [x] Reduce parser and dependency-resolution overhead from repeated cache persistence in the project loader path by batching `FileLookupCache` saves and flushing once per resolve or post-resolve lookup.
- [x] Prune workspace discovery and LSP entry-file refresh work by ignoring `artifacts/` and `node_modules/` during discovery and caching dependency-name references on the discovery result so `_workspace_entry_files()` does not reopen dependency files.
- [x] Scope the materialized structural graph input path to structural entry roots and preserve shared discovery metadata while keeping dependency-aware snapshot resolution on the full workspace discovery.
- [x] Bound the remaining dependency-list-triggered LSP background diagnostics and unchanged-entry rebuild work by preserving unchanged bundles across workspace refresh and scheduling only stale or newly discovered entries after `.l` or `.z` saves.
- [x] Rework structural graph and related report collection further so the pipeline derives dependency, call, and graphics-layout reports from one shared semantic pass instead of repeated per-entry rebuild patterns.
- [x] Prune repo-audit and pipeline full-tree scans by switching `collect_repo_file_inventory()` to top-down pruned traversal and by making production-summary KLOC collection reuse workspace discovery instead of root-level `rglob()`.
- [x] Add focused regression coverage that proves the optimized paths stay bounded and that cache or discovery semantics do not regress.
- [x] Run focused pytest, Ruff, and source-file Pyright validation for the touched slice and update this plan with the observed results.

## Surprises & Discoveries

- Observation: the parser core itself is not the first scaling problem.
  Evidence: `src/sattline_parser/api.py` already caches the formatted grammar and Lark parser artifacts, while the larger repeated-work costs sit above it in `src/sattlint/_app_analysis_loading.py`, `src/sattlint/core/workspace_discovery.py`, `src/sattlint_lsp/workspace_store.py`, and `src/sattlint/devtools/_structural_report_graphs.py`.

- Observation: the current "fast cache validation" path appears inverted.
  Evidence: `src/sattlint/_app_analysis_loading.py` calls `cache.validate(cached, fast=False)` when `fast_cache_validation` is true and the payload has a manifest, which forces the expensive full-manifest `stat()` sweep implemented in `src/sattlint/cache.py`.

- Observation: workspace discovery still traverses directories that are large in this repository but irrelevant to source loading.
  Evidence: `src/sattlint/core/workspace_discovery.py` prunes `.git`, `.venv`, `build`, `dist`, and a few cache directories, but it does not prune `artifacts` or `node_modules`, both of which are present in this working tree and can become large.

- Observation: LSP background diagnostics already cap resident snapshot count, but refresh still rebuilds whole-entry bundles rather than incrementally updating a shared workspace model.
  Evidence: `src/sattlint_lsp/workspace_store.py` limits cached entry snapshots with `max_cached_entry_snapshots`, yet `_build_bundle()` still calls `load_workspace_snapshot()` per entry and `_server_scan_helpers.py` schedules batches of entry-file rebuilds for background diagnostics.

- Observation: structural reporting has two different costly failure modes.
  Evidence: `src/sattlint/devtools/_structural_report_graphs.py` has one path that stores every snapshot in a list and another path that streams results without storing them, but both still call `load_workspace_snapshot()` once per program file.

- Observation: repo-audit already has some shared preload context, but adjacent helper surfaces still do independent whole-tree scans.
  Evidence: `src/sattlint/devtools/leak_detection_scan_paths.py` preloads Python texts and ASTs for repo-audit, yet `src/sattlint/devtools/pipeline_checks.py` still builds a full repo inventory with `repo_root.rglob("*")`, and `src/sattlint/devtools/production_summary.py` still rereads every source file to compute KLOC.

- Observation: the lookup cache is small but can become disproportionately noisy under large dependency closure.
  Evidence: `src/sattlint/cache.py` rewrites the entire `file_lookup_cache.json` on each `set()` or `forget()`, and `src/sattlint/engine.py` calls those methods directly inside the hot dependency-resolution path.

- Observation: the materialized structural graph-input path was broader than the streaming path.
  Evidence: `src/sattlint/devtools/_structural_report_graphs.py::collect_workspace_graph_inputs()` iterated every discovered program file, while `_stream_workspace_graph_reports()` already narrowed to `STRUCTURAL_ENTRY_ROOTS` via `_structural_report_discovery()`.

- Observation: production-summary KLOC collection did not need its own root-level file walk.
  Evidence: `src/sattlint/devtools/production_summary.py` was using `resolved_root.rglob()` for `.s/.x/.l/.z`, even though `src/sattlint/core/workspace_discovery.py` already provides a pruned source-file inventory with the correct SattLine suffix rules.

- Observation: touched test modules still carry substantial inherited Pyright strictness debt.
  Evidence: focused source-file Pyright is clean for the implementation files, but running Pyright across the touched test modules surfaces large pre-existing diagnostics in files such as `tests/test_editor_api.py` and `tests/parser/test_engine.py` that were not introduced by this slice.

- Observation: dependency-list saves already had enough local information to avoid global LSP cache churn.
  Evidence: `src/sattlint_lsp/workspace_store.py` maintains `_source_file_to_entry_keys`, so a saved `.l` or `.z` file can invalidate only the entry bundles that actually depended on it before the workspace refresh recomputes root entries.

- Observation: the structural bundle still had one duplicated semantic walk after the earlier entry-scoping fix.
  Evidence: `src/sattlint/devtools/structural_reports.py::collect_structural_reports()` called `_stream_workspace_graph_reports()` for dependency and call graphs but then separately called `collect_graphics_layout_report()` over the same snapshot set.

## Decision Log

- Decision: treat the first milestone as a behavior-preserving performance hardening slice, not a feature rewrite.
  Rationale: the review found avoidable repeated work in existing seams. The first job is to remove those costs without changing the visible feature contract of parsing, analysis, repo audit, or the LSP.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: fix the fast-cache-validation bug before introducing broader caching changes.
  Rationale: the current branch inversion is a concrete local defect with immediate user-facing cost during startup and analysis flows. It is cheap to verify and should be corrected before designing larger cache refactors.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: prefer pruning and reuse over adding more long-lived caches.
  Rationale: this repository already has multiple cache layers. The review found the bigger wins in avoiding unnecessary traversal or rebuilds, not in creating additional caches that would need new invalidation policy.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: keep structural graph reporting streaming-first.
  Rationale: the retained-snapshot path has the highest memory risk on thousands of files. The durable fix should reduce rebuild count and peak residency rather than formalizing the all-snapshots-in-memory variant.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: keep repo-audit preload context as the canonical source of shared Python texts and ASTs.
  Rationale: repo-audit already has a reusable `PythonSourceScanContext` seam. The better direction is to thread that context into neighboring checks and inventory paths, not to create parallel preload mechanisms.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: align the materialized structural graph-input collector with the streaming structural-entry filter before attempting a larger graph-pipeline redesign.
  Rationale: the mismatch was a local, behavior-preserving source of unnecessary snapshot work and peak memory. Fixing that seam reduces cost immediately and keeps the wider refactor optional.
  Date/Author: 2026-05-21 / Copilot (GPT-5.4)

- Decision: use source-only Pyright as the finish-gate proof for this slice after validating behavior with focused pytest.
  Rationale: the implementation files are type-clean, while several touched test modules already carry unrelated Pyright debt. Paying that debt down would have widened scope away from the performance seams in this plan.
  Date/Author: 2026-05-21 / Copilot (GPT-5.4)

- Decision: treat dependency-list saves as targeted entry invalidation plus targeted workspace refresh, not as a full diagnostic reset.
  Rationale: `.l` and `.z` saves are workspace-control events, but the snapshot store already knows which entry bundles referenced the changed file. Reusing that mapping preserves unaffected bundles and diagnostics while still rebuilding newly selected or stale entries.
  Date/Author: 2026-05-21 / Copilot (GPT-5.4)

- Decision: extend the structural streaming pass to accumulate graphics layout instead of reusing the materialized-snapshot collector.
  Rationale: graphics layout is snapshot-derived like dependency and call graphs, so accumulating it during the existing stream removes one more per-entry semantic walk without forcing the pipeline back to an all-snapshots-in-memory design.
  Date/Author: 2026-05-21 / Copilot (GPT-5.4)

## Outcomes & Retrospective

**First milestone complete (fast-cache-validation inversion fix).**

`ensure_ast_cache()` in `src/sattlint/_app_analysis_loading.py` was calling `cache.validate(cached, fast=False)` in the branch guarded by `if fast and has_manifest:`, forcing an expensive full `stat()` sweep even when the caller explicitly opted in to the cheap path with `fast_cache_validation=True`. The fix is a one-character correction: `fast=False` → `fast=True`.

Two new regression tests in `tests/test_app_analysis_project_cache.py` now prove the fast contract explicitly by recording the `fast` argument passed into the `validate()` stub. One test asserts `fast=True` is passed when `fast_cache_validation=True` and the payload has a manifest; the other asserts `fast=False` is passed when `fast_cache_validation=False`. The existing behavior test was updated to reflect the corrected contract (FakeCache.validate now returns True for `fast=True`, not `fast=False`).

Validation: 7 tests pass; Ruff and Pyright clean on touched files; pre-commit passes.

Remaining milestones (project-loader cache, workspace discovery / LSP refresh, structural reporting, repo-audit scan pruning) stay open for subsequent slices.

**Second milestone set complete (loader batching, discovery pruning, structural entry scoping, repo scan pruning).**

This turn completed four additional performance hardening slices.

`src/sattlint/cache.py`, `src/sattlint/engine.py`, and `src/sattlint/_app_analysis_loading.py` now batch `FileLookupCache` writes in memory and flush once at the end of `resolve()` or after the one post-resolve dependency lookup used by project loading. This removes repeated JSON rewrites from the hot dependency-resolution loop without changing lookup-cache payloads.

`src/sattlint/core/workspace_discovery.py` now prunes `artifacts/` and `node_modules/` during workspace discovery and records dependency-name references in the discovery result. `src/sattlint_lsp/workspace_store.py::_workspace_entry_files()` now consumes that cached set instead of reopening dependency files while deciding which program files are roots for workspace analysis.

`src/sattlint/devtools/_structural_report_graphs.py` now scopes `collect_workspace_graph_inputs()` through the same structural-entry filter already used by the streaming graph-report path, while still passing the full discovery object into `load_workspace_snapshot()` so dependency resolution remains workspace-aware.

`src/sattlint/devtools/pipeline_checks.py` now uses top-down pruned traversal for repo inventory instead of `rglob("*")`, and `src/sattlint/devtools/production_summary.py` now reuses workspace discovery to collect SattLine source files for KLOC. That removes two independent full-tree walks over large irrelevant directories.

Focused regression coverage was added in `tests/test_lsp_diagnostics.py`, `tests/test_editor_api.py`, `tests/parser/test_cache.py`, `tests/parser/test_engine.py`, `tests/test_recommendation_routing.py`, `tests/devtools/test_devtools_orphans.py`, and `tests/test_structural_reports.py`.

Validation observed this turn:

- Focused pytest slices passed for discovery/LSP entry selection, lookup-cache batching, repo inventory and production summary collection, and structural graph-input scoping.
- Ruff passed on all edited files.
- Pyright passed on the edited implementation files in `src/`.
- Pyright over the touched test modules still reports inherited strictness debt in existing test files outside the scope of this performance slice.

Remaining plan work is narrower now. The largest open piece is the deeper LSP refresh scheduling and broader structural-report reuse beyond entry scoping.

**Third milestone set complete (targeted dependency-list refresh and streamed graphics-layout reuse).**

This turn closed the remaining clean LSP refresh slice and the next structural reuse slice.

`src/sattlint_lsp/workspace_store.py` now preserves unchanged cached bundles across `refresh_workspace()` and reports which entries were removed versus which entries still need work. `src/sattlint_lsp/server.py` now handles saved `.l` and `.z` files by invalidating only the entry bundles that depended on that control file, refreshing workspace discovery, clearing removed entry state, and scheduling only the union of stale and newly discovered entries. That avoids the old full-diagnostic reset and avoids rebuilding unchanged entries just because one dependency list changed.

`src/sattlint/devtools/_structural_report_graphics.py`, `src/sattlint/devtools/_structural_report_graphs.py`, and `src/sattlint/devtools/structural_reports.py` now accumulate graphics-layout entries during the existing streaming graph pass. The structural bundle no longer does one pass for dependency and call graphs and then a second pass over the same snapshots for graphics layout.

Focused regression coverage was added in `tests/test_lsp_diagnostics.py`, `tests/test_lsp_workspace_documents.py`, and `tests/test_structural_reports.py`.

Validation observed this turn:

- Focused pytest passed for unchanged-bundle preservation during workspace refresh.
- Focused pytest passed for dependency-list saves scheduling only stale or new entries.
- Focused pytest passed for streamed structural bundle reuse of the graphics-layout report.
- Ruff passed on the touched implementation and test files for this slice.
- Pyright passed on the touched implementation files for this slice.

The remaining plan work is now mostly in deeper optional follow-up, not the originally identified clean local hotspots.

## Context and Orientation

This plan is about performance and scalability in the actual owning seams, not generic cleanup. The parser lives in `src/sattline_parser/`, but the first scaling risks sit one layer above it. `src/sattlint/cache.py` owns two cache families. `ASTCache` stores whole-project cache payloads keyed by analysis target. `FileASTCache` stores per-file parsed ASTs. `FileLookupCache` stores previously found dependency and code-file locations. `src/sattlint/_app_analysis_loading.py` owns the user-facing cache maintenance path used by `ensure_ast_cache`, and `src/sattlint/engine.py` owns the project-loader path that reads dependencies, resolves files, parses source, and records lookup hits.

Workspace and editor performance live under `src/sattlint/core/` and `src/sattlint_lsp/`. `src/sattlint/core/workspace_discovery.py` walks a workspace root and classifies source files. `src/sattlint/core/semantic.py` turns an entry file plus discovery context into a semantic snapshot by instantiating `SattLineProjectLoader`. `src/sattlint_lsp/workspace_store.py` caches per-entry `SnapshotBundle` values for the language server, and `src/sattlint_lsp/_server_scan_helpers.py` schedules background diagnostics. In this repository, an entry file means a top-level `.s` or `.x` program that the LSP or structural reports treat as a root for dependency resolution.

The structural and audit pipeline surfaces live under `src/sattlint/devtools/`. `src/sattlint/devtools/_structural_report_graphs.py` builds workspace dependency and call-graph inputs, either by collecting all snapshots or by streaming them. `src/sattlint/devtools/structural_reports.py` coordinates those reports with adjacent graphics and impact-analysis outputs. `src/sattlint/devtools/leak_detection_scan_paths.py` builds the shared repo-audit Python text and AST preload context. `src/sattlint/devtools/audit_core.py`, `src/sattlint/devtools/audit_core_discovery.py`, and `src/sattlint/devtools/repo_audit.py` build repo-audit checks on top of that context. `src/sattlint/devtools/pipeline_checks.py` and `src/sattlint/devtools/production_summary.py` still contain whole-tree inventory or reread paths that were called out by the review.

The current review identified four concrete bottleneck classes. First, `fast_cache_validation` is mislabeled in practice because the fast setting can still force full-manifest validation. Second, workspace discovery and LSP background diagnostics can scale with the whole workspace and then again with the number of entry files. Third, structural graph reporting rebuilds semantic state once per entry instead of deriving multiple reports from one shared resolved graph. Fourth, repo-audit and adjacent pipeline helpers still have some whole-repo scans that do not sufficiently prune irrelevant trees or reuse already loaded file contents.

This plan is intentionally bounded. It does not attempt to redesign the parser, remove existing caches wholesale, or introduce asynchronous background daemons. It focuses on eliminating repeated file reads, unnecessary parsing or semantic-load passes, expensive scans over large repositories, excess memory residency in graph pipelines, and obvious bottlenecks in current validation and analysis flows.

## Plan of Work

Start with the cheapest, most falsifiable defect: fix `ensure_ast_cache()` so the fast path in `src/sattlint/_app_analysis_loading.py` actually calls the fast validation branch in `src/sattlint/cache.py`. Add or update tests in `tests/test_app_analysis_project_cache.py` so they prove two things. First, `fast_cache_validation=True` no longer forces full-manifest validation when a cache payload already has a manifest. Second, the slower full-validation path still runs when the caller explicitly requests strict validation or when the payload shape requires it. Keep the existing CLI behavior and output text stable unless a test proves the wording is incorrect.

Next, harden the project-loader cache and dependency-resolution path in `src/sattlint/engine.py` and `src/sattlint/cache.py`. The goal is not a new cache layer. The goal is to remove avoidable repeated persistence and repeated file reads. Keep the in-memory base-directory index built by `_get_base_index()`, but avoid rewriting the lookup-cache JSON file on every single resolution hit. A buffered save, delayed flush, or single-save-on-resolve approach is acceptable if it preserves correctness after successful runs. Keep `FileASTCache` semantics stable, and do not expand pickle payload size.

Then bound workspace discovery and LSP refresh cost. Update `src/sattlint/core/workspace_discovery.py` so discovery prunes obvious non-source roots that are already large in this repository, especially `artifacts` and `node_modules`, without hiding real SattLine source trees. Move any dependency-name reread that currently happens in `src/sattlint_lsp/workspace_store.py::_workspace_entry_files()` into the discovery result or another cacheable structure so entry-file classification does not reopen every dependency file on each workspace refresh. Keep the LSP snapshot cap in place, but rework scheduling in `src/sattlint_lsp/_server_scan_helpers.py` and refresh behavior in `src/sattlint_lsp/workspace_store.py` so unchanged entries are not rebuilt more broadly than necessary.

After that, reduce repeated semantic loads in structural reporting. `src/sattlint/devtools/_structural_report_graphs.py` should keep a streaming-first implementation and derive dependency-graph, call-graph, graphics-layout, and impact-analysis outputs from one shared graph-input pass wherever possible. The retained-snapshot collection path should either be removed from the main pipeline path or reduced to a thin compatibility adapter used only by tests that explicitly need materialized snapshots. The intended outcome is that one report bundle build no longer means one full workspace semantic rebuild per report family.

Finally, prune repo-wide scan bottlenecks in `src/sattlint/devtools/pipeline_checks.py`, `src/sattlint/devtools/production_summary.py`, and any adjacent repo-audit helper that still falls back to root-level `rglob()` without pruning or shared content reuse. Reuse `tracked_paths`, `PythonSourceScanContext`, or other already computed inventories where available. If a full-tree walk remains necessary, make it top-down and prune directories before descending rather than filtering after traversal.

At each milestone, add focused tests that count work rather than only asserting final payloads. For example, monkeypatch file-reading or validation helpers to assert call counts, monkeypatch `load_workspace_snapshot()` in structural-report tests to prove one shared graph-input flow, and use temporary workspace fixtures that include decoy directories such as `artifacts/` or `node_modules/` to prove discovery prunes them.

## Concrete Steps

Run all commands from the repository root.

Inspect the exact owning seams before editing:

    rg -n "ensure_ast_cache|fast_cache_validation|cache\.validate|ASTCache\.validate" src/sattlint/_app_analysis_loading.py src/sattlint/cache.py src/sattlint/app_analysis.py
    rg -n "_get_base_index|_find_code_with_context|_find_deps_with_context|_load_or_parse|_lookup_cache\.set|_lookup_cache\.forget" src/sattlint/engine.py src/sattlint/cache.py
    rg -n "discover_workspace_sources|_workspace_entry_files|ensure_configured|refresh_workspace|_build_bundle|schedule_workspace_scan|prefetch_entries" src/sattlint/core/workspace_discovery.py src/sattlint_lsp/workspace_store.py src/sattlint_lsp/_server_scan_helpers.py
    rg -n "collect_workspace_graph_inputs|_stream_workspace_graph_reports|collect_repo_file_inventory|build_python_source_scan_context|_compute_kloc" src/sattlint/devtools/_structural_report_graphs.py src/sattlint/devtools/structural_reports.py src/sattlint/devtools/pipeline_checks.py src/sattlint/devtools/leak_detection_scan_paths.py src/sattlint/devtools/production_summary.py

Land the cache-validation milestone first and prove it with the narrowest tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_analysis_project_cache.py tests/parser/test_engine.py -x -q --tb=short

Expected success signal after the first milestone: the focused tests pass, and the updated cache test proves that `fast_cache_validation=True` does not force manifest-wide file validation when a cheap fast-path check is sufficient.

Then land the workspace-discovery and LSP-refresh milestone and run the nearest editor-facing proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_editor_api_workspace_snapshot.py tests/test_lsp_workspace_documents.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py -x -q --tb=short

Expected success signal after the second milestone: discovery tests prove irrelevant large directories are pruned, and the LSP tests still produce the same diagnostics or snapshot behavior for real source files.

Then land the structural-report and repo-scan milestone and run the owning devtools tests:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_structural_reports.py tests/test_structural_reports_graphs.py tests/test_pipeline_collection_graphs.py tests/test_repo_audit.py tests/test_ai_work_map_freshness.py -x -q --tb=short

Expected success signal after the third milestone: the structural-report tests still build valid reports, and the repo-audit or freshness tests prove the inventory path still returns correct results after scan pruning or shared-inventory reuse.

After the focused pytest slices are green, run touched-file quality gates for the whole performance slice:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/_app_analysis_loading.py src/sattlint/cache.py src/sattlint/engine.py src/sattlint/core/workspace_discovery.py src/sattlint/core/semantic.py src/sattlint_lsp/workspace_store.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint/devtools/_structural_report_graphs.py src/sattlint/devtools/structural_reports.py src/sattlint/devtools/pipeline_checks.py src/sattlint/devtools/leak_detection_scan_paths.py src/sattlint/devtools/production_summary.py tests/test_app_analysis_project_cache.py tests/parser/test_engine.py tests/test_editor_api_workspace_snapshot.py tests/test_lsp_workspace_documents.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_structural_reports.py tests/test_structural_reports_graphs.py tests/test_pipeline_collection_graphs.py tests/test_repo_audit.py tests/test_ai_work_map_freshness.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/_app_analysis_loading.py src/sattlint/cache.py src/sattlint/engine.py src/sattlint/core/workspace_discovery.py src/sattlint/core/semantic.py src/sattlint_lsp/workspace_store.py src/sattlint_lsp/_server_scan_helpers.py src/sattlint/devtools/_structural_report_graphs.py src/sattlint/devtools/structural_reports.py src/sattlint/devtools/pipeline_checks.py src/sattlint/devtools/leak_detection_scan_paths.py src/sattlint/devtools/production_summary.py tests/test_app_analysis_project_cache.py tests/parser/test_engine.py tests/test_editor_api_workspace_snapshot.py tests/test_lsp_workspace_documents.py tests/test_lsp_document.py tests/test_lsp_diagnostics.py tests/test_structural_reports.py tests/test_structural_reports_graphs.py tests/test_pipeline_collection_graphs.py tests/test_repo_audit.py tests/test_ai_work_map_freshness.py

If the slice changes LSP loading behavior, restart the language server after validation so editor behavior matches the updated Python side.

## Validation and Acceptance

Acceptance is about bounded work that a human can observe through tests and behavior, not about adding comments that say something is faster. `ensure_ast_cache` must honor the user's fast-versus-full validation setting, and the tests must prove the fast path avoids the manifest-wide `stat()` sweep while still rebuilding stale or malformed cache payloads when needed.

Workspace discovery acceptance requires that a temporary workspace containing real SattLine source files plus large decoy directories such as `artifacts/` or `node_modules/` still finds the correct source files without descending into the decoys. LSP acceptance requires that background diagnostics continue to publish correct diagnostics, but no longer rebuild obviously unaffected entry bundles or reread dependency files more broadly than the updated tests allow.

Structural-report acceptance requires that building the report bundle does not perform one full semantic rebuild per report family and does not retain unnecessary per-entry snapshots in the main pipeline path. The report payloads must stay behavior-compatible with current tests for dependency graphs, call graphs, graphics layout, and impact analysis.

Repo-audit and pipeline acceptance requires that correctness stays stable while the work becomes more bounded. Inventory, freshness, and audit tests must still return the same findings for relevant files, but the implementation must no longer rely on unpruned `rglob("*")` over large irrelevant trees when shared inventory or top-down pruning is available.

## Idempotence and Recovery

This plan is safe to execute in small passes. The fast-cache-validation fix is isolated and can be reverted independently if a regression appears. Discovery-pruning changes should be introduced with temporary-workspace tests so they can be repeated safely and so any over-pruning can be diagnosed by adding one missing directory exception rather than backing out the whole slice.

If buffered lookup-cache persistence proves too risky, recover by keeping the existing lookup-cache data model and only reducing write frequency within one resolve operation rather than across process lifetime. If the structural-report refactor grows too broad, keep the streaming path as the default production flow and leave the materialized-snapshot path in place only for tests that explicitly require it. If a repo-audit inventory optimization changes findings, prefer restoring correctness first and then pruning the next lower-level traversal seam rather than weakening the audit behavior.

## Artifacts and Notes

Capture three kinds of evidence while executing this plan.

The first artifact should prove the cache-validation fix, for example a focused test transcript showing the cache fast path stayed on the cheap branch:

    tests/test_app_analysis_project_cache.py::test_ensure_ast_cache_uses_fast_validation_without_manifest_walk PASSED

The second artifact should prove workspace pruning or LSP bounding on a temporary fixture, for example a test transcript showing discovery ignored decoy large directories while still loading the real entry file.

The third artifact should prove the structural or audit pipeline does less repeated work, for example a test that monkeypatches `load_workspace_snapshot()` or a file-reading helper and asserts the reduced call count after the refactor.

Keep the final recorded evidence concise. This plan does not need synthetic timing claims if call-count or traversal-bounding tests already prove the optimized shape.

## Interfaces and Dependencies

The controlling cache interfaces are `ASTCache.validate()` in `src/sattlint/cache.py`, `ensure_ast_cache()` in `src/sattlint/_app_analysis_loading.py`, and the lookup plus per-file AST cache use inside `src/sattlint/engine.py`. The implementation should preserve the current cache payload formats unless a version bump is strictly necessary. If a payload change is required, update `CACHE_VERSION` and make the invalidation behavior explicit in this document as work proceeds.

The controlling workspace interfaces are `WorkspaceSourceDiscovery` in `src/sattlint/core/workspace_discovery.py`, `load_workspace_snapshot()` in `src/sattlint/core/semantic.py`, `SnapshotBundle` in `src/sattlint_lsp/workspace_store.py`, and the background diagnostic scheduling in `src/sattlint_lsp/_server_scan_helpers.py`. Do not introduce a second, parallel workspace model; reuse these seams.

The controlling devtools interfaces are `WorkspaceGraphInputs` in `src/sattlint/devtools/structural_reports.py`, the graph-input builders in `src/sattlint/devtools/_structural_report_graphs.py`, `PythonSourceScanContext` in `src/sattlint/devtools/repo_audit_shared.py`, and the inventory helpers in `src/sattlint/devtools/pipeline_checks.py` and `src/sattlint/devtools/production_summary.py`. Reuse existing shared contexts first, and add new reusable helpers only when the current seams cannot express the bounded-work behavior this plan requires.
