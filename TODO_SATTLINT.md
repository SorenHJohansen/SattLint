# TODO - SattLint Analyzer Backlog

Backlog view of the analyzer roadmap for SattLine code. Each row is a discrete feature sized against the current repo seams.

- Scope uses: single-file, workspace, cross-module, or LSP-only.
- Implementation bucket uses: new analyzer, extend VariablesAnalyzer, shared semantic core, or reporting only.
- Confidence is delivery confidence with the current parser, resolver, and test scaffolding.
- Acceptance tests name the existing suites that should be extended first.
- Status is a conservative repo review as of 2026-04-22: `Partial` means narrower or adjacent coverage exists, and `Open` means no matching implementation was found. Fully completed items are intentionally removed from this active backlog.

Repo review note as of 2026-04-22:

- Active backlog below excludes fully completed rows and keeps only remaining `Open` and `Partial` work.
- Several active rows remain `Partial` because narrower adjacent coverage already exists in the semantic core, VariablesAnalyzer, or reporting pipeline.

| ID | Status | Area | Feature | Scope | Implementation bucket | Confidence | Dependencies | Acceptance tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | Open | Structural quality and maintainability | Duplicate logic detection | workspace | new analyzer | Medium | AST normalization or hashing, expression or block comparison, duplicate grouping in reports | Add `tests/test_analyzers.py` cases for structurally identical logic blocks with renamed locals and for near-miss blocks that should not collapse |
| 7 | Open | Naming and semantic conventions | Engineering unit consistency and propagation | cross-module | new analyzer | Low | Unit metadata source, parameter mapping comparison, range or scaling metadata, optional config catalog of allowed conversions | Add `tests/test_analyzers.py` cases for unit mismatches across connected modules, transitive propagation, and accepted conversions when configured |
| 10 | Partial | Timing and real-time constraints | Timing and determinism analysis | workspace | shared semantic core | Medium | Temporal access graph with scan ordering, cycle-budget config, timer semantics, latency or jitter heuristics | Add `tests/test_dataflow.py` and `tests/test_analyzers.py` cases for cycle-budget overruns, same-cycle order sensitivity, TON or TOF or PT misuse, and latency-sensitive signal chains |
| 11 | Partial | Initialization and startup semantics | Power-up and restart correctness | workspace | shared semantic core | Medium | First-scan definite assignment, retained-state model, startup ordering graph, initial-value propagation | Add `tests/test_dataflow.py` and `tests/test_analyzers.py` cases for uninitialized first-scan reads, power-up state mismatches, cold vs warm restart behavior, and module initialization order dependencies |
| 12 | Partial | Concurrency and execution ordering | Scan-level concurrency and arbitration analysis | cross-module | shared semantic core | Medium | Module execution order model, cross-module writer inventory, arbitration heuristics, last-writer detection | Add `tests/test_analyzers.py` cases for cross-module write collisions, read or write ordering dependencies, hidden last-write-wins behavior, and multiple writers without arbitration |
| 13 | Open | Signal lifecycle semantics | Signal lifecycle modeling | workspace | shared semantic core | Medium | Lifecycle stages such as init, active, stale, and invalid, refresh cadence heuristics, orphan detection | Add `tests/test_analyzers.py` cases for stale-signal use, missing refresh, and signals never updated after initialization |
| 14 | Open | Control stability and feedback | Control loop and stability heuristics | single-file | new analyzer | Medium | Feedback-loop matcher, hysteresis heuristics, threshold toggle detection, generalized runaway feedback patterns | Add `tests/test_analyzers.py` cases for flip-flop control, runaway feedback, missing hysteresis, and unstable threshold toggling |
| 15 | Open | Fault handling and recovery | Fault handling completeness and recovery | workspace | new analyzer | Medium | Fault-state inventory, critical-path classification, safe-state recovery reachability, alarm vs fault role checks | Add `tests/test_analyzers.py` cases for missing error paths, unhandled fault states in SFC or state logic, inconsistent alarm vs fault behavior, and unreachable recovery paths |
| 16 | Partial | Interface contracts and module boundaries | Strong semantic interface contracts | workspace | extend VariablesAnalyzer | Medium | Required or optional inference, hidden required parameter mining, partial initialization contracts, semantic role compatibility across mappings | Add `tests/test_analyzers.py` cases for hidden required parameters, optional vs required usage, partial initialization contracts, and semantic mismatches across connected modules |
| 17 | Open | Numeric and engineering validity | Numeric and engineering constraint analysis | single-file | new analyzer | Medium | Range heuristics, divide-by-zero guard reasoning, overflow or underflow checks, scaling validation, saturation pattern detection | Add `tests/test_analyzers.py` cases for overflow or underflow risk, invalid scaling, divide-by-zero in guarded branches, and missing saturation logic |
| 18 | Open | Configuration and code alignment | Configuration drift against code and recipes | workspace | new analyzer | Medium | Config or recipe inventory, MES or MMS or ICF crosswalk, code-to-config symbol matching, stale-field detection | Add `tests/test_analyzers.py` and `tests/test_pipeline.py` coverage for code expecting missing config parameters, unused config fields, recipe assumption mismatches, and stale config after code evolution |
| 19 | Open | S88 control architecture | S88 control module contract analysis | workspace | new analyzer | Medium | S88 command or state inventory, control-module heuristics, reachability matrix, required transition templates | Add `tests/test_analyzers.py` cases for missing Start or Stop or Hold or Abort contracts, unreachable states, and missing control-module transitions |
| 20 | Open | S88 control architecture | S88 phase sequencing correctness | workspace | new analyzer | Medium | Phase model extraction, legal transition matrix, phase-state reachability, exit-condition validation | Add `tests/test_analyzers.py` cases for illegal phase transitions and missing or inconsistent phase exit conditions |
| 21 | Partial | Safety-critical semantics | Safety-path correctness beyond tracing | cross-module | shared semantic core | Low | Extend safety-path traces with reset symmetry, validation gates, redundancy expectations, and safe-state assertions | Add `tests/test_analyzers.py` cases for shutdown paths missing resets, missing redundant confirmation paths, and unsafe single-point control of emergency logic |
| 22 | Partial | Advanced semantic inference | Lightweight behavioral range and state inference | workspace | shared semantic core | Medium | Abstract interpretation for value ranges, state propagation across branches, saturation detection, impossible-state classification | Add `tests/test_dataflow.py` and `tests/test_analyzers.py` cases for impossible conditions and saturated states not caught by current constant-condition rules |

## AI Execution Plan

Execution plan converts backlog into AI-sized waves that fit current repo seams and avoid overlapping semantic-core work.

Wave 1 and Wave 2 are complete. Active implementation work now starts at Wave 3.

### Operating Rules

- One AI task should target one backlog ID or one tightly coupled prerequisite slice.
- Default implementation order per feature: metadata or contract first, focused tests second, analyzer logic third, shared machine-readable output fourth, CLI or pipeline or LSP exposure last.
- Do not run multiple AI tasks in parallel against `src/sattlint/analyzers/dataflow.py`, `src/sattlint/core/semantic.py`, or `src/sattlint/analyzers/sattline_semantics.py` unless they are explicitly coordinated under same wave.
- Prefer checked-in fixtures and targeted pytest modules before broader pipeline validation.
- Treat `tests/test_analyzers.py` as a starting point, not a dumping ground. Create or extend narrower suites when a feature introduces a distinct seam.

### Definition Of Done Per Backlog Item

- Rule or analyzer metadata added in analyzer registry and semantic-layer metadata where applicable.
- Acceptance tests from the backlog row are added or updated first.
- Findings flow through normalized contracts when the feature emits machine-readable results.
- CLI or LSP exposure is added only after tests and finding shape are stable.
- Validation uses the smallest relevant command first, then widens only if needed.

Recommended focused validation commands:

- Parser or strict-validation slices: `& ".venv/Scripts/sattlint.exe" syntax-check <target>`
- Analyzer or CLI slices: `& ".venv/Scripts/python.exe" -m pytest tests/test_analyzers.py tests/test_app.py -q`
- Semantic-core slices: `& ".venv/Scripts/python.exe" -m pytest tests/test_dataflow.py tests/test_sattline_semantics.py tests/test_analyzers.py -q`
- Pipeline or artifact slices: `& ".venv/Scripts/python.exe" -m pytest tests/test_pipeline.py tests/test_artifact_contracts.py -q`
- Editor or LSP slices: `& ".venv/Scripts/python.exe" -m pytest tests/test_editor_api.py tests/test_lsp_server.py -q`

### Wave 3: Standalone Heuristic Analyzers

Goal: deliver medium-risk analyzers that mostly consume existing AST and resolution data without requiring new abstract interpretation.

Items:

- `3` Duplicate logic detection
- `14` Control loop and stability heuristics
- `15` Fault handling completeness and recovery
- `17` Numeric and engineering constraint analysis

Why here:

- These are feature-rich but can still be built as analyzers on top of current AST, call-signature, and workspace-resolution seams.
- They are easier to review once reporting and profile infrastructure from Wave 2 exists.

Risk note:

- `3` needs aggressive counterexamples to avoid false positives.
- `15` should not guess plant semantics beyond evidence in code or config.

### Wave 4: Contract And Cross-Module Semantics Expansion

Goal: extend interface and lifecycle analysis where current variables and semantic layers already have partial coverage.

Items:

- `16` Strong semantic interface contracts
- `13` Signal lifecycle modeling
- `18` Configuration drift against code and recipes

Why here:

- `16` extends existing contract checks and should sharpen the VariablesAnalyzer path before deeper shared-semantic changes.
- `13` and `18` benefit from stronger shared metadata, confidence labels, and rule-profile controls.

Parallelization:

- `16` should go first.
- `13` and `18` can follow once contract and finding-shape conventions are stable.

### Wave 5: Shared Semantic-Core Expansion

Goal: tackle features that require changes to shared execution-state, ordering, and inference models.

Items:

- `10` Timing and determinism analysis
- `11` Power-up and restart correctness
- `12` Scan-level concurrency and arbitration analysis
- `21` Safety-path correctness beyond tracing
- `22` Lightweight behavioral range and state inference

Why late:

- These features are not isolated analyzers. They depend on shared temporal, ordering, and state-propagation machinery.
- Running them too early invites duplicated heuristics and incompatible local fixes.

Execution constraint:

- Treat this wave as a coordinated program, not five independent AI tasks.
- Start with `22` and shared state machinery, then layer `10`, `11`, and `12`, then extend safety behavior in `21`.

Suggested order inside wave:

1. `22` lightweight behavioral range and state inference
2. `10` timing and determinism analysis
3. `11` power-up and restart correctness
4. `12` scan-level concurrency and arbitration analysis
5. `21` safety-path correctness beyond tracing

### Wave 6: Domain-Specific Integration Features

Goal: finish features that need external metadata catalogs, stronger domain conventions, or explicit plant semantics.

Items:

- `7` Engineering unit consistency and propagation
- `19` S88 control module contract analysis
- `20` S88 phase sequencing correctness

Why last:

- These need agreed source-of-truth metadata and domain rules before coding starts.
- Without that contract, AI will fill gaps with heuristics that are hard to review and harder to trust.

Required preparation before implementation:

- Decide where engineering-unit metadata lives.
- Decide what counts as authoritative S88 commands, states, and legal transitions.
- Add small gold fixtures that represent intended plant conventions.

### Parallel Work Matrix

Safe to parallelize from the current active backlog:

- `14`, `17`

Should be serialized or tightly coordinated:

- `16`
- `10`, `11`, `12`, `21`, `22`
- `7`, `19`, `20`

### Suggested Next 10 AI Tasks

1. Implement `3` duplicate logic detection with strong counterexamples.
2. Implement `14` control loop and stability heuristics.
3. Implement `17` numeric and engineering constraint analysis.
4. Sharpen `16` strong semantic interface contracts.
5. Implement `13` signal lifecycle modeling.
6. Implement `18` configuration drift against code and recipes.
7. Start `22` lightweight behavioral range and state inference.
8. Layer `10` timing and determinism analysis on top of the `22` state machinery.
9. Extend `11` power-up and restart correctness on the same state model.
10. Add `12` scan-level concurrency and arbitration analysis once ordering data is stable.

### Release Strategy

- Ship each wave behind existing analyzer metadata and finding contracts.
- Prefer small reviewable merges over one analyzer mega-branch.
- After each wave, rerun focused tests first, then a quick pipeline profile, then update backlog status from `Open` or `Partial` only when feature logic, exposure, and named acceptance tests all land.
