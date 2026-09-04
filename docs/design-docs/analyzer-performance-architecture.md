# SattLint Analyzer Performance & Extensibility Architecture Plan

Status: Implemented through Phase G (Phases 0–G shipped; see §5 per-phase checkmarks)
Owner: All agents (awaiting approval; then owner = implementer by `AGENTS.md` routing)
Latest: 2026-09-04

## Purpose

This design doc is a single root plan for two goals:

1. **Make SattLint fast** — eliminate the redundant heavy computation that currently dominates
   the ~238s runtime.
2. **Make SattLint easy to extend** — add a new analyzer by declaring dependencies and reading
   shared results, instead of re-running expensive foundations and hand-wiring context.

It also evaluates the user-proposed idea of keeping the analysis *foundation* always ready and
cached like the ASTs.

## Terminology

| Term | Meaning |
| ----- | ------- |
| **Foundation** | The shared, deterministic, AST-derived core an analyzer needs: type graph, typedef index, moduletype index, datatype registry, symbol-table skeleton. |
| **Collected view** | Expensive per-instance results produced **once** and shared (access graph, usage tracker, alias/effect links). |
| **Derived view** | Cheap analysis that reads collected views instead of re-collecting. |
| `AnalysisSharedArtifacts` | **Typed per-target holder** with three distinct, strongly-typed compartments (see §2.1): `foundation`, `collected_views`, `derived_reports`. |

---

## 1. Diagnosis: why it is slow

The ~238s run is dominated by **the same variables analysis being recomputed many times**, not by
unique analyzer logic on `KaHAMPCSøjleLib` (42 files, 1941 typedefs), measured with the
string-overflow scan skipped per request:

| Analyzer | Duration | Why |
| -------- | -------- | --- |
| `mms-interface` | 114.8s | Constructs a **bare `VariablesAnalyzer()`** and re-runs the full analysis; rebuilds `TypeGraph`. Registry passes only `debug`+`config`, so it never sees `shared_artifacts`. |
| `variables` | 52.2s | The canonical expensive pass. `root-traversal` ~24-48s is the core cost (after two prior optimizations). |
| `sfc` | 51.9s | `_SfcAccessCollector` **subclasses `VariablesAnalyzer`** and re-runs the full `.run()` traversal to capture parallel writes. |

**~219s of ~238s is the same variables work repeated three times.**

Two optimizations were already shipped (returned `root-traversal` 52.27s → 23.5s and variables
98.97s → 38.5s on clean runs): nested contract extractors now thread `shared_artifacts`, and
`resolve_moduletype_def_strict` gained a `typedef_index` to avoid a 1941-element linear scan.

**Root cause (architectural):** analyzers are treated as independent, opaque functions rather than
consumers of a shared, layered, memoized result. Dependencies (`requires=("variables",)`) only
order execution — they do **not** reuse the dependency's output.

---

## 2. Target architecture

A **layered pipeline** with explicit dependencies and memoized per-target results.

```
                 ┌────────────────────────────────────────────────────┐
                 │  AnalysisSharedArtifacts (per-target)             │
                 │  ┌──────────────────────────────────────────────┐ │
                 │  │ foundation : Foundation        (app-owned)   │ │
                 │  │ collected_views : CollectedViews (once)      │ │
                 │  │ derived_reports : ReportsByKey  (memoized)   │ │
                 │  └──────────────────────────────────────────────┘ │
                 └────────────────────────────────────────────────────┘
                                   ▲
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
   ┌───────────┐             ┌───────────┐              ┌───────────┐
   │ foundation│  ─dep──▶   │ variables │  ─dep──▶    │   sfc     │
   │ (layer 0) │            │ (layer 1) │             │ (layer 2) │
   └───────────┘             └───────────┘             └───────────┘
                                  │ dep                     │ dep
                                  ▼                         ▼
                            ┌───────────┐              ┌───────────┐
                            │   mms     │              │ dataflow  │
                            │ (layer 2) │              │ (layer 2) │
                            └───────────┘              └───────────┘
```

**Core rules**

1. **Foundation is owned by the app** (not any analyzer), built **lazily but centrally** via
   `shared_artifacts.ensure_foundation()`, and published into
   `AnalysisContext.shared_artifacts.foundation`. See §3.5 for why lazy construction is preferred
   over "always ready".
2. **Compute-once / consume-many.** An analyzer that declares `requires=("variables",)` is handed
   the already-computed canonical result (in `collected_views` and `derived_reports`) — it never
   re-runs the underlying instance traversal.
3. **Every analyzer receives `AnalysisContext`** (which carries `shared_artifacts`). No analyzer
   depends on `context_kwargs` opt-in to reach shared state.
4. **Cheap by construction.** The one instance-aware collection pass happens exactly once;
   everything else is a derived consumer of that pass.

### 2.1 Shared artifact API (typed, not a generic dict)

Shared state is deliberately split into **three typed compartments** instead of one generic
`computed` dictionary. A generic dictionary is convenient initially but becomes weakly typed,
hard to discover, and easy to access by the wrong name. Compartments:

| Compartment | Type | Contents | Written by | Read by |
| ----------- | ---- | -------- | ---------- | ------- |
| `foundation` | `Foundation` | type graph, typedef index, moduletype index, datatype registry, symbol-table skeleton | app-owned `ensure_foundation()` | all analyzers (immutable) |
| `collected_views` | `CollectedViews` | one instance-aware collection pass: access graph, usage tracker, alias links, effect flow | variables collection pass | sfc, mms, derived analyzers |
| `derived_reports` | `ReportsByKey` | memoized per-analyzer `Report`s | each analyzer (once) | dispatcher + dependent analyzers |

Each compartment is a typed dataclass with named fields (e.g. `collected_views.access_graph`,
`derived_reports.variables`), so field access is discoverable and Pyright-checked. Loose dictionaries
are used only internally, never as the cross-analyzer contract.

### 2.2 What the plan is NOT

Foundation caching is useful but is **not** the deepest speed win. The largest gain comes from
guaranteeing **one instance-aware collection pass** and making every other analyzer a derived
consumer of it. Sequencing below (§8) therefore fixes traversal redundancy *before* adding
persistent foundation caching.

---

## 3. Foundation as a cacheable, app-owned service

**Yes — this is a good idea**, and it mirrors the existing AST-cache mechanism (see `cache.py`,
`_app_analysis_loading.py:ensure_ast_cache`).

### 3.1 What belongs in the cached foundation

The foundation is a **pure, deterministic function of the parsed ASTs** — safe to content-address
and regenerate on file change:

- Type graph (`TypeGraph.from_basepicture`)
- Typedef index (the 1941-element index; avoids linear casefold scans)
- Moduletype index
- Datatype registry
- Symbol-table **skeleton** (structure only)

### 3.2 What must stay OUT of the cached foundation

These are **instance-sensitive** (depend on submodule wiring / instance trees, not file bytes) and
must be recomputed per actual traversal, *not* cached as a blob:

- `root-traversal`
- Per-instance symbol-table population
- Access graph / usage / alias / effect flow

Caching these as a static blob would silently produce stale results on wiring changes — the same
staleness risk the AST cache already avoids by keying on source content.

### 3.3 Cache mechanics

- **Key**: hash of the same input file content/mtime set the AST cache uses, plus a
  `FOUNDATION_CACHE_SCHEMA_VERSION` and the project cache key. Mirror
  `compute_analysis_report_cache_key` (`cache.py:397`).
- **Invalidation — conservative at first**: recompute the foundation **on any source change**.
  Selective invalidation (recomputing only the typedef/moduletype/instance-wiring-relevant subset)
  is deferred until measurements show it matters. Conservatism first is safer because reach edges
  between constructs are easy to miss on an initial pass.
- **Read-only shared state**: analyzers may consume the foundation but must never mutate it.

### 3.4 Separation of cache keys

Keep the **foundation** cache key (source-content-derived) distinct from the **analyzer/report**
cache key (rule/config-derived, see `PROJECT_CACHE_CONFIG_KEYS`). Changing a lint rule must not
invalidate the foundation, and editing a source file must not have to discard rule-derived caches.

Why the caching is sound: the foundation is a pure function of ASTs, so staleness risk matches the
already-proven AST cache, and it is exactly the layer the three slow analyzers currently rebuild
independently — caching it once is the direct architectural fix, not a compatibility shim.

### 3.5 Lazy but centralized construction (not "always ready")

"Always ready" risks doing unnecessary work on **every startup and every file-watch event**, even
when no analyzer needs the foundation (e.g. a config-only run, or an analyzer that only reads
`derived_reports`). Preferred shape:

```
shared_artifacts.ensure_foundation() -> Foundation
```

- A single **application-owned service** owns the persistent/loaded foundation.
- `ensure_foundation()` is **lazy**: it builds (or loads from the persistent cache) the foundation
  only when an analyzer actually requests it, then memoizes it on `shared_artifacts.foundation`.
- On a file-change event the app **invalidates** the cached foundation rather than eagerly rebuilding
  it; the rebuild happens on the next `ensure_foundation()` call. This keeps the model "always
  consistent" without "always busy".
- Analyzers never construct the foundation themselves; they call/consume `ensure_foundation()` via
  the app-owned service — eliminating the ~17s × 3 redundant rebuilds once shared.

---

## 4. Standard analyzer contract (extensibility)

Replace the loose `analyzer_attr(base_picture, debug=, config=, ...)` + `context_kwargs` indirection
with a declarative, compiler-checked contract. New analyzer = write `run(context)` + declare.

```python
register_analyzer(
    key="sfc",
    requires=("variables",),       # topological order + result reuse
    contributes="derived_reports.sfc",  # typed compartment + key
)

def analyze_sfc(context: AnalysisContext) -> SimpleReport:
    sa = context.shared_artifacts
    sa.ensure_foundation()                     # lazy, app-owned
    access_graph = sa.collected_views.access_graph   # typed, discoverable
    ...
    return report
```

- Dispatcher topologically orders by `requires`, runs each analyzer **once**, memoizes the resulting
  `Report` into `derived_reports[key]`.
- Adding a new analyzer no longer requires understanding `context_kwargs`/provider plumbing; the
  framework wires registration, ordering, shared-artifact read/write, and telemetry automatically.
- `requires=("variables",)` means "consume the canonical variables collection", **not** "run
  variables again".

Use `direct_context=True` convention so every analyzer receives `AnalysisContext` and there is no
way for a spec to (accidentally) omit access to `shared_artifacts` — the exact bug that cost
`mms-interface` ~114s.

---

## 5. Phased roadmap

Each phase is independently testable; the 1135-test suite must stay green and issue output must be
behaviorally identical (see the canonicity note below) after every phase.

**Canonicity note (not necessarily byte-identical):** asserting *byte-identical* output may be
stricter than necessary if issue ordering is not formally deterministic across runs. Prefer asserting
**identical issue sets** plus **stable, deterministic ordering** — or, first verify empirically that
byte identity already holds before enforcing it.

**Success criteria are split on two axes, in order:**
1. **Reduced foundation-build count** — the same AST-derived foundation is built once, not 3×
   (Phase A). This alone does **not** imply a major speedup, because mms/SFC may still repeat the
   expensive traversal even when the foundation is shared.
2. **Reduced traversal count** — the instance-aware collection pass runs once (Phase B/D). This is
   the deep, dominant win.
A phase is only "done" when its success criterion (counts instrumented, per below) is met.

### 5.1 SFC overlay caveat

Consuming the existing access graph is sufficient for SFC **only if** the primary variables pass
already records everything parallel-write detection needs. If parallel writes rely on information
the primary pass never captures, the overlay approach silently fails. Therefore:
- First verify, with a focused test, that the primary pass records branch-level write provenance.
- **If not, add explicit collection hooks to the primary pass** (e.g. `on_branch_write(path, kind)`),
  so parallel-write data lands in `collected_views` during the single collection pass — never in a
  second full `.run()`.

### Phase 0 — Instrument and baseline  [x] shipped
- Add counters that assert **how many times foundation construction occurs** and **how many times
  `root-traversal` runs** per full target analysis.
- Record the baseline for `KaHAMPCSøjleLib`: expect ~3 foundation builds and ~3 traversals today.
- Every later phase asserts the drop (foundation → 1; then traversal → 1).
- *Shipped:* `variable_root_traversals` counter + process-wide `_process_root_traversal_count` /
  `count_process_root_traversals()`; profile text in `app_analysis.py`; baseline 3 traversals.

### Phase A — Thread shared state everywhere  [x] shipped
1. Create the `AnalysisSharedArtifacts` holder **unconditionally** for every target
   (`_app_analysis_checks.py:96-104`), so `shared_artifacts` is always present.
2. Thread `shared_artifacts` into `mms-interface`:
   - registry spec `_registry_spec_templates.py:72`: add `analysis_context`/`shared_artifacts` to
     `context_kwargs`
   - `analyze_mms_interface_variables` (mms/`__init__.py:210`): consume the shared foundation instead
     of rebuilding `TypeGraph`.
3. Pass `shared_artifacts` to `_SfcStepContractCollector` (sfc/`__init__.py:482`).
- **Success criterion:** foundation builds drop from 3 → 1. Do not claim a traversal win here.
- *Shipped (A/C):* unconditional shared holder; mms spec `requires=("variables",)`; mms reuses the
  canonical variables result (~102s → ~1.5s); `_SfcStepContractCollector` threads `shared_artifacts`.

### Phase B — Memoize the canonical variables result  [x] shipped
4. Add the typed `derived_reports: ReportsByKey` + `collected_views: CollectedViews` compartments to
   `AnalysisSharedArtifacts`; record the variables `Report` and its collected views once.
5. Add a dispatcher memoization check so `requires=("variables",)` reuses the canonical result and
   guarantees a single execution.
- *Shipped:* `AnalysisSharedArtifacts.variable_analyzer` slot populated in `analyze_variables`; the
  `derived_reports` compartment is typed as a `ReportsByKey` (`MutableMapping`) so dispatcher and
  dependent analyzers get a discoverable, named type (not a bare dict) for memoized per-analyzer
  reports.

### Phase C — Make mms a derived consumer  [x] shipped (rolled into Phase F collected views)
6. Refactor `analyze_mms_interface_variables` to consume `collected_views`/`derived_reports.variables`
   (its `usage_locations` / inventory) instead of holding a bare `VariablesAnalyzer`.
- **Success criterion:** mms issue output equals the pre-refactor output while adding no traversal.
- *Shipped:* mms-interface ~1.5ms; fully migrated onto typed `collected_views` (`usage_tracker` +
  `alias_links`) in Phase F.

### Phase D — Refactor SFC around explicit collection hooks  [x] shipped
7. Verify (focused test) whether the primary pass records branch-level write provenance.
8. If not, add **explicit collection hooks** to the primary pass (per §5.0), landing parallel-write
   data in `collected_views`. `_SfcAccessCollector` becomes a derived overlay reading those views —
   never a second full `.run()`; `_SfcStepContractCollector` reuses `ensure_foundation()`.
- **Success criterion:** total traversals drop from 3 → 1 (this is the largest speed phase).
- *Shipped:* canonical `VariablesAnalyzer.run()` as `_SfcAccessCollector`; `_SfcStepContractCollector`
  threads `shared_artifacts`; sfc ~46ms (was a separate ~33-40s traversal); `process-root-traversals`
  now 1 (was 3). Investigation showed the hand-rolled lightweight SFC walk was both slower (73s vs
  33s) *and* skipped the canonical filtering, so the canonical run is the correct colletion path.

### Phase E — Foundation as an app-owned, cacheable service (only after D)  [x] shipped
9. Extract foundation construction into a single `ensure_foundation(project) -> Foundation` service
   (`shared_artifacts.ensure_foundation()`), lazy-but-centralized per §3.5.
10. Add `FOUNDATION_CACHE_SCHEMA_VERSION` + content-derived cache key; store/load like the AST cache.
11. Invalidate conservatively on **any** source change; rebuild lazily on next `ensure_foundation()`.
12. Keep `root-traversal` and instance-sensitive population out of the cached blob (§3.2).
- *Shipped:* `AnalysisSharedArtifacts.ensure_foundation(build_fn)` lazy + memoized;
  `FOUNDATION_CACHE_SCHEMA_VERSION` + `compute_foundation_cache_key` (`cache.py`); `FoundationCache`
  store/load (mirrors `FileASTCache`) in `_cache_classes.py`; app seeds the content-derived inputs in
  `_app_analysis_checks._seed_foundation_cache_data`. Verified miss→hit: `variable-foundation-builds`
  = 1 (write) then 0 (disk restore) across two runs with an identical issue set (26010/6/0/276); the
  ~71MB foundation blobs to `~/.cache/sattlint/foundation/`. §3.2 instance-sensitive data is never
  cached (`variable-root-traversals` stays 1). Selective invalidation remains deferred per §3.3.

### Phase F — Split variables into collect + views  [x] shipped
13. Extract the one-time collection pass; make cheap issue-kind analyzers
    (`field-read/never-read`, `layout-overlap`, ...) pure derived views over the collected access
    graph / usage tracker.
14. This is the biggest single lever for extensibility: near-zero marginal cost to add issue kinds
    and analyzers.
- *Shipped:* typed `CollectedViews` compartment (access_graph, usage_tracker, alias_links,
  effect_flow, contexts_by_module_path, root_env, typedef_index) populated once from the canonical
  run; `mms` migrated off analyzer internals onto `collected_views`; sfc unchanged (reads SFC-specific
  `parallel_writes` from the canonical analyzer). `collected_views` matches analyzer state exactly
  (68651 events, 12998 aliases, 3020 contexts); full suite green.

### Phase G — Public developer API  [x] shipped
15. Provide `register_analyzer`/decorator (§4) wiring registration, dependency ordering, shared
    artifact read/write, and telemetry.
16. Add a `scripts/`-style benchmark harness that asserts the Phase 0 counters on the corpus target,
    to guard against regressions.
- *Shipped:* `register_analyzer(key=, requires=, contributes=)` decorator +
  `get_registered_plugin_analyzers()` in `analyzers/plugin.py` (plus `clear_registered_plugin_analyzers()`
  for test isolation); `AnalyzerSpec.contributes` field; plugin specs merged into
  `registry.get_default_analyzers()` and exported from `sattlint.analyzers.registry`.
  `scripts/benchmark_analyzer_counters.py` asserts `process-root-traversals == 1`,
  `variable-foundation-builds == 1`, `variable-root-traversals == 1` on a corpus target that exists in
  this repo (defaults to `MinimalProgram`, since the proprietary `KaHAMPCSøjleLib` corpus is not shipped
  here; pass `--target` to point at a configured real target). The harness is cache-isolated (scratch
  `XDG_CACHE_HOME` + `use_cache=False` loader) so each iteration measures a genuinely cold heavy pass and
  does not replay cached foundation/report counts. Focused tests for the API live in
  `tests/test_analyzer_architecture.py` (registration semantics, casefold key dedup, registry reset,
  merge into `get_default_analyzers`, and end-to-end run through `run_registry_analyzer` receiving the
  full `AnalysisContext`/shared artifacts with a `requires=("variables",)` dependency satisfied without
  re-traversal).

---

## 6. Failure & concurrency behavior

Explicitly specified so shared/cached state cannot silently corrupt a run.

- **Foundation construction fails.** `ensure_foundation()` raises a typed, catchable error, the
  target is marked failed (like existing parser/loader failures), and the run is aborted cleanly for
  that target — a broken foundation must never produce partially-valid analyzer output. No analyzer
  proceeds with a half-built foundation.
- **Two analyzers request the same result concurrently.** The dispatcher is currently **single
  threaded** (analysis runs sequentially per target) — document and enforce that invariant. The
  shared artifact API is a per-target, single-owner structure; if live-diagnostics ever becomes
  concurrent, `ensure_foundation()` and `derived_reports` memoization must be protected by a per-target
  lock and built under it (double-checked locking), so only one builder runs. Do not introduce
  concurrency in this plan's scope; just specify the locking contract for a future move.
- **A file changes while analysis is running.** The in-flight run keeps the snapshot it read
  (`shared_artifacts` is captured per target iteration). The file-watch handler invalidates the
  *persistent* foundation and schedules a fresh analysis for the next cycle; it never mutates an
  in-progress `shared_artifacts`. This matches how ASTs are already snapshotted per run.
- **Cached data has an incompatible schema.** On load, compare the stored
  `FOUNDATION_CACHE_SCHEMA_VERSION` against the current constant; on mismatch, discard the cache and
  rebuild (no partial migration in v1). Same policy as the existing AST/report caches.

## 7. Guardrails

- Keep the 1135-test suite green and analyzer issue output behaviorally identical after each phase
  (identical issue sets + stable ordering; verify byte identity first before enforcing it).
- Keep touched Python files Ruff-clean and Pyright strict-clean.
- Follow `AGENTS.md` restrictive-command rules (read-only git only; no `rm`/`sudo`/package mgmt).
- Do not modify SattLine source files outside this repository unless explicitly requested.
- Treat cached foundation objects as read-only shared state.
- Do not skip Phase 0 instrumentation; every phase must assert the foundation/traversal-count drop.
- Prefer root-cause fixes over compatibility shims (per `AGENTS.md` and `core-beliefs.md`).

## 8. Recommended implementation order

(Confirmation of the phases above, in priority order.)

1. **Instrument** foundation-construction and `root-traversal` counts (Phase 0).
2. **Make `shared_artifacts` unconditional** (Phase A-1).
3. **Memoize the canonical variables result** into typed compartments (Phase B).
4. **Fix mms-interface to consume it** — foundation-thread first, then full derived consumption
   (Phase A-2/C).
5. **Refactor SFC around explicit collection hooks** — the biggest speed win; reach a total
   traversal count of 1 (Phase D).
6. **Only then add persistent foundation caching** (Phase E) — lazy-but-centralized, conservative
   invalidation.
7. **Finally introduce the public `register_analyzer` API** (Phase G).

The order deliberately puts **traversal redundancy elimination before foundation caching**, because
foundation caching is useful but is not the deepest win: the dominant gain is one instance-aware
collection pass with all other analyzers as derived consumers.

## 9. Open questions

1. Can `mms-interface` fully consume `derived_reports.variables` / `collected_views` (its
   `usage_locations` / inventory) instead of holding a bare `VariablesAnalyzer`? Needs a semantic
   equivalence check against current output.
2. Does the primary variables pass already record branch-level write provenance, or do SFC's
   parallel writes require new collection hooks? (Resolve in Phase D-7 before attempting the overlay.)
3. Is analyzer issue ordering formally deterministic today? (Determines whether the gate is
   "identical sets + stable ordering" or strict byte identity.)
4. Should the foundation cache be invalidated on **any** source change, or only on changes affecting
   typedef/moduletype/instance-wiring constructs? (Conservatively: any change, per §3.3.)

## 10. File map

- Registry/context: `src/sattlint/analyzers/_registry_spec_templates.py`, `_registry_specs.py`,
  `_registry_dispatch.py`
- Framework/context/shared: `src/sattlint/analyzers/framework/__init__.py`
- App orchestration/cache: `src/sattlint/_app_analysis_checks.py`, `_app_analysis_loading.py`,
  `cache.py`, `_cache_manager.py`
- Variables foundation: `src/sattlint/analyzers/variables/__init__.py`
- mms: `src/sattlint/analyzers/mms/__init__.py`, `_mms_interface_analysis.py`
- sfc: `src/sattlint/analyzers/sfc/__init__.py`, `_sfc_collectors.py`, `_sfc_step_contracts.py`
- Resolution/core hot path: `src/sattlint/resolution/paths.py`, `symbol_table.py`,
  `_moduletype_resolution.py`
