# SattLint Analyzer Reference and Rework Plan

> Status: Draft — implementation plan + definitive analyzer reference
> Audience: someone who knows SattLine but is new to SattLint
> Scope: how all 34 registered analyzers work exactly; wiring/organization fixes; adding the ICF check as an analyzer

## Goal

1. Document, precisely and exhaustively, what each of the 34 registered analyzers
   scans and how each decides to emit a finding, so a SattLine engineer who has
   never seen SattLint can predict what a run will report.
2. Catalogue the wiring, overlap, and organization problems found in the current
   registry and propose fixes.
3. Plan the addition of the currently hidden ICF configuration validation as a
   first-class registered analyzer.

## Context

SattLint parses one or more SattLine `BasePicture` programs plus libraries into a
module tree, runs a set of analyzers, and reports `Issue` objects. Every analyzer
is described by an `AnalyzerSpec` built from templates in
`src/sattlint/analyzers/_registry_spec_templates.py`; the catalog aggregates them
in `src/sattlint/analyzers/registry/__init__.py`. Issue kinds are the finding
types (`Issue.kind`). Many analyzers also map their kinds to `SemanticRule`s
(`_sattline_semantic_rules_data.py`, `_sattline_semantic_rules_more_data.py`,
`rule_profiles.py`) that give each finding an id, severity, and category.

### Key SattLine concepts used below

- **BasePicture** — the root program unit (a `.s` file). Owns local variables,
  submodules, moduletype definitions, and module code.
- **ModuleTypeDef** — a reusable type (in `TYPEDEFINITIONS`) with
  `MODULEPARAMETERS` (parameters), `LOCALVARIABLES`, submodules, and module code.
- **SingleModule / FrameModule / ModuleTypeInstance** — concrete nested modules.
  A `ModuleTypeInstance` instantiates a `ModuleTypeDef` and maps parameters with
  `Name => source` (a literal or a variable reference).
- **Parameter mapping** — `Param => literal` or `Param => VariableName`.
- **ModuleCode** — the code body of a scope, containing `EQUATIONBLOCK`s and
  `SEQUENCE`s.
- **EquationBlock** — a named block of statements (`A = B;`, `IF ... ENDIF;`).
- **SFC** — a `SEQUENCE` of steps (`SEQSTEP`), transitions (`SEQTRANSITION`,
  `WAIT_FOR <condition>`), breaks (`SEQBREAK`), forks (`SEQFORKS`), and
  alternative/parallel branches (`SFCAlternative`, `SFCParallel`,
  `SFCSubsequence`, `SFCTransitionSub`). Steps have `ENTERCODE`, `ACTIVECODE`,
  `EXITCODE`.
- **State variables** — declared with the `State` keyword; they may be read with
  `:OLD` (previous scan) or `:NEW` (immediate) qualifiers.
- **Frame module** — a UI frame container; only frame modules may hold
  base-picture code per the engineering spec.
- **MIN/MAX style bounds** — conventions where `Min_<Name>` / `Max_<Name>`
  sibling variables declare limits for `<Name>`.

### How analyzers are organized

Three groups:

1. **Semantic contributors** — analyzers whose kinds map to semantic rules and are
   aggregated by the combined `sattline-semantics` analyzer.
2. **Composed analyzers** — thin wrappers that run another analyzer and forward a
   subset of its kinds (`powerup`, `timing`, `scan-concurrency`,
   `scan-shared-access`, `interface-contracts`, `state-inference`).
3. **Standalone analyzers** — registered but not part of the semantic layer.

Analyzer **category** (correctness/heuristic/style/development) is separate from
the **rule category** attached to each finding (variable-lifecycle,
interface-contracts, module-structure, control-flow, engineering-spec).

Severity per finding is either error or warning (one kind is info). The combined
`--list-checks` / planner surfaces descriptions; the default CLI analyzer set is
`DEFAULT_CLI_ANALYZER_KEYS` in `src/sattlint/analyzers/registry/__init__.py:58`.

---

## Part A — Analyzer-by-analyzer reference

Each section gives: what it scans, how it works, the issue kinds (with severity
and the exact message template where fixed), a SattLine example, and config notes.

### A1. `sattline-semantics` — "SattLine semantics" (correctness, semantic layer)

**What it is.** The combined analyzer. It runs the transform-invariant trace
checks, then every semantic contributor, maps their issues to semantic rules, and
deduplicates by `(rule.id, module_path, data)`.

**How it works.** `analyze_sattline_semantics` first runs
`detect_transform_invariant_violations` (a structural walk) producing
`duplicate_sibling_name` and `unexpected_submodule_type`. If an
`unexpected_submodule_type` is found, the whole layer short-circuits (the module
tree is too broken to analyze). Otherwise every contributor analyzer is run and
its issues are mapped via `map_variable_issues`, `map_framework_issues`,
`map_spec_issues`, and `map_profiled_issues`. Findings are grouped into five
report categories: Variable lifecycle, Interface contracts, Module structure,
Control flow, Engineering spec.

**Issue kinds.** No kinds of its own; it aggregates all contributors (Part A,
sections A2–A34) plus:
- `duplicate_sibling_name` (error) — sibling modules with the same
  case-insensitive name.
- `unexpected_submodule_type` (error) — unexpected non-module nodes under the
  submodule tree.

**Note.** `sattline-semantics` is not batch-dispatched and is not in the default
CLI analyzer set; it is the LSP-facing surface.

---

### A2. `variables` — "Variable issues" (correctness, contributor)

**What it scans.** Every declaration and every read/write in the module tree: root
locals, moduletype parameters and locals, submodule locals, datatype fields,
parameter mappings, and sequence/equation statements.

**How it works.** `VariablesAnalyzer` (composed of many mixins in
`src/sattlint/analyzers/variables/`) collects variable environment, datatype
layouts, and access events, then applies ~26 `IssueKind` checks. It is
configurable via `selected_issue_kinds` (the interactive menu in
`analyzers/variable_analyses.py`).

**Issue kinds (26).** Warnings:
- `unused` — declared variable never read or written.
- `unused_datatype_field` — RECORD field never used anywhere.
- `field_read_only` — RECORD field read but never written for an instance.
- `read_only_non_const` — writable variable only ever read.
- `field_never_read` — RECORD field written but never read for an instance.
- `never_read` — variable written but never subsequently read.
- `write_without_effect` — written value is read internally but never reaches a
  root-visible output (low confidence).
- `ui_only` — consumed only through graphics/interact wiring.
- `implicit_latch` — set True on some paths with no matching False write on the
  complementary path.
- `reset_contamination` — reset-state writes missing/incomplete across sequence
  flow.
- `naming_role_mismatch` — role prefix/suffix (Cmd, Status, Alarm) contradicts
  observed read/write behavior.
- `procedure_status` — procedure status output not checked in control logic.
- `global_scope_minimization` — root global whose access stays in one subtree.
- `hidden_global_coupling` — root global used as an implicit interface across
  several module paths.
- `high_fan_in_out` — root global read/written by many distinct module paths
  (threshold: 3+ modules).
- `datatype_duplication` — complex datatypes duplicated by structure.
- `name_collision` — case-insensitive declaration name collisions in a scope.
- `layout_overlap` — sibling module invocations / rectangular objects overlapping.
- `min_max_mapping_mismatch` — Min_/Max_ parameter mappings not aligned by base
  name.
Errors (interface contracts):
- `unknown_parameter_target` — mapping targets a parameter the moduletype does
  not declare.
- `required_parameter_connection` — instance leaves an internally-used moduletype
  parameter unmapped.
- `contract_mismatch` — mapped datatypes incompatible across the boundary
  (including missing required anytype fields and dynamic-array element
  mismatches).
- `string_mapping_mismatch` — string-like datatypes incompatible (e.g.
  `identstring` vs `string`).
No rule (emitted but not surfaced in the combined report):
- `magic_number` — unlabeled numeric literal (excluding 0).
- `record_component_order_dependence` — positional record-component access makes
  field order part of the runtime contract.
The `shadowing` kind lives in the enum but is produced by the dedicated
`shadowing` analyzer (A7).

**Examples.**
- `LOCALVARIABLES Spare: integer;` with no other reference → `unused`.
- RECORD `SensorType` with field `UnusedField` never touched → `unused_datatype_field`.
- `Child : ChildType (BogusParam => 1)` where `ChildType` has no `BogusParam` → `unknown_parameter_target`.

---

### A3. `picture-display-paths` — "PictureDisplay paths" (correctness, standalone)

**What it scans.** PictureDisplay module paths produced by `ComButProc_`,
`ToggleWindow`, and picture-display rows.

**How it works.** Walks `graphics_picture_display_occurrences`, diagnoses each
`path_row` against the loaded module tree. Literal paths like `"+MissingPanel"`
are resolved directly; variable paths like `"Paths.OperationPath"` are first
resolved by an exact-string inference engine that tracks string provenance from
initializers and parameter mappings before resolution is attempted.

**Issue kinds.**
- `picture_display_paths.unresolved` (info when target is a library; no semantic
  rule). Failure reasons:
  - `missing_named_child` — named module not found under the parent, or the
    declaring module is absent.
  - `ambiguous_named_child` — name matches several children.
  - `missing_program` — program unit prefix not loaded (e.g. `OtherProg:+Panel`).
  - `wildcard_miss` — `*Name` matches no descendant.
  - `missing_parent` — too many leading `-` steps (above BasePicture).
  - `unimplemented_asset` — `.emf`/`.wmf` references (not implemented).

**Example.** Path `+MissingPanel` under `Root` with no such module →
`could not be resolved: module 'MissingPanel' was not found under 'Root'`.

---

### A4. `mms-interface` — "MMS interface mappings" (correctness, contributor)

**What it scans.** `MMSWriteVar`, `MMSReadVar`, `MMSReadVarCyc`, `MMSReadWrite`
instances (recursively through moduletype typedefs, resolving parameter mappings
to source variables and write locations) plus external `.icf` entries.

**How it works.** Builds an interface inventory of (source variable, datatype,
external tag) entries, then checks tag uniqueness, datatype consistency, tag
family spelling, and whether outgoing sources are written.

**Issue kinds.**
- `mms.duplicate_tag` (error) — same normalized external tag mapped more than
  once. Message: `MMS tag 'MV_1001' is configured 2 times across the analyzed target.`
- `mms.datatype_mismatch` (error) — same tag resolves to conflicting datatypes.
  Message: `MMS tag 'MV_1001' resolves to conflicting datatypes: integer, real.`
- `mms.naming_drift` (warning) — same tag family with multiple spellings.
  Message: `MMS tag family 'MV1001' appears with multiple spellings: 'MV-1001', 'MV_1001'.`
- `mms.dead_tag` (warning) — outgoing tag whose source variable is never written.
  Message: `Outgoing MMS tag 'MV_1001' maps to 'OtherVal', but the source is never written inside the analyzed target.`

**Example.** Two `MMSWriteVar` instances mapping `LocalVariable => TagVal`/`OtherVal`
(integer vs real) and `RemoteVarName => "MV_1001"` duplicated → duplicate_tag +
datatype_mismatch; `OtherVal` never written → dead_tag.

---

### A5. `sfc` — "SFC checks" (correctness, contributor; `requires=("variables",)`)

**What it scans.** Every SFC sequence in reachable module code, including
alternative, parallel, subsequence, and transition-sub branches.

**How it works.** `SfcAnalyzer` walks sequence node lists, checking structural
reachability after terminators (`SFCBreak`, `SFCFork`), simplifying transition
guard logic, comparing guards across transitions, and applying configured step
contracts. Parallel-branch write conflicts are detected by collecting writes per
branch of an `SFCParallel`.

**Issue kinds.**
- `sfc_parallel_write_race` (error) — parallel branches write the same variable.
  Message: `Parallel branches in sequence 'Seq' write to the same variable(s): ...`
- `sfc_unreachable_sequence_node` (warning) — node after a terminator can never
  run. Message: `Sequence 'Seq' contains unreachable node 'X' because 'Break' terminates that path earlier.`
- `sfc_unreachable_transition` (warning) — transition can never fire for the same
  reason.
- `sfc_transition_always_true` (warning) — guard simplifies to true.
- `sfc_transition_always_false` (warning) — guard simplifies to false.
- `sfc_duplicate_transition_guard` (warning) — equivalent guards in one branch.
- `sfc_illegal_state_combination` (error) — configured mutually exclusive steps
  can run at the same time (config: `mutually_exclusive_steps`).
- `sfc_missing_step_enter_contract` (warning) — step's enter block omits required
  writes (config: `step_contracts.required_enter_writes`).
- `sfc_missing_step_exit_contract` (warning) — step's exit block omits required
  writes (`required_exit_writes`).
- `sfc_step_state_leakage` (warning) — stale state inherited because enter writes
  are missing.

**Example.** `SEQSTEP Unreachable` placed after `SEQBREAK` in the same branch →
unreachable-sequence-node; two `SFCParallel` branches both writing `SharedOutput`
→ parallel-write-race.

---

### A6. `comment-code` — "Commented-out code" (correctness, contributor)

**What it scans.** All SattLine source files on the graph (`.s`, `.x`, `.l`,
`.z`).

**How it works.** Reads each file (decompressing if necessary), finds comment
blocks whose content parses as valid SattLine code, and classifies each hit with
indicators: `assignment`, `call`, `control`, `comparison`.

**Issue kinds.**
- `comment_code` (warning) — valid code inside a comment. Message:
  `CommentedCode.s:17-19 control, assignment`.
- `comment_code_read_error` (error) — file exists but could not be read/decoded
  (`OSError`, `UnicodeError`, `ValueError`). Note: non-existent paths are skipped
  silently, not reported.

**Example.** `(* IF Running THEN Running = False; ENDIF; *)` → `control, assignment`.

---

### A7. `shadowing` — "Variable shadowing" (correctness, contributor)

**What it scans.** Local declarations in the module tree (root-origin only).

**How it works.** Walks the module tree; for each local declaration, checks
(case-insensitively) whether any ancestor declaration has the same name. Only
declarations originating from the analyzed root are considered; external library
typedefs are ignored.

**Issue kinds.**
- `shadowing` (warning) — local hides an outer/global name. Role text:
  `shadows 'Setting' from Root.Parent`.

**Example.** Child moduletype declares local `Setting`, parent declares `setting`;
`Mirror = Setting;` inside the child references the wrong declaration.

---

### A8. `spec-compliance` — "Engineering spec compliance" (correctness, contributor)

**What it scans.** AST-visible constructs: base-picture code placement, SFC step
and transition names, `NNESystem:OPMessage` instances, and
`NNEMESIFLib:MES_BatchControl` instances.

**How it works.** `analyze_spec_compliance` checks each rule directly:

- BasePicture module code must be empty (code belongs in frame modules).
- `SEQSTEP` names must start with `ST_`; transitions must have a name and start
  with `TR_` (recursively through alternative/parallel/subsequence/transition-sub
  branches).
- `OPMessage` instances must not resolve `UseSignature` to True (literal mapping
  or variable init).
- `MES_BatchControl` instance name must be exactly `MES_BatchControl`, `Max_TRY`
  must resolve to 10, and `Repeat_TRY` to 20 (literal, init value, or moduletype
  default).

**Issue kinds (all warning, engineering-spec).**
- `spec.basepicture_direct_code`
- `spec.sequence_step_prefix` — e.g. `Sequence step 'step_mix' must start with 'ST_' ...`
- `spec.transition_name_missing`
- `spec.transition_prefix`
- `spec.opmessage_use_signature`
- `spec.mes_batch_control_name`
- `spec.mes_batch_control_max_try`
- `spec.mes_batch_control_repeat_try`

**Example.** `SEQTRANSITION WAIT_FOR Done` (unnamed) or
`OPMessage (UseSignature => True)`.

---

### A9. `loop-output-refactor` — "Loop output refactor" (correctness, contributor)

**What it scans.** Each module's `ModuleCode`: equation blocks and SFC step
`ENTER`/`ACTIVE`/`EXIT` code (including inside alternative/parallel/subsequence/
transition-sub branches).

**How it works.** Treats each of those code chunks as an execution block with a
read set and a write set (root variable name, casefolded). Builds a directed graph
block → block when one block writes a variable another block reads, computes
strongly connected components (Tarjan), and reports every SCC with ≥2 blocks.

**Issue kinds.**
- `sorting.loop_output_refactor` (warning). Message:
  `Dependency loop across sorted blocks in 'Root': EquationBlock 'Input', EquationBlock 'Feedback', ...`.
  At least one dependency in the cycle is delayed by a full scan.

**Example.** `EquationBlock Input: A = B;` and `EquationBlock Feedback: B = A;`
form a two-block cycle.

---

### A10. `alarm-integrity` — "Alarm integrity" (correctness, contributor)

**What it scans.** Alarm function-block instances and alarm boolean writes.

**How it works.** An **alarm source** is a `ModuleTypeInstance` whose resolved
moduletype declares (or whose instance maps) a tag parameter (name in
`tag`/`alarmtag`/`eventtag`) **and** a priority or condition parameter
(`priority`/`severity`, or `condition`/`alarmcondition`/`enablemodule`/`enable`/
`active`/`trigger`). For each candidate it resolves tag/priority/condition values
(literal mapping, variable init, or moduletype default) and compares them across
all candidates. Separately, it collects boolean writes to alarm-like variables and
checks they are both set True and cleared False.

**Issue kinds.**
- `alarm.duplicate_tag` (error) — same tag across ≥2 sources.
  Message: `Alarm tag 'X' is configured more than once across alarm sources: ...`
- `alarm.duplicate_condition` (warning) — same condition reused.
- `alarm.conflicting_priority` (warning) — same tag/condition with differing
  priorities/severities (e.g. 1 and 3).
- `alarm.never_cleared` (warning) — alarm variable written only True, never
  False. Message: `Alarm variable 'AlarmTrip' is only written with True and is never explicitly cleared to False in this scope.`

**Example.** `AlarmTrip: boolean := False; ... AlarmTrip = True;` with no False
write → never-cleared.

---

### A11. `initial-values` — "Initial value validation" (correctness, contributor)

**What it scans.** Instances of recipe (`recpar`) and engineering (`engpar`)
parameter modules.

**How it works.** For each such instance, finds the required value-like parameter
(names in `value, default, defaultvalue, initialvalue, initvalue, boolvalue,
intvalue, realvalue, stringvalue, recipevalue, engineeringvalue, setpoint`, or any
name ending in `value` outside the allowlist). The parameter is satisfied only if
it is mapped to a literal, mapped to a variable with an `init_value`, or defaulted
in the moduletype. Otherwise `initial-values.missing_required_default` fires.

**Issue kinds.**
- `initial-values.missing_required_default` (warning).
  Message: `Recipe parameter 'RecipeSP' (RecParReal) is missing a required initial value; checked Value and no default or explicit initialized mapping is configured.`

**Example.** `RecParReal` declares `Value: real;` with no mapping/default while
`MinValue`/`MaxValue` are configured → finding.

---

### A12. `interface-contracts` — "Interface contracts" (correctness, composed)

**What it scans.** Moduletype instance parameter mappings.

**How it works.** Runs the `variables` analyzer with `selected_issue_kinds`
restricted to the four contract kinds and forwards only those.

**Issue kinds (all error, interface-contracts).**
- `unknown_parameter_target` — mapping targets an undeclared parameter.
- `required_parameter_connection` — internally-used parameter left unmapped.
  Role: `required parameter connection missing for 'RequiredValue'`.
- `contract_mismatch` — incompatible datatypes across the boundary (including
  missing required anytype fields, dynamic-array element mismatches).
- `string_mapping_mismatch` — string-like type incompatibility.

**Example.** `Child : ChildType` with no mapping while `ChildType` uses
`RequiredValue` internally → required-parameter-connection.

---

### A13. `powerup` — "Power-up" (correctness, composed)

Composed of `initial-values` + `unsafe-defaults` (A11, A32). Forwards:
- `initial-values.missing_required_default` (warning)
- `unsafe_defaults.true_boolean_default` (warning)

Report sections: "Missing startup values", "Unsafe startup defaults".

---

### A14. `naming-consistency` — "Naming consistency" (style, standalone)

**What it scans.** Declaration names for variables (locals + module parameters),
modules (`SingleModule`, `FrameModule`, root-origin `TypeDef`), and instances
(`ModuleTypeInstance`).

**How it works.** Classifies each name into a style via regex:
`pascal` (`FlowRate`), `camel` (`legacyTemp`), `snake` (`tank_level`),
`upper_snake` (`MAX_LIMIT`), `lower` (`flowrate`), `upper` (`MAXLIMIT`); anything
with a separator that matches none → `unknown` (ignored). With the default
`infer` mode, the most common style per symbol kind wins and outliers are flagged.
Explicit per-target styles and allowlists are configurable under
`analysis.naming.{variables,modules,instances}.{style,allow}`.

**Issue kinds.**
- `naming.inconsistent_style` (warning).
  Message: `Variable name 'tank_level' uses snake style, but variable names are expected to use pascal style.`

**Example.** `FlowRate`, `PumpSpeed` (pascal) and `tank_level` (snake) → the
snake name is flagged.

---

### A15. `cyclomatic-complexity` — "Cyclomatic complexity" (style, standalone)

**What it scans.** The root program, each root-origin module type, each nested
module, and each SFC step.

**How it works.** Complexity starts at 1 and adds: one per `IF`/`ELSIF` branch
(+1 per branch condition pair), one per `AND`/`OR` connector, one per ternary
branch, and one per extra `SFCAlternative`/`SFCParallel` branch, plus recursive
contribution of nested conditions and step ENTER/ACTIVE/EXIT code. Thresholds are
fixed code constants: **10** for program/module/module-type, **6** for SFC steps.
Only strictly-above-threshold values are reported.

**Issue kinds.**
- `module.cyclomatic_complexity` (warning).
  Message: `Program 'Root' has cyclomatic complexity 11, exceeding threshold 10.`
- `step.cyclomatic_complexity` (warning).
  Message: `Step 'HeatUp' in sequence 'MainSeq' has cyclomatic complexity 7, exceeding threshold 6.`

---

### A16. `parameter-drift` — "Parameter drift" (heuristic, standalone)

**What it scans.** Every moduletype instance's resolved parameter values.

**How it works.** Groups instances by `(moduletype, parameter name)` and resolves
each value to a literal (literal mapping, init-value mapping, or moduletype
default). When ≥2 instances resolve to ≥2 distinct literal values (string literals
casefolded/stripped), each drifting instance is reported. Mappings from globals,
dotted refs, or unresolvable variables are skipped.

**Issue kinds.**
- `module.parameter_drift` (warning).
  Message: `Module type 'DoseValve' parameter 'Timeout' varies across instances: Program.ValveA=10, Program.ValveB=15.`

---

### A17. `signal-lifecycle` — "Signal lifecycle" (correctness, contributor)

**What it scans.** Each module scope's statement sites in order (equations then
sequences).

**How it works.** Keeps a `written` set seeded with variables that have an
`init_value`. Walks statements in order; assignments and `SetBooleanValue(target,
True/False)` add their root name to `written`. A read whose name is not in
`written` is recorded as a read-before-write; writes that are never followed by a
read are unconsumed. Branch handling: for `IF` statements the `written` sets of
all branches are intersected; SFC branches are flattened linearly (no condition
evaluation).

**Issue kinds (warnings, variable-lifecycle).**
- `signal_lifecycle.read_before_write` — one issue per variable listing all
  offending sites. Message: `Signal 'X' may be consumed before any known write in {sites}.`
- `signal_lifecycle.unconsumed_write` — one issue per variable.
  Message: `Signal 'X' is written but never consumed later in this scope; writes appear in {sites}.`

**Example.** `OutputSignal = InputSignal;` before any write to `InputSignal`, and
`NeverConsumed = False;` with no later read.

---

### A18. `loop-stability` — "Loop stability" (correctness, contributor)

**What it scans.** Each module scope's assignments.

**How it works.** Collects, per scope, every target assigned a scalar literal,
and reports any variable that receives ≥2 distinct literal values in that scope
(compared by `repr`). Conflict is per-scope and path-insensitive.

**Issue kinds.**
- `loop_stability.conflicting_setpoint` (warning).
  Message: `Variable 'Setpoint' receives conflicting literal assignments in this scope: Eq=10, Eq=20.`

**Example.** `Setpoint = 10;` then `Setpoint = 20;` in one equation block.

---

### A19. `fault-handling` — "Fault handling" (correctness, contributor)

**What it scans.** Boolean variables whose name contains `fault` or `alarm`, per
module scope.

**How it works.** Collects writes per such variable. If a variable is written
`True` and never written `False` in the scope → missing recovery. If it is written
`True` and never read in the scope → unhandled.

**Issue kinds (warnings, control-flow).**
- `fault_handling.missing_recovery` — raised but never cleared/acknowledged.
- `fault_handling.unhandled_fault` — raised but never consumed by reachable logic.

**Example.** `HighFault = True;` with no False write and no later read → both
kinds.

---

### A20. `numeric-constraints` — "Numeric constraints" (correctness, contributor)

**What it scans.** Literal assignments in all module scopes.

**How it works.** Bounds are inferred from sibling variables named
`Min_<name>` / `Max_<name>` (prefix or suffix). An assignment whose literal
resolves outside `[Min, Max]` is reported.

**Issue kinds.**
- `numeric_constraints.limit_violation` (warning).
  Message: `Assignment to 'Output' in {site} resolves to 12, outside the visible range [0, 10].`

**Example.** `Min_Output = 0`, `Max_Output = 10`, then `Output = 12;` → finding.

---

### A21. `data-dependency` — "Data dependency" (correctness, contributor)

**What it scans.** Statement-level read/write facts across all module scopes.

**How it works.** `collect_statement_facts` emits per-statement read/write facts
in execution order. Per module it maintains `initialized_roots`. For each
statement: a read is an **initialization hazard** iff its declaration is in the
same module, is **not** a module parameter, has **no** `init_value`, and is not
yet in `initialized_roots`. Dependency chains are built transitively through
writes; a chain of ≥3 symbols (`Target -> Mid -> Source`) is reported as a path.

**Issue kinds.**
- `data_dependency.path` (warning).
  Message: `Dependency path 'Output' -> 'Mid' -> 'Input' is established in {site}.`
- `data_dependency.initialization_order` (error).
  Message: `Write to 'Output' depends on 'Source' before that value is initialized or written earlier in {site}.`

**Example.** `Mid = Input; Output = Mid;` (chain) and `Output = Source; Source = 3;`
(init-order hazard).

---

### A22. `config-drift` — "Config drift" (correctness, contributor)

**What it scans.** Moduletype instance configuration parameter mappings.

**How it works.** Groups instances of the same moduletype (case-insensitive) and
compares their mapped configuration parameter value signatures. If ≥2 instances
yield ≥2 distinct value signatures for a parameter, the group is reported.

**Issue kinds.**
- `config_drift.instance_configuration` (warning).
  Message: `Module type 'DoseValve' has drifting instance configuration for Timeout: ValveA(Timeout=10), ValveB(Timeout=15).`

---

### A23. `scan-loop-resource-usage` — "Scan-loop resource usage" (correctness, standalone)

**What it scans.** Builtin calls in continuously-executed scan-cycle contexts:
every statement in every `EQUATIONBLOCK`, and the `ACTIVECODE` of every SFC step.

**How it works.** Each builtin signature declares `precision_scangroup` (from the
builtin registry shards `_sattline_builtins_part1..5.py`). Calls to builtins with
`precision_scangroup=False` inside a scan-cycle context are reported. One-shot
ENTER/EXIT step code and any other context are deliberately not flagged. Typical
offenders are string/time/status/system builtins (`AssignSystemString`,
`StringToTime`, `IntegerToString`, `GetSystemType`, ...).

**Issue kinds.**
- `scan_cycle.resource_usage` (warning).
  Message: `Call 'AssignSystemString' is not precision-scan-safe and should not run in equation block 'MainEq' at 'Root'.`

**Example.** `AssignSystemString(SysVarId, Value, Status);` inside an equation
block.

---

### A24. `resource-usage` — "Resource usage" (correctness, contributor)

**What it scans.** Resource-handle calls: acquire via `OpenDevice`/
`OpenReadFile`/`OpenWriteFile`, release via `CloseDevice`/`CloseFile`. Only
handles **locally owned** (declared in the same module, not module parameters)
are tracked, per module in statement order.

**How it works.** From statement facts, tracks each handle's acquire/release
state through the scope.

**Issue kinds (warnings, control-flow).**
- `resource_usage.acquire_without_release` — second acquire before previous
  released. Message: `Resource handle 'FileRef' is reacquired via 'OpenWriteFile' in {site} before the previous file acquire from 'OpenReadFile' at {prev} is released.`
- `resource_usage.release_without_acquire` — release with no prior acquire.
  Message: `Resource handle 'FileRef' is released via 'CloseFile' in {site} without a matching prior acquire in this scope.`
- `resource_usage.leaked_resource` — handle still active at scope end.
  Message: `Resource handle 'FileRef' acquired via 'OpenReadFile' at {site} is never released in this scope.`
Also forwards `scan_cycle.resource_usage` (A23).

**Example.** `OpenReadFile(FileRef, "first.txt", ...)` then
`OpenWriteFile(FileRef, "second.txt", ...)` with no close in between.

---

### A25. `scan-concurrency` — "Scan concurrency" (correctness, composed)

Composed over `same-cycle` (A27); forwards only `sfc_parallel_write_race`. This
kind is the parallel-SFC write/write conflict: two `SFCParallel` branches writing
the same variable or field in their ACTIVE code. A write/write conflict suppresses
the read/write report for the same symbol.

---

### A26. `scan-shared-access` — "Scan shared access" (correctness, composed)

Composed over `same-cycle` (A27); forwards only
`same_cycle_non_state_multi_site_hazard`. Detects a **non-STATE** variable read in
one continuous scan site and written in another within the same scan. Scan sites
are `EQ:<equation>`, `STEP:<name>:ACTIVE/ENTER/EXIT`, and
`STEP:<name>:TRANS:<transition>` (self-looping). Reads+writes within one site do
not trigger it.

---

### A27. `same-cycle` — "Same-cycle hazards" (correctness, contributor)

**What it scans.** Access events (read/write, canonical path, module path, site
label, continuous-site label, State flag) collected across the program tree,
including accesses arriving through moduletype-instance parameter mappings of
dependency module types.

**How it works.** Collects "cycle events" then runs four collectors.

**Issue kinds.**
- `same_cycle_shared_access_hazard` (warning, interface-contracts) — a shared
  variable read and written in the same scan across **different module paths**.
  Message: `Variable 'Root.SharedValue' is read and written in the same scan across modules: Reader (read); Writer (write)`.
- `same_cycle_parallel_read_write_hazard` (warning, control-flow) — one parallel
  branch reads, another writes the same variable.
  Message: `Parallel branches in sequence 'Seq' both read and write the same variable(s): Root.SharedValue`.
- `sfc_parallel_write_race` (error, control-flow) — two parallel branches both
  write (see A5/A25).
- `same_cycle_non_state_multi_site_hazard` (warning, interface-contracts) — see
  A26.

**Example.** Module `Reader` does `Output = SharedValue;` while module `Writer`
does `SharedValue = 0;` → shared-access-hazard.

---

### A28. `timing` — "Timing" (correctness, composed)

Composed of `dataflow` (the three scan-cycle temporal kinds) +
`scan-loop-resource-usage`. Forwards:
- `dataflow.scan_cycle_stale_read` (warning) — `:OLD` read after a same-scan
  write; `:OLD` still yields the previous-scan value.
- `dataflow.scan_cycle_implicit_new` (warning) — implicit (unqualified) read of a
  State symbol after a same-scan write; should use `:NEW`.
- `dataflow.scan_cycle_temporal_misuse` (error) — `:OLD` used as a write target or
  out/inout parameter; `:OLD` is read-only.
- `scan_cycle.resource_usage` (warning) — from A23.

Report sections: "Scan-cycle stale reads", "Implicit same-scan dependencies",
"Temporal state misuse", "Scan-loop resource hazards".

**Examples.** `PrevAccum = Accum:Old;` immediately after
`Accum = Accum + Smoothed;`; `MaxLim(1.0, 2.0, 0.1, Flag:Old);` passing `:OLD` as
an out-parameter.

---

### A29. `version-drift` — "Version drift" (heuristic, contributor)

**What it scans.** `SingleModule`s with the same case-insensitive name
(root-origin only).

**How it works.** Fingerprints each module (counts + hashes of module parameters,
local variables, submodules, parameter mappings, sequences, equations); the
variant key **excludes datecode**, so pure date-code bumps are not drift. When ≥2
structural variants exist among ≥2 instances, the representative variants are
diffed and drift is reported per module name with material-difference buckets and
upgrade notes.

**Issue kinds.**
- `module.version_drift` (warning).
  Message: `Module 'Mixer' has 2 structural variants across 2 instances; drift is present in module code.`

**Example.** Two `Mixer` modules identical except an equation `Output = 1;` vs
`Output = 2;` → drift.

---

### A30. `safety-paths` — "Safety paths" (correctness, contributor)

**What it scans.** Signal paths whose dot-segment chain contains a safety keyword
(`emergency`, `shutdown`, `estop`), using the variable access graph.

**How it works.** Builds access traces from the VariablesAnalyzer access graph and
classifies a path as safety-critical by keyword. Reports a safety signal that has
≥1 writer and **0 readers** across the target.

**Issue kinds.**
- `safety-path.unconsumed_signal` (warning).
  Message: `Safety-critical path 'Root.EmergencyShutdown' is written but never read across the analyzed target.`

**Example.** `EmergencyShutdown = InCommand;` inside `GuardType`, never read
anywhere.

---

### A31. `taint-paths` — "Taint paths" (correctness, contributor)

**What it scans.** Effect-flow edges from external inputs to critical sinks.

**How it works.** Classifies **sources** by name keywords: `mes` (`mes, mms, opc,
batch`), `operator` (`operator, manual, command, cmd, setpoint`), `sensor`
(`sensor, measurement, measured, feedback, probe, transmitter`). Classifies
**sinks** by `emergency, shutdown, estop, interlock, trip`. Follows effect-flow
edges and reports a flow only when it **spans multiple modules** (single-module
wiring is not flagged).

**Issue kinds.**
- `taint-path.external_input_to_critical_sink` (warning).
  Message: `Operator input 'Root.OperatorCommand' reaches safety-critical sink 'Root.Guard.EmergencyShutdown' via {intermediate}.`

**Example.** Operator input flowing through a `GuardType` moduletype mapping into
`EmergencyShutdown`.

---

### A32. `unsafe-defaults` — "Unsafe defaults" (correctness, contributor)

**What it scans.** Boolean declarations (root locals, root-origin moduletype
parameters/locals, all nested module parameters/locals) whose `init_value` is
`True`.

**How it works.** Tokenizes the identifier; if it contains a `bypass` or `enable`
token, the default is reported. `bypass` names "can bypass safety checks from
startup"; `enable` names "can activate equipment or logic from startup".

**Issue kinds.**
- `unsafe_defaults.true_boolean_default` (warning).
  Message: `Boolean variable 'SafetyBypass' defaults to True, which can bypass safety checks from startup.`

**Example.** `EnablePump: boolean := True;` or `SafetyBypass: boolean := True;`.

---

### A33. `dataflow` — "Lightweight dataflow" (correctness, contributor)

**What it scans.** Equation blocks and SFC sequences (step ENTER/ACTIVE/EXIT,
transition conditions, alternative/parallel branches) in the reachable module
tree plus root-origin typedefs and resolvable root-origin instances.

**How it works.** A symbolic state machine. The state map is keyed by
`(module_path, variable, field...)` and holds `ScalarValue` (compile-time
constant), `INITIALIZED` (assigned, non-scalar), or `UNKNOWN` (absent). Values
seed from `init_value`; writes apply scalars; `:OLD` keys hold the previous-scan
snapshot. It is **path-sensitive**: each branch starts from a copy of the state,
conditions are evaluated/constant-folded, unreachable branches are skipped, and
branch assumptions (`x == literal`) are injected. At joins (`SFCAlternative`,
`SFCParallel`, `IF`) states are merged so a key survives only if every branch has
a non-UNKNOWN value; unequal-but-known values collapse to `INITIALIZED`; a
partial write is dropped, so a later read fires read-before-write. `PendingWrite`
markers track writes not yet observed by a read (for dead-overwrite and
scan-cycle temporal checks).

**Issue kinds (11).**
- `dataflow.read_before_write` (warning, variable-lifecycle) — symbol has no
  state entry at read time (never seeded, no definite write surviving merge).
  Message: `Variable reference 'X' may be read before it is assigned on this path.`
- `dataflow.dead_overwrite` (warning, variable-lifecycle) — write while a
  `PendingWrite` exists for the same root (previous value never read).
  Message: `Variable reference 'X' is overwritten before its previous value is read.`
- `dataflow.condition_always_true` / `condition_always_false` (warning,
  control-flow) — condition folds to a definite bool (self-compare, AND/OR fact
  tautology/contradiction, or constant folding).
- `dataflow.unreachable_branch` (warning, control-flow) — a branch whose condition
  is statically false, or any later ELSIF/ELSE after a statically-true condition.
- `dataflow.unreachable_sequence_node` (warning, control-flow) — node after
  `SFCBreak`/`SFCFork` in the same branch list.
- `dataflow.self_compare_condition` (warning, control-flow) — same resolved symbol
  on both sides of a comparison; `==`/`<=`/`>=` → True, `<>`/`<`/`>` → False
  (additionally emits condition_always_true/false).
- `dataflow.scan_cycle_stale_read` (warning, control-flow) — `:OLD` read of a
  symbol with a pending write; `:OLD` refers to previous scan.
- `dataflow.scan_cycle_implicit_new` (warning, control-flow) — implicit read of a
  State symbol with a pending write; suggest `:NEW`.
- `dataflow.scan_cycle_temporal_misuse` (error, control-flow) — write through
  `:OLD` (assignment target, out/inout parameter, or array-element write).
- `dataflow.invalid_state_access` (error, control-flow) — `:OLD`/`:NEW` requested
  on a variable/leaf field resolved to a definite non-State declaration.

**Examples.** `Output = Uninitialized;` (read-before-write);
`Flag = True; Flag = Condition;` (dead overwrite);
`IF Flag AND NOT Flag THEN ...` (always false);
`StateBox.Regression.Running:Old` on a non-State nested field (invalid-state-access).

---

### A34. `state-inference` — "State inference" (correctness, composed of dataflow)

**How it works.** Instantiates `DataflowAnalyzer`, runs it, and **re-keys** three
of its kinds into the `state_inference.*` namespace, then emits a structured
summary artifact (`kind: "sattlint.state_inference_summary"`) listing inferred
boolean states, numeric ranges, and string states (excluding `:OLD`/pending keys).

**Issue kinds (warnings inherited from dataflow; no semantic rules).**
- `state_inference.condition_always_true`
- `state_inference.condition_always_false`
- `state_inference.unreachable_branch`
Plus the summary artifact.

**Example.** `Count: integer := 5;` then `IF Count < 0 THEN ...` →
always-false + unreachable-branch, and a summary `{"symbol": "Root.Count",
"minimum": 5, "maximum": 5}`.

---

## Part B — Wiring, overlap, and organization issues

> **Status (2026-09-08):** items B1.2 (parallel-write-race ownership), B1.4
> (state-inference re-label) and the redundant-composed-analyzer removals are
> implemented — see `results-clarity-and-analyzer-dedup.md`. `interface-contracts`,
> `powerup`, `scan-concurrency`, `scan-shared-access`, `timing`, and
> `state-inference` were removed from `DEFAULT_CLI_ANALYZER_KEYS` (still
> registered + selectable); `same-cycle` no longer emits `sfc_parallel_write_race`
> (owner `sfc`), and `resource-usage` no longer forwards `scan_cycle.resource_usage`
> (owner `scan-loop-resource-usage`).

### B1. Genuine double-reporting (same finding from multiple analyzers)

1. **Read-before-write: `dataflow` vs `signal-lifecycle`.** Both fire on
   uninitialized reads of the same code, with **different rule ids**
   (`semantic.read-before-write` vs `semantic.signal-lifecycle-read-before-write`)
   and **no dedup** in the semantic layer. Their algorithms also differ in
   ordering (dataflow walks sequences before equations; signal-lifecycle the
   reverse) so they can disagree. This is the strongest overlap.
   - **Fix options:** (a) make `signal-lifecycle` the scope-level owner and drop
     read-before-write from `dataflow` (dataflow keeps value/condition analysis),
     or (b) keep both but register a single shared rule id and dedupe in the
     semantic layer. Recommend (a) — signal-lifecycle is the purpose-built
     lifecycle checker; dataflow's real value is its value/condition analysis.
2. **`sfc_parallel_write_race`: `sfc` vs `same-cycle`.** Same kind string, same
   rule id — the semantic layer dedupes, but two analyzers do the work.
   - **Fix:** pick one owner. `same-cycle` is the shared-access owner and already
     the dependency of `scan-concurrency`; consider making it the sole producer
     and removing parallel-write-race from the `sfc` analyzer (or vice versa),
     then keep `scan-concurrency` as the public forwarder.
3. **Unreachable sequence nodes: `dataflow` vs `sfc`.** Structurally identical
   post-`SFCBreak`/`SFCFork` termination logic, different rule ids
   (`semantic.unreachable-sequence-node-dataflow` vs
   `semantic.unreachable-sequence-node`). A third dormant trace kind
   (`unreachable_sequence_node` in `core/tracing`) is unused and dropped.
   - **Fix:** consolidate into the `sfc` analyzer (it already splits transition vs
     step findings); remove the dataflow copy and the dormant trace kind (or map
     it).
4. **`state-inference` = re-label of `dataflow`.** It adds nothing but a summary
   artifact.
   - **Fix:** fold the summary into `dataflow` and delete `state-inference`, or
     keep `state-inference` only as the summary producer and drop its three
     duplicated kinds.

### B2. Forwarding / composition inconsistencies

5. **`resource-usage` embeds `scan_cycle.resource_usage` without declaring
   `composed_analyzer_keys`**, unlike `timing`, `scan-concurrency`,
   `scan-shared-access`, and `powerup`, which declare their composition.
   - **Fix:** add `composed_analyzer_keys=("scan-loop-resource-usage",)` and
     `composed_issue_kind_names=("scan_cycle.resource_usage",)` to the template.
6. **`interface-contracts` and `state-inference` are compositions but not marked
   as `composed_analyzer_keys`** (interface-contracts uses a `selected_issue_kinds`
   projection; state-inference re-labels). Standardize on the composition
   metadata so tooling sees the dependency graph.

### B3. Rules that never surface in the combined report

7. **`scan_cycle.resource_usage` never appears in `sattline-semantics`.** Its
   owner (`scan-loop-resource-usage`) and both forwarders (`resource-usage`,
   `timing`) are not semantic contributors, so the rule is registered but
   unreachable in the combined report.
   - **Fix:** make `scan-loop-resource-usage` a semantic contributor (source
     `scan-loop-resource-usage`) or add `_RULE_ANALYZER_ALIASES` wiring.
8. **No-rule kinds are dropped silently:** variables `magic_number` and
   `record_component_order_dependence`, and `picture_display_paths.unresolved`
   (no rule at all) and the three `state_inference.*` kinds.
   - **Fix:** either register semantic rules for them or remove them from the
     default variable-analysis set; ensure severity is uniform (e.g.
     `picture_display_paths.unresolved` is info only when the target is a
     library, otherwise default).

### B4. Registry / delivery inconsistencies

9. **Default CLI set vs selectable vs contributor is inconsistent.**
   `naming-consistency`, `cyclomatic-complexity`, `parameter-drift`, and
   `version-drift` are selectable but not in `DEFAULT_CLI_ANALYZER_KEYS`;
   `sattline-semantics` is not CLI-exposed at all; `version-drift` and
   `parameter-drift` are category `heuristic` yet wired as semantic contributors
   (warnings).
   - **Fix:** decide a policy — e.g. every registered analyzer is selectable and
     either in the default set or explicitly "opt-in"; align category
     (correctness for contributors) and document the exceptions.
10. **`development` category is unused**, and `comment-code` is categorized
    `correctness` (it is arguably style). Revisit categories.
11. **"Lightweight dataflow" is a misleading name** — it is a full symbolic
    analysis, not lightweight. Rename to "Dataflow" and update the description.
12. **`loop-stability` vs `loop-output-refactor` naming is confusing** — they are
    unrelated (setpoint conflicts vs block ordering cycles). Consider renaming
    (e.g. "Conflicting setpoints" and "Equation-block dependency cycles") or at
    least clarifying descriptions.

### B5. Correctness divergences worth noting

13. **Statement-order divergence:** dataflow walks SFC sequences before equations;
    signal-lifecycle walks equations before sequences. When consolidating
    read-before-write (B1.1), unify the ordering.
14. **`comment-code` read-error semantics:** missing files are silently skipped;
    only existing-but-unreadable files are reported. Decide whether missing files
    (configured but absent) should be reported instead of skipped.
15. **`shadowing` is both a variables enum member and a dedicated analyzer** — the
    variables analyzer does not produce it; remove it from the enum or document
    the delegation to avoid confusion.

---

## Part C — Plan: add the ICF config check as an analyzer

> **Status (2026-09-08):** Phases I1–I3 implemented and validated. The `icf`
> analyzer is registered, selectable, in `DEFAULT_CLI_ANALYZER_KEYS`, and runs
> once per analysis session across the whole `icf_dir` (see notes below). Phase
> I4 unit tests are in `tests/analyzers/test_icf_analyzer.py` plus a whole-run
> hook test in `tests/app/test_analysis_checks.py`; corpus manifests are still a
> follow-up.

### Current state

`validate_icf_entries_against_program` (`src/sattlint/analyzers/icf/__init__.py:698`)
validates each `.icf` entry (a `Program:Path` reference) against the program's
`TypeGraph`. It is currently **not a registered analyzer**:

- It is surfaced only through the interactive `run_icf_validation` handler
  (`src/sattlint/application/commands.py:349`,
  `src/sattlint/cli/startup.py:207`); there is **no CLI subcommand**.
- The `mms-interface` analyzer calls it as a resolution source
  (`_mms_interface_helpers.py:237-244`) but uses only `resolved_entries`; its
  issues are not surfaced there either.

The existing checks it produces: program mismatch, unit/group tag mismatches,
unresolved paths, invalid field paths/datatypes, reference case mismatches,
missing journal parameter fields, unit structure drift, and mixed value-prefix
letters.

### Phase I1 — Wrap the validator as a registered analyzer

- Create `src/sattlint/analyzers/icf/analyzer.py` (or extend
  `icf/__init__.py`) with `analyze_icf_configuration(base_picture, icf_dir, ...)`
  returning a `SimpleReport`. Map `ICFValidationIssue` to `Issue` kinds:
  - `icf.program_mismatch`
  - `icf.unit_tag_mismatch`
  - `icf.group_key_mismatch`
  - `icf.unresolved_path`
  - `icf.invalid_field_path`
  - `icf.invalid_datatype`
  - `icf.reference_case_mismatch`
  - `icf.missing_journal_field`
  - `icf.unit_structure_drift`
  - `icf.value_prefix_inconsistency`
- Reuse `configured_icf_files` (`src/sattlint/project/support.py:216`) for file
  discovery via the `icf_dir` config.

### Phase I2 — Register the analyzer spec

- Add a template in `_registry_spec_templates.py`:
  `key="icf"`, `name="ICF configuration"`, `category="correctness"`,
  `context_kwargs=("config", "graph", "debug")`, `semantic_rule_source="icf"`.
- Add semantic rules for the kinds (severity error for unresolved/invalid paths,
  warning otherwise) in a new `ICF_RULES` group wired through
  `_sattline_semantic_rules_data.py` / `rule_profiles.py`, with
  `_RULE_ANALYZER_ALIASES` entries so `sattline-semantics` includes them.
- Wire `analyze_icf_configuration` into `_REGISTRY_MONKEYPATCH_SURFACE` and the
  registry dispatch.

### Phase I3 — Delivery

- Add `icf` to `DEFAULT_CLI_ANALYZER_KEYS` (it is a real correctness check and
  currently hidden).
- Keep `mms-interface`'s resolution usage (it becomes a consumer of the same
  underlying validator; optionally have `mms-interface` forward
  `icf.*` kinds or keep them separate — recommend keeping them separate, with
  `mms-interface` documenting that ICF validation is a separate analyzer).
- Decide whether the interactive `run_icf_validation` handler now delegates to
  the analyzer (recommended) to avoid two code paths.

### Implementation notes (2026-09-08)

The delivered analyzer diverges from the original Phase I1–I3 sketch in these
grounded ways:

- **Once-per-session whole-run delivery.** ICF validation is inherently a
  directory-wide check, but the checks engine runs each analyzer once per loaded
  target. To avoid emitting every finding once per configured program/library,
  `icf` is a whole-run analyzer: `application/checks.py` strips it from the
  per-target loop and runs it exactly once per session, folding the results into
  a synthetic `ICF configuration` target (`ICF_ANALYZER_KEY` / `ICF_TARGET_NAME`).
- **Full `icf_dir` parity.** `analyze_icf_configuration` (in
  `src/sattlint/analyzers/icf/analyzer.py`) validates every `*.icf` under
  `icf_dir` regardless of configured targets. For each file it reuses the
  in-memory program when it matches, otherwise loads it via `load_program_ast`.
- **Kind names match the validator's real reasons** (the plan's names were
  aspirational): `icf.program_mismatch`, `icf.unresolved_path`,
  `icf.invalid_field_path`, `icf.reference_case_mismatch`, `icf.unit_tag_mismatch`,
  `icf.group_tag_mismatch`, `icf.missing_journal_field`, `icf.unit_structure_drift`,
  `icf.value_prefix_inconsistency`, plus `icf.program_load_failed` (added so a
  program that cannot be loaded is reported instead of silently skipped).
- **Standalone, not a semantic contributor.** `icf` has no
  `semantic_rule_source`; it is a standalone analyzer with rules registered in
  `rule_profiles._EXTRA_RULES_BY_KIND` (source `icf`) so findings get rule ids +
  severity. It is deliberately not folded into the `sattline-semantics` combined
  pass, which runs per program.
- **`run_icf_validation` retained (for now).** The hidden interactive handler is
  left in place; removing it (Phase I3 decision) is a follow-up because it is
  wired into `startup` and covered by several tests.

### Phase I4 — Tests and docs

- Corpus manifests `analyzer-icf-*.json` and `.sl`/`.icf` fixtures for each kind.
- Update the analyzer descriptions and this document.
- Verify: `ruff`, `pyright` strict, focused pytest, and the registry dependency
  graph tests.

---

## Appendix — Quick reference table

| Key | Name | Category | Group | Default CLI |
|---|---|---|---|---|
| sattline-semantics | SattLine semantics | correctness | semantic layer | no |
| variables | Variable issues | correctness | contributor | yes |
| picture-display-paths | PictureDisplay paths | correctness | standalone | yes |
| mms-interface | MMS interface mappings | correctness | contributor | yes |
| sfc | SFC checks | correctness | contributor | yes |
| comment-code | Commented-out code | correctness | contributor | yes |
| shadowing | Variable shadowing | correctness | contributor | yes |
| spec-compliance | Engineering spec compliance | correctness | contributor | yes |
| loop-output-refactor | Loop output refactor | correctness | contributor | yes |
| alarm-integrity | Alarm integrity | correctness | contributor | yes |
| initial-values | Initial value validation | correctness | contributor | yes |
| interface-contracts | Interface contracts | correctness | composed | yes |
| powerup | Power-up | correctness | composed | yes |
| naming-consistency | Naming consistency | style | standalone | no |
| cyclomatic-complexity | Cyclomatic complexity | style | standalone | no |
| parameter-drift | Parameter drift | heuristic | standalone | no |
| signal-lifecycle | Signal lifecycle | correctness | contributor | yes |
| loop-stability | Loop stability | correctness | contributor | yes |
| fault-handling | Fault handling | correctness | contributor | yes |
| numeric-constraints | Numeric constraints | correctness | contributor | yes |
| data-dependency | Data dependency | correctness | contributor | yes |
| config-drift | Config drift | correctness | contributor | yes |
| scan-loop-resource-usage | Scan-loop resource usage | correctness | standalone | yes |
| resource-usage | Resource usage | correctness | contributor | yes |
| scan-concurrency | Scan concurrency | correctness | composed | yes |
| scan-shared-access | Scan shared access | correctness | composed | yes |
| same-cycle | Same-cycle hazards | correctness | contributor | yes |
| timing | Timing | correctness | composed | yes |
| version-drift | Version drift | heuristic | contributor | no |
| safety-paths | Safety paths | correctness | contributor | yes |
| taint-paths | Taint paths | correctness | contributor | yes |
| unsafe-defaults | Unsafe defaults | correctness | contributor | yes |
| dataflow | Lightweight dataflow | correctness | contributor | yes |
| state-inference | State inference | correctness | composed | yes |
| icf (planned) | ICF configuration | correctness | contributor (planned) | yes (planned) |
