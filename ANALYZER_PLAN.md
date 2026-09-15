# Analyzer Plan

Status: implemented
Supersedes: [`ANALYZER_PIPELINE_PLAN.md`](ANALYZER_PIPELINE_PLAN.md), [`ANALYZER_CONSOLIDATION_PLAN.md`](ANALYZER_CONSOLIDATION_PLAN.md)
Related: [`TUI_PRUNING_PLAN.md`](TUI_PRUNING_PLAN.md), [`PARSER_PROJECT_LAYER_PLAN.md`](PARSER_PROJECT_LAYER_PLAN.md)

Two parts, one work program:
- **Part A — Content (what):** the analyzer set, finding ownership, config, descriptions, metadata.
- **Part B — Execution (how):** selection and running — *select an analyzer → run it → print its report.* Nothing else.

Ordering: **Part A before Part B** — the machinery refactor operates on the final analyzer set, and removing `sattline-semantics` outright (rather than folding it) makes the pipeline's projection option moot.

---

# Part A — Content

## A1. Decisions (confirmed)

Legend: **KEEP** · **REMOVE** · **MERGE** (fold into owner) · **MOVE** (reparent unchanged) · **NEW** · **CONFIG** (make configurable) · **REWORD** (description only)

| Analyzer | Finding | Decision |
|---|---|---|
| **alarm-integrity** | Duplicate alarm tag | KEEP |
| | Duplicate alarm condition | KEEP |
| | Conflicting alarm priority | **REMOVE** (redundant sub-case of duplicate-tag / duplicate-condition) |
| | Alarm never cleared | **KEEP** (distinct from reset contamination) |
| **comment-code** | Commented-out code | KEEP |
| | Comment-code read error | **REMOVE** (file already parsed by the strict loader) |
| **loop-stability** (Conflicting setpoints) | Conflicting setpoint | **REMOVE analyzer** → new dataflow rule "same symbol assigned conflicting constants" |
| **data-dependency** | Dependency path | **REMOVE** (fires on any 2-hop chain; low value) |
| | Initialization order | **MERGE** into variables (with signal-lifecycle read-before-write) → analyzer emptied → **REMOVE** |
| **dataflow** | Dead overwrite | KEEP |
| | Condition always true / false | KEEP |
| | Unreachable branch | KEEP |
| | Self-compare condition | KEEP |
| | Stale :OLD read | KEEP |
| | Implicit :NEW read | KEEP |
| | :OLD misuse | **REMOVE** (vendor toolchain catches; verify) |
| | Invalid state access | **REMOVE** (vendor toolchain catches; verify) |
| | *(new)* Conflicting constants | **NEW** (from loop-stability) |
| | *(new)* Transition always true/false | **MOVE** from sfc (dataflow owns condition truth) |
| | *(new)* Non-state multi-site access | **MOVE** from same-cycle |
| **datatype-fields** | Unused / read-only / never-read fields | KEEP (standalone; drop `requires`, Part B) |
| | *(open)* field-level write-without-effect etc. | **OPEN** (possible extension) |
| **spec-compliance** | Code outside a frame module | **REMOVE** |
| | Wrong sequence step prefix (ST_) | **CONFIG** (prefix configurable) |
| | Transition has no name | KEEP |
| | Wrong transition prefix (TR_) | **CONFIG** |
| | OPMessage UseSignature enabled | **REMOVE** |
| | Wrong MES_BatchControl name / Max_TRY / Repeat_TRY | **REMOVE** (all 3) |
| | *(new)* Sequence + equation block name prefix check | **NEW** (configurable) |
| **icf** | All findings | KEEP, except value-prefix example **REWORD** |
| **mms-interface** | Duplicate MMS tag | KEEP |
| | MMS datatype mismatch | **REWORD + REFRAME** to anytype-ends check |
| | MMS naming drift | **REMOVE** |
| | Dead MMS tag | KEEP |
| | *(new)* Outgoing tag written-but-never-read | **NEW** (semantics to clarify) |
| **numeric-constraints** | Limit violation | **REMOVE analyzer** |
| **parameter-drift** | Parameter drift | **REMOVE analyzer** |
| **picture-display-paths** | Unresolved display path | KEEP; **REWORD** intro (drop vendor names); library targets run but only intra-library failures are findings (see A4) |
| | *(new)* Path above base picture (`-------*Test`) | **NEW** |
| | *(optional new)* Library `Program:`-coupling | **NEW** (configurable; see A4) |
| **same-cycle** | Same-cycle shared access | KEEP |
| | Parallel read/write hazard | KEEP |
| | *(new)* Parallel write race | **MOVE** from sfc |
| | Non-state multi-site access | **MOVE** to dataflow |
| **sfc** | Parallel write race | **MOVE** to same-cycle |
| | Unreachable sequence node / transition | KEEP |
| | Transition always true / false | **MOVE** to dataflow |
| | Duplicate transition guard | KEEP (in sfc) |
| **unsafe-defaults** | Unsafe boolean default | **MERGE** into variables; **CONFIG** bypass/enable keys |
| **variables** | Unused variable | KEEP |
| | Read-only non-const | KEEP |
| | Written but never read | KEEP |
| | Write without effect | KEEP |
| | UI-only variable | **REMOVE** |
| | Implicit latch | KEEP |
| | Reset contamination | KEEP |
| | Naming role mismatch | **REMOVE** |
| | Procedure status ignored | KEEP |
| | Global can be localized | KEEP |
| | Hidden global coupling | KEEP |
| | High fan-in/out | KEEP (root locals only); **REWORD** |
| | Duplicated datatype | KEEP |
| | Name collision | **REMOVE** |
| | Layout overlap | **REMOVE** |
| | Min/Max mapping mismatch | KEEP; **REWORD** example |
| | Unknown parameter target | KEEP |
| | Required parameter not connected | **REMOVE** |
| | Contract mismatch | KEEP |
| | String mapping mismatch | KEEP |
| | Magic number | KEEP |
| | Record order dependence | KEEP; **REWORD** example |
| | *(moved in)* Read before write / init order | **MOVE** from signal-lifecycle + data-dependency |
| | *(moved in)* Shadowing | **MOVE** from shadowing analyzer |
| | *(moved in)* Unsafe boolean default | **MOVE** from unsafe-defaults |
| **shadowing** | Variable shadowing | **MERGE** into variables → analyzer removed |
| **signal-lifecycle** | Read before write | **MERGE** into variables → analyzer removed |
| **version-drift** | Version drift | **REFRAME** to "same ModuleTypeDef name, different DateCode" |
| **cyclomatic-complexity** | High module complexity | KEEP; **REWORD** description |
| | High step complexity | KEEP |
| | *(new)* High equation-block complexity | **NEW** |
| **symbolic_lite.py** | (unused engine) | **REMOVE** (verify no import) |
| **sattline-semantics** | Aggregate layer | **REMOVE** with LSP surface (see B6) — resolved: remove, do not fold |

**Resulting analyzer set:** **variables** (now includes lifecycle, read-before-write, shadowing,
unsafe defaults), **datatype-fields**, **picture-display-paths**, **mms-interface**, **icf**,
**sfc**, **comment-code**, **spec-compliance**, **alarm-integrity**, **cyclomatic-complexity**,
**same-cycle**, **dataflow**, **version-drift**. Removed: loop-stability, data-dependency,
numeric-constraints, parameter-drift, shadowing, signal-lifecycle, unsafe-defaults,
sattline-semantics.

## A2. Moves and merges (details)

### A2.1 Parallel-branch access → same-cycle
`sfc.parallel_write_race` (write-write) and `same_cycle.parallel_read_write_hazard` (read-write)
become two kinds of one "parallel branch access hazard" owned by **same-cycle**, sharing the
existing `_SfcAccessCollector` + `paths_conflict`/`conflict_rep` machinery. Keep a single canonical
variables traversal (no double `_SfcAccessCollector` run); sfc drops the race.

### A2.2 Condition-truth → dataflow
`sfc_transition_always_true/false` fold into `dataflow.condition_always_true/false`. dataflow already
evaluates every transition guard ([`_dataflow_traversal.py:214`](src/sattlint/analyzers/dataflow/_dataflow_traversal.py:214));
sfc's `_sfc_guard_logic` truth engine is removed. `sfc_duplicate_transition_guard` stays in sfc
(duplicate-condition, not truth).

### A2.3 Non-state multi-site → dataflow
`same_cycle.non_state_multi_site` moves to dataflow, which already owns scan-cycle/state semantics.
dataflow gains a per-scan, non-STATE cross-site read+write check.

### A2.4 Read-before-write family → variables
`signal_lifecycle.read_before_write` + `data_dependency.initialization_order` merge into one
**variables** lifecycle finding with one exclusion policy (init value / module parameters /
same-module declaration). Signal-lifecycle and data-dependency analyzers are removed.

### A2.5 Shadowing → variables
The single `shadowing` finding folds into **variables**; analyzer removed.

### A2.6 Unsafe defaults → variables (configurable)
`unsafe_defaults.true_boolean_default` folds into **variables** as a lifecycle kind; the
"bypass"/"enable" token set becomes config (`analysis.unsafe_default_tokens`).

### A2.7 Conflicting constants → dataflow
New dataflow rule tracking assigned constant values per symbol **with reads in between** (covers the
case `dead_overwrite` misses: `X = 1; Y = X; X = 2;`). Must be path-sensitive so branch-exclusive
constants do not fire. Replaces `loop_stability.conflicting_setpoint`.

### A2.8 Version drift reframe
Change from "same-named module instances with structural variants" to **same ModuleTypeDef name with
different DateCode in the same project**.

### A2.9 spec-compliance config
`ST_`/`TR_` prefixes become config. Add a configurable sequence-name and equation-block-name prefix check.

### A2.10 MMS datatype mismatch reframe
Change from "same tag resolves to different source datatypes" to **per-connection**: the anytype on
the SattLine side and the anytype on the tag side must resolve to the same datatype. Requires
resolving the tag-side datatype (see D6).

### A2.11 New checks
- picture-display-paths: "path escapes above the base picture" (e.g. `-------*Test`).
- mms-interface: outgoing tag written but never read (semantics to clarify, D6).

## A3. Metadata layer removal (severity / confidence / category / applies_to)

Remove the display-only tiering (never used; nothing filters or exits on it):
- **`severity`** (`error`/`warning`/`info`) and **`confidence`** (`definite`/`likely`/`style`/…)
  on findings/issues — displayed only, no filtering, no config, no exit-code gating (exit codes stay 0/2).
- **Semantic-rule `category`** (engineering-spec / control-flow / variable-lifecycle / …) and
  **`applies_to`** — consumers were the removed `sattline-semantics` aggregate grouping and the
  registry report.
- **`supports_live_diagnostics`** analyzer flag — LSP-only; dead once the LSP surface is removed.
- The **`severity="info" if analyzed_target_is_library`** branch in picture-display-paths (see A4).

Keep: **`rule_id`** (stable key for corpus manifests and baselines) and **`explanation`/`suggestion`**
("Why it matters" / "Suggested fix" — user-facing help).

Coupling to update together: `Issue`, `AnalysisFinding` (drops severity/confidence fields),
`SimpleReport.summary` (drops the `[severity | confidence | rule_id]` column), `SemanticRule`,
`materialize_issue_metadata` / `register_issue_metadata_materializer`,
`_sattline_semantic_issue_metadata.py`, `_sattline_semantic_models.py`, findings JSON output,
Results tree metadata.

**Rule-id removal: hard delete** (decided). No hidden deprecated ids; corpus `expected_finding_ids`
and `CHANGELOG.md` are updated in the same change. Applies unless production baselines keyed by
`semantic.*` must survive.

## A4. PictureDisplay paths in library targets

Decision: a library PictureDisplay that references the embedding program is **not bad practice**;
but most library displays can and should be verified in isolation.

Path model (resolution is scoped to one program's module tree — the `Program:` prefix or the
declaring target):
- **Down-only** (`+` descent, `*Token` wildcard, named segments, `0` root-jump) never leaves the
  program tree → for a library target that tree is the library, so these are always checkable.
- **`-` ascent** is verifiable while the parent exists inside the library tree; it fails with
  `missing_parent` / "stepped above BasePicture" only when the ascent would exit the library.
- **`Program:<name>`** is external by definition (`missing_program`) — unverifiable in library
  analysis, and a hardcoded-coupling smell.

Handling:
- **Run** picture-display-paths for library targets (remove `picture-display-paths` from
  `LIBRARY_SUPPRESSED_ANALYZER_KEYS`, `application/checks.py:57`).
- **Report** the provably intra-library failures: `wildcard_miss`, `missing_named_child`,
  `ambiguous_named_child` during descent.
- **Suppress** the "reaches beyond the library" classes: `missing_program`, and `missing_parent` /
  "stepped above BasePicture".
- Optionally add a configurable finding for explicit `Program:<name>` coupling in a library.
- Real verification of library displays inside the embedding program remains out of scope.

Once picture-display-paths runs for libraries, `LIBRARY_SUPPRESSED_ANALYZER_KEYS` is empty →
**remove the skip-list mechanism** (Part B).

## A5. Config additions

`analysis.spec_compliance.step_prefix` / `transition_prefix` / `sequence_prefix` /
`equation_prefix`; `analysis.unsafe_default_tokens`; cyclomatic thresholds (module / step / new
equation-block); fan-in/out threshold. **Config only where a real knob exists** (decided) — no
per-finding on/off toggles (that is rule profiles again).

---

# Part B — Execution

## B1. Target mental model

```
selected key(s) ──► exact set of AnalyzerSpecs ──► run(context) ──► Report ──► output
```

1. **Selection is exact.** The analyzers that run are exactly the ones selected. No analyzer is
   silently added, dropped, reordered for correctness, or collapsed into another.
2. **An analyzer is self-contained.** `run(context) -> Report` depends only on the target, config,
   and shared *computation* it can build itself. It never depends on another analyzer having run first.
3. **No planning.** No "normalized plan", no dependency expansion, no suite collapsing, no
   handler/queue validation.
4. **No batching.** No per-target batch vs whole-run split as an execution concept; whether an
   analyzer runs once per target or once per run is a declared `scope` property.
5. **No execution ordering semantics.** Catalog order is display order only.
6. **Output is per selected analyzer.** Results are not merged or cross-filtered by another analyzer.

## B2. `AnalyzerSpec` (slimmed)

```python
@dataclass(frozen=True)
class AnalyzerSpec:
    key: str
    name: str
    description: str
    run: Analyzer                      # run(context) -> Report
    category: str = "correctness"      # keep 3 values; reassign survivors (Part A)
    enabled: bool = True
    scope: AnalyzerScope = "per-target"   # replaces the ICF batch split
    context_kwargs: tuple[str, ...] = ()
    direct_context: bool = False
```

Removed: `requires`, `composed_analyzer_keys`, `composed_issue_kind_names`,
`supports_live_diagnostics` (A3), `semantic_mapping_kind`/`semantic_rule_source`
(no aggregate consumer once `sattline-semantics` is removed, B6).

## B3. Selection filter + one execution loop

```python
def resolve_selected_analyzers(*, selected_keys, get_enabled_analyzers_fn) -> tuple[AnalyzerSpec, ...]:
    enabled = get_enabled_analyzers_fn()
    if not selected_keys:
        return tuple(enabled)  # "no selection" == default CLI set
    selected = {canonicalize_analyzer_key(key) for key in selected_keys}
    return tuple(spec for spec in enabled if canonicalize_analyzer_key(spec.key) in selected)

analyzers = resolve_selected_analyzers(...)
per_target = [s for s in analyzers if s.scope == "per-target"]
per_run = [s for s in analyzers if s.scope == "per-run"]

for target in iter_loaded_projects(cfg):
    context = build_analysis_context(target, ..., create_shared_artifacts=True)
    for spec in per_target:
        record_result(spec, run_with_cache(spec, context))

for spec in per_run:
    record_result(spec, run_with_cache(spec, config_only_context(cfg)))
```

No `_with_required_analyzers`, no `_order_analyzers_for_batch`, no analyzer-key branches in the runner.

## B4. Shared computation stays, dependency enforcement goes

`AnalysisSharedArtifacts` remains an **opportunistic per-target cache**, not a contract:
- `variables` may publish its foundation/collected views when it happens to run; `mms`/`sfc`/
  `datatype-fields` may reuse them, otherwise they build what they need (all three already fall back).
- `requires` validation is deleted; a consumer selected alone always runs.
- `derived_reports` is deleted — no analyzer reads another analyzer's `Report`.

Selecting `mms-interface` alone runs it; selecting `variables` + `mms-interface` together lets
`mms-interface` reuse the foundation. Neither is a dependency.

## B5. UI de-planner

- Delete `_AnalyzeRunPlan`; pass `tuple[str, ...]` selected keys directly.
- Rename `_planner_*` → `_analyzer_*` / `_analyze_*`; `_run_selected_analysis_plan` →
  `_run_selected_analyzers`.
- Rewrite `_analyze_note_text()` in `_app_textual_setup_display.py` (lines 227–260): remove
  `plan.missing_handlers` / `plan.executable_steps` (a live latent crash) and the "planner queue" /
  "suites collapse" / "normalized plan" copy; replace with `"N analyzers selected. Use Run selected
  analyzers."`
- Rename `_ANALYZE_PLANNER_LIST_ID_PREFIX` and `analyze-planner-*` IDs/text; keep the `/` filter.

## B6. sattline-semantics and the LSP surface — REMOVE (resolved)

`sattline-semantics` is **removed**, not folded (the earlier "reporting projection" option is
dropped). It is the LSP-only aggregate ([`sattline_semantics.py:114`](src/sattlint/analyzers/sattline_semantics.py:114));
the LSP surface goes with `TUI_PRUNING_PLAN.md`. Consequences:
- Delete `sattline_semantics.py` + `_sattline_semantic_*` rule/mapping/contract modules.
- Delete `collect_lsp_report_issues`, `get_lsp_projection_analyzers`, `get_semantic_contributor_specs`,
  `get_*_lsp_analyzer_keys`, `_is_batch_dispatch_analyzer`, `SEMANTIC_LAYER_ANALYZER_KEY`,
  `lsp_exposed` / `exposed_via` delivery fields.
- Delete the semantic-rule metadata layer (A3) in the same change.
- `derived_reports` and `use_shared_artifacts` are removed (B4); the editor/LSP snapshot API in
  `sattlint/__init__.py` is removed with the LSP surface.

## B7. issue-kind cleanup

The removed/merged findings stale `variable_analyses.py` (the "1".."25" catalog) and
`--issue-kind` / `--list-issue-kinds`. Per `TUI_PRUNING_PLAN.md`, **remove** `--issue-kind` and the
`selected_issue_kinds` plumbing: `normalize_selected_issue_kind_values`,
`_filter_report_for_selected_issue_kinds`, the `variables`/`VariablesReport` special-cases in
`checks.py`, `AnalyzerSpec.supports_selected_issue_kinds`, and the `"selected_issue_kinds"` context
provider. `variable_analyses.py` is deleted with the issue-kind catalog.

---

# Part C — Description review

Reviewed against three rules: **adequate** (matches what the code does), **simple English** (short
sentences, no unexplained jargon, readable by non-native speakers), **clear example** (concrete,
actually produced by the implementation).

## C1. Variables — TRIM + REWORD

```
Checks every variable, datatype field, and input/output mapping in the project.

Finds:
- Unused variable - declared but never read or written.
- Read-only but not CONST - only read, never written, and not marked CONST.
- Written but never read - written but never read.
- Write without effect - written and read, but the value never reaches an output.
  Example: 'Scaled = RawInput * 2;' then 'Temp = Scaled + 1;' - Scaled only feeds another local value.
- Implicit latch - a flag is set on one path, never cleared on another.
  Example: 'IF StartCmd THEN Running = True; ENDIF;' with no 'Running = False' on the other path.
- Reset contamination - a value written during normal operation is not reset on reset paths.
  Example: a step writes 'Output', but no step clears it when ResetCmd arrives.
- Read before write - a variable is read before it is written or initialized in the same scope.
  Example: 'Output = InputSignal;' when InputSignal has no init value and is never written first.
- Procedure status ignored - a procedure status output is never checked.
  Example: 'RunHomingProcedure(HomingStatus);' and HomingStatus is never checked in logic.
- Shadowing - a local variable hides a variable with the same name in an outer scope.
  Example: a child module declares local 'Level' while a global 'Level' already exists.
- Unsafe default - a bypass or enable flag starts as True.
  Example: 'SafetyBypass: boolean := True;'
- Global can be localized - a global is only used in one module.
  Example: 'SharedCount' is only touched inside PumpModule.
- Hidden global coupling - modules share a global without an interface.
  Example: 'EngineOil' is written in EngineModule and read in DisplayModule.
- High fan-in/out - too many modules read or write the same root-level variable.
  Example: 'RunningState' is read or written by more than ten modules.
- Duplicated datatype - two datatypes have the same structure.
  Example: two RECORDs with the same fields but different names.
- Min/Max mapping mismatch - Min_/Max_ mappings do not match by name.
  Example: 'MaxValue => MaxValue' is fine, but 'MinValue => MinLimit' points to a different name.
- Unknown parameter target - a mapping points to a parameter that does not exist.
  Example: 'NotDeclared => RawInput' but the type has no 'NotDeclared' parameter.
- Contract mismatch - connected parameters have different types.
  Example: 'SetPoint => RawCounter' where RawCounter is integer but SetPoint expects real.
- String mapping mismatch - two string-like types do not match.
  Example: 'BatchName => RawString' where RawString is string but BatchName expects identstring.
- Magic number - a number is used without a name.
  Example: 'Scaled = RawInput * 0.95 + 100.0;' - 0.95 and 100.0 have no meaning.
- Record order dependence - the meaning of a record read depends on the declared field order.

Datatype-field findings move to the dedicated opt-in 'datatype-fields' analyzer.
```

## C2. datatype-fields — REWORD (simpler, shorter)

```
Checks three things about RECORD fields: unused, read-only, and never-read fields.

Finds:
- A field no code ever touches.
  Example: 'UnusedField' with no code path.
- A field that is only read, never written.
  Example: a received record whose 'Status' field is never written.
- A field that is only written, never read back.
  Example: dead output logic.

This analyzer always loads the files that use the datatype, so it is slower than a
plain 'variables' run. Because of that it is opt-in.
```

## C3. picture-display-paths — REWORD intro

```
Checks that the paths used by PictureDisplay buttons point to a real screen or module.

Finds:
- Unresolved display path - a path points to a screen or module that cannot be found in the project.
  Example: a button that opens '+MissingPanel' when no module with that name exists.
```

## C4. mms-interface — REWORD + remove naming drift

```
Checks the MMS connections (read and write blocks) between the program and external systems.

Finds:
- Duplicate MMS tag - the same external tag is used more than once.
  Example: two write blocks both send to tag 'MV_1001'.
- MMS datatype mismatch - the two ends of one MMS connection use different datatypes.
  Example: the SattLine variable is integer but the external tag is real.
- Dead MMS tag - an outgoing tag is never written by the program.
  Example: tag 'LEVEL.SENSOR' is configured but never referenced in the code.
```
(Reframe note: "the two ends" is the target semantics; requires tag-side datatype, D6.)

## C5. icf — REWORD one example only

Value-prefix example is wrong (regex is `^([A-Za-z])::`, `AB::` cannot match):

```
- ICF value prefix inconsistency - the file uses different single-letter prefixes on different lines.
  Example: one line uses 'A::Program:...' and another uses 'B::Program:...'.
```

## C6. sfc — REWORD (after parallel-race and guard-truth move out)

```
Checks all SFC sequences (step diagrams).

Finds:
- Unreachable sequence node - a step can never run.
  Example: a step placed after a step that already ended the branch.
- Unreachable transition - a transition can never fire.
  Example: a transition placed after a step that already ended the branch.
- Duplicate transition guard - two transitions have the same condition.
  Example: TrA and TrB both wait for 'Ready == True'.
```

## C7. comment-code — TRIM (remove read-error bullet)

```
Reads the source files and looks for SattLine code hidden inside comments.

Finds:
- Commented-out code - a comment contains real code.
  Example: '(* IF Running THEN Running = False; ENDIF; *)'.
```

## C8. spec-compliance — REWORD (after removals + config)

```
Checks the code against the engineering style rules.

Finds:
- Transition has no name - a transition has no name.
  Example: 'SEQTRANSITION WAIT_FOR Done'.
- Wrong sequence step prefix - a step name does not start with the configured prefix (default 'ST_').
  Example: 'SEQSTEP step_mix'.
- Wrong transition prefix - a transition name does not start with the configured prefix (default 'TR_').
  Example: 'SEQTRANSITION MyTrans'.
- Wrong sequence name prefix - a sequence name does not start with the configured prefix.
- Wrong equation block name prefix - an equation block name does not start with the configured prefix.
```

## C9. alarm-integrity — KEEP, TRIM one bullet

```
Checks the alarm blocks and the alarm flag writes.

Finds:
- Duplicate alarm tag - the same alarm tag is used by two alarms.
  Example: Alarm1 and Alarm2 both use tag 'TEMP_HIGH'.
- Duplicate alarm condition - two alarms use the same condition.
  Example: Alarm2 reuses the exact condition of Alarm1.
- Alarm never cleared - an alarm flag is set but never reset.
  Example: 'TempHigh = True;' with no later 'TempHigh = False;'.
```

## C10. cyclomatic-complexity — REWORD intro + add equation block

```
Counts how many different paths the logic can take.

Finds:
- High module complexity - a program or module has too many paths.
  Example: a program with 11 paths when the limit is 10.
- High step complexity - an SFC step has too many paths.
  Example: a step with many nested IF branches.
- High equation block complexity - an equation block has too many paths.
  Example: an equation block with 12 paths when the limit is 10.
```

## C11. same-cycle — REWORD (write-race moves in, multi-site moves out)

```
Checks that the same variable is not read and written at the same time in one scan cycle.

Finds:
- Same-cycle shared access - a shared variable is read and written in the same scan by different modules.
  Example: module Reader does 'Output = SharedValue;' while module Writer does 'SharedValue = 0;'.
- Parallel read/write hazard - one parallel branch reads and another writes the same variable.
  Example: a Writer branch does 'Shared = 1;' while a Reader branch does 'Temp = Shared;'.
- Parallel write race - two parallel branches write the same variable.
  Example: two PARALLELSEQ branches both write 'SharedOutput'.
```

## C12. dataflow — REWORD (gains + losses, simpler :OLD/:NEW wording)

```
Follows the values of variables through the code step by step.

Finds:
- Dead overwrite - a write is replaced before its value is ever read.
  Example: 'Flag = True; Flag = Condition;'.
- Conflicting constants - the same variable gets two different constant values in one path.
  Example: 'Setpoint = 10;' then 'Setpoint = 20;'.
- Condition always true - a condition is always true.
  Example: 'IF RawInput >= 0 OR RawInput < 0'.
- Condition always false - a condition is always false.
  Example: 'IF RawInput < RawInput'.
- Unreachable branch - a branch can never run.
  Example: 'IF Level > 100 AND Level < 50'.
- Self-compare condition - a variable is compared with itself.
  Example: 'IF RawInput == RawInput'.
- Stale :OLD read - :OLD is read after the value was written in this scan, so it still means the previous scan.
  Example: 'Counter = Counter + 1; IF Counter:Old == 0'.
- Implicit :NEW read - a State value is read after a write, but :NEW is missing.
  Example: a transition waits for 'Level == 5' after an ENTERCODE wrote 'Level = 5;'.
- Non-state multi-site access - a non-State variable is read and written in more than one place in one scan.
  Example: 'Temp' is read and written in two equation blocks in the same scan.
```

## C13. version-drift — REWORD (reframe to datecode)

```
Checks that two module types with the same name are really the same version.

Finds:
- Version drift - two module types have the same name but different DateCodes.
  Example: two 'Mixer' module types, one dated 2026-01-01 and one dated 2026-06-01.
```

## C14. Removed analyzers (no description)

loop-stability (Conflicting setpoints), data-dependency, numeric-constraints, parameter-drift,
shadowing, signal-lifecycle, unsafe-defaults (fold into variables), sattline-semantics,
`symbolic_lite.py`.

---

# Part D — Delivery

## D1. Impact / coupling

Removing or renaming a finding touches: `_registry_spec_templates.py`, the semantic rule metadata
(`_sattline_semantic_issue_metadata.py`, `_sattline_semantic_rules*.py`, `_sattline_semantic_models.py`),
`application/findings.py` (label map), the analyzer module + its report/summary classes
(`LoopStabilityReport`, `ParameterDriftReport`, …), its tests, `variable_analyses.py`, the delivery
metadata (`_registry_delivery_data.py`), and the spec/description text.

Execution-layer coupling: `_registry_dispatch.py`, `registry/__init__.py`, `_registry_specs.py`,
`plugin.py`, `framework/` (`AnalyzerSpec`, `_shared_analysis.py`), `application/checks.py`,
`ui/_app_textual_analyze.py`, `ui/_app_textual_setup_display.py`, `ui/_app_textual_actions.py`,
`ui/_app_textual_shared.py`.

Config: add `analysis.spec_compliance.*prefixes`, `analysis.unsafe_default_tokens`, cyclomatic and
fan-in/out thresholds. Config removals: none.

## D2. Phases

Each phase keeps `ruff`, `pyright`, and the focused analyzer tests green.
Phase status is tracked inline below (`[done]` = complete and validated).

1. **Fix the live stale-planner crash** (independent, shippable now): `_app_textual_setup_display.py`
   `plan.missing_handlers` / `plan.executable_steps`. **[done]**
2. **Content removals + metadata layer** (Part A §A1 removals, §A3): conflicting alarm priority,
   comment-code read error, dependency path, dataflow :OLD misuse + invalid state access,
   spec-compliance removals, MMS naming drift, numeric-constraints, parameter-drift, variables
   UI-only / naming role / name collision / layout overlap / required-parameter,
   `symbolic_lite.py`; hard-delete `semantic.*` ids; update corpus manifests + `CHANGELOG.md`. **[done]**
3. **Moves/merges** (Part A §A2): parallel race → same-cycle; transition truth → dataflow;
   non-state multi-site → dataflow; read-before-write + init-order + shadowing + unsafe-defaults →
   variables. **[done]**
   - shadowing → variables; unsafe-defaults → variables; read-before-write + init-order → variables
     (merged `read_before_write` kind + `semantic.read-before-write` rule);
   - transition always-true/false folded into dataflow `condition_always_true/false` (sfc truth
     engine removed; `semantic.transition-always-*` hard-deleted);
   - parallel write-race → same-cycle (sfc drops the race; no double `_SfcAccessCollector` run);
   - non-state multi-site → dataflow (`dataflow.non_state_multi_site`; `semantic.non-state-multi-site`).
4. **New checks + config schema** (Part A §A2.7–A2.11, §A5): dataflow conflicting-constants,
   same-cycle write race, cyclomatic equation-block, spec prefix config + new prefix checks,
   picture-display above-base, MMS outgoing-tag-written-never-read, unsafe-default tokens,
   thresholds. **[done]**
   - dataflow `conflicting_constants` (path-sensitive; replaces `loop_stability.conflicting_setpoint`;
     the `loop-stability` analyzer is removed, `semantic.loop-conflicting-setpoint` hard-deleted);
   - cyclomatic `equation.cyclomatic_complexity` + configured module/step/equation-block thresholds;
   - spec-compliance `step_prefix`/`transition_prefix`/`sequence_prefix`/`equation_prefix` config,
     opt-in sequence-name and equation-block-name prefix checks;
   - picture-display `picture_display_paths.above_base` for ascent past the base picture;
   - `analysis.unsafe_default_tokens` and `analysis.fan_in_out_threshold` config;
   - **MMS outgoing-tag-written-never-read deferred**: D6 #2 semantics still open; a literal
     "written but never read internally" check flags every legitimate write-only export, so it is
     not implemented.
5. **Description rewrite** (Part C) with registry/findings/semantic-rule updates in the same change.
   **[done]** — all analyzer descriptions rewritten per Part C; version-drift and MMS
   datatype-mismatch semantic rules reframed; spec rules gained the sequence/equation prefix entries.
6. **Execution — remove the dependency graph** (Part B): `AnalyzerSpec.requires`,
   `_registry_spec_templates` `requires=`, `_registry_dispatch` helpers, `registry`
   validation/order helpers, `plugin.requires`. Selecting `mms`/`sfc`/`datatype-fields` alone must
   work (they already fall back). **[done]**
7. **Selection dispatch + batch split** (Part B §B3): `get_cli_dispatch_analyzers` → exact filter;
   add `scope`; icf → `scope="per-run"`; simplify `collect_run_checks_result`; remove
   `_run_whole_run_analyzer`. **[done]** — `resolve_selected_analyzers` added; per-target/per-run
   split driven by `AnalyzerSpec.scope`; `_run_per_run_analyzer` replaced `_run_whole_run_analyzer`.
8. **Shared-artifact decoupling** (Part B §B4): delete `derived_reports` and
   `run_registry_analyzer(use_shared_artifacts=...)`; keep the opportunistic foundation cache.
   **[done]** — `ReportsByKey`/`derived_reports` and the dead semantic counters removed; the
   foundation/collected-views cache stays.
9. **Remove `sattline-semantics` + LSP surface** (Part B §B6) with `TUI_PRUNING_PLAN.md`; remove
   `LIBRARY_SUPPRESSED_ANALYZER_KEYS` (empty after A4). **[done]** — sattline-semantics and the
   `_sattline_semantic_*` engine deleted; LSP dispatch helpers, `get_*_lsp_analyzer_keys`,
   `_is_batch_dispatch_analyzer`, `SEMANTIC_LAYER_ANALYZER_KEY`, `lsp_exposed`/`exposed_via`,
   and the package-root editor snapshot API removed; picture-display-paths runs for library
   targets (intra-library failures reported, `missing_program`/`missing_parent` suppressed);
   skip-list mechanism deleted.
10. **UI de-planner** (Part B §B5). **[done]** — `_AnalyzeRunPlan` deleted; selected keys passed
    directly as `tuple[str, ...]`; `_planner_*` renamed to `_analyzer_*`/`_analyze_*`;
    `_run_selected_analysis_plan` → `_run_selected_analyzers`; `_ANALYZE_PLANNER_LIST_ID_PREFIX`
    and `analyze-planner-*` ids/text renamed; `/` filter kept.
11. **issue-kind cleanup** (Part B §B7) with `TUI_PRUNING_PLAN.md`. **[done]** — `--issue-kind` /
    `--list-issue-kinds` removed; `normalize_selected_issue_kind_values`,
    `_filter_report_for_selected_issue_kinds`, the `variables`/`VariablesReport` special-cases,
    `AnalyzerSpec.supports_selected_issue_kinds`, and the `"selected_issue_kinds"` context
    provider removed; `AnalysisContext.selected_issue_kinds` removed; `variable_analyses.py`
    deleted; run-record `selected_issue_kinds` fields removed.
12. **Docs + dead-code sweep**: `ARCHITECTURE.md`, `AGENTS_REFERENCE.md`, `FEATURE_GUIDE.md`,
    `CLI_COMMANDS.md`, `CHANGELOG.md`, `plugin.py` docstring,
    `.github/instructions/analyzer-architecture.instructions.md`, and remaining
    "planner"/"requires"/"batch"/"severity" references. **[done]**

## D3. Tests

Remove/rewrite:
- `tests/analyzers/test_analyzers_registry_dependency_graph.py` — delete.
- `tests/analyzers/test_analyzer_isolation.py` — delete the `requires`-raise test; keep the
  isolation/order-independence tests, now covering **all** analyzers.
- `tests/analyzers/test_analyzer_architecture.py` — drop `requires` assertions + plugin test update.
- `tests/analyzers/suites/test_versiondrift_registry.py` — delete the two `requires`-for-sfc tests.
- `tests/analyzers/test_datatype_fields_analyzer.py:104` — drop the `requires` assert.
- `tests/corpus/test_corpus_regression_exactness.py` — replace `deterministic_dependency_order`
  with direct per-spec runs.
- `tests/test_corpus_analyzers.py:141` — drop the `requires` branch.
- Tests for every removed finding and its semantic rule; corpus manifests updated (D1).
- `tests/app/test_app_textual.py` — rename planner tests/IDs; regression test for the Phase-1 crash.

Add:
- Every enabled analyzer runs standalone from an empty context and returns a `Report`.
- `resolve_selected_analyzers` returns exactly the selected keys (no additions/reordering).
- icf is `scope="per-run"` and runs exactly once regardless of target count.
- dataflow conflicting-constants is path-sensitive (no branch-exclusive false positive; catches
  `X = 1; Y = X; X = 2;`).
- picture-display-paths library behavior: intra-library failures reported, `missing_program` /
  `missing_parent` suppressed.

## D4. Validation

```
python -m pytest tests/analyzers -q
python -m pytest tests/app -q
ruff check && ruff format --check && pyright
python -m pytest -q
```

Behavioral smoke:
```
sattlint analyze --check mms-interface
sattlint analyze --check sfc
sattlint analyze --check datatype-fields
sattlint analyze --check icf
sattlint analyze --list-checks
```
Each single-check run must succeed with no other analyzer's output and no
"requires analyzer results from" error; `--list-checks` reflects the final analyzer set.

## D5. Risks

- Removing `derived_reports` / `requires` may increase runtime when several foundation-sharing
  analyzers are selected together. Mitigation: keep the lazy foundation/collected-views cache.
- Rule-id hard delete breaks persisted runs/baselines referencing removed ids; corpus manifests
  updated in the same change.
- The picture-display library change flips behavior from "skipped" to "checked (filtered)" — verify
  against real libraries to confirm no surprise findings.
- `scope="per-run"` is still a special case; it is declarative and analyzer-owned, not runner-owned.

## D6. Open questions

### Decided
1. **Rule-id removal: hard delete.**
2. **Analyzer categories: keep the 3 (`correctness`/`heuristic`/`style`), reassign survivors.** No
   per-finding categories.
3. **Configurability: config only where a real knob exists** (thresholds, token sets, prefixes). No
   per-finding on/off toggles.
4. **Severity / confidence / rule-metadata: remove** (A3).
5. **PictureDisplay library handling: run for library targets; report intra-library failures only,
   suppress `missing_program` / `missing_parent`; optional `Program:`-coupling check** (A4).
6. **sattline-semantics: remove** (B6) — not folded.

### Still open
1. MMS datatype mismatch: is the tag-side datatype resolvable inside the target (MMS library /
   external tag config)? If not, the "two ends" check needs a declaration source.
2. MMS "outgoing tag written but never read": what exactly should it catch?
5. datatype-fields extension: which additional field-level lifecycle kinds are worth the cost?
6. picture-display library `Program:`-coupling: on by default or opt-in?
7. `depends_on_analyzers` delivery metadata: keep as documentation or delete with the graph?
