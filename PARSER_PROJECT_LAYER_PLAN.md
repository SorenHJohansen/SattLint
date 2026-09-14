# Move SattLine Project Loading into `sattline-parser`

Status: proposal
Target repo: `sattline-parser` (branch `add-full-project-parsing`, currently clean at `main`)
Consumer repo: `SattLint`
Related: [`ANALYZER_PIPELINE_PLAN.md`](ANALYZER_PIPELINE_PLAN.md), [`TUI_PRUNING_PLAN.md`](TUI_PRUNING_PLAN.md)

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
- No project, search-root, file-discovery, dependency-resolution, or companion-file
  graphics layer exists yet. The branch is empty.

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
| `project/models.py` | `SattLineProject` = **`.slproj` file wrapper** | **rename** (collision) |
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
    code: BasePicture                 # existing synthetic AST, wrapped not replaced
    graphics: GraphicsModel | None    # parsed companion model (see §3.5)
    dependencies: tuple[str, ...]     # declared names from .l/.z
    format: ProgramFormat             # DRAFT/OFFICIAL + which artifacts were found
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
        lookup_hook: LookupHook | None = None,   # optional discovery override
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
class ProjectLoadError(Exception): ...          # base; carries program + dependency
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
"requester-relative" ordering policy. The `contextual_lookup` hook is preserved as
an optional `lookup_hook` injection point (used today by the LSP workspace
lookup; see §9).

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
program.code            # BasePicture (existing synthetic AST)
program.graphics        # parser graphics model
program.dependencies    # declared names from .l/.z

dep = project.get("SomeReachableLib")   # no path knowledge required
project.graph()                          # resolved dependency edges
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
- `contextual_lookup` → keep as an optional `lookup_hook` in the parser; if the
  LSP surface is removed (see `TUI_PRUNING_PLAN.md`), drop it.

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

**Phase 1 — Parser domain skeleton (additive)**
- Add `sattline_parser.project` with `LoadMode`, `SattLineProgram`,
  `SattLineProject` (load not yet wired), `DependencyGraph`, and the structured
  error types.
- Add unit tests for the model/errors only. No behavior moved yet.

**Phase 2 — Parser file discovery + formats**
- Move extension/fallback rules, root indexing, ordered lookup, and the
  per-artifact draft→official fallback into the parser.
- Move `FileLookupCache` ownership (new namespace).
- Tests: draft, official, per-artifact fallback, multiple roots.

**Phase 3 — Parser dependency resolution + graph**
- Move `.l`/`.z` parsing, recursive loading, identity registry, cycle
  representation, and duplicate-dependency handling.
- Move the per-file AST parse cache ownership.
- Tests: recursive deps, missing dep, parse failure, duplicate dep, cycle,
  repeated access does not reparse, complete closure.

**Phase 4 — Parser graphics parsing**
- Move `.g`/`.y` parsing (`graphics/validation.py`, `validation_bindings.py`) into
  a parser graphics model and companion-path resolution.
- SattLint keeps correlation (`correlate_composite_records`,
  `correlate_picture_display_records`) and warnings.
- Tests: graphics parse; SattLint correlation tests unchanged.

**Phase 5 — SattLint thin adapter**
- Rewrite `load_project`/`load_program_ast` to call `SattLineProject.load`, then
  validate + index into `ProjectGraph`.
- Keep `iter_loaded_projects` and analyzer-facing signatures stable.
- Reconcile strictness (§7) and cycles (§3.4).

**Phase 6 — Retire the old loader**
- Delete `loader.py`, `loader_base.py`, `loader_lookup.py`, `loader_config.py`,
  the moved graphics parse modules, and the parser-owned file caches from
  SattLint.
- Keep `loading.py` (slim), `support.py`, `project_graph.py`, `validation/`,
  analysis caches, correlation/analysis graphics.
- Update `engine.py` re-exports.

**Phase 7 — Docs and cleanup**
- Update `ARCHITECTURE.md`, `AGENTS_REFERENCE.md`, `PYTHON_API.md` (parser project
  API), and SattLint's project-loading docs.
- Add a parser-facing README section for the project layer.

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
  wrapper vs the parser's loaded project). Must be resolved before Phase 1.
- **Behavioral change in strictness**: SattLint currently tolerates partial
  projects; the requested parser default is strict. This affects the TUI/CLI UX
  for missing proprietary libraries.
- **Cycle policy change**: SattLint raises today; the parser represents cycles.
  Confirm no analyzer depends on `CircularDependencyError`.
- **Cache format migration**: moving parse/lookup cache ownership invalidates
  existing caches; budget a rebuild.
- **Graphics split**: parsing vs correlation must be separated cleanly or the
  move will drag analysis back into the parser.

**Open questions (decide before the matching phase)**

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
