# SattLint review findings and fix plan

Status: High severity closed; Medium in progress. A resolution pass on
2026-11-16 fixed every High row and the Medium rows listed in "Resolution
status" below, with regression tests and a clean gate. The remaining Medium and
Low rows are still open; each open row keeps its original finding text.

Two read-only review waves completed. All six continuation
passes are complete (C1 to C6).
Branch: `feature/parser-2026.11.5`
Pull request: #84
Scope: the whole repository, not only the parser upgrade diff.

This document records the open findings from the second review wave. The first
wave produced about forty findings, all fixed on the branch. The second wave
found more, including three places where the first fix batch is incomplete.

Finding counts: 15 High (11 from the first two waves, 3 from C4, 1 from C5),
about 75 Medium, and about 150 Low and nit items. The continuation passes alone
added 249 findings across C1 to C6.

Review method note: the first pass capped each reviewer at eight to ten
findings, and every reviewer stopped exactly at the cap, so that list is a floor
rather than a total. The continuation passes have no cap and their results are
appended below when they arrive.

## Resolution status

Status: 2026-11-16, `feature/parser-2026.11.5`.

Fixed in this pass. Rows with a dedicated regression test: H1, H2, H3, H4, H5,
H6, H7, H8, H9, H10, H11, C2-19, C2-23, C2-47, the per-target analyzer
failure channel, all-targets-failed ordering, `latest` fallback and project
scoping, pseudo-target findings, C4-1, C4-2, C4-4, C4-5, C4-6, C4-9, C4-10,
C4-14, C6-16, C5-9, and the reset-contamination recursion/deduplication. The
remaining fixed rows (C2-24, C2-34, atomic saves, C4-7, C4-8, C4-11 to C4-13,
C4-17, C4-18, C4-36, C6-1, C5-10, C5-18) are covered by structural changes and
the full suite rather than one targeted test each.

- High: H1, H2, H3, H4, H5, H6, H7, H8, H9, H10, H11, C2-9, C4-1, C4-2, C4-3, C5-9.
- Application and runs: per-target analyzer failure channel, all-targets-failed ordering, `latest` fallback, failure-graph cache guard, pseudo-target persistence, C2-19, C2-23, C2-24, C2-34, C2-47.
- CLI and config: project-scoped run payloads, merged `analysis` table, NDJSON envelope and error document, config-warning channel, atomic saves, C4-4 to C4-14, C4-17, C4-18, C4-36.
- Analyzers: module-type subtrees in reset/latching, read-before-write variable naming, C3-15 typedef tag.
- Tests, security, CI: C6-1 (`uv sync --locked`), C6-16 (cache isolation at the source binding).
- UI: C5-10 run status, C5-18 browser extensions.

Still open from the Medium list (kept verbatim below): the dataflow pairwise
scan cost, latch frontier cap, mapped-literal string capacity, parameter/local
symbol kinds, library-scoped record definitions, empty semantic indexes,
C3-9 to C3-14, C1-12 to C1-21, C5-11 to C5-17 and C5-19, and C6-2 to C6-5. All
Low and nit items are open. The gate (`ruff`, `ruff format`, `pyright`, the full
pytest suite, `scripts/check_docs.py`, pre-commit) is clean on the fixed slice.

## High severity

| ID | Area | Location | Finding | Fix |
| --- | --- | --- | --- | --- |
| H1 | Semantic index | `models/project_graph.py:243`, resolve helpers `:186-211` | `index_from_basepic` records every program's root origin under `bp.header.name`, which is always the literal `BasePicture`, so each program overwrites one entry. Targets inherit the last indexed program's source file and library, which misclassifies libraries, corrupts target reports and snapshots, and breaks the reverse-consumer manifest. | Pass the program name to `record_root_origin` and key it by that name. Resolve `root_origin_for_basepicture` by object identity, as `graphics_attachments_for` does. Fix the `header.name` fallback at `project/loading.py:101`. |
| H2 | Cache | `project/loading.py:372` | the analysis-cache metadata step runs before the unresolved-library early return, so the report cache serves findings computed against an incomplete graph even though the AST entry is skipped. | Move the metadata attachment below the guard, so a graph that is not persisted carries no report-cache metadata. |
| H3 | Cache | `project/loading.py:252`, `application/checks.py:209` | `get_cache_dir()` and `get_runs_dir()` call `mkdir` and raise before the new `None` fallback is reached. Cache degradation is unreachable on a real load and on run persistence. | Add one guarded path resolver returning `Path \| None` and use it at both sites. Add a test that drives a real load with a blocked cache directory. |
| H4 | `.slproj` | `project/io.py:58`, `project/models.py:44-49` | Project values are cast, not validated. A missing key raises `KeyError` and surfaces as `internal_error` at exit 3; a string where a list is expected is iterated character by character; wrong types pass silently. | Validate against the project defaults in `load_project`, raise `ValueError` so the wrapper maps to `project_invalid` at exit 2, and warn on unknown keys. |
| H5 | CLI | `cli/_findings.py:197`, `application/findings.py:203`, `analyzers/registry/__init__.py:167` | `findings --rule` filters on `rule_id`, which analyzers almost never set, so it matches nothing for nearly every rule. `analyzers list` always publishes an empty rule list, so the valid value cannot be discovered. | Match on `rule_id or kind`, casefolded, and populate catalogue rule IDs or remove the field and its documentation. |
| H6 | Dataflow | `analyzers/dataflow/_dataflow_non_state_sites.py:207-230` | The non-state typedef walker expands `modulecode` and `submodules` with no active-typedef guard. A recursive module type raises `RecursionError`, and analyzer failures now abort the whole run. | Thread the active-typedef guard around the recursion, as the state walker does. |
| H7 | Reset contamination | `analyzers/reset_contamination/__init__.py:278`, `:311` | The origin filter uses `same_origin_file_stem`, which returns `True` when `origin_file` is absent, so dependency-library typedefs are treated as root-owned and reported under the analyzed target. | Switch to `matches_root_origin` with the analyzed-target library and origin-library arguments. |
| H8 | Change review | `change_review/_ast_normalize.py:40-44` | Primitives are returned bare, so `True` and `1` fingerprint identically and `Enable = TRUE;` versus `Enable = 1;` reports no change. The `Enum` branch is dead for `StrEnum` and `IntEnum` members. | Tag leaves by kind and test `isinstance(value, Enum)` before the primitive test. |
| H9 | Change review | `change_review/_code_model.py:135-145`, `:191-194` | The equation and SFC block iterators yield comment nodes as statements, so a comment-only edit renumbers the block and produces false changes. | Skip `CodeComment` items in both iterators. |
| H10 | UI | `ui/_app_textual_actions.py:1099-1102` | File open, new project, and quit are dispatched directly, bypassing the busy and modal guards. A project can be swapped under a running analysis, and the run can be attributed to the new project. | Route those ids through the toolbar action handler and snapshot config and project path into the action closure. |
| H11 | Analyzer catalogue | `analyzers/registry/__init__.py:31-41`, `:143-148`, `:188-192` | Nine analyzers run by default, but only six are marked CLI-exposed. The guard test derives its expectation from the same catalogue, so it cannot catch the disagreement. | Derive the declared set from the default analyzer key list, mark the three templates, and assert a one-to-one match. |

| C4-1 | CLI startup | `cli/startup.py:184-191`, `config/paths.py:18` | `get_config_path()` runs before the empty-argv check and creates the config directory as a side effect. With an unwritable `XDG_CONFIG_HOME`, every headless command, including ones that need no config, crashes with a raw traceback at exit 1, outside the documented exit codes. | Resolve the config path inside the interactive branch, or catch `OSError` and return exit 2 with an error envelope. |
| C4-2 | CLI output | `cli/_output.py:49-72`, `:77` | Writes go straight to `sys.stdout` and `sys.stderr`. With `PYTHONIOENCODING=ascii` or a legacy Windows console code page, a non-ASCII finding raises `UnicodeEncodeError`, which becomes `internal_error` at exit 3 and discards the whole result. | Write through a UTF-8 stream with `errors="backslashreplace"` in the text writer and `emit_error`. |
| C4-3 | CLI read paths | `cli/_project.py:108-110` | Building the `project show` payload calls `get_cache_dir()`, `get_runs_dir()`, and `resolve_review_output_dir()`, each of which `mkdir`s. A read-only cache location turns a display command into exit 3. | Report the paths without creating them, or degrade to the unresolved string. |

| C5-9 | UI text rendering | `ui/_app_textual_widgets.py:74`, `:272`, `:418`, `:537-545`, `:559`, `:617`, `ui/_app_textual_actions.py:356-362` | `Static` defaults to Rich markup and receives untrusted text such as exception messages, paths, and project names. A message with a lowercase bracket tag silently loses text, and one with a closing tag raises `MarkupError` and aborts the app, exactly when the error dialog is needed. | Pass `markup=False` or wrap the text in `rich.text.Text`. |

Ranked just below these: the TUI stores the user config file as the run project
path until a project is opened (`ui/_app_textual_analyze.py:444`,
`ui/_app_textual_results.py:403`, `cli/startup.py:216`). Runs made in that state
are attributed to `~/.config/sattlint/config.toml` and disappear once a real
project is opened. Keep the project path in its own field and pass an empty
value when no project is open.

## Medium severity

### Application, runs, cache

- Per-target analyzer exceptions bypass the analyzer-failure channel. Only `KeyboardInterrupt` is caught, so a raising spec exits 3 as `internal_error` and the partial output is lost (`application/checks.py:431-449`, `cli/commands.py:303`).
- A run where every target failed is reported as a self-check failure because the empty-target check runs before the failures check (`cli/commands.py:281-302`).
- `--run latest` fails when the newest record is unreadable instead of falling back to an older readable run (`cli/_findings.py:234-255`, `runs/io.py:93-103`).
- A graph with load failures is still cached, and the failed file is not in the manifest, so the frozen failure state replays (`project/loading.py:377`, `parser_adapter.py:415-424`).
- The per-run analyzer pseudo-target is persisted as a run target, so run history and `findings --target` see a phantom target (`application/checks.py:170-177`, `:570-577`).

### CLI, config, reporting

- `findings` and `show` omit `project_path`, and `latest` resolves across projects (`cli/_findings.py:258-266`, `cli/commands.py:368`).
- `project show` reports the unmerged `analysis` table while paths are merged (`cli/_project.py:105`).
- NDJSON errors are prose on stderr, and NDJSON success discards the run envelope (`cli/_output.py:75-83`, `cli/commands.py:103-104`).
- Config warnings are written into the JSON error channel, so stderr is not one JSON document (`config/io.py:57-64`, `cli/_project.py:75`).
- Config and project saves truncate in place instead of temp plus replace (`project/io.py:79-80`, `config/io.py:97-98`).

- C4-4: an `--output` write failure is reported as an internal error (exit 3) instead of a user error (exit 2) (`cli/_output.py:54-56`).
- C4-5: a failed run never touches the `--output` path, so a previous artifact stays in place and a pipeline can archive stale findings (`cli/_output.py:75-83`, `cli/commands.py:271-313`).
- C4-6: grouped text output prints machine identifiers such as `unused (4)` and `variables (4)` instead of human labels (`cli/_findings.py:209-214`, `cli/commands.py:412-414`).
- C4-7: `--group-by` is silently inert for NDJSON because only flat finding records are emitted (`cli/commands.py:94-106`, `:383-402`).
- C4-8: `findings` filter values are never validated, so `--analyzer not-real` returns zero matches at exit 0 while `analyze --analyzer not-real` fails correctly (`cli/commands.py:369-376`).
- C4-9: target existence is checked case-sensitively, so `Demo` configured against `demo.x` fails self-check although `--target` matching is casefolded (`config/validation.py:449-456`).
- C4-10: config value types are unvalidated. `debug = "false"` passes validation and later surfaces as a target load failure naming the target (`config/validation.py:223-358`, `project/loader_config.py:116`).
- C4-11: saving app settings fails when any configured directory or target is missing, because the save path runs the filesystem checks meant for the analysis preflight (`config/io.py:75-77`).
- C4-12: `--quiet` does not suppress config warnings on stderr (`cli/_project.py:65-66`, `:75`).
- C4-13: an invalid `SATTLINT_UI` value raises `ValueError`, which startup does not catch, so it prints a traceback (`cli/startup.py:203-209`, `:106-110`).
- C4-14: a closed pipe is reported as `internal_error` at exit 3, so `findings ... | head -1` fails under `pipefail` (`cli/entry.py:225-236`).

### Analyzers, resolution

- Module-type subtrees are invisible to reset contamination and implicit latching. `ModuleTypeInstance` falls through the module collector, and the typedef check does not walk `mt.submodules` (`analyzers/reset_contamination/__init__.py:99-158`).
- The cross-site dataflow scan compares all accesses pairwise and re-walks the module tree (`analyzers/dataflow/_dataflow_non_state_sites.py:88-110`).
- Read-before-write findings never name the variable in text reports (`analyzers/variables/_variables_read_before_write.py:69-85`).
- The boolean latch merge builds a full product with no frontier cap, unlike its non-boolean sibling (`analyzers/reset_contamination/_reset_latching_paths.py:179-192`).
- String inference assumes MAXSTRING capacity for mapped literals, regardless of the target datatype (`analyzers/string_inference.py:333-346`).
- Module parameters and module-type instance locals are recorded with the wrong symbol kind, and only the typedef path splits them (`core/_semantic_index_reference_support.py:136-143`, `:219-226`).
- Same-named record types from different libraries collapse to the last indexed because `datatype_defs` is keyed by name only (`models/project_graph.py:130`, `:256-261`).
- Collected analysis issues and the access and effect-flow indexes are always empty, so consumers see "nothing found" rather than "not computed" (`core/_semantic_index.py:76`, `:167-178`, `_semantic_snapshot.py:180-194`).

- C3-9: per-typedef usage facts are keyed by module-type name only, so two types with the same name in different libraries collapse and the wrong parameter directions are propagated (`variables/_variables_submodules.py:241`, `:252`, `_variables_execution.py:707`).
- C3-10: compound reset guards are never classified. `IF NOT Seq.Reset AND Guard THEN X := 0` yields no reset path, and the reset write is filed as a run write, so a genuine reset reports as contamination (`reset_contamination/_reset_path_condition.py:34-49`, `__init__.py:209-216`).
- C3-11: alias propagation is single-pass, so multi-hop chains and link order decide whether a usage reaches the root (`variables/_variables_execution.py:717`, `_variables_status.py:126-151`).
- C3-12: string inference never descends into SFC step bodies, and a frame module context is built with an empty environment, so picture names assigned in step or frame code are invisible (`string_inference.py:351-352`, `:372-399`, `:233-241`).
- C3-13: two leaf-path expanders disagree. One raises on a datatype cycle and unknown record, the other silently treats both as a leaf, and their ordering differs (`variables/_variables_access.py:284-350`, `resolution/type_graph.py:97-146`).
- C3-14: every suppression gate resolves the selected issue-kind set through `getattr` on `self: object`, and about forty sibling probes do the same. A rename silently turns every gate into "collect everything" (`variables/_variables_contracts.py:38-54`).
- C3-15: typedef findings in spec compliance are not tagged `TypeDef:`, so path rewriting and report locations differ from every other analyzer (`spec_compliance.py:82`). Low-medium.
- C3-16: origin filtering of nested single modules is inconsistent. Module drift and datatype-field analysis check the origin; SFC reachability, spec compliance, cyclomatic complexity, and unsafe defaults do not, so dependency module trees can produce findings (`sfc/_sfc_module_walk.py:42-48`, `spec_compliance.py:86-93`, `cyclomatic_complexity.py:82`).

### Core, models, architecture

- C1-11: the cache-degradation fix is incomplete. `get_cache_dir_fn()` runs before the guarded builder in three loading paths, and `create_profiler()` calls `get_cache_dir()` before the run's `try`, so an unusable cache location still aborts the whole run (`project/loading.py:252`, `:478`, `:585`, `core/profiling.py:35`). Extends H3.
- C1-12: the partial-index rollback retracts three collections but not the definitions already committed. A failure inside `index_from_basepic` leaves `source_files`, `root_origins`, `datatype_defs`, `moduletype_defs`, and possibly a dependency edge behind, so the target is reported failed while its records stay in the merged picture and cache manifest (`parser_adapter.py:415-424`, `project_graph.py:243-261`). Extends the earlier rollback fix.
- C1-13: root definitions are rooted at the literal `BasePicture`, so program-qualified lookups never match. `find_definitions("Program.Used")` returns nothing while `BasePicture.Used` returns the definition (`core/_semantic_index.py:112-113`, `:162-163`).
- C1-14: the ICF analyzer loads project data itself, and its in-memory reuse check can never succeed because it compares `header.name`, which is always `BasePicture`. Every entry triggers a second load that bypasses the analysis cache and the target failure sink (`analyzers/icf/analyzer.py:96-110`).
- C1-15: registering a plugin with an existing key silently replaces the built-in analyzer and duplicates the catalogue row (`analyzers/plugin.py:45-58`, `registry/__init__.py:189-199`).
- C1-16: the catalogue is cached while the plugin registry is not, so registration order changes what the CLI and UI see (`registry/__init__.py:155-177`, `:184-185`).
- C1-17: three frame-context builders disagree about parameter mappings, parent chain, and parameter keys, so the snapshot scopes frame code differently from the analyzers that report on it (`core/_semantic_index_reference_support.py:101-114`, `variables/_variable_traversal_support.py:93-107`, `_dependency_usage_scope_support.py:167-178`).
- C1-18: snapshot file indexes are keyed by basename only, so same-named files in different libraries collide and a reference query can return definitions from another library (`core/_semantic_helpers.py:136-139`, `_semantic_snapshot.py:170-174`).
- C1-19: failure and warning state is stored three ways, one of them write-only, and failure detail is re-parsed from prose markers instead of the typed record (`project_graph.py:133-136`, `loading_support.py:229-247`, `support.py:26-38`).
- C1-20: logger-based debug diagnostics are never visible because `configure_logging` is never called, and `debug` is truthiness-checked, so `debug = "false"` enables it (`core/logging.py:16-26`, `cli/startup.py:202`).
- C1-21: `engine.py` is a test-only second loader with different semantics: no cache, no failure recording, exceptions escape. Six test files use it, so corpus and crash-sweep coverage exercise a loader users never run, which is how the root-origin defect stayed invisible (`engine.py:89-111`).

Duplicate of earlier items: C1-22 restates the pseudo-target count mismatch (A8, C2-8), and C1-23 restates `.slproj` validation (H4).

### Tests, security, performance

- `ASTCache.save` writes the manifest before the signed payload, so a failed payload write leaves a fresh manifest with a stale payload (`cache/classes.py:107-126`).
- Cache and run files are world-readable, and the HMAC key sits beside the data it protects (`cache/__init__.py:183-197`, `:240`).
- `graphics_source_context_path` falls back across artifact families, so a `.g` file can be validated against a same-stem `.x` body (`graphics/graphics_context_helpers.py:97-104`).
- About thirty tests use relative cache roots such as `cache-dir`, which write into the checkout, and the process-global cache manager is never reset between tests (`tests/app/...`, `cache/manager.py:81-114`).
- The PTY smoke test inherits the developer's real `HOME` and config (`tests/app/test_app_textual.py:4176-4201`).
- The foundation cache is unreachable in production and is not part of cache clearing (`analyzers/framework/_shared_analysis.py:86-91`, `cache/manager.py:54-78`).
- The fuzzers create and delete a temporary file per input (`scripts/fuzz/graphics_fuzzer.py:33-39`, `scripts/fuzz/icf_fuzzer.py:33-39`).

- C6-1: CI uses `uv sync --frozen`, which does not assert that `uv.lock` matches `pyproject.toml`. Only `--locked` (or `uv lock --check`) catches a changed bound or an added dependency (`.github/workflows/ci.yml:39`, `:84`, `:128`, `:156`, `publish.yml:42`).
- C6-2: twenty-seven test modules star-import fixture barrels that also re-export `Any`, `cast`, `SimpleNamespace`, and private aliases, which hides unused imports and dead helpers from Ruff and Pyright.
- C6-3: the same behaviour tests are copied verbatim into two and three files (version-drift delta three times, default-enabled twice, frame-submodule latching twice), so a behaviour change must be applied in three places.
- C6-4: the Textual test factory creates a real temporary project directory in the shared temp area for every app it builds, roughly 68 call sites, outside `tmp_path` isolation.
- C6-5: analyzer tests reach about sixty private symbols through a hand-maintained `SimpleNamespace` façade, so an internal rename breaks tests with no behaviour change.

### UI, change review

- Settings autosave clears the dirty marker after a failed project save, and the manual save action is unreachable (`ui/_app_textual_settings.py:81-96`, `ui/_app_textual_actions.py:530-571`).
- Quit checks neither busy nor dirty state (`ui/_app_textual_actions.py:581-583`, `:1102`).
- The results tree survives a project change and can show the deleted project's findings (`ui/_app_textual_actions.py:674-679`, `:768-782`).
- Branch-nested transition context is read from the top-level sequence list instead of the enclosing branch (`change_review/semantic_diff.py:121-137`, `_code_model.py:197-227`).

- C5-10: a failed or cancelled run is reported as success. The completion message ignores analyzer failures and cancellation (`ui/_app_textual_analyze.py:448-455`).
- C5-11: typing an analyzer filter silently clears selections that do not match, and clearing the filter does not restore them (`ui/_app_textual_analyze.py:155-160`, `:390-402`).
- C5-12: a rebuilt ListView loses its highlight, so Open and Remove can stay disabled or act on nothing. The results list already works around this with `call_after_refresh` (`ui/_app_textual_setup_targets.py:107-111`, `ui/_app_textual_widgets.py:560-563`).
- C5-13: case-insensitive identifiers are compared case-sensitively in the semantic diff, so `EQUATIONBLOCK Main` versus `MAIN`, or `Integer` versus `integer`, reports a change (`change_review/_code_model.py:141-142`, `:188-194`, `semantic_diff.py:221-233`, `impact.py:77-86`).
- C5-14: structural sequence edits can be invisible. A step with empty blocks and no fork produces no statement and never appears, and branch-nested steps are never matched (`change_review/semantic_diff.py:274-279`, `:422-456`).
- C5-15: review source snippets are keyed by bare file name, so two libraries with a same-named source file collapse to one and snippets can read the wrong file (`change_review/loader.py:78-82`, `source.py:20-39`).
- C5-16: a second interaction request is completed with `None` instead of being queued, so the caller treats an unseen confirmation as a denial (`ui/_app_textual_actions.py:182-186`, `ui/_app_textual_shared.py:202-218`).
- C5-17: Change Review aborts the whole batch on one bad target, unlike Analyze, so one stale target blocks review generation for every valid target (`application/change_review.py:33-36`).
- C5-18: the draft-mode file browser hides targets the loader accepts, because it filters on `.s` and `.l` only and ignores the official fallbacks (`ui/_app_textual_setup_targets.py:308-309`, `core/syntax.py:70-76`).
- C5-19: Cancel is treated as a submission. Escape re-applies and saves the current value, or reports "name cannot be empty" (`ui/_app_textual_widgets.py:156-171`, `ui/_app_textual_actions.py:885-903`).

Correction to the earlier UI report: the running-analysis note is never rendered at all (see C5-24), so the claim that it tells the user to wait was wrong. The dispatch bypass in H10 stands.

## Low severity

- Negative `--limit` silently slices from the end (`cli/commands.py:379-381`).
- Added and removed changes publish the other side's source location (`change_review/semantic_diff.py:408-409`).
- Delivery metadata names test files that do not exist (`analyzers/registry/_registry_delivery_data.py:7-15`).
- The word `scope` means delivery taxonomy in the catalogue and runtime dispatch in the analyzer spec (`analyzers/registry/__init__.py:58-77`).
- The semantic snapshot loader duck-types the typed graph (`core/semantic.py:49-60`).
- A dead tracing module is the only `core` to `analyzers` import (`core/tracing.py`, `analyzers/framework/__init__.py:65`).
- ICF unit buckets are stringly typed (`analyzers/icf/__init__.py:609-624`).
- A public test hardcodes `/home/sorenhj` (`tests/app/test_app_textual.py:3733`).
- `_string_models.py` keeps dead aliases after the shared table move (`analyzers/_string_models.py:42-46`).
- A failed `analyze --output PATH` leaves an older file at that path.
- The self-check prints a missing-library error but still returns success (`config/_self_check.py:36-43`).

- C6-6: a paired code body that cannot be parsed silently disables the whole PictureDisplay path diagnostic class (`graphics/graphics_context_helpers.py:107`, `core/syntax.py:200`).
- C6-7: the corpus harness accepts a coarse kind name in place of the rule id that fired, and filters an `unknown` id everywhere, so a manifest can pass with a different finding than it pinned (`tests/test_corpus_analyzers.py:113`, `:43`).
- C6-8: two graphics resolution helpers are defined twice, and private names appear in both modules' `__all__` (`graphics/picture_display_runtime.py:61`, `picture_display_runtime_helpers.py:88`).
- C6-9: the module-type recursion guard in the runtime tree is excluded from coverage, so a regression would hang rather than fail (`graphics/picture_display_runtime.py:266`).
- C6-10: legacy cache migration never finishes when a destination name collides, so it re-walks the old tree on every `get_cache_dir()` call (`cache/__init__.py:267`).
- C6-13: a session fixture can load the developer's real configuration when a developer-only environment flag is set, and nothing consumes it (`tests/helpers/app_menus_support.py:148`).
- C6-14: absolute POSIX paths such as `/tmp/icf` and `/tmp/sattlint-test.slproj` appear in tests that also run on Windows, so the absolute-path branches are not truly exercised (`tests/analyzers/test_icf_analyzer.py:21`, `tests/app/test_app_textual.py:2346`).
- C6-15: the dependency guard only inspects top-level imports, so an import inside `TYPE_CHECKING` is invisible, and its allowlist still names two deleted fuzz modules (`tests/test_dependency_guard.py:71`, `:102`).
- C6-16: test cache isolation patches two importers instead of the source binding, so `core/profiling.py`, `runs/io.py`, and `cli/_project.py` can write into the real cache (`tests/conftest.py:32`).
- C6-17: the per-test timeout uses the thread method, which cannot interrupt a blocked C call or PTY read (`pyproject.toml:76`).
- C6-18: a missing manifest directory fails at collection time with an assertion traceback instead of a reported test failure (`tests/corpus/test_manifest_schema.py:26`).
- C6-19: `tests/app/test_app_textual.py` is 4254 lines against an 800-line cap and holds about 300 private accesses.
- C6-20: CI never runs `pre-commit`, so whitespace, end-of-file, YAML/TOML, merge-conflict, line-ending, and large-file hooks run only on developer machines.
- C6-21: a release re-run passes `skip-existing: true`, so the job can exit green without publishing the new artifact (`publish.yml:106`).
- C6-22: `scripts/check_docs.py` ignores documents by exact filename, truncates link targets at the first `)`, and matches skip directories against any path segment (`scripts/check_docs.py:41`, `:47`, `:56`).
- C6-23: the fuzz targets call `atheris.Fuzz()` with no default time or run bound (`scripts/fuzz/icf_fuzzer.py:42`, `graphics_fuzzer.py:42`).
- C6-24: three helper modules open with "Tests for ..." docstrings but contain no tests, so a search for analyzer coverage lands in a barrel.
- C6-25: 99 of 156 test files disable several Pyright checks, so the type gate on tests mostly verifies imports.
- C6-27: asset containment is lexical, so a symlink inside the program directory that points outside satisfies the existence check (`graphics/validation.py:105`, `:173`, `picture_display_paths.py:192`).
- C6-29: the fuzz extra resolves atheris wheels for manylinux x86_64 only, which is documented but would break the job if the runner moved.

## Branch status of these findings

- Incomplete fixes from the first batch: H2, H3, and the TUI project path.
- Introduced by the branch: the TUI project path attribution.
- Pre-existing and uncovered: H1, H4 to H11, and nearly all Medium and Low items.

## Parser upgrade to 2026.11.6

Status: published 2026-11-15. The branch moves from 2026.11.5 to 2026.11.6 on
this same branch, before merge. The public surface is additive: every name
SattLint imports still exists, the changed constructors only add keyword fields,
and `parse_and_validate` only adds keyword arguments. The delta is the pin, the
lock, a gate run, and a before and after on the behavior list below.

Steps, all on this branch:

1. Bump the pin to `2026.11.6`, regenerate `uv.lock`, and install the dev extras.
2. Re-run the full gate and the corpus manifests.
3. Verify the behavior changes that reach SattLint:
   - a 21-character declaration now parses and reports a validation finding;
   - unknown SFC accessors become undefined references;
   - boolean parameter mapping values are preserved instead of read as the global keyword;
   - lookup roots compare as filesystem paths, so roots differing only in case are distinct;
   - dependency cycles follow resolved artifacts, so a symlink alias is a cycle;
   - the loader is split into four collaborators with unchanged public behavior.
4. Adopt the parts that replace local code:
   - `parse_and_validate` now accepts external definitions, so single-file validation can see the loaded closure instead of calling the validator separately;
   - `UnitIdentity` and `ArtifactIdentity` expose the parser's own identity rules, which the root-origin and casefold work should align with;
   - the project symbol index can back or cross-check the dependency usage facts.
5. Treat new surfaces as product work, not upgrade work: SARIF output for SattLint findings, `format_source` for canonical Change Review snippets, `to_jsonable` for a simpler normalization pass, and the interactor property catalogue and coordinate tails for graphics validation.

Acceptance: the pin, lock, and gate are clean; corpus findings are unchanged
except where 2026.11.6 fixes a parser fact; and every behavior change above has a
recorded before and after.

## Parser feature adoption

The 2026.11.5 release adds parser capabilities SattLint does not use yet. Items
P2, P4, and P6 below are selected for adoption. Items 1 (executing-system
classification), 3 (distribution in reports), 5 (compressed-source position
mapping), and 7 (distribution validation in `syntax-check`) from the earlier
ranking are not included here.

### P2, parallel project load with `workers`

Value: the first load of a large closure dominates analysis time. SattLint loads
serially and hermetically, so every first run, refresh, and cache invalidation
pays the full parse cost.

Approach: add a loader worker setting to the user config and `.slproj` (default
1, optionally auto up to 8), pass it to `SattLineProject.load`, and keep the
serial path for the Textual worker until the Windows spawn path has a test.

Acceptance: the real corpus loads with the same closure and the same findings at
one worker and at several, and the chosen count appears in the debug load
summary. Batch B.

### P4, header change description in Change Review

Value: the picture header now carries the written syntax version, dates, and the
optional change description. Change Review does not compare the header at all,
so a header-only edit with a developer note is invisible. Dates change on every
editor save, so only the description and the written version are useful.

Approach: read the header metadata during review, include the description and
syntax version in the review metadata, and keep dates out of findings.

Acceptance: a header-only edit that adds or changes the description is reported
once, and a date-only edit is not. Batch B.

### P6, adopt the parser extension and companion helpers

Value: removes SattLint's duplicated extension table and its own companion
resolver, both of which have already drifted (the cross-family fallback in
`syntax-check` and the duplicated list in config validation).

Approach: use the parser's `body_mode`, `deps_extensions_for_code`, and
`find_companion_beside` through the surface module, and delete the local copies.

Acceptance: the existing companion tests cover the same-family, cross-family,
and case-insensitive cases, and a new test asserts that the config validator and
the loader agree on the extension list. Batch B.

## Fix plan

### Batch A, before merge

0. Move the parser pin to 2026.11.6 and re-run the gate. The surface is additive, so this is a pin and lock change plus the behavior checks in the upgrade section.
1. H1 root-origin keying.
2. H2 report-cache metadata ordering.
3. H3 guarded cache and runs directory resolution, including C1-11 profiler construction.
4. TUI project path separation.
5. H4 `.slproj` validation.
6. H5 and H11 rule identity and catalogue exposure.
7. H6 typedef recursion guard.
8. H7 reset-contamination origin filter.
9. H8 and H9 change-review fingerprints and comments.
10. H10 File menu and quit guards.
11. C4-1, C4-2, and C4-3: startup config crash, non-UTF-8 output, and read-only commands creating cache directories.
12. C5-9: Rich markup in UI error and path text.

### Batch B, after merge

- Application and run-history Mediums: per-target failure channel, all-targets-failed message, `latest` fallback, failure-cache skip, pseudo-target persistence, new-ICF invalidation (C2-19), foundation cache clearing (C2-23), unique cache temp files (C2-24), per-run-only selection (C2-34), atomic run records and unique ids (C2-47).
- CLI Mediums: project-scoped runs and payloads, merged `analysis`, NDJSON envelope and error document, config warning channel, atomic saves, plus C4-4 to C4-14.
- Analyzer Mediums: module-type subtrees, dataflow bucketing, read-before-write variable, latch frontier cap, mapped-literal capacity, symbol kinds for parameters and locals, library-scoped record definitions, empty indexes, plus C3-9 to C3-16.
- Test and CI Mediums: `uv sync --locked` (C6-1), explicit imports instead of star barrels (C6-2), one owner per duplicated test (C6-3), `tmp_path` project directories (C6-4), replace the private helper façade (C6-5).
- Parser feature adoption: P2 parallel load, P4 header change description, P6 parser extension and companion helpers.
- Core Mediums: C1-12 to C1-21, including rollback completeness, program-qualified semantic paths, ICF reuse, plugin registration and catalogue cache, frame-context parity, snapshot file keys, typed failure state, logging setup, and the test-only loader.
- UI and change review Mediums: C5-10 to C5-19, including run-status reporting, selection preservation, ListView highlight, casefolded diff identity, structural sequence edits, snippet keying, queued requests, per-target review failures, draft file-browser filters, and cancel semantics.

### Batch C, cleanup

- Security and performance: cache file permissions, manifest and payload ordering, companion source context, test cache roots and manager reset, PTY environment, foundation cache wiring, fuzz temp files, symlink asset containment (C6-27), test cache isolation at the source binding (C6-16), timeout method (C6-17), dependency guard reach (C6-15).
- UI Mediums and all Low items, including the C2, C3, C4, and C6 nits recorded above.

## Verification per batch

- Focused tests for the touched slice, including a new test that fails without each fix.
- `python -m ruff check .`
- `python -m ruff format --check .`
- `python -m pyright src/sattlint tests`
- `python -m pytest -q -p no:cacheprovider`
- `python -m pre_commit run --all-files`
- `python scripts/check_docs.py` and Markdownlint when docs change.

## Continuation log

Six continuation reviews are running with no finding cap. Each entry is filled
in as its report arrives. Findings from a continuation are added to the
sections above as well, with a `C` prefix so they are traceable to this log.

### C1, core and architecture

Status: complete. 50 additional findings beyond the first ten.

Scope: `core/`, `models/`, `utils/`, `engine.py`, `parser_api.py`, `assets/`,
`analyzers/registry/`, plus layering, cycles, duplication, error policy,
typing, determinism, and dead code.

Medium, recorded in the new Core Medium section above: C1-11 to C1-21.

Low and nits

- C1-24: `core/workspace_discovery.py` is an unused subsystem, and `SemanticSnapshot.discovery` is stored and never read.
- C1-25: duplicate containment policy in two modules, and a casefolded path key that collapses case-distinct directories.
- C1-26: `core/terminal.py` keeps duplicate public and private wrappers and disables typing for the whole file.
- C1-27: `log_debug_exception` ignores its config argument and contradicts its module docstring.
- C1-28: `core/interaction.pause` raises `EOFError` when stdin is closed, and menu choices are unvalidated.
- C1-29: `core/semantic` carries an unused `debug` parameter, bypasses path-based preprocessing, and uses a third library-naming convention.
- C1-30: the snapshot facade is mostly unexercised, and one query mixes declared and directory library identity.
- C1-31: the definition list and definition dict can diverge, and there are two more initializer formatting conventions.
- C1-32: the reference-support mixin annotates `self: Any` on every method in a 300-line mixin.
- C1-33: call signature views carry unused members, allocate parameter tuples per access, and use a suffix test for status channels.
- C1-34: `CallSite` is an untyped tuple whose argument element nobody reads.
- C1-35: `utils/text_processing.py` builds a second grammar cache and duplicates hint computation.
- C1-36: `utils/_comment_scanning.py` depends on a positional ten-argument factory and matches block ends by length.
- C1-37: `models/usage.py` uses magic access kinds and inconsistent path copying.
- C1-38: `models/_variable_issues.py` carries a dead label table, a 20-field union type, and reflection-based metadata lookup.
- C1-39: `models/project_graph.py` has write-only diagnostics, a graphics fallback that can never match, and writes provenance back into parser-owned nodes.
- C1-40: registry dead surface, plus `canonicalize_analyzer_keys` returning the unstripped key.
- C1-41: the registry import graph drags in every analyzer and the project loader.
- C1-42: profiling docs and helpers drift, including a documented flag that does not exist.
- C1-43: reflection over the typed graph remains at five more sites.
- C1-44: assets are read at import time with no fallback, and their normalization lives in the UI.
- C1-45: findings enrichment catches everything, and two label tables disagree, including legacy alias pairs.
- C1-46: the cache manager has an unguarded global and asymmetric resilience between its two builders.
- C1-47: shared helpers silently accept wrong types, and origin ownership can be decided from stems alone.
- C1-48: an unused validation subclass duplicates its parent (`validation/shared.py:43-52`).
- C1-49: three stale documentation references name modules that do not exist.
- C1-50: the dependency guard misses the edges that exist now, including `core` to `project`, `graphics` to `project`, and `analyzers` to the project loader.

Confirmed clean by this pass: determinism in the listed surfaces, the parser
boundary, casefolded indexing apart from the noted comparisons, and asset
packaging.

### C2, application and run history

Status: complete. 46 additional findings beyond the first eight.

Scope: `application/`, `runs/`, `cache/`, `project/cache.py`, and the
cache-related parts of `project/loading.py`.

High

- C2-9, HIGH: root-origin lookups cannot identify a target, and the consumers
  added on this branch rely on them (`project/loading.py:91`, `:259`,
  `models/project_graph.py:243`, `parser_adapter.py:298`). Same root cause as
  H1. The new consumers are `source_paths_for_current_target`,
  `target_is_library`, and the origin override in `build_project_view`. Tests
  hide it because stubs write real program names into the map.

Medium

- C2-19: a newly added ICF file never invalidates a cached report
  (`project/cache.py:84`, `project/loading.py:155`). The manifest is a snapshot,
  so a new `.icf` changes neither key nor manifest.
- C2-23: "clear all caches" never clears the analysis foundation, which then
  grows without bound (`cache/manager.py:41`, `:54`, `cache/classes.py:25`).
- C2-24: two concurrent runs race on a fixed temporary file name
  (`cache/__init__.py:237-250`). The loser can delete the winner's temp file
  between write and replace, and abandoned `*.tmp` files are never pruned.
- C2-34: a per-run-only analyzer selection still loads every target and builds
  the report cache (`application/checks.py:394`), parsing the whole project for
  no per-target analyzer.
- C2-47: run records are written non-atomically and the id can collide
  (`runs/io.py:31`, `:53`). A crash leaves a truncated record that no pruner
  removes, and a frozen or stepped clock can overwrite an existing run.

Low

- C2-10: manifest mode default is OFFICIAL while the companion helper defaults
  to DRAFT (`project/loading.py:134`, `graphics_context_helpers.py:29`).
- C2-11: a suppressed cache-write failure is completely silent
  (`project/loading.py:383`).
- C2-12: AST-refresh reporting claims success when the cache was unavailable
  (`project/loading.py:478`, `:567`, `:585`).
- C2-13: stale stage timings are persisted as if measured now
  (`project/loading.py:275`, `application/checks.py:413`).
- C2-14: reflection-based call adaptation in the load path
  (`loading_support.py:96`).
- C2-20: dead helpers `variable_issue_kinds_cache_key` and
  `unavailable_libraries` in `project/cache.py:103`.
- C2-21: typed cache fields read back through `getattr`
  (`project/cache.py:53`).
- C2-22: the cache boundary erases the report type (`project/cache.py:70`).
- C2-25: `ASTCache.clear` races the pruner, and the failure escapes into a user
  action (`cache/classes.py:209`, `project/loading.py:486`).
- C2-26: validation happens after the expensive deserialization
  (`cache/classes.py:128`).
- C2-27: an empty manifest produces an entry that can never go stale
  (`cache/__init__.py:92`, `cache/classes.py:114`).
- C2-28: `Any` return types hide the new `None` cache contract
  (`cache/manager.py:117`, `project/cache.py:41`).
- C2-29: cache-key construction is hand-maintained and coarse
  (`cache/__init__.py:332`). The parser version is embedded by hand, and
  `repr(cfg.get(...))` makes directory order and mode case significant.
- C2-30: `get_cache_dir()` migrates on every call and mutates during reads
  (`cache/__init__.py:288`).
- C2-31: the cache manager registry never shrinks (`cache/manager.py:81`).
- C2-32: reading a cache creates the HMAC key file
  (`cache/__init__.py:157`, `:175`).
- C2-35: raw exception text is written into human-readable output
  (`application/checks.py:270`, `:567`).
- C2-36: the per-run analyzer runner cannot return `None`, but the annotation and a
  caller branch say it can (`application/checks.py:257`, `:564`).
- C2-37: issue counts disagree between the analyzer record and the run summary
  (`application/checks.py:119`, `:288`, `runs/types.py:187`).
- C2-38: analyzer scope is stringly dispatched with a silent default
  (`application/checks.py:372`, `:523`).
- C2-39: oversized function and module in `application/checks.py:318`
  (about 280 lines with a complexity suppression).
- C2-41: untyped options pass-through in `application/analyze.py:39`, `:56`.
- C2-42: dead production entry points for cache clearing
  (`application/project.py:187`, `:229`), including an unguarded
  `clear_all` call site.
- C2-43: `run_logged_cli_action` is dead and untyped
  (`application/output.py:29`).
- C2-44: finding payloads carry an untyped dict through the run store
  (`application/findings.py:19`, `:109`), with silent `str()` coercion.
- C2-48: unvalidated run ids reach the filesystem
  (`runs/io.py:23`, `:106`). `load_run("..")` and `delete_run("../x")` escape
  the runs directory.
- C2-49: orphan summary sidecars are never collected (`runs/io.py:62`, `:93`).
- C2-50: `list_runs` writes during a read (`runs/io.py:96`).
- C2-51: run-record typing relies on `dict[str, Any]` and dict-shaped timings
  (`runs/types.py:37`, `:73`, `:137`, `:191`).
- C2-52: corrupt scalar fields degrade silently instead of rejecting the record
  (`runs/types.py:25`, `:113`).
- C2-53: retention limit special cases for zero and negative values are
  undocumented (`runs/io.py:66`).
- C2-54: `save_run` reuses a supplied id without checking
  (`runs/io.py:40`), silently overwriting a stored run.

Nits

- C2-15: `format_debug_missing_entries` and `TargetLoadError` re-parse marker
  strings instead of using the structured failures map
  (`loading_support.py:259`, `project/support.py:25`, `:86`).
- C2-16: direct dict indexing for `program_dir` in the reverse-consumer scan
  (`loading_support.py:120`).
- C2-17: the debug summary now requires the full typed graph
  (`loading_support.py:59`, `project/loading.py:79`).
- C2-18: the origin-file fallback can match several libraries at once
  (`project/loading.py:95`).
- C2-33: the report cache unpickles every entry on construction
  (`cache/classes.py:219`, `:285`).
- C2-40: disabling run history also disables pruning
  (`application/checks.py:207`).
- C2-45: duplicated scalar coercers in `application/findings.py:64` and
  `runs/types.py:18`.
- C2-46: synthesized `context` means two different things
  (`application/findings.py:160`).

### C3, analyzers and resolution

Status: complete. 31 additional findings beyond the first eight.

Scope: every analyzer and the resolution layer.

Medium, recorded in the Analyzers Medium section above: C3-9 through C3-16.

Low

- C3-17: a frozen `Issue` is mutated in place, including `object.__setattr__` on the message, and its dict values are rewritten by text search (`framework/issue.py:18-26`, `shared/instance_paths.py:144-157`).
- C3-18: `_modules_fingerprints.normalize_ast_value` keeps a dict-shaped AST branch with magic keys, so the same value signs differently as a dict and as a dataclass, and the casefold sets differ (`_modules_fingerprints.py:111-121`, `:131-140`).
- C3-19: procedure-status findings report only the first binding when a sink is reused by two calls (`variables/_variables_status.py:158-176`).
- C3-20: shadowing ignores module parameters, so a local that captures a mapped parameter is never reported (`variables/_variables_shadowing.py:65-68`, `:96-98`).
- C3-21: instance-level variable issues are emitted only in limited runs, the inverse of the other analyzers, so full and `--module` runs disagree (`variables/_variable_module_issue_scan.py:170-190`).
- C3-22: seven sites re-hardcode the direction sets that `CallParameter` already models as `direction`, `channel_kind`, and `is_status_channel` (`dataflow/__init__.py:172-178`, `_dataflow_non_state_sites.py:396-403`, `_dependency_usage_facts.py:303-321`, `_reset_path_writes.py:66-73`, `_variables_effect_flow.py:269-281`, `_variables_effect_sources.py:69-81`, `_variables_status.py:110-116`).
- C3-23: mapping-contract helpers return positional 4-tuples and 2-tuples unpacked far from the definition (`variables/_variables_contracts.py:143-148`, `:190-195`, `:293-301`).
- C3-24: `SfcReachabilityFinding` carries a stringly-typed terminator dict with magic keys (`sfc/__init__.py:33-42`, `:51-55`, `:117-128`).
- C3-25: reset condition flags are a dict of magic keys (`reset_contamination/_reset_path_condition.py:30-56`).
- C3-26: reflection accessors bypass the typed facade that already exposes the same state (`variable_usage_reporting.py:30-45`).
- C3-27: `any_var_index` falls back to the first declaration when a global name is ambiguous (`variables/_variables_access.py:410-418`).
- C3-28: `find_all_aliases` drops a second field prefix because its visited test ignores the prefix, unlike the upstream walk (`resolution/_alias_utils.py:41`, `:74`).
- C3-29: an exact-path self reference cannot resolve through the ancestor branch because the length test excludes equality (`resolution/scope.py:16-22`).
- C3-30: resolution diagnostics can list candidates the failing lookup refused, because the message reads the base picture while the lookup used the index (`resolution/_moduletype_resolution.py:145-148`, `:83-88`).
- C3-31: dead shared module `shared/_report_defaults.py`, all four factories uncalled.
- C3-32: dead exported `first_instance_path_for_moduletype` rebuilds a full module-tree walk per call (`shared/instance_paths.py:76-84`).
- C3-33: a re-export wall in `reset_contamination/_reset_path_collection.py:12-176` where only two names are consumed.
- C3-34: duplicated `VarRef` and `str` branches (`variables/_variables_access.py:404-417`).
- C3-35: the same 27-line external-mapping block appears twice (`variables/_variables_effect_flow.py:388-414`, `:460-486`).
- C3-36: a context copy is built per child and used only for frame and instance children (`variables/_variables_submodules.py:353-357`).
- C3-37: two same-named `CommentCodeHit` models in two layers are copied field by field, and a missing graph seam degrades to an empty clean report (`comment_code.py:43-54`, `utils/text_processing.py:19-27`, `reporting/comment_code_report.py:10-18`).
- C3-38: the plugin registry is a process-global dict where import order decides analyzer order and a duplicate key silently overwrites (`analyzers/plugin.py:19`, `:43-56`, `:67`).
- C3-39: an unused-datatype-field check skips a record whose fields were never accessed at all, while the same record with one field touched reports the rest (`variables/_variable_issue_collection.py:460-464`).

Open question recorded by this pass: whether the parser delivers `:Old` in lower or mixed case. The corpus manifest `semantic-scan-cycle` depends on it. If that manifest passes, the case-sensitive comparisons in `dataflow/__init__.py:252` are safe; otherwise they need casefolding. No hand-built test currently pins the real spelling.

### C4, CLI, config, reporting

Status: complete. 46 additional findings beyond the first eight.

Scope: `cli/`, `config/`, `reporting/`, and the `.slproj` handling.

High, recorded in the High table above: C4-1 config path crash, C4-2 non-UTF-8
output, C4-3 read-only commands creating cache directories.

Medium, recorded in the CLI Medium section above: C4-4 to C4-14.

Low

- C4-15: `findings --module ""` silently hides every finding (`cli/_findings.py:165-181`).
- C4-16: NDJSON is buffered, not streamed, feeds the broken-pipe failure, and emits nothing on interruption (`cli/_output.py:63-65`).
- C4-17: `init_project` accepts a `name`, documents it, and never stores it (`project/io.py:102-134`).
- C4-18: `init_project` shallow-copies the module-level default lists, so a returned project aliases process-wide defaults (`project/io.py:120-131`).
- C4-19: a non-table `analysis` crashes `project show` while `analyze` rejects it cleanly; `run_history`, `output`, and `review` tables in a `.slproj` are silently ignored (`cli/_project.py:105`, `project/models.py:39-53`).
- C4-20: the variables report can print `Status: issues` with `Issues: 0` because status and count use different sets (`reporting/variables_report.py:380-400`).
- C4-21: an issue kind with no renderer produces no section while still counting in the total (`reporting/variables_report.py:317-349`).
- C4-22: table columns misalign when a variable is missing because widths use object fields while rendering `?` (`reporting/_variables_report_rendering.py:243-272`).
- C4-23: the same module path renders two ways, and an empty path has two labels (`?` and `(unknown)`) (`reporting/_variables_report_rendering.py:31-40`, `:200`).
- C4-24: ordering is case-sensitive in some reports and casefolded in others (`reporting/_variables_report_rendering.py:434-441`).
- C4-25: case variants of one datatype are listed twice in the sorting-sensitive section (`reporting/_variables_report_rendering.py:480-488`).
- C4-26: ICF drift rendering parses the producer's wording with regexes, so a wording change degrades output silently (`reporting/icf_report.py:39-99`).
- C4-27: report target renaming uses `hasattr`/`setattr` and swallows `AttributeError` (`reporting/target_report.py:27-38`).
- C4-28: a relative `review.output_dir` resolves against the working directory (`change_review/settings.py:17-19`).
- C4-29: startup copy refers to "Setup" while the view is named "Configuration Settings" (`cli/startup.py:211`, `cli/menu.py:21-47`).
- C4-30: repeated `--format` flags disagree before and after a successful parse (`cli/entry.py:190-197`).
- C4-31: `--exact-module` is a silent no-op without `--module` (`cli/entry.py:136`, `cli/_findings.py:169-171`).
- C4-32: an ambiguous run prefix is reported as "not found" (`cli/_findings.py:239-247`).
- C4-33: `--run ""` silently means `latest` (`cli/_findings.py:226`).
- C4-34: findings that differ only in their data payload are merged, keeping the first payload (`cli/_findings.py:80-119`).
- C4-35: a dead branch in project resolution re-inserts a directory that `glob` already matches (`cli/_project.py:34-38`).
- C4-36: `.slproj` version checking is truthiness-based and its message contradicts itself (`project/io.py:60-65`).
- C4-37: two UI writers hardcode `slproj_version: 1` instead of the constant (`ui/_app_textual_actions.py:552`, `:919`).
- C4-38: `project show` text omits `analysis`, `slproj_version`, and the user config path (`cli/commands.py:135-148`).
- C4-39: output writers disagree on JSON formatting and escaping (`cli/_output.py:60`, `:77`, `runs/io.py:56`).
- C4-40: summary payload types mark always-emitted fields optional (`cli/_payloads.py:105-113`).
- C4-41: config warnings are formatted, split, and reassembled, so a message containing `"] "` mis-parses (`config/io.py:32-34`, `:62-64`).
- C4-42: `project_status` shows the containing directory and has no caller (`project/io.py:137-151`).
- C4-43: the UI-mode setter ignores its argument (`cli/_interaction.py:22-25`).
- C4-44: the analyzer listing has no header or legend (`cli/commands.py:171-176`).
- C4-45: the extension list is duplicated in config validation (`config/validation.py:445-449`).
- C4-46: a blank `--project` value silently falls back to discovery (`cli/_project.py:22-24`).

Confirmed clean by this pass: `reporting/corpus_diff.py`,
`reporting/comment_code_report.py`, `config/analysis.py`, `config/defaults.py`,
the success and error payload shapes, the `.slproj` save and reload round trip,
project discovery and ambiguity handling, and analyzer key canonicalization
apart from the rule-identity gap already reported.

### C5, UI and change review

Status: complete. 47 additional findings beyond the first eight.

Scope: `ui/`, `change_review/`, and the UI-facing parts of
`application/project.py`.

High, recorded in the High table above: C5-9 Rich markup crash.

Medium, recorded in the UI Medium section above: C5-10 to C5-19.

Low

- C5-20: the target-load error marker can attach to unrelated output, including another project's, and is not cleared on project changes (`ui/_app_textual_actions.py:328-386`).
- C5-21: trimming the session log loses the reader's scroll position (`ui/_app_textual_actions.py:294-318`).
- C5-22: the retention note advertises twice what the batch trim keeps (`ui/_app_textual_actions.py:302-309`).
- C5-23: lowering retention does not apply until the next write (`ui/_app_textual_settings.py:139-170`).
- C5-24: all view guidance is dead. The note strip is always emptied, so the analyze, setup, settings, and summary notes never render (`ui/_app_textual_actions.py:706-714`).
- C5-25: analysis output is not live despite the promise, because the runner buffers every line and replays it after the run (`ui/_app_textual_actions.py:633`, `application/checks.py:341`).
- C5-26: the Results empty state repeats on every refresh and blames the wrong reason (`ui/_app_textual_results.py:607-618`).
- C5-27: run-history lookup compares the stored path as a raw string, so case differences hide runs on case-insensitive filesystems (`ui/_app_textual_results.py:403-412`).
- C5-28: the run overview prints the recorded absolute project path, which Ctrl+C copies into shared logs (`ui/_app_textual_results.py:347-357`).
- C5-29: a block that stopped touching a variable is dropped from related context (`change_review/impact.py:99-109`, `:246-257`).
- C5-30: removed calls remain listed as callees in change context (`change_review/impact.py:186-203`).
- C5-31: review size statistics mix characters and bytes (`change_review/loader.py:79-86`, `review.py:329-333`).
- C5-32: artifact names use local time at one-second resolution, disagree with UTC metadata, and overwrite within the same second (`change_review/artifacts.py:24-26`, `review.py:349`).
- C5-33: one location is reported for a block that exists at two locations with different files and line numbers (`change_review/review.py:250-292`).
- C5-34: block header search misses lowercase keywords and prefers the farthest match (`change_review/review.py:94-119`).
- C5-35: review lookups are quadratic and re-split files repeatedly (`change_review/review.py:150-207`, `source.py:55-69`).
- C5-36: the AST refresh modal keeps an unbounded, re-rendered status history (`ui/_app_textual_widgets.py:605-641`).
- C5-37: a menu request with no options crashes on mount (`ui/_app_textual_widgets.py:101-111`).
- C5-38: a failed pane mount leaves the shell permanently locked because request state is set before the mount (`ui/_app_textual_actions.py:186-198`).
- C5-39: error dialogs stack without limit (`ui/_app_textual_actions.py:356-362`, `:385-386`).
- C5-40: the file browser reports a directory update when nothing changed (`ui/_app_textual_setup_targets.py:264-276`).
- C5-41: free-text setup prompts save values without validation, and comma-join list values (`ui/_app_textual_setup_actions.py:35-74`).
- C5-42: the AST refresh worker catches too few exception types and can print a traceback over the TUI (`ui/_app_textual_widgets.py:669-683`).
- C5-43: async prompt tasks drop their exceptions (`ui/_app_textual_actions.py:205-222`).
- C5-44: the analyzer list is rebuilt on every refresh, resetting scroll position (`ui/_app_textual_analyze.py:213-230`, `:288-299`).
- C5-45: focusing or toggling an analyzer wipes the session log (`ui/_app_textual_analyze.py:33-61`, `:334-341`).
- C5-46: Change Review shares the analyze action id, so the two cannot be distinguished (`ui/_app_textual_analyze.py:424-428`, `:495-499`).
- C5-47: ambiguous typedef resolution silently picks the first match (`change_review/_code_model.py:550-559`).
- C5-48: the relevant-block statistic counts blocks that are not rendered (`change_review/review.py:271-272`, `:356-359`).
- C5-49: focus is not restored after a dialog closes (`ui/_app_textual_actions.py:225-246`).
- C5-50: UI terminology diverges from the CLI and docs for project, run history, and toggle labels (`ui/_app_textual_shared.py:144-155`, `ui/_app_textual_app.py:154-162`, `:283-327`).

Nits

- C5-51: dead UI machinery, including test-only helpers, an unwired candidate scanner, an unused run-config action, write-only job fields, an unreachable help view, and unused menubar methods.
- C5-52: dead change-review model surface, including unused priority constants, never-populated context fields, and unreachable renderer branches.
- C5-53: latent fingerprint fragility in the `set` and `dict` branches of `normalize_ast_value`, which no current node reaches.
- C5-54: private Textual API coupling in the results tree (its update list, the label node, its expanded flag, the tree invalidation call), which a Textual upgrade can break silently.
- C5-55: the project branch of `action_save_config` duplicates the project persistence helper, checks the suffix case-sensitively, and has no error handling.

Confirmed clean by this pass: worker-to-UI hops, span and layout stripping in fingerprints, interaction futures, the AST refresh modal lifecycle, empty-list and missing-file handling, and the `application/project.py` bindings the UI relies on.

### C6, tests, security, performance, packaging

Status: complete. 29 additional findings beyond the first eight.

Scope: `tests/`, `cache/`, `graphics/`, packaging, workflows, and `scripts/`.

Medium, recorded in the Medium section above: C6-1 lock drift, C6-2 star-import
barrels, C6-3 duplicated tests, C6-4 leaked temp project directories, C6-5 the
private helper façade.

Low-Medium: C6-6 silent diagnostic loss, C6-7 coarse corpus matching.

Low and nits, recorded in the Low section above: C6-8, C6-9, C6-10, C6-13,
C6-14, C6-15, C6-16, C6-17, C6-18, C6-19, C6-20, C6-21, C6-22, C6-23, C6-24,
C6-25, C6-27, C6-29.

Duplicates already recorded: C6-11 repeats C2-24 (cache temp name), C6-12
repeats C2-47 (non-atomic run records), C6-26 repeats C2-28 and C2-31, and
C6-28 repeats C2-33 (report cache unpickle on construction).

Confirmed clean by this pass: signed cache envelopes and HMAC comparison,
`0o600` key creation with `O_EXCL`, stat-snapshot manifest validation, run id
construction, action pinning and workflow permissions, lock and
`requires-python` and Ruff-rev consistency, repository hygiene and ignore
rules.
