# Library Resolution & Config Cleanup

> Status: Implemented — all phases (P1–P6) landed and verified (full suite green, ruff clean, pyright strict clean)
> Goal owner: library resolution / config surface
> Related: architecture-upgrade-plan.md, release-1.0-and-doc-alignment.md

## Goal

Make library resolution honest and complete, and strip the leftover legacy
seams that make the config and scan surface misleading:

1. Parse **all** reachable libraries. Remove the hardcoded `controllib`
   "expected proprietary" exception and resolve every dependency like any
   other.
2. Remove the dead "vendor code is not parsed" mechanism
   (`_ignored_dirs` / `_find_vendor_code` / `_find_vendor_deps` /
   `ignored_vendor`).
3. Decide and implement a clear, consistent treatment of ICF files.
4. Fix ABB library-root resolution (stop guessing it from a directory-name
   substring; drop the `__missing_abb_lib__` sentinel).
5. Clean up the surviving legacy config options, dead toggles, inert project
   keys, and inconsistent draft/official handling flagged in the review.

## Context

A review of the config and scan surface found several legacy decisions where
the codebase has special-cased or silently swallowed behavior that should be
ordinary, plus dead scaffolding left behind by past refactors. Key facts:

- `src/sattlint/core/libraries.py` hardcodes `controllib` as an
  "expected proprietary dependency". The loader short-circuits parsing for it
  (`project/loader.py:128-134`) and `record_missing_library`
  (`project/loader_base.py:85-96`) swallows it as a filtered warning
  (`project/support.py:209-216, 224`). When the source genuinely does not
  exist, it is **surfaced as a normal missing library**; when it does exist, it
  is currently skipped.
- The "vendor not parsed" path (`_ignored_dirs`, `_find_vendor_code`,
  `_find_vendor_deps`, `ignored_vendor`) is dead: `_ignored_dirs` is always
  empty and never populated.
- ICF (`icf_dir`) is a real config key but is outside the loader key set and
  consumed by two separate code paths (`project/support.py:228` and
  `analyzers/mms/_mms_interface_helpers.py:99`). ICF is **not** SattLine code;
  it is an ABB tag/interface format validated *against* parsed programs.
- The ABB library root is guessed by name substring `"abb"` in workspace
  discovery (`core/workspace_discovery.py:279-283`), and the LSP/semantic path
  falls back to a nonexistent `__missing_abb_lib__` sentinel
  (`core/semantic.py:270`).
- Multiple legacy options are inert or mis-wired (see Phase P5).

## Phases

### Phase P1 — Parse all libraries; remove the `controllib` exception

Remove the special case so every dependency is resolved and parsed through the
normal path.

Changes:
- Delete `src/sattlint/core/libraries.py` (and its module docstring contract).
- `project/loader.py:8` remove the import; delete the expected-unavailable
  short-circuit at `loader.py:128-134` so a located `code_path` is always
  parsed.
- `project/loader_base.py:14, 85-96` — `record_missing_library`: remove the
  `reason` branch; every missing library now falls through to normal
  missing/failure handling (`graph.missing` + `graph.unavailable_libraries`,
  or `FileNotFoundError` when `strict`).
- `project/support.py:9, 209-216, 224` — delete `is_expected_unavailable_warning`
  and its use inside `target_validation_warnings`.
- `engine.py:16, 231, 234` — drop the re-exported
  `expected_unavailable_library_reason` / `is_expected_unavailable_library` and
  their `__all__` entries.
- Tests: `tests/project/test_project_graph_invariants.py`
  (`test_record_missing_library_controllib_is_not_missing`),
  `tests/app/test_app_support_helpers.py`,
  `tests/app/test_analysis_loading.py`
  (`test_target_validation_warnings_suppresses_controllib_dependency_warning`),
  `tests/app/test_analysis_run.py`
  (`test_run_variable_analysis_hides_controllib_dependency_warnings`).
  Invert/delete the "hides/suppresses/is-not-missing" expectations; a present
  `controllib` source is now parsed, an absent one is a surfaced missing
  library.
- Docs: `.github/instructions/sattline-invariants.instructions.md` — replace
  the "`controllib` is expected unavailable" invariant with "all dependencies
  are resolved and parsed when present; a missing dependency is always
  reported". Also update the `core/libraries.py` reference in
  `docs/exec-plans/architecture-upgrade-plan.md`.

Acceptance: `controllib` is not referenced anywhere in `src/`. If a
`controllib` source file exists under any configured lib dir, it is parsed and
indexed; if it is absent, the analysis reports it as a missing dependency
(never silently filtered). `graph.unavailable_libraries` is still populated for
genuinely missing libraries.

Verification: `pytest -q tests/project/test_project_graph_invariants.py
tests/app/test_analysis_loading.py tests/app/test_analysis_run.py`; then a
real-target run in both modes.

**Decision D1 (required before work):** if real `controllib` sources are not
present on disk, removing the exception turns a formerly-silent gap into a
visible missing-dependency warning for every project that references it.
Confirm that is the intended, honest behavior (this plan assumes yes).

### Phase P2 — Remove the "vendor code is not parsed" mechanism

Delete the dead vendor/ignored-dirs path entirely.

Changes:
- `project/loader_base.py:160` — remove `self._ignored_dirs`.
- `project/loader_lookup.py:25-30` — delete `_is_ignored_base` and every call
  site: `_ordered_lookup_bases` `add()` (`:120`), `_find_in_cached_base`
  (`:244`), the flat fallback loops (`:303`, `:364`), and `_find_vendor_code` /
  `_find_vendor_deps` (`:397-413`).
- `project/loader.py:238-242` — delete the `if vendor_code or vendor_deps:`
  branch so an unresolved dependency always goes through
  `record_missing_library`.
- `models/project_graph.py:48-49, 105` — remove `_ignored_vendor_factory` and
  the write-only `ignored_vendor` field.
- Update any tests asserting `ignored_vendor` or vendor behavior.

Acceptance: no references to `_ignored_dirs`, `_find_vendor_code`,
`_find_vendor_deps`, or `ignored_vendor` remain. Unresolved dependencies are
reported via `record_missing_library` only.

### Phase P3 — ICF files: explicit, consistent, first-class

Recommendation: **keep ICF out of the generic code loader** — it is not SattLine
source and has no dependency graph — but make it an explicit, consistent input
with one definition of where it lives and honest diagnostics.

Changes:
- Consolidate ICF discovery into a single inventory helper
  (`configured_icf_files` in `project/support.py:228-238`), and have
  `analyzers/mms/_mms_interface_helpers.py:99-119` call it instead of
  re-implementing `icf_dir` scanning. One source of truth for `icf_dir` +
  `*.icf` glob.
- Track ICF inputs in analysis input accounting: include the resolved `icf_dir`
  / `.icf` file set in the relevant cache/analysis key so ICF staleness is
  reflected, and emit a first-class warning when `icf_dir` is set but empty
  (currently a bare `⚠ No .icf files found`).
- Emit a clear diagnostic when a configured `.icf` names a program that fails
  to load (make the existing "failed to load program" path explicit in the ICF
  validation summary).
- Do **not** add `icf_dir` to the loader key set
  (`project/loader_config.py:21`); keep the loader restricted to SattLine
  source/deps.

Acceptance: one function discovers ICF files; ICF inputs participate in
cache/staleness tracking; missing/empty ICF inputs produce explicit
diagnostics; the loader still never sees `.icf`.

Decision D2 (settled): **remove the stale docs.** Delete every remaining
`format-icf` command reference (README, feature-guide, SUPPORT, architecture),
keeping only the historical exec-plan note. `format-icf` stays a library
function only (`analyzers/icf/_icf_file_io.py`).

### Phase P4 — Fix ABB library-root resolution

Stop guessing the ABB root by directory name; prefer configured value; drop the
sentinel.

Changes:
- `core/workspace_discovery.py:279-283` — remove the `"abb" in dirname`
  heuristic. `discover_workspace_sources` should not invent an `abb_lib_dir`;
  leave it `None` and let the caller supply the configured value.
- `core/semantic.py:270` — thread the configured `ABB_lib_dir` into
  `load_workspace_snapshot` and prefer it; when unset, use `None` (do **not**
  build `root / "__missing_abb_lib__"`). The loader already treats `None` abb
  root correctly via the program/other-lib fallbacks.
- Keep the "vendor-last" lookup ordering (`loader_lookup.py:112-159`,
  `workspace_discovery.py:168-174`) — that ordering is correct; only the
  root *choice* was broken.
- `config/validation.py:427` already requires an explicitly-set `ABB_lib_dir`
  to exist; keep that.

Acceptance: no `"abb"` substring sniffing and no `__missing_abb_lib__` in the
codebase. The ABB root is exactly the configured `ABB_lib_dir` (or absent).

### Phase P5 — Config surface cleanup

Remove/repair the surviving legacy options. Split into mechanical (safe) and
behavioral (decisions).

Mechanical:
- `project/models.py:76` — drop the dead `merged.pop("ignore_ABB_lib", None)`.
- `config/types.py:21`, `config/io.py:36-45, 81-83`, `config/validation.py:145-152`
  — remove `telemetry.path` entirely (declaration, dual strip, deprecation
  warning).
- `project/types.py:36-37`, `models.py:79-87`, `ui/_app_textual_actions.py:475-476`
  — **remove** `output_dir` / `cache_dir` from `ProjectDict` and the
  `SattLineProject` properties (Decision D4, settled). Cache/output always go
  to the standard user-level locations (`~/.config/sattlint` for config,
  `~/.cache/sattlint` for caches via `get_cache_dir()`); nothing is
  project-relative or per-project configurable.
- `cli/app_commands.py:113`, `application/project.py:248-249`,
  `application/checks.py:164-165` — stop smuggling `use_cache` through the
  `ConfigDict`; pass it as a real parameter. Same for the `analysis_target`
  pseudo-key (`project/support.py:292`).
- Remove dead `force_dependency_resolution` param (`project/loading.py:340,361,369`,
  `application/project.py:176-182`).
- `defaults.py:96-98` — remove the empty `OPTIONAL_TOP_LEVEL_OVERRIDE_KEYS`
  vestige.

Behavioral:
- **Mode default drift** — config defaults to `"official"`
  (`config/defaults.py:47`) while `__init__.py:53` and
  `project/loading_support.py:193` default to `"draft"`. Make config the single
  authority: all loaders/semantic paths must read `mode` from the effective
  config and never fall back to a different literal.
- **Centralize the draft/official extension table.** Today it is duplicated in
  at least four places with slightly different behavior: `core/syntax.py:56-69`
  (canonical `CodeMode` + `code_ext`/`deps_ext`/`graphics_ext`),
  `application/commands.py:42-43` (`DRAFT_SOURCE_SUFFIXES`/
  `OFFICIAL_SOURCE_SUFFIXES`), `config/validation.py:411-412` (`target_exists`),
  `project/loading_support.py:151-152` (reverse-consumer suffixes), and the
  draft-mode `.x`/`.z` fallbacks in `loader_lookup.py:277,338`. Consolidate on
  one exported mapping and derive all of these from it. Specifically decide
  whether draft mode should still fall back to official files (currently it
  does).
- **UI dead toggles** — `scan_root_only` and `use_file_ast_cache` are read in
  `ui/_app_textual_setup_targets.py:116-117` but are not valid config keys and
  are not consumed (the loader takes `use_file_ast_cache` as an explicit arg
  defaulting to `True`). Either wire `use_file_ast_cache` to the loader arg, or
  remove both toggles. `scan_root_only` was already removed once — recommend
  removal.
- **Official-files-lenient-validation policy** — `core/syntax.py:290-293` and
  `graphics/graphics_context_helpers.py:113` auto-enable
  `allow_old_state_assignment` / `allow_unresolved_external_datatypes` for
  `.x`/`.z`. Decision D5 (settled): **remove the leniency; official and draft
  files get the same bar.** Assigning to `:OLD` is always illegal (reading
  `Var:OLD`/`Var:NEW` is common and valid), so `allow_old_state_assignment`
  becomes `False` in every mode and on every path: flip the `True` defaults
  (`validation/__init__.py:89,182`, `structure_core.py:217,246,343`,
  `sequences.py:80,539,677`) and delete the extension-based conditions at the
  two call sites. For `allow_unresolved_external_datatypes`, drop the `.x`/`.z`
  condition in `core/syntax.py:291-293` and keep only the mode-agnostic
  `dependency_context_path is not None` rule. Update test fixtures that
  intentionally rely on the old `True` default, and audit callers of
  `validate_transformed_basepicture*` that pass no flag.
- **Naming default** `style: "infer"` (`defaults.py:76-78`, `types.py:10`) is a
  directive, not a style. Rename to `auto` or treat "infer" as an internal
  sentinel, and deduplicate the duplicated defaults across `config/defaults.py`
  and `project/types.py`.

Acceptance: no inert top-level config keys; `mode`/extensions have one source
of truth; `use_cache`/`analysis_target` are parameters, not dict keys; TUI
toggles are wired or gone.

### Phase P6 — Dead code / compatibility seams + minor bugs

Changes:
- Repoint the entry point from the legacy `sattlint.app` shim to the real CLI
  module (`pyproject.toml:83`, `app.py`, `_COMPATIBILITY_HELPERS` at
  `app.py:322`), or explicitly keep the shim as documented public compat.
- Remove the stale `pyproject.toml:111` per-file-ignore for the deleted
  `src/sattlint/config.py`.
- `cli/entry.py:47-72` — drop `_ParsedCliArgs` phantom fields.
- `cli/cli_output.py:26-37` — remove the dead `--json` alias machinery.
- `cli/_interaction.py:63-68` — `set_interactive_ui_mode` has two identical
  branches; collapse.
- Minor correctness fixes: mojibake `âŒ` in `config/_self_check.py:87`;
  mangled `Config warning ...]` format in `config/io.py:69-71`; default-profile
  description mismatch (`defaults.py:84` vs `project/types.py:53` vs
  `rule_profiles.py:270`).

Acceptance: entry point targets a real module; no phantom CLI fields; no dead
`--json`; the two UI/self-check cosmetic bugs fixed.

## Dependency order

P1 → P2 → P3 → P4 are independent enough to land in any order, but P1 and P2
both touch `project/loader.py` and `record_missing_library`, so do **P1 then
P2** sequentially to avoid merge conflicts. P3, P4 are independent of P1/P2.
P5 and P6 are independent cleanup and can land last, P6 after P5 where they
touch the same files (e.g. `project/models.py`).

Suggested sequence: P1 → P2 → P4 → P3 → P5 → P6.

## Definition of Done

- Every reachable dependency is parsed when present; none is special-cased as
  "expected unavailable". Missing dependencies are always reported.
- The vendor/ignored-dirs mechanism and `ignored_vendor` no longer exist.
- ICF has one discovery path, participates in staleness tracking, and produces
  explicit diagnostics; `format-icf` docs/code are aligned (D2).
- ABB root comes from config only; no name-sniffing, no sentinel.
- No inert config keys, no pseudo-keys in `ConfigDict`, one `mode`/extension
  source of truth, TUI toggles wired or removed.
- Full suite green; Ruff + Pyright strict clean on the touched slice.

## Gates / Verification

- Run focused tests after each phase (see per-phase verification).
- Run `pytest -q` on `tests/`, then `ruff check src tests`, `pyright` on
  `src/sattlint` (see `docs/maintainers/quality-gates.md`).
- Validate config: `sattlint validate-config` on a real `.slproj` before and
  after P5 (`ABB_lib_dir` is kept as-is, D3).
- Run a real-target analysis in both official and draft mode to confirm no
  new hard failures from parsing previously-skipped libraries.

## Decisions

Settled before implementation:

- **D1 — Parse all libs even when a proprietary source is absent.** Confirmed:
  the source is required; an absent library is surfaced as a normal missing
  dependency, never silently filtered.
- **D2 — ICF `format-icf`: remove the stale docs.** Keep the library function.
- **D3 — Keep the `ABB_lib_dir` config key (uppercase).** No rename; the
  internal `abb_lib_dir` normalization stays as-is.
- **D4 — Remove inert `.slproj` `output_dir` / `cache_dir`.** Cache/output
  always go to the standard user-level dirs (config → `~/.config/sattlint`,
  cache → `~/.cache/sattlint`), not per-project.
- **D5 — Same validation bar for official and draft; `:OLD` assignment always
  illegal.** Remove the extension-based leniency: `allow_old_state_assignment`
  is `False` everywhere (defaults flipped), `allow_unresolved_external_datatypes`
  is mode-independent (dependency-context only). See P5.
