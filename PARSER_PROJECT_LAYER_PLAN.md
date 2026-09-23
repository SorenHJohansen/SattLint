# Move SattLine Project Loading into `sattline-parser`
Status: approved — Phase 0 recon complete (decisions frozen 2026-09-21); **Phase 1 shipped 2026-09-21**; **Phase 2 shipped 2026-09-21**; **Phase 3 shipped 2026-09-21**; **Phase 4 shipped 2026-09-21**; **Phase 5 shipped 2026-09-22**; **Phase 6 shipped 2026-09-22**; **Phase 7 shipped 2026-09-22**; **Phase 8 shipped 2026-09-23** (shell retired)

Target repo: `sattline-parser` (branch `add-full-project-parsing`, now ahead of `main` with the Phase 1 project-layer skeleton, the Phase 2 discovery/formats layer, the Phase 3 resolution/parse-cache layer, and the Phase 4 graphics-companion parsing layer)
Consumer repo: `SattLint`
Related: [`ANALYZER_PIPELINE_PLAN.md`](ANALYZER_PIPELINE_PLAN.md), [`TUI_PRUNING_PLAN.md`](TUI_PRUNING_PLAN.md). **Note:** both referenced docs no longer exist in this repo (the TUI/LSP pruning they covered landed; `ANALYZER_PIPELINE_PLAN.md` never shipped here). The `TUI_VISUAL_PLAN.md` remains the surviving planning doc.

---

## 0. Phase 0 — board frozen (2026-09-21)

Verified against `sattline-parser` at `add-full-project-parsing` == `main`/`origin/main`
(`d5cfec2`, v2026.9.1) and `SattLint` at `main` (`3c7f51b`). The §2.2 symbol table below is
**current and accurate** — every listed module still exists with the stated responsibility.
At Phase 0 no parser project-layer code existed (`src/sattline_parser/project/` absent); the
Phase 1 skeleton has since landed (see the Phase 1 "Shipped" note in §10).

### 0.1 Open questions — resolved

| Q | Decision | Consequence / note |
|---|---|---|
| Q1 | Rename SattLint's `.slproj` wrapper to `SattLintProjectFile` | **DONE** in SattLint (`project/models.py`, `io.py`, `project/__init__.py`, `tests/project/test_project_io.py`). The name `SattLineProject` is now free for the parser. |
| Q2 | Strict-only: parser default strict; SattLint adapter reports per-target load failures | **Behavioral change**: drop the partial-graph UX (`graph.missing/warnings/failures` continuation in `iter_loaded_projects`). Missing proprietary ABB libs will fail their target. TUI/CLI must catch parser `ProjectLoadError` per target. |
| Q3 | **Keep raising on cycles** (deviation from §3.4/§7) | Parser still must detect cycles to short-circuit recursion, so it records cycle edges internally; **SattLint adapter raises `CircularDependencyError` when the resolved graph contains a cycle**, preserving today's observable behavior (loader.py:92-95, engine re-export). |
| Q4 | Version-conflict detection stays in SattLint | `collect_dependency_version_conflicts` remains in `resolution/dependency_versions.py`; the adapter calls it after building `SattLineProject`. |
| Q5 | **Drop** `contextual_lookup`/`lookup_hook` | LSP/editor surface is gone (TUI pruning); no caller passes `contextual_lookup` today — the engine.py/loader_config.py wiring is dead. Parser `SattLineProject.load` needs no lookup seam. |
| Q6 | Keep `ProjectGraph` as the SattLint analysis index, rebuilt from the parser project | Consumers (`analyzers`, change review, TUI) stay on `ProjectGraph` (moduletype/datatype defs, origins, timings, cache metadata). |
| Q7 | New parser-owned cache dir + version | `FileLookupCache`/`FileASTCache` move behind a new parser namespace/version; SattLint stops reading them. One-time cache rebuild accepted. |

### 0.2 Phase 0 verification notes

- `SattLineProjectLoader.resolve(..., strict=False)` is the default (loader.py:61); strict-only per Q2 changes this.
- Cycles raise `CircularDependencyError` (loader.py:92-95); no analyzer imports it (only `engine.py` re-exports) — low blast radius for the Q3 adapter change.
- `ProjectGraph` mixes graph + analysis index (ast_by_name, library_dependencies, missing/warnings/failures, moduletype/datatype defs, timings, cache metadata) — confirmed at `models/project_graph.py`; split as planned in §6.
- `attach_graphics_companion` (graphics/graphics_helpers.py:193) mixes parse + correlate + warn — the parse part (`graphics/validation.py` → `GraphicsValidationResult`) is a clean extraction target for Phase 4.
- Parser `parse_source_file`/`parse_source_text` single-source API and `tests/parser` corpus are untouched (no parser commit yet).

### 0.3 Remaining prerequisites before parity is green

1. Parser must ship a release containing `sattline_parser.project`; SattLint bump `sattline-parser>=2026.9.1,<2027` (pyproject.toml:27) before Phase 5. **Done**: `pyproject.toml` already bumps to `>=2026.9.1,<2027`; Phases 1–4 are on the `add-full-project-parsing` branch and Phase 5 was built and validated against that branch (installed editable into the SattLint venv). CI validates Phase 5 only once the parser project layer is released to PyPI.
2. LSP/editor remnants: none live, but the dead `contextual_lookup` plumbing (engine.py, loader_config.py) gets removed when the old loader retires (Phase 6).

---

## 1. Goal and end-state boundary

Make `sattline-parser` the canonical SattLine **artifact/project layer**:

> `sattline-parser` answers: *"What is this SattLine project and its complete dependency graph?"*
> `SattLint` answers: *"What do I want to analyze about it?"*

Two domain objects in the parser:

- **`SattLineProject`** — owns search roots, load mode, file discovery, dependency
  resolution, and the complete resolved dependency graph.
- **`SattLineProgram`** — one logical SattLine program/library: parsed code AST,
  parsed graphics model, declared dependency names, and source/format info.

Individual `.s/.g/.l/.x/.y/.z` paths are **not** part of the normal public API.
The existing synthetic AST (`BasePicture`) stays the code representation; it is
wrapped, not replaced.

SattLint keeps: semantic validation, analyzers/rules, diagnostics, analysis
configuration, SattLint-specific indexing, change review, reporting, TUI/CLI, and
analysis-specific caching/policies.

---

## 2. Current state

### 2.1 `sattline-parser` (what exists today)

- `api.py`: `parse_source_file` / `parse_source_text` → `BasePicture`;
  `read_text_with_fallback`, `load_source_text`, coded/compressed preprocessing.
- `models/ast_model.py`: `BasePicture` already carries `origin_file`, `origin_lib`,
  `graphics_file`, `graphics_bindings`, `graphics_messages`,
  `graphics_composite_records`, `graphics_picture_display_records`,
  `library_dependencies`.
- `transformer/_graphics_interact_mixin.py`: parses **inline** `GraphObjects`
  sections in code. This is not `.g`/`.y` companion-file parsing.
- **Phase 1 shipped:** `src/sattline_parser/project/` now holds the domain skeleton
  (`LoadMode`, `ProgramFormat`, the graphics companion model, `SattLineProgram`,
  `SattLineProject` registry, `DependencyGraph`, structured load errors); `load()` is not
  wired. No search-root, discovery, dependency-resolution, or companion-file parsing yet.
- **Phase 2 shipped:** `formats.py`, `lookup_cache.py`, `discovery.py` add `ArtifactKind`,
  the extension/fallback helpers, `SourceIndex`, `shared_lookup_root_for`/
  `ordered_lookup_bases`/`ProjectLookup`, and the parser-owned versioned `FileLookupCache`
  (`LOOKUP_CACHE_VERSION = 1`, Q7). Program loading and dependency resolution stay on the
  SattLint side until Phases 3/5; the SattLint repo is unmodified by Phase 2.
- **Phase 3 shipped:** `loader.py` (`read_dependency_names`, `ProjectLoader`) wires
  `SattLineProject.load`: recursive requester-relative dependency resolution, casefolded
  identity (each name visited/parsed once per load; cycles recorded as edges, never
  raised), strict/non-strict failure behavior, and the optional parser-owned `FileASTCache`
  (`ast_cache.py`, HMAC-signed pickle + stat validation) with lookup-cache flush under a
  caller-supplied `cache_dir`. Graphics companion parsing remains Phase 4; the SattLint
  repo is unmodified by Phase 3.
- **Phase 4 shipped:** `graphics_bindings.py` + `graphics_parsing.py` move the `.g`/`.y`
  parse (record scanner, picture-display rows, `Var`/`Lit`/`Expr` bindings, and
  Lark-parsed expression bindings with source-span offsetting) into two parser modules
  mirroring SattLint's `validation.py` / `validation_bindings.py` split. `parse_graphics_text`/
  `parse_graphics_file` produce a `GraphicsModel` (content problems are messages, never
  raised); `resolve_graphics_companion_path` does the same-directory `with_suffix`
  substitution; the loader wires the companion onto `SattLineProgram.graphics` +
  `ProgramFormat.graphics_ext` (draft `.g`/`.y`, official `.x`/`.y`-only) and maps
  companion-read failures onto `ArtifactLoadError`/`DependencyParseError`. Correlation and
  asset-path warnings stay SattLint-side (Phase 5); the SattLint repo is unmodified by Phase 4.

### 2.2 `SattLint` (what exists today)

Project loading is spread across `src/sattlint/project/` and friends:

| File | Responsibility | Destination |
|---|---|---|
| `project/loader.py` | recursive visit, cycle detection, validation, index, graphics attach | **split**: discovery/resolution → parser; validation/index → SattLint |
| `project/loader_base.py` | loader state, cache wiring, `CircularDependencyError`, missing-library recording | split |
| `project/loader_lookup.py` | search-root ordering, dir index, extension candidates, draft→official fallback, `.l`/`.z` read, AST/lookup cache | **parser** (mostly) |
| `project/loader_config.py` | `SattLineProjectLoaderConfig/Runtime/Dependencies`, legacy factory compat | mostly **delete**; thin config in parser |
| `project/loading.py` | orchestration: cache, timings, reverse consumers, `ProjectGraph` view, `load_project` | **SattLint** (slim adapter) |
| `project/loading_support.py` | reverse-consumer discovery, cache metadata, compat shims, debug summaries | **SattLint** |
| `project/models.py` | `SattLineProject` = **`.slproj` file wrapper** | **rename** → **done**: `SattLintProjectFile` (Q1) |
| `project/support.py` | `TargetLoadError`, configured ICF files | **SattLint** |
| `models/project_graph.py` | `ProjectGraph` analysis index + `merge_project_basepicture` | **SattLint** (repopulated) |
| `core/syntax.py` | `CodeMode`, ext helpers, parse wrappers, validation markers | **split**: `LoadMode`/ext → parser; validation → SattLint |
| `graphics/validation.py` + `validation_bindings.py` | parse `.g`/`.y` into bindings/messages/records | **parser** (parse part) |
| `graphics/graphics_context_helpers.py` | companion-path resolution + source context | **parser** (path resolution) / SattLint (warnings) |
| `graphics/graphics_helpers.py` | `attach_graphics_companion` orchestration + warning correlation | **split**: parse → parser; correlate/warn → SattLint |
| `graphics/picture_display_paths.py`, `picture_display_runtime.py` | correlate records against the project, resolve paths | **SattLint** (analysis) |
| `cache/classes.py` `FileASTCache`, `FileLookupCache` | per-file AST + lookup caches | **parser** (ownership) |
| `cache/classes.py` `AnalysisReportCache`, `FoundationCache` | analysis caches | **SattLint** |
| `engine.py` | `build_project_loader`, `load_project_graph` re-export facade | **SattLint** (thin adapter) |

Key facts that shape the move:

- Extensions and fallback already exist in `core/syntax.py`:
  `code_ext_candidates` → `(".s", ".x")` in draft, `(".x",)` in official; same
  pattern for deps and graphics. Draft fallback is already **per artifact**.
- The current `SattLineProjectLoader` loads with `strict=False` from
  `loading.py:239`, collecting `missing`/`warnings`/`failures` instead of failing.
- `ProjectGraph` mixes the dependency graph (`library_dependencies`,
  `ast_by_name`) with the SattLint analysis index (`moduletype_defs`,
  `datatype_defs`, `root_origins`, timings, cache metadata).
- Cycle detection currently **raises** `CircularDependencyError`
  (`loader.py:95`); the requested behavior is to **represent** cycles instead.
- `attach_graphics_companion` (`graphics/graphics_helpers.py:193`) mixes parsing
  the `.g`/`.y` file with correlating it against the project graph.

---

## 3. Target domain model (in `sattline-parser`)

New package: `src/sattline_parser/project/`.

### 3.1 `LoadMode`

```python
class LoadMode(Enum):
    DRAFT = "draft"
    OFFICIAL = "official"
```

- `OFFICIAL`: only `.x` / `.y` / `.z`.
- `DRAFT`: prefer `.s` / `.g` / `.l`; fall back **independently per artifact** to
  `.x` / `.y` / `.z` when the draft counterpart is missing. Never assume all three
  come from the same revision.
- SattLint's `CodeMode` is replaced by (or aliased to) `LoadMode`.

### 3.2 `SattLineProgram`

```python
@dataclass(frozen=True)
class SattLineProgram:
    name: str
    code: BasePicture  # existing synthetic AST, wrapped not replaced
    graphics: GraphicsModel | None  # parsed companion model (see §3.5)
    dependencies: tuple[str, ...]  # declared names from .l/.z
    format: ProgramFormat  # DRAFT/OFFICIAL + which artifacts were found
    # provenance metadata (not the primary API):
    #   source file names / library, for diagnostics and SattLint indexing
```

- `program.code` is the AST SattLint consumes directly.
- `program.graphics` is the parser's graphics representation, not correlated
  records (correlation stays in SattLint).
- Paths are internal metadata; callers use `project.get(name)`, not path lookups.

### 3.3 `SattLineProject`

```python
class SattLineProject:
    @classmethod
    def load(
        cls,
        roots: Sequence[Path],
        mode: LoadMode,
        targets: Sequence[str],
        *,
        strict: bool = True,
        debug: Callable[[str], None] | None = None,
    ) -> "SattLineProject": ...

    def get(self, name: str) -> SattLineProgram: ...
    def __contains__(self, name: str) -> bool: ...
    def programs(self) -> Mapping[str, SattLineProgram]: ...
    def dependencies_of(self, name: str) -> tuple[str, ...]: ...
    def dependents_of(self, name: str) -> tuple[str, ...]: ...
    def graph(self) -> DependencyGraph: ...
```

- `roots` is a generic ordered list; SattLint maps
  `[program_dir, *other_lib_dirs, ABB_lib_dir]` onto it.
- `get` is case-insensitive and returns the canonical instance.
- Every reachable dependency is loaded and present in the registry.
- `graph()` exposes resolved edges; cycles are edges, not errors.

### 3.4 Identity, registry, cycles

- Canonical registry keyed by `name.casefold()`; one `SattLineProgram` per logical
  identity. `project.get("ControlLib")` always returns the same object.
- Loading is memoized by identity, so repeated access and diamond dependencies
  never reparse.
- Cycle handling: keep a `loading` set during traversal. When a name is already
  `loading`, record the edge and return the in-progress program handle instead of
  recursing. Cycles appear in `graph()` and do **not** raise.

### 3.5 Graphics model

Add a parser-owned representation for `.g`/`.y` companion files, e.g.
`SattLineGraphics` / `GraphicsModel` with `bindings`, `messages`,
`composite_records`, `picture_display_records`. This is the **parse** result only.
SattLint's correlation (`correlate_composite_records`,
`correlate_picture_display_records`) and path warnings remain in SattLint.

### 3.6 Errors

```python
class ProjectLoadError(Exception): ...  # base; carries program + dependency


class DependencyNotFoundError(ProjectLoadError): ...


class DependencyParseError(ProjectLoadError): ...


class ArtifactLoadError(ProjectLoadError): ...
```

Each error identifies the **program** and the **dependency/artifact** involved.
Strict loading fails fast; a non-strict/diagnostic mode can be added later.

---

## 4. Responsibility split (the contract)

| Concern | `sattline-parser` | `SattLint` |
|---|---|---|
| SattLine file formats (`.s/.x`, `.g/.y`, `.l/.z`) | ✅ owns | |
| File discovery across roots | ✅ owns | |
| Draft/official selection + per-artifact fallback | ✅ owns | |
| Code parsing → `BasePicture` | ✅ owns | |
| Graphics companion parsing | ✅ owns | |
| Dependency-file parsing | ✅ owns | |
| Dependency resolution + graph | ✅ owns | |
| `SattLineProject` / `SattLineProgram` | ✅ owns | |
| Per-file parse cache + lookup cache | ✅ owns | |
| Semantic analysis / analyzers / rules | | ✅ owns |
| Diagnostics + semantic validation | | ✅ owns |
| Analysis configuration / policies | | ✅ owns |
| SattLint-specific indexing (`ProjectGraph`) | | ✅ owns |
| Change review / reporting / TUI / CLI | | ✅ owns |
| Analysis report + foundation caches | | ✅ owns |

---

## 5. Discovery and resolution algorithm

Moved from `loader_lookup.py`/`loader.py`, generalized:

1. Build an index per root: `stem.casefold() → {ext → path}` for the mode's
   candidate extensions.
2. For each artifact (code, graphics, deps), resolve the file by trying the
   mode's candidate extensions in order, honoring an ordered root preference:
   requester directory → shared cluster root → same/sibling branches → all roots
   → (SattLint passes ABB last).
3. Parse `.l`/`.z` into declared dependency names (newline-separated, trimmed).
4. Recurse into each declared dependency against the roots, with the dependency
   file's directory as the requester context.
5. Build resolved edges `program → dependency programs`.
6. Memoize by identity; represent cycles; never duplicate-load.

The SattLint-specific root semantics (`program_dir`, `other_lib_dirs`,
`abb_lib_dir`) become a caller-supplied ordered `roots` list plus an optional
"requester-relative" ordering policy. The `contextual_lookup`/`lookup_hook`
seam is **dropped** — the LSP/editor surface is gone (TUI pruning), so
`SattLineProject.load` takes no discovery hook (Q5, §0.1).

---

## 6. Caching and identity ownership

- **Parser owns**: the per-file AST/parse cache and the file-lookup cache.
  These are properties of parsing/discovery, not analysis. Move the logic behind
  `FileASTCache` / `FileLookupCache` into the parser (new namespace + version).
- **SattLint owns**: `AnalysisReportCache`, `FoundationCache`, and every
  analysis-level policy (what to cache, when to invalidate, what counts as an
  analysis input).
- **Cache migration risk**: the on-disk format/version currently lives in
  `sattlint/cache` (`CACHE_VERSION = 15`). Moving ownership is a breaking cache
  change; the parser must start its own cache namespace and SattLint must not
  read the old parser-owned files. Call this out as a one-time rebuild.
- SattLint must **not** implement filesystem lookup or dependency-load caches
  after the move.

---

## 7. Failure behavior

- `SattLineProject.load(..., strict=True)` (default): fail the whole load if a
  declared dependency is not found, a dependency cannot be parsed, or a required
  artifact cannot be loaded. No partial project.
- Structured errors identify program + dependency/artifact.
- SattLint's current lenient behavior (`strict=False`, `graph.missing`,
  `graph.warnings`, `graph.failures`, per-target "failed to load" continuation)
  is a **behavioral change**. Decision required (see §10, open questions):
  - either SattLint calls a future non-strict/diagnostic parser mode and keeps
    its partial-project UX, or
  - SattLint catches structured errors per target and reports them, dropping the
    partial graph.
- Cycles are **not** failures (§3.4). SattLint's `CircularDependencyError` policy
  must be revisited.

---

## 8. API design

### 8.1 Parser (canonical)

```python
from sattline_parser.project import SattLineProject, LoadMode

project = SattLineProject.load(
    roots=[Path(".../programs"), Path(".../libs"), Path(".../ABB")],
    mode=LoadMode.DRAFT,
    targets=["BasePicture"],
)

program = project.get("BasePicture")
program.code  # BasePicture (existing synthetic AST)
program.graphics  # parser graphics model
program.dependencies  # declared names from .l/.z

dep = project.get("SomeReachableLib")  # no path knowledge required
project.graph()  # resolved dependency edges
```

### 8.2 SattLint adapter (thin)

`load_project` in `project/loading.py` becomes:

1. Build `roots` from cfg (`program_dir`, `other_lib_dirs`, `ABB_lib_dir`).
2. Map cfg mode → `LoadMode`.
3. `parser_project = SattLineProject.load(roots=..., mode=..., targets=[target_name])`.
4. Run SattLint semantic validation on each `program.code`.
5. Build the SattLint `ProjectGraph` index from `parser_project.programs()`.
6. Attach analysis cache metadata, timings, reverse-consumer additions.
7. Return `(project_bp, graph)` as today (or migrate callers to the new model).

`iter_loaded_projects`, `ensure_ast_cache`, `force_refresh_ast`,
`load_program_ast`, and `source_paths_for_current_target` keep their signatures
where possible so analyzers, change review, and the TUI do not churn.

---

## 9. Refactoring strategy (move, don't copy)

Do **not** copy `SattLineProjectLoader` wholesale. Work symbol-first:

1. **Classify every symbol** in `project/`, `graphics/`, `cache/`, `core/syntax.py`
   as: *SattLine artifact/project fact* (→ parser), *SattLint analysis policy*
   (→ stays), or *mixed* (→ split).
2. **Extract the pure artifact/project core** into the parser:
   extension/fallback rules, discovery, `.l`/`.z` parsing, recursion, graph,
   identity/cycle handling, companion-graphics parsing.
3. **Leave SattLint-specific orchestration** in SattLint: validation, indexing,
   timings, reverse consumers, cache metadata, report/foundation caches.
4. **Delete the old loader path** only after the adapter is green.

Mixed symbols to split explicitly:

- `attach_graphics_companion` → parser parses; SattLint correlates + warns.
- `core/syntax.py` → parser gets `LoadMode` + extension helpers; SattLint keeps
  validation markers and `validate_single_file_syntax`.
- `ProjectGraph` → parser project owns programs + edges; SattLint keeps
  `ProjectGraph` as the analysis index, rebuilt from the parser project.
- `contextual_lookup` → **dropped** (Q5): the LSP/editor surface was removed in
  the TUI pruning, so the parser `load()` has no `lookup_hook` seam (Phase 1 ships
  without it).

---

## 10. Migration phases

Each phase must keep both repos green independently.

**Phase 0 — Recon and freeze the boundary**
- Inventory every symbol in the table in §2.2; write the keep/move/split decision
  next to it.
- Confirm the parser branch and that `parse_source_file`/`parse_source_text`
  tests stay untouched.
- Decide the naming collision: SattLint's `.slproj` wrapper `SattLineProject`
  (`project/models.py`) **must be renamed** (e.g. `SattLintProjectFile`) before
  the parser type lands. This is a prerequisite, not a detail.

**Phase 1 — Parser domain skeleton (additive) — DONE (2026-09-21)**
- Add `sattline_parser.project` with `LoadMode`, `SattLineProgram`,
  `SattLineProject` (load not yet wired), `DependencyGraph`, and the structured
  error types.
- Add unit tests for the model/errors only. No behavior moved yet.

Shipped on `add-full-project-parsing`:
- `src/sattline_parser/project/{__init__,errors,models,project}.py` + `tests/project/test_project_layer.py` (21 tests, `tests/project/` suite new).
- `SattLineProject.load(roots, mode, targets, *, strict=True, debug=None)` raises `NotImplementedError`; **no** `lookup_hook`/`contextual_lookup` seam (Q5).
- Registry is casefold-canonical: case-insensitive `get` (raises `KeyError`) / `__contains__`, read-only `programs()`, plus `dependencies_of`/`dependents_of` and `graph()` (sorted casefolded nodes, declared edges).
- Graphics model mirrors SattLint's `validation_bindings.py` shapes (`GraphicsMessage`, `GraphicsCompositeRecord`, `GraphicsPictureDisplayRecord`/`GraphicsPictureDisplayPathRow`) so Phase 4 reuses them as-is.
- Errors: `ProjectLoadError` (carries `program` + optional `dependency`) and `DependencyNotFoundError`/`DependencyParseError`/`ArtifactLoadError`.
- Validation: full parser suite green (328 tests), coverage 100%, ruff lint+format clean, Pyright strict (0 errors).
- CHANGELOG: `[Unreleased]` → Added entry.
- Gap vs §3.3 until Phase 3 wires resolution: `dependencies_of`/`dependents_of` read declared names (`program.dependencies`, caller spelling) and `graph()` edges are casefolded canonical identities that may reference dependency names that are not yet registry nodes.

**Phase 2 — Parser file discovery + formats — DONE (2026-09-21)**
- Move extension/fallback rules, root indexing, ordered lookup, and the
  per-artifact draft→official fallback into the parser.
- Move `FileLookupCache` ownership (new namespace).
- Tests: draft, official, per-artifact fallback, multiple roots.

Shipped on `add-full-project-parsing`:
- `src/sattline_parser/project/{formats,lookup_cache,discovery}.py` + `tests/project/{test_formats,test_lookup_cache,test_discovery}.py`.
- `formats.py`: `ArtifactKind` (CODE/GRAPHICS/DEPS), `code_ext`/`deps_ext`/`graphics_ext`, the candidate helpers (draft `.s/.l/.g` → official `.x/.z/.y` per artifact), `preferred_extension`, `candidate_extensions`.
- `lookup_cache.py`: parser-owned `FileLookupCache` (`LOOKUP_CACHE_VERSION = 1`, own namespace per Q7), key `f"{kind}:{mode}:{name.casefold()}"`, entry `{"base_dir": resolved, "ext"}`, interval flush (default 25) / `write_through`, atomic tmp+fsync+`os.replace`, on-boot `prune_stale_entries`, `_normalize_base_dir` with `expanduser`+`resolve` (OSError fallback).
- `discovery.py`: `SourceIndex` (indexes `.s/.x/.l/.z`), `shared_lookup_root_for` (requester-walk cluster of ≥2 sibling roots), `ordered_lookup_bases` (requester → same-branch → sorted sibling branches → remaining roots in order; terminal/last root last, preserving SattLint's ABB-terminal behavior), `ProjectLookup.find`/`find_code`/`find_deps` (ordered scan → cached-base check → plain-root scan; drafts fall back per artifact; cache writes via `_remember`, stale-cache forget on disallowed base or missing file).
- Behavior preserved from SattLint's `loader_lookup.py` + `cache/classes.py`; port-fidelity rule kept (last root stays terminal/fallback).
- Validation: full parser suite green **400 tests**, coverage 100%, ruff lint+format clean, Pyright strict (0 errors).
- CHANGELOG: `[Unreleased]` → Added entry (Phase 2 block above the Phase 1 block).
- Gap: SattLint still loads projects with its own loader until Phase 5; no SattLint code/tests touched in Phase 2.

**Phase 3 — Parser dependency resolution + graph — DONE (2026-09-21)**
- Move `.l`/`.z` parsing, recursive loading, identity registry, cycle
  representation, and duplicate-dependency handling.
- Move the per-file AST parse cache ownership.
- Tests: recursive deps, missing dep, parse failure, duplicate dep, cycle,
  repeated access does not reparse, complete closure.

Shipped on `add-full-project-parsing`:
- `src/sattline_parser/project/{ast_cache,loader}.py` + `tests/project/{test_ast_cache,test_loader}.py`; `project.py` `load` wired; `project/__init__.py` exports `ProjectLoader`.
- `loader.py`: `read_dependency_names` (newline-separated, stripped, blank-dropped, order-preserved via `read_text_with_fallback`), `ProjectLoader` recursive resolver — identity registry keyed by casefolded names (each name visited/parsed exactly once per load, no parse memo needed), requester-relative lookup (`deps_path.parent → find_code`/`find_deps`; draft fallback unchanged), duplicate deps load once while `program.dependencies` keeps declared spelling + caller spelling through the version-conflict surface, cycles recurse-guarded and recorded as dependency edges (never raised — Q3's adapter-side `CircularDependencyError` lands in Phase 5).
- `ast_cache.py`: parser-owned `FileASTCache` (`FILE_AST_CACHE_VERSION = 1`, magic `SATTLINE-PARSER-PICKLE-V1`, per-dir 32-byte HMAC key written 0600 at first use), keyed by `sha256(path+mode)`, stat-validated (`mtime_ns`+`size`) + path/mode/version/HMAC checks before trusting a cached `BasePicture`, atomic tmp+fsync+`os.replace`, `prune_stale_entries` + `drain_startup_pruned_entries`; lookup-cache `flush()` at end of `resolve`.
- `SattLineProject.load(roots, mode, targets, *, strict=True, debug=None, cache_dir=None)`: `cache_dir=None` keeps loads hermetic (in-memory, no disk writes); strict fails fast, `strict=False` skips the failing program and continues; failures surface as `DependencyNotFoundError`/`DependencyParseError`/`ArtifactLoadError` with `program` = requester (target when top-level) and `dependency` = the failing artifact.
- Validation: full parser suite green **460 tests**, coverage 100% (incl. `ast_cache.py` 187/187 and `loader.py` 85/85), ruff lint+format clean, Pyright strict (0 errors).
- CHANGELOG: `[Unreleased]` → Added entry (Phase 3 block above the Phase 2 block).
- Gap: `.g`/`.y` companion parsing is Phase 4; the SattLint adapter wiring is Phase 5; SattLint repo untouched by Phase 3.

**Phase 4 — Parser graphics parsing — DONE (2026-09-21)**
- Move `.g`/`.y` parsing (`graphics/validation.py`, `validation_bindings.py`) into
  a parser graphics model and companion-path resolution.
- SattLint keeps correlation (`correlate_composite_records`,
  `correlate_picture_display_records`) and warnings.
- Tests: graphics parse; SattLint correlation tests unchanged.

Shipped on `add-full-project-parsing`:
- `src/sattline_parser/project/{graphics_bindings,graphics_parsing}.py` + `tests/project/test_graphics_parsing.py`; `__init__.py` exports `parse_graphics_text`/`parse_graphics_file`/`resolve_graphics_companion_path`; `models.py` adds `GraphicsModel.errors`/`warnings`; `loader.py` + `tests/project/test_loader.py` wire the companion onto each program.
- `graphics_bindings.py` (ported from `validation_bindings.py`): `_BINDING_LINE_RE`, `_graphics_expression_parser` (lru_cached `build_lark_parser(start="expression")`), `_unwrap_expression_root`, `_offset_source_spans` (byte-for-byte port incl. dict/tuple/Tree/children/dataclass/`__dict__` branches), `_coerce_graphics_literal`, `_normalize_graphics_expression`, `_parse_graphics_binding_match` (var/lit/expr + parse-failure warnings; negatives and empty payloads dropped), `_parse_graphics_binding_line`.
- `graphics_parsing.py` (ported from `validation.py`): `_nonempty_record_lines`, `_find_record_end`, `_extract_literal_path`, `_split_nested_picture_display_payload`, `_parse_picture_display_row`, `_extract_picture_display_record` (rows from `record_lines[5:-2]`, KeepPictureShape `t`/`f` casefolded, subtype `"2"` gating picture-display records, families `1/2/4/5`), `resolve_graphics_companion_path` (same-directory `with_suffix`; `.x`→`.y` only; draft `.g`→`.y` fallback; `.g`/`.y` input → itself), public `parse_graphics_text`/`parse_graphics_file`. Content problems become `GraphicsMessage` values — never raised; read `OSError` propagates to the loader.
- `loader.py`: `_load_one` resolves + parses the companion and stores `program.graphics` + `format.graphics_ext`; `_load_graphics` maps `OSError` → `ArtifactLoadError` (top-level) / `DependencyParseError` (dependency) with the same strict/non-strict behavior.
- Validation: full parser suite green **525 tests**, coverage 100% (both new modules at 100%), ruff lint+format clean, Pyright strict (0 errors).
- CHANGELOG: `[Unreleased]` → Added entry (Phase 4 block above the Phase 3 block).
- Gap: SattLint's `attach_graphics_companion` keeps correlation + asset-path warnings and the adapter wiring is Phase 5; SattLint repo untouched by Phase 4.

**Phase 5 — SattLint thin adapter — DONE (2026-09-22)**
- Rewrite `load_project`/`load_program_ast` to call `SattLineProject.load`, then
  validate + index into `ProjectGraph`.
- Keep `iter_loaded_projects` and analyzer-facing signatures stable.
- Reconcile strictness (§7) and cycles (§3.4).

Shipped on the SattLint side:
- `src/sattlint/project/parser_adapter.py`: `ParserProjectBinding` (frozen config + timing/status/cache hooks; `roots`/`parser_mode()`/`new_lookup()`), `load_parser_project` (`SattLineProject.load(..., cache_dir=None)` — hermetic/no parser-owned file caches in SattLint), `find_code_path`/`find_dependency_path`/`read_dependency_names`/`syntax_check_program`, and `convert_project_into_graph` mirroring the recursive loader's `_visit`: per-program validation (strict root raise, non-root structural warnings), `mark_local_validation`, graphics attachment (`attach_graphics_companion`, SattLint keeps correlation + asset-path warnings), library naming, version-conflict detection (`DependencyVersionCompatibilityError` in strict, `version compatibility warning` otherwise) then `add_library_dependencies` + `index_from_basepic`, single try/except re-recording validation warnings and `record_project_failure` in non-strict. Cycles raise `CircularDependencyError` always (Q3) built from registry order with original spellings; parser-dropped roots and dangling dependency names become `record_missing_library` entries (deduped via `graph.unavailable_libraries`); reverse-consumer visits skip already-present programs.
- Because `BasePicture.header.name` is always the literal `"BasePicture"` keyword (real identity lives on `program_name`), dependency-library resolution carries the old loader's `_lib_by_name` cache as a `lib_names` map owned by the loader shell (`SattLineProjectLoader._lib_by_name`) and threaded through the adapter — the same mechanism the recursive loader used (root-graph lookups cannot resolve program names).
- `src/sattlint/project/loader.py` is now a thin `SattLineProjectLoader(SattLineProjectLoaderBase)` shell (public contract: `resolve`, `visit_target`, `find_dependency_path`, `read_dependency_names`; the old `flush_lookup_cache` is gone with the lookup-cache seam in Phase 6); `visit_target` does no syntax check (matching the old `_active_root_key is None` reverse-consumer path); `_binding()` wires `dbg`/`_update_status`/`_stage_timing_sink`/`_graphics_timing_sink`/`_ast_cache.save`.
- `tests/project/test_parser_adapter.py`: 11 focused tests (binding roots & LoadMode; schema-only graph population; dangling/root-missing `missing` recording; cycle raise with original spelling; reverse-consumer dedup; ast-only skipping graphics+index; hermetic `.s`/`.l` round-trip; strict missing-target raise; path/name lookup; library-name fallthrough program_dir → other_lib_dirs → abb → parent).
- Validation: full SattLint suite green (**1071 passed**), `ruff check` clean, `ruff format --check` clean, Venv Pyright `src tests` **0 errors** (LSP's own non-venv diagnostics are not authoritative — it cannot resolve even `sattline_parser.models.ast_model`).
- CHANGELOG: `[Unreleased]` → Added entry added above.
- Gap (resolved in Phase 6): `loader_base.py`, `loader_lookup.py`, `loader_config.py`, and the recursive loader's parser-owned cache semantics were untouched until Phase 6; engine's `contextual_lookup` plumbing remained dead code until then.

**Phase 6 — Retire the old loader — DONE (2026-09-22)**
- Delete `loader_base.py`, `loader_lookup.py`, `loader_config.py` factory
  machinery, and the parser-owned file caches from SattLint.
- Keep `loading.py` (slim), `support.py`, `project_graph.py`, `validation/`,
  analysis caches, correlation/analysis graphics.
- Update `engine.py` re-exports.

Shipped on the SattLint side:
- `src/sattlint/project/loader_lookup.py` deleted (the lookup cache owned it; the
  parser now owns `FileLookupCache` behind `cache_dir=None` and the adapter stays
  hermetic).
- `cache/classes.py`: `FileLookupCache`, `FileASTCache`, and
  `DEFAULT_LOOKUP_CACHE_FLUSH_INTERVAL` deleted; `cache/manager.py` rewritten so
  `CacheManager` tracks only `ASTCache` + `AnalysisReportCache`;
  `cache/__init__.py` drops `FileASTCache`/`FileLookupCache`/`LOOKUP_CACHE_VERSION`
  and the `CachePruneResult` entries/helpers for them.
- `project_graph.py`: `ast_cache_counts` (and its `_ast_cache_counts_factory`)
  deleted.
- `loading_support.py`: `ast_cache_save` stage dropped from `_STAGE_ORDER` and the
  refresh-total formatter; `_loader_flush_lookup_cache` deleted.
- `loading.py`/`application/project.py`/`engine.py`: `use_file_ast_cache`,
  `contextual_lookup`, `SattLineProjectLoaderDependencies`, and all flush try/finally
  plumbing removed.
- `loader_config.py`: `SattLineProjectLoaderRuntime.contextual_lookup` and the
  `SattLineProjectLoaderDependencies` dataclass deleted; the legacy
  `**kwargs`-based `_LegacyProjectLoaderFactory`/`_legacy_loader_kwargs` path deleted
  (structured `(config, *, runtime=None)` factories only).
- `parser_adapter.py`: `use_file_ast_cache` + `ast_cache_save_fn` removed from
  `ParserProjectBinding`; both `_index_program` cache write hooks deleted.
- Test call sites updated across `tests/`; suite green (**1063 passed**), `ruff check`
  clean, `ruff format --check` clean, Venv Pyright `src tests` **0 errors**.
- Graphics parse modules stay live this phase (deferred per scope decision);
  `syntax-check` strictness untouched.

**Phase 7 — Docs and cleanup — DONE (2026-09-22)**
- Update `ARCHITECTURE.md`, `AGENTS_REFERENCE.md`, `PYTHON_API.md` (parser project
  API), and SattLint's project-loading docs.
- Add a parser-facing README section for the project layer.

Shipped on the SattLint side:
- `ARCHITECTURE.md`: parser layer now the SattLine **project** layer
  (`SattLineProject` owns roots, mode, discovery, dependency resolution, and the
  resolved graph); loader flow diagram shows `SattLineProjectLoader` shell →
  `parser_adapter` → `sattline_parser.project` → `ProjectGraph` reindex.
- `AGENTS_REFERENCE.md`: repo-map row for `src/sattlint/project/` now reads
  "`.slproj` project model + parser-adapted loading (`parser_adapter.py`,
  `loading.py`)".
- `PYTHON_API.md`: adds the `sattlint.project` sample (loader shell, loading
  orchestration) and the `sattline_parser` project-layer row
  (`SattLineProject`/`SattLineProgram`/`ProjectLoader`/`FileASTCache`/
  `FileLookupCache` + graphics parse helpers).
- `README.md` (`Project Files` section): notes that discovery, dependency
  resolution, and parsing run in `sattline-parser`'s project layer; SattLint
  re-validates and re-indexes into `ProjectGraph`.

Shipped on `add-full-project-parsing`:
- `README.md`: new "Project layer" Usage section (resolve a whole project via
  `SattLineProject.load`, inspect `SattLineProgram`/`DependencyGraph`,
  `cache_dir=None` hermetic loads, `.g`/`.y` companions).

**Phase 8 — Retire the `SattLineProjectLoader` shell — DONE (2026-09-23)**
- Delete `project/loader.py` (`SattLineProjectLoader` shell) and
  `project/loader_base.py`. Every load path now routes through
  `loader_config.build_parser_binding` (+ `ParserProjectBinding`) into
  `parser_adapter.load_parser_project`/`convert_project_into_graph`.
- `loader_config.py`: `build_parser_binding(cfg, *, status_update_fn, refresh_mode,
  stage_timing_sink, graphics_timing_sink) -> ParserProjectBinding` with
  `debug_fn=_make_debug_fn(debug)`; keeps `validate_loader_config`, the load-timing
  sink types, and the coerce helpers.
- `loading.py`: `load_project` builds the binding, drives the recursive graph via
  the `_load_parser_graph`/`_visit_target_into_graph` module-level seams, and reads
  reverse-consumer/manifest dependency names via `parser_adapter.find_dependency_path`
  + `read_dependency_names`; `load_program_ast` similarly builds the binding + graph
  seam and raises when the program is absent.
- `loading_support.py`: `_include_reverse_library_consumers` now takes injected
  `find_dependency_path_fn`/`read_dependency_names_fn`/`visit_target_fn` callables
  instead of a `loader` (cycle-boundary: loading_support must not import parser_adapter).
- `engine.py`: `build_project_loader` returns `ParserProjectBinding`; `load_project_graph`
  builds the binding and inlines the graph load; errors (`CircularDependencyError`,
  `DependencyVersionCompatibilityError`) and helpers re-exported from parser_adapter.
- `parser_adapter.py` absorbs `CircularDependencyError`, `DependencyVersionCompatibilityError`,
  `record_missing_library`, and `mark_local_validation` (the last re-exported from
  `core.syntax`) so engine re-exports stay complete.
- Test migrations: 5 direct-construction suites (`test_corpus_analyzers.py`,
  `test_full_analysis_crash_sweep.py`, `test_corpus_regression_exactness.py`,
  `test_picture_display_fixture_integration.py`, `test_gfile_and_records.py`) build a
  `cfg: dict[str, object]` + `load_project_graph`; `test_parser_adapter`/
  `test_project_graph_invariants` imports repointed to parser_adapter; the app suites
  (`test_analysis_load_project.py`, `test_analysis_project_cache.py`,
  `test_analysis_loading.py`) patch the new seams (`build_parser_binding`,
  `_load_parser_graph`, `find_dependency_path`, `read_dependency_names`,
  `_visit_target_into_graph`, injected callables).
- Validation: full SattLint suite green (**1063 passed**), `ruff check` clean,
  `ruff format --check` clean, Venv Pyright `src tests` **0 errors**.

---

## 11. Tests

### 11.1 Parser (required by the request)

- draft loading (`.s/.g/.l`)
- official loading (`.x/.y/.z`)
- draft → official fallback, **per artifact** (e.g. `.s` + `.y` + `.l`)
- multiple search roots and root precedence
- recursive dependencies
- missing dependency → strict failure with program/dependency identity
- dependency parse failure → strict failure with identity
- duplicate dependency declared twice → loaded once
- dependency cycles → represented, no duplicate load, no infinite recursion
- repeated access to the same program → same instance, no reparse
- correct construction of the existing synthetic AST (`BasePicture`)
- graphics companion parsing

### 11.2 SattLint (preserve behavior)

- `load_project` / `iter_loaded_projects` / `ensure_ast_cache` /
  `force_refresh_ast` keep working through the adapter.
- Semantic validation still runs and still marks local validation.
- `ProjectGraph` index still contains moduletype/datatype defs and origins.
- Reverse-consumer loading still works.
- Change review and analyzers unchanged.
- Cache behavior: one-time rebuild acceptable; no reads of stale parser-owned
  cache files.

---

## 12. Risks and open questions

**Risks**

- **Naming collision**: two `SattLineProject` classes (SattLint's `.slproj`
  wrapper vs the parser's loaded project). **Resolved** (Q1, done in Phase 0):
  the SattLint wrapper is `SattLintProjectFile`; the parser owns `SattLineProject`
  (Phase 1).
- **Behavioral change in strictness**: SattLint currently tolerates partial
  projects; the requested parser default is strict. This affects the TUI/CLI UX
  for missing proprietary libraries.
- **Cycle policy change**: SattLint raises today; the parser represents cycles.
  Confirm no analyzer depends on `CircularDependencyError`.
- **Cache format migration**: moving parse/lookup cache ownership invalidates
  existing caches; budget a rebuild.
- **Graphics split**: parsing vs correlation must be separated cleanly or the
  move will drag analysis back into the parser.

**Open questions (decide before the matching phase) — all resolved in §0.1**

1. `SattLineProject` naming: rename SattLint's `.slproj` wrapper to what?
   (`SattLintProjectFile`? `ProjectConfig`?)
2. Strictness: does SattLint adopt strict-only and report per-target load
   failures, or do we add the diagnostic/non-strict parser mode now?
3. Cycles: is representing cycles acceptable to SattLint, or must the adapter
   still surface them as errors for some analyzers?
4. Where does dependency version-conflict detection
   (`collect_dependency_version_conflicts`) live — parser project fact or
   SattLint analysis policy?
5. `lookup_hook`/`contextual_lookup`: keep as a parser injection seam, or drop it
   with the LSP surface (see `TUI_PRUNING_PLAN.md`)?
6. Does `ProjectGraph` survive as the SattLint analysis index, or do we migrate
   consumers to the parser project and keep only a thin SattLint index?
7. Cache namespaces/versions: new parser cache dir and version, or reuse a
   subdirectory of the SattLint cache dir passed in by the caller?
