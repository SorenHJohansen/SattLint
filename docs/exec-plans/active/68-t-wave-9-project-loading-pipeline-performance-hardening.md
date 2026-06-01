# T-Wave-9 Project Loading Pipeline Performance Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan reduces the time and I/O cost of loading a SattLine project for analysis by attacking the hottest parts of the current project-loading pipeline rather than adding more top-level cache toggles. After this work lands, a warm project-cache hit should avoid deserializing a large project pickle just to decide that the cache is valid, a file-AST cache hit should avoid repeating purely local structural validation work, and cold-cache dependency loading should stop paying the full wall-clock penalty of strictly serial sibling resolution when parallel-safe work exists.

The user-visible proof is practical. A maintainer should be able to warm the project cache once, rerun the same analysis target, and observe that cache validation no longer spends its dominant time loading a large pickle before any manifest check. They should also be able to refresh AST caches and analyze a dependency-heavy target while stage timings show reduced time in validation and dependency traversal for unchanged inputs. The acceptance bar is not "new helper methods exist"; it is faster repeated loads with correctness preserved by focused regression tests and stable CLI behavior.

## Progress

- [x] (2026-06-01 00:00Z) Created this ExecPlan from the current loading-pipeline review and anchored the work to the owning seams in `src/sattlint/cache.py`, `src/sattlint/_app_analysis_loading.py`, `src/sattlint/engine.py`, and `src/sattlint/validation.py`.
- [x] (2026-06-01 00:00Z) Confirmed the current baseline contract: project-cache validation in `ASTCache` still requires a loaded payload, `load_project()` and `ensure_ast_cache()` still call `cache.load()` before `cache.validate()`, and the previous active `62` path conflicted with an already completed `62` plan.
- [ ] Split project-cache manifest metadata from the serialized project payload so full validation can stat files without deserializing the project pickle.
- [ ] Update app-side project-cache call sites to validate by key or manifest sidecar before loading the cached project tuple.
- [ ] Separate local structural validation from dependency-sensitive validation so file-AST cache hits can skip only the safe subset of repeated validation work.
- [ ] Add a versioned file-AST validation marker and use it to bypass duplicate local validation on cache hits while preserving dependency-sensitive checks in project resolution.
- [ ] Restructure dependency walking so sibling discovery and parse work can run in parallel without corrupting shared loader state or graph mutation.
- [ ] Reduce serialized project size by moving eager merged-definition materialization away from the canonical cached project object.
- [ ] Re-measure the stage timings and document the before/after effects for cache-hit validation, AST-hit validation, and cold-cache dependency resolution.

## Surprises & Discoveries

Observation: the previous active performance path conflicted with an already completed `62` plan and held two different follow-on plans in one file.
Evidence: `docs/exec-plans/completed/62-t-wave-8-performance-and-scalability-hardening.md` already exists, while the former active `62` file contained both analyzer-execution and project-loading follow-on content.

Observation: the current project-cache API shape forces the app layer to unpickle before it can answer the cheap question of whether the manifest is still valid.
Evidence: `ASTCache.validate()` in `src/sattlint/cache.py` accepts an already-loaded payload object, and `load_project()` plus `ensure_ast_cache()` in `src/sattlint/_app_analysis_loading.py` call `cache.load()` before `cache.validate()`.

Observation: "skip validation on file-AST cache hit" is not a single safe toggle in the current loader.
Evidence: `_load_or_parse()` in `src/sattlint/engine.py` returns a cached `BasePicture`, but `_visit()` performs validation later using `graph.datatype_defs` and `graph.moduletype_defs`, so some validation work depends on already-resolved external definitions rather than only on the local file.

Observation: the most obvious concurrency seam is not thread-safe as currently implemented.
Evidence: `SattLineProjectLoader` mutates `_visited`, `_visit_stack`, `_lookup_cache`, `_base_indexes`, `_lib_by_name`, and `ProjectGraph` while also sharing parser and transformer instances.

Observation: the current merged project object likely amplifies both disk and memory cost by copying dependency definitions into the root `BasePicture`.
Evidence: `merge_project_basepicture()` in `src/sattlint/engine.py` uses `replace()` to build a synthetic `BasePicture` with full `datatype_defs` and `moduletype_defs` lists sourced from the project graph.

## Decision Log

- Decision: assign the project-loading follow-on a new active identifier rather than reusing `62`.
  Rationale: `62` already belongs to a completed plan, so loader-pipeline follow-on work needs a new id to avoid tracker ambiguity.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

- Decision: sequence the work as manifest split first, validation split second, parallel dependency resolution third, and merged-project size reduction fourth.
  Rationale: the first two changes are the highest-ROI improvements with the smallest correctness surface. They also simplify measurement for later concurrency and representation changes.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

- Decision: do not treat all validation as skippable on file-AST cache hits.
  Rationale: some validation in project loading is dependency-sensitive because it uses externally resolved datatype and moduletype definitions. Only local structural checks should move behind a versioned file-AST validation marker.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

- Decision: avoid directory-`mtime` shortcuts as a correctness gate for project-cache validation.
  Rationale: directory metadata is not a reliable signal for in-place file-content edits, so it is unsuitable as the primary validity proof for a strict analysis cache.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

- Decision: treat the canonical cached project object as `root BasePicture + ProjectGraph`, and make any merged analyzer view a derived representation rather than the only persisted form.
  Rationale: this preserves a smaller source-of-truth model and reduces the chance that eager merged copies dominate serialization cost.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This plan has not been implemented yet. Its immediate outcome is to convert the loading-pipeline analysis into an executable, repo-native plan with explicit owning files, acceptance criteria, and phased sequencing. The main risk to watch during implementation is accidental broadening: this plan should stay focused on measurable loading-path cost in the project cache, file-AST cache, dependency walker, and merged-project representation.

The largest technical caution is that some of the proposed speedups sound simple at the symptom level but cross abstraction boundaries in the current implementation. The plan therefore intentionally spends a full slice on separating local versus dependency-sensitive validation before any skip path is introduced, and it treats parallel dependency resolution as a loader redesign rather than a one-line thread-pool patch.

## Context and Orientation

The owning project-cache seam lives in `src/sattlint/cache.py`. `compute_cache_key()` computes the high-level project-cache key from config values only. `ASTCache.save()` currently serializes a payload that contains both the project tuple and the manifest of input files. `ASTCache.validate()` currently takes a loaded payload and checks schema version, optional fast-mode behavior, and manifest validity. Because the manifest lives inside the pickle payload, any caller that wants to do a full validity check must deserialize the cached object first.

The app-level project loading seam lives in `src/sattlint/_app_analysis_loading.py`. `load_project()` creates the cache key, calls `cache.load()`, and only then asks `cache.validate()` whether the cached project is valid. `ensure_ast_cache()` repeats the same shape across multiple targets when refreshing or probing AST caches. This means warm-cache validation cost is partly determined by pickle I/O and deserialization cost rather than only by stat calls over the manifest.

The loader seam lives in `src/sattlint/engine.py`. `SattLineProjectLoader.__init__()` creates the parser, transformer, lookup cache, file-AST cache, and per-base directory indexes. `_find_code_with_context()` and `_find_deps_with_context()` locate source and dependency-list files for each requested name. `_load_or_parse()` either returns a cached `BasePicture` from `FileASTCache` or parses a fresh one. `resolve()` and `_visit()` perform recursive dependency traversal, local and dependency-sensitive validation, graphics companion attachment, conflict collection, and definition indexing into `ProjectGraph`.

The main validation seam lives in `src/sattlint/validation.py`. `validate_transformed_basepicture()` currently acts as the loader's broad post-transform validation entry point. For this plan, "local structural validation" means checks that depend only on one file's transformed AST. "Dependency-sensitive validation" means checks that rely on external datatype or moduletype definitions, cross-file parameter compatibility, or other information gathered during project resolution.

The representation seam lives at `merge_project_basepicture()` in `src/sattlint/engine.py`. Today the loader persists a derived project object that eagerly copies all dependency definitions into a synthetic root `BasePicture`. That shape is convenient for analyzers that expect one object, but it inflates the serialized payload and duplicates data already represented in the project graph.

The focused regression coverage already exists near the owner seams. `tests/parser/test_cache.py` covers cache helper persistence and manifest validation behavior. `tests/test_app_analysis_project_cache.py` covers app-side project-cache routing and fast/full validation flags. `tests/parser/test_engine_loader_helpers.py` covers loader stage timings and `_load_or_parse()` behavior. `tests/parser/test_engine.py` covers merge behavior and dependency-walk outcomes.

## Plan of Work

Start with `src/sattlint/cache.py` and split the project-cache manifest from the project payload. Add a manifest sidecar path helper alongside the existing pickle path helper. Change `ASTCache.save()` so it snapshots manifest metadata once, writes that manifest to a small JSON sidecar, and writes the project pickle without embedding the full manifest. Change `ASTCache.validate()` so the primary validation path accepts a cache key, reads the sidecar manifest, and performs fast or full validation without deserializing the project pickle. Preserve backward compatibility long enough to treat old cache entries as misses or to fall back safely while the schema rolls forward.

Then update the app-layer call sites in `src/sattlint/_app_analysis_loading.py`. `load_project()` should validate the cache entry by key before loading the cached project tuple. On a valid cache hit, it can then call `cache.load()` and attach manifest metadata to the graph as it does today. `ensure_ast_cache()` should stop using `cached.get("files")` as the manifest-presence probe because the manifest will no longer live inside the project pickle. Instead, it should ask the cache whether manifest metadata exists for the key and whether the entry is valid under `fast_cache_validation`.

After the project-cache contract is corrected, split validation responsibilities. Refactor `validate_transformed_basepicture()` or add adjacent helpers in `src/sattlint/validation.py` so the loader can perform local structural validation separately from dependency-sensitive validation. The loader path in `src/sattlint/engine.py` should record which local validation schema version has been applied to a cached file AST. On a `FileASTCache` hit, `_load_or_parse()` may then skip only the local structural pass when the schema version matches. `_visit()` must still perform the dependency-sensitive pass that uses `graph.datatype_defs` and `graph.moduletype_defs`.

Next, restructure dependency resolution in `src/sattlint/engine.py` rather than sprinkling locks over the current implementation. Separate read-only sibling discovery and parse work from shared graph mutation, validation, version-conflict collection, and indexing. The first safe target is parallel sibling file discovery plus parse for dependency names at the same depth with worker-local parser state and no direct `ProjectGraph` mutation inside the workers. Once those results are collected, keep graph updates and dependency-sensitive validation on the main thread until a clearer concurrent graph contract exists.

Then reduce serialized project size by moving eager merged-definition materialization to the analyzer boundary. Keep the cached project object as the root `BasePicture` plus `ProjectGraph`, and either make `merge_project_basepicture()` produce a smaller derived analyzer view on demand or teach the analyzer/reporting entry points to consume `root_bp + graph` directly where practical. This change should preserve current analyzer behavior while avoiding a large synthetic `BasePicture` as the only persisted form.

Finally, measure and document the effects. Reuse the existing stage-timing sink in the loader to record before/after timings for `load_or_parse`, `validate`, `attach_graphics`, and `index`, and add any narrow timing needed for project-cache validation itself. Record those measurements in this plan's `Progress`, `Surprises & Discoveries`, and `Artifacts and Notes` sections as slices land.

## Concrete Steps

Run all commands from the repository root.

Start with the cache-owner tests while changing the manifest contract:

    ./scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_cache.py -x -q --tb=short
    ./scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_analysis_project_cache.py -k "fast_path or slow_path or ensure_ast_cache" -x -q --tb=short

Expected behavior for the manifest split slice:

    - project-cache tests pass with sidecar manifest coverage
    - app-level cache tests prove that validation can occur before loading the project payload
    - stale or missing sidecar manifests cause a rebuild instead of a bad cache hit

Then validate the loader validation split and file-AST cache behavior:

    ./scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_engine_loader_helpers.py -x -q --tb=short
    ./scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_engine.py -k "merge_project_basepicture or load_or_parse or dependency" -x -q --tb=short

Expected behavior for the validation split slice:

    - cached file ASTs can bypass only the local structural validation pass when the validation schema matches
    - dependency-sensitive validation still runs during project resolution and still surfaces compatibility warnings or errors
    - loader stage timing coverage remains intact

Use touched-file static checks after each Python slice:

    python scripts/run_repo_python.py -m ruff check src/sattlint/cache.py src/sattlint/_app_analysis_loading.py src/sattlint/engine.py src/sattlint/validation.py tests/parser/test_cache.py tests/test_app_analysis_project_cache.py tests/parser/test_engine.py tests/parser/test_engine_loader_helpers.py
    python scripts/run_repo_python.py -m pyright src/sattlint/cache.py src/sattlint/_app_analysis_loading.py src/sattlint/engine.py src/sattlint/validation.py tests/parser/test_cache.py tests/test_app_analysis_project_cache.py tests/parser/test_engine.py tests/parser/test_engine_loader_helpers.py

When the parallel dependency slice lands, rerun the narrow loader suites and then one behavior-level proof on a dependency-heavy target through the repo-owned AST refresh path:

    ./scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_engine.py tests/parser/test_engine_loader_helpers.py -x -q --tb=short
    ./scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_analysis_project_cache.py -k "force_refresh_ast or load_project" -x -q --tb=short

Record before/after timing evidence by running one representative target twice, once from a cold cache and once from a warm cache, with debug timing enabled through the existing app-analysis path. Save the resulting timing snippets under `Artifacts and Notes` in this plan.

## Validation and Acceptance

Acceptance for the manifest split slice requires more than a new sidecar file. A warm project-cache hit must be provably validatable before the large project payload is deserialized. Focused tests must demonstrate that a stale manifest forces rebuild, a missing manifest forces rebuild, and a valid manifest permits the later payload load.

Acceptance for the file-AST cache slice requires that unchanged cached ASTs stop repeating only the local structural validation work, while dependency-sensitive validation still runs and still catches cross-file incompatibilities. The loader must not silently skip warnings or correctness checks that rely on external definitions.

Acceptance for the dependency-resolution slice requires a measurable wall-clock improvement on a dependency-heavy cold-cache run without changing resolution results, warnings, or missing-library behavior. The loader must remain deterministic from the caller's perspective: the same target, config, and filesystem state should produce the same graph contents and warnings before and after the concurrency change.

Acceptance for the representation slice requires that analyzers still receive the definitions they need, but the canonical cached project object no longer pays the full cost of an eagerly merged synthetic `BasePicture` unless a downstream consumer explicitly requests that view.

The overall plan is complete when focused tests pass, touched-file Ruff and Pyright checks pass, and the plan includes captured before/after evidence for cache validation time, validation duplication reduction, and one cold-cache dependency-resolution measurement.

## Idempotence and Recovery

Cache-schema work must treat older cache entries as safe misses. If a new manifest sidecar is absent or unreadable, the system should rebuild instead of trying to coerce the old payload into a partially trusted state.

File-AST validation markers must be versioned so future validation-rule changes can invalidate only the stale local-validation proof without forcing unrelated loader rewrites. Bumping the validation schema must make old file-AST entries fall back to revalidation rather than failing analysis.

Parallel dependency work should land behind a design that can safely fall back to serial resolution for debugging and rollback. If a concurrency regression appears, maintainers need a minimal path to restore the old serial behavior while keeping the earlier cache-contract improvements.

Because the loader and cache surfaces are shared by app-analysis and other entry points, each slice should remain independently shippable. Do not combine manifest split, validation refactor, concurrency redesign, and merge-representation changes into one unreviewable patch.

## Artifacts and Notes

Current baseline observations captured before implementation:

    - `src/sattlint/cache.py`: `ASTCache.validate()` accepts a loaded payload object rather than a cache key
    - `src/sattlint/_app_analysis_loading.py`: `load_project()` and `ensure_ast_cache()` call `cache.load()` before `cache.validate()`
    - `src/sattlint/engine.py`: `_load_or_parse()` returns cached `BasePicture` objects, but `_visit()` performs broad validation later with external definition context
    - `src/sattlint/engine.py`: `merge_project_basepicture()` eagerly copies project graph definitions into a synthetic root `BasePicture`

Current owner-suite anchors for implementation:

    - `tests/parser/test_cache.py`
    - `tests/test_app_analysis_project_cache.py`
    - `tests/parser/test_engine_loader_helpers.py`
    - `tests/parser/test_engine.py`

Implementation note for future updates to this plan:

    When a slice lands, add one short before/after timing snippet here. Keep the snippet focused on one observable change such as "warm cache validation avoided project pickle load" or "cold-cache dependency walk dropped from Xs to Ys on target Z".

## Interfaces and Dependencies

The cache owner remains `src/sattlint/cache.py`. At the end of the manifest split slice, `ASTCache` should expose a manifest-aware validation surface that can answer validity by key without requiring prior payload deserialization. `load()` should remain responsible only for returning the cached project payload when the caller has already decided it is worth loading.

The app-analysis owner remains `src/sattlint/_app_analysis_loading.py`. `load_project()` and `ensure_ast_cache()` must keep the current user-facing behavior and config semantics, including `fast_cache_validation`, while switching to the new cache contract. Any metadata attachment to `ProjectGraph` should continue to reflect the real manifest files used for invalidation.

The loader owner remains `src/sattlint/engine.py`. `SattLineProjectLoader` may gain helper methods or collaborator types to support parallel-safe dependency discovery and parse work, but the public behavior of `resolve()` and the graph contents it returns must stay stable. Shared mutable graph updates should remain behind one deterministic control point.

The validation owner remains `src/sattlint/validation.py`. The end state should clearly separate local structural validation from dependency-sensitive compatibility validation so cached ASTs can reuse only the proof that is actually local to the file.

The representation boundary between loading and analysis currently passes through `merge_project_basepicture()` in `src/sattlint/engine.py`. If downstream analyzers or reports need an analyzer view richer than `root_bp + graph`, that view should be derived on demand rather than treated as the only canonical persisted form.

Focused tests should remain in `tests/parser/test_cache.py`, `tests/test_app_analysis_project_cache.py`, `tests/parser/test_engine_loader_helpers.py`, and `tests/parser/test_engine.py`. Add new tests to those owner suites rather than creating a disconnected performance-only test module unless a genuinely new owner surface appears.
