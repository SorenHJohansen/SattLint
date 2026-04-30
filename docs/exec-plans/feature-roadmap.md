# Feature Roadmap

Planned new capabilities for SattLint. These are features that do not exist yet, not debt in existing code.

For actual code quality and architecture debt, see `docs/exec-plans/tech-debt-tracker.md`.

Last updated: 2026-04-30

## Quick Reference

| Check | Command |
|-------|---------|
| Parser | `sattlint syntax-check <file>` |
| All tests | `pytest tests/` |
| Quick audit | `sattlint-repo-audit --profile quick --output-dir artifacts/audit` |
| Type check | `mypy src/` |
| Lint | `ruff check src/` |
| Format | `ruff format src/` |

---

## Priority Model

- P1: high value, should be scheduled in the next planning cycle
- P2: valuable but can wait for a later cycle or external demand

---

## Program C: New Analyzer Capabilities

New analysis passes that do not yet exist in the engine.

### C Wave Summary

| Wave | Owner | Target Window | Items | Validation |
| --- | --- | --- | --- | --- |
| C-Wave-1 | Semantic core | 2026-Q3 | C-010, C-011, C-012, C-016, C-022 | `sattlint syntax-check` + `pytest tests/` |
| C-Wave-2 | Analyzer roadmap | 2026-Q3 | C-003, C-013, C-014, C-015, C-017, C-018 | `sattlint syntax-check` + `pytest tests/` |
| C-Wave-3 | Semantic core | 2026-Q4 | C-021 | `pytest tests/` |
| C-Wave-Backlog | Domain integration | Backlog | C-007, C-019, C-020 | Deferred |

---

### C-003 Duplicate Logic Detection

**Feature ID:** C-003

**Status:** Open

**Priority:** P1

**Owner:** Analyzer roadmap

**Target Window:** 2026-Q3

**Wave:** C-Wave-2

**Purpose:** Detect duplicate or near-duplicate logic across modules to reduce maintenance burden.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Duplicate finder | `src/sattlint/analyzers/duplicate_logic.py` | Find duplicate equations/SFC |
| 2 | Similarity scorer | `src/sattlint/analyzers/duplicate_logic.py` | Score similarity |
| 3 | Reporter | `src/sattlint/analyzers/duplicate_logic.py` | Report findings |

**Input:** BasePicture with modulecode

**Output:** List of duplicate logic findings with locations and similarity scores

**Validation:** `pytest tests/test_duplicate_logic.py`

---

### C-007 Engineering Unit Consistency

**Feature ID:** C-007

**Status:** Open

**Priority:** P2

**Owner:** Analyzer roadmap

**Target Window:** Backlog

**Wave:** C-Wave-Backlog

**Purpose:** Ensure engineering units (kg, C, %, etc.) are consistent and properly propagated.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Unit extractor | `src/sattlint/analyzers/engineering_units.py` | Extract unit attributes |
| 2 | Consistency checker | `src/sattlint/analyzers/engineering_units.py` | Check propagation |
| 3 | Reporter | `src/sattlint/analyzers/engineering_units.py` | Report violations |

**Input:** Variables with engineering_unit attributes

**Output:** Consistency violations

**Validation:** `pytest tests/test_engineering_units.py`

**See also:** Deferred until S88 domain scope confirmed

---

### C-010 Timing and Determinism Analysis

**Feature ID:** C-010

**Status:** Partial

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q3

**Wave:** C-Wave-1

**Purpose:** Analyze timing constraints and execution determinism in SattLine code.

**What exists:** [x] Partial implementation in analyzers

**What needs completion:**

- [ ] Timing constraint validation
- [ ] Determinism verification
- [ ] Race condition detection

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Timing analyzer | `src/sattlint/analyzers/timing.py` | Analyze timing constraints |
| 2 | Determinism checker | `src/sattlint/analyzers/timing.py` | Verify deterministic execution |
| 3 | Race detector | `src/sattlint/analyzers/timing.py` | Detect race conditions |

**Input:** Modulecode with timing expressions

**Output:** Timing and determinism issues

**Reuses:**
- `analyzers/dataflow.py` - expression evaluation

**Validation:** `pytest tests/test_timing_determinism.py`

---

### C-011 Power-up and Restart Correctness

**Feature ID:** C-011

**Status:** Partial

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q3

**Wave:** C-Wave-1

**Purpose:** Validate correct initialization and state after power-up/restart.

**What exists:** [x] Partial implementation

**What needs completion:**

- [ ] Power-up state validation
- [ ] Restart behavior analysis

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Power-up analyzer | `src/sattlint/analyzers/powerup.py` | Analyze initialization |
| 2 | Restart checker | `src/sattlint/analyzers/powerup.py` | Verify restart behavior |
| 3 | Reporter | `src/sattlint/analyzers/powerup.py` | Report issues |

**Input:** BasePicture with initialization logic

**Output:** Power-up/restart issues

**Validation:** `pytest tests/test_powerup.py`

---

### C-012 Scan-level Concurrency Analysis

**Feature ID:** C-012

**Status:** Partial

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q3

**Wave:** C-Wave-1

**Purpose:** Analyze concurrent scan execution and arbitration logic.

**What exists:** [x] Partial implementation

**What needs completion:**

- [ ] Concurrency detection
- [ ] Arbitration logic analysis

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Concurrency detector | `src/sattlint/analyzers/scan_concurrency.py` | Find concurrent code |
| 2 | Arbitration analyzer | `src/sattlint/analyzers/scan_concurrency.py` | Analyze arbitration |
| 3 | Reporter | `src/sattlint/analyzers/scan_concurrency.py` | Report findings |

**Input:** Multi-scan or concurrent execution paths

**Output:** Concurrency and arbitration issues

**Validation:** `pytest tests/test_concurrency.py`

---

### C-013 Signal Lifecycle Modeling

**Feature ID:** C-013

**Status:** Open

**Priority:** P1

**Owner:** Analyzer roadmap

**Target Window:** 2026-Q3

**Wave:** C-Wave-2

**Purpose:** Model signal lifecycle from creation through use to ensure proper handling.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Lifecycle tracer | `src/sattlint/analyzers/signal_lifecycle.py` | Trace signal paths |
| 2 | Model builder | `src/sattlint/analyzers/signal_lifecycle.py` | Build lifecycle model |
| 3 | Reporter | `src/sattlint/analyzers/signal_lifecycle.py` | Report issues |

**Input:** Signals and their read/write paths

**Output:** Lifecycle issues (uninitialized read, zombie, etc.)

**Validation:** `pytest tests/test_signal_lifecycle.py`

---

### C-014 Control Loop Stability

**Feature ID:** C-014

**Status:** Open

**Priority:** P1

**Owner:** Analyzer roadmap

**Target Window:** 2026-Q3

**Wave:** C-Wave-2

**Purpose:** Detect control loop stability issues and oscillation patterns.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Loop detector | `src/sattlint/analyzers/loop_stability.py` | Identify control loops |
| 2 | Stability analyzer | `src/sattlint/analyzers/loop_stability.py` | Analyze stability |
| 3 | Reporter | `src/sattlint/analyzers/loop_stability.py` | Report findings |

**Input:** Control loops (P, PI, PID)

**Output:** Stability warnings

**Validation:** `pytest tests/test_loop_stability.py`

---

### C-015 Fault Handling Completeness

**Feature ID:** C-015

**Status:** Open

**Priority:** P1

**Owner:** Analyzer roadmap

**Target Window:** 2026-Q3

**Wave:** C-Wave-2

**Purpose:** Analyze fault handling completeness and recovery paths.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Fault finder | `src/sattlint/analyzers/fault_handling.py` | Find fault handlers |
| 2 | Coverage analyzer | `src/sattlint/analyzers/fault_handling.py` | Analyze coverage |
| 3 | Recovery checker | `src/sattlint/analyzers/fault_handling.py` | Verify recovery |
| 4 | Reporter | `src/sattlint/analyzers/fault_handling.py` | Report issues |

**Input:** Alarm handlers, fault responses

**Output:** Missing or incomplete fault handling

**Validation:** `pytest tests/test_fault_handling.py`

---

### C-016 Interface Contracts

**Feature ID:** C-016

**Status:** Partial

**Priority:** P1

**Owner:** Variables analyzer

**Target Window:** 2026-Q3

**Wave:** C-Wave-1

**Purpose:** Enforce strong interface contracts between modules.

**What exists:** [x] Partial implementation in variables analyzer

**What needs completion:**

- [ ] Interface contract validation
- [ ] Parameter contract enforcement

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Contract extractor | `src/sattlint/analyzers/interface_contracts.py` | Extract contracts |
| 2 | Validator | `src/sattlint/analyzers/interface_contracts.py` | Validate compliance |
| 3 | Reporter | `src/sattlint/analyzers/interface_contracts.py` | Report violations |

**Input:** Module parameters and their constraints

**Output:** Contract violations

**Validation:** `pytest tests/test_interface_contracts.py`

---

### C-017 Numeric Constraint Analysis

**Feature ID:** C-017

**Status:** Open

**Priority:** P1

**Owner:** Analyzer roadmap

**Target Window:** 2026-Q3

**Wave:** C-Wave-2

**Purpose:** Analyze numeric and engineering constraints (ranges, limits, precision).

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Constraint extractor | `src/sattlint/analyzers/numeric_constraints.py` | Extract constraints |
| 2 | Range analyzer | `src/sattlint/analyzers/numeric_constraints.py` | Analyze ranges |
| 3 | Reporter | `src/sattlint/analyzers/numeric_constraints.py` | Report violations |

**Input:** Variables with engineering constraints

**Output:** Constraint violations

**Validation:** `pytest tests/test_numeric_constraints.py`

---

### C-018 Configuration Drift

**Feature ID:** C-018

**Status:** Open

**Priority:** P1

**Owner:** Analyzer + config

**Target Window:** 2026-Q3

**Wave:** C-Wave-2

**Purpose:** Detect configuration drift against code and recipes.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Config parser | `src/sattlint/analyzers/config_drift.py` | Parse configurations |
| 2 | Drifter | `src/sattlint/analyzers/config_drift.py` | Compare to code |
| 3 | Reporter | `src/sattlint/analyzers/config_drift.py` | Report drift |

**Input:** Recipe/configuration files + BasePicture

**Output:** Configuration drift findings

**Validation:** `pytest tests/test_config_drift.py`

---

### C-019 S88 Control Module Contracts

**Feature ID:** C-019

**Status:** Open

**Priority:** P2

**Owner:** Domain integration

**Target Window:** Backlog

**Wave:** C-Wave-Backlog

**Purpose:** Analyze S88 control module contracts and phase interfaces.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | S88 model | `src/sattlint/analyzers/s88_contracts.py` | S88 domain model |
| 2 | Contract checker | `src/sattlint/analyzers/s88_contracts.py` | Verify contracts |
| 3 | Reporter | `src/sattlint/analyzers/s88_contracts.py` | Report issues |

**Input:** S88 control modules

**Output:** Contract violations

**See also:** Deferred until S88 domain scope confirmed

---

### C-020 S88 Phase Sequencing

**Feature ID:** C-020

**Status:** Open

**Priority:** P2

**Owner:** Domain integration

**Target Window:** Backlog

**Wave:** C-Wave-Backlog

**Purpose:** Validate S88 phase sequencing correctness.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Phase analyzer | `src/sattlint/analyzers/s88_sequencing.py` | Analyze phases |
| 2 | Sequencer | `src/sattlint/analyzers/s88_sequencing.py` | Validate order |
| 3 | Reporter | `src/sattlint/analyzers/s88_sequencing.py` | Report issues |

**Input:** S88 phases

**Output:** Sequencing errors

**See also:** Deferred until S88 domain scope confirmed

---

### C-021 Safety Path Depth

**Feature ID:** C-021

**Status:** Partial

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q4

**Wave:** C-Wave-3

**Purpose:** Analyze safety-path correctness beyond simple tracing.

**What exists:** [x] Partial implementation

**What needs completion:**

- [ ] Safety path depth analysis
- [ ] Safety verification

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Safety tracer | `src/sattlint/analyzers/safety_paths.py` | Trace safety paths |
| 2 | Depth analyzer | `src/sattlint/analyzers/safety_paths.py` | Analyze depth |
| 3 | Reporter | `src/sattlint/analyzers/safety_paths.py` | Report findings |

**Input:** Safety tags and paths

**Output:** Safety path findings

**Validation:** `pytest tests/test_safety_paths.py`

---

### C-022 State Inference

**Feature ID:** C-022

**Status:** Partial

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q3

**Wave:** C-Wave-1

**Purpose:** Infer variable ranges and behavioral states from code.

**What exists:** [x] Partial implementation

**What needs completion:**

- [ ] Variable range inference
- [ ] State machine inference

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Range inferrer | `src/sattlint/analyzers/state_inference.py` | Infer ranges |
| 2 | State inferrer | `src/sattlint/analyzers/state_inference.py` | Build state model |
| 3 | Reporter | `src/sattlint/analyzers/state_inference.py` | Report inferred states |

**Input:** Modulecode

**Output:** Inferred ranges and states

**Reuses:**
- `analyzers/dataflow.py` - expression evaluation

**Validation:** `pytest tests/test_inference.py`

---

### C-023 Data Flow Dependency Analysis

**Feature ID:** C-023

**Status:** Open

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q4

**Wave:** C-Wave-3

**Purpose:** Track data dependencies between variables to identify potential data races or incorrect initialization sequences.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Dependency tracker | `src/sattlint/analyzers/data_dependency.py` | Track variable dependencies |
| 2 | Race detector | `src/sattlint/analyzers/data_dependency.py` | Detect potential data races |
| 3 | Initialization checker | `src/sattlint/analyzers/data_dependency.py` | Check initialization sequences |
| 4 | Reporter | `src/sattlint/analyzers/data_dependency.py` | Report findings |

**Input:** BasePicture with modulecode

**Output:** Data dependency findings with potential issues

**Reuses:**
- `analyzers/dataflow.py` - expression evaluation
- `core/semantic.py:load_workspace_snapshot()` - workspace loading

**Validation:** `pytest tests/test_data_dependency.py`

---

### C-024 Resource Usage Analysis

**Feature ID:** C-024

**Status:** Open

**Priority:** P1

**Owner:** Semantic core

**Target Window:** 2026-Q4

**Wave:** C-Wave-3

**Purpose:** Analyze resource allocation/deallocation patterns to detect leaks or improper usage.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Resource tracker | `src/sattlint/analyzers/resource_usage.py` | Track resource allocation/deallocation |
| 2 | Leak detector | `src/sattlint/analyzers/resource_usage.py` | Detect resource leaks |
| 3 | Usage validator | `src/sattlint/analyzers/resource_usage.py` | Validate proper resource usage patterns |
| 4 | Reporter | `src/sattlint/analyzers/resource_usage.py` | Report findings |

**Input:** BasePicture with modulecode

**Output:** Resource usage findings with leak/usage issues

**Reuses:**
- `analyzers/dataflow.py` - expression evaluation
- `analyzers/scan_loop_resource_usage.py` - existing resource usage analysis

**Validation:** `pytest tests/test_resource_usage.py`

---

## Program D: New Tooling And CI Capabilities

New tooling, testing infrastructure, and pipeline features that do not yet exist.

### D Wave Summary

| Wave | Owner | Target Window | Items | Validation |
| --- | --- | --- | --- | --- |
| D-Wave-2 | Multiple | 2026-Q3 | D-016, D-017, D-018, D-022, D-023, D-026, D-036, D-038, D-039, D-040, D-041, D-042 | `pytest tests/` |
| D-Wave-Backlog | Semantic tooling | Backlog | - | Deferred |

---

### D-016 Fault Injection Testing

**Feature ID:** D-016

**Status:** Open

**Priority:** P1

**Owner:** Test infrastructure

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Inject faults and test system robustness.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Fault injector | `src/sattlint/devtools/fault_injection.py` | Inject faults |
| 2 | Test runner | `src/sattlint/devtools/fault_injection.py` | Run tests |
| 3 | Reporter | `src/sattlint/devtools/fault_injection.py` | Report results |

**Input:** Test cases + fault specifications

**Output:** Robustness test results

**Validation:** `pytest tests/test_fault_injection.py`

---

### D-017 Property-based Parser Testing

**Feature ID:** D-017

**Status:** Open

**Priority:** P1

**Owner:** Parser tooling

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Use property-based testing for parser robustness.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Property definitions | `src/sattlint/devtools/property_tests.py` | Define properties |
| 2 | Generator | `src/sattlint/devtools/property_tests.py` | Generate test cases |
| 3 | Runner | `src/sattlint/devtools/property_tests.py` | Run property tests |

**Input:** Grammar/properties

**Output:** Property test results

**Validation:** `pytest tests/test_property_based.py -v`

---

### D-018 Fuzzing Targets

**Feature ID:** D-018

**Status:** Open

**Priority:** P1

**Owner:** Parser tooling

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Create fuzzing targets for parser and analyzers.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Fuzzer | `src/sattlint/devtools/fuzzer.py` | Fuzz parser |
| 2 | Corpus builder | `src/sattlint/devtools/fuzzer.py` | Build corpus |
| 3 | Crash analyzer | `src/sattlint/devtools/fuzzer.py` | Analyze crashes |

**Input:** Fuzzing targets

**Output:** Crash reports

**Validation:** Run fuzzer, verify no crashes

---

### D-022 Finding Validation Feedback

**Feature ID:** D-022

**Status:** Open

**Priority:** P1

**Owner:** Pipeline + UX

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Create feedback loop for validating findings.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Feedback collector | `src/sattlint/devtools/feedback.py` | Collect feedback |
| 2 | Validator | `src/sattlint/devtools/feedback.py` | Validate findings |
| 3 | Reporter | `src/sattlint/devtools/feedback.py` | Report accuracy |

**Input:** Findings + user feedback

**Output:** Validation metrics

**Validation:** `pytest tests/test_feedback.py`

---

### D-023 Core Invariant Checks

**Feature ID:** D-023

**Status:** Open

**Priority:** P1

**Owner:** Devtools

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Run core invariant checks during development.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Invariant definitions | `src/sattlint/devtools/invariants.py` | Define invariants |
| 2 | Checker | `src/sattlint/devtools/invariants.py` | Check invariants |
| 3 | Reporter | `src/sattlint/devtools/invariants.py` | Report violations |

**Input:** Codebase

**Output:** Invariant violations

**Validation:** `sattlint-repo-audit --profile quick`

---

### D-026 Configuration Validation

**Feature ID:** D-026

**Status:** Open

**Priority:** P1

**Owner:** Config + CLI

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Validate configuration files against schemas.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Schema validator | `src/sattlint/config_validation.py` | Validate configs |
| 2 | Reporter | `src/sattlint/config_validation.py` | Report issues |

**Input:** Configuration files

**Output:** Validation errors

**Validation:** `pytest tests/test_config_validation.py`

---

### D-033 Test Quality Checks

**Feature ID:** D-033

**Status:** Open

**Priority:** P1

**Owner:** Devtools + QA

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Repository maintainability and test quality checks.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Quality checks | `src/sattlint/devtools/test_quality.py` | Define checks |
| 2 | Reporter | `src/sattlint/devtools/test_quality.py` | Report metrics |

**Input:** Test files

**Output:** Quality metrics

**Validation:** Run quality checks, verify metrics

---

### D-036 Analyzer Reference Examples

**Feature ID:** D-036

**Status:** Open

**Priority:** P1

**Owner:** Docs generation

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Generate analyzer reference documentation with examples.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Doc generator | `src/sattlint/docgenerator/reference.py` | Generate docs |
| 2 | Examples extractor | `src/sattlint/docgenerator/reference.py` | Extract examples |
| 3 | Formatter | `src/sattlint/docgenerator/reference.py` | Format output |

**Input:** Analyzer code

**Output:** Reference documentation

**Validation:** Check generated docs

---

### D-038 SFC Scan Cycle Simulation

**Feature ID:** D-038

**Status:** Open

**Priority:** P1

**Owner:** Simulation tooling

**Target Window:** 2026-Q3

**Wave:** D-Wave-2

**Purpose:** Enable AI to reason about module behavior through simulation; Verify module correctness; Detect steady-state and cycles.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Variable tracker | `src/sattlint/simulation/variable_state.py` | Track vars, deltas, metadata |
| 2 | Equation solver | `src/sattlint/simulation/equation_solver.py` | Evaluate equations |
| 3 | SFC engine | `src/sattlint/simulation/sfc_engine.py` | Execute SFC |
| 4 | Scan context | `src/sattlint/simulation/scan_context.py` | Active steps, snapshots |
| 5 | State hash | `src/sattlint/simulation/state_hash.py` | Steady/cycle detection |
| 6 | Main executor | `src/sattlint/simulation/executor.py` | Scan loop, modes |
| 7 | CLI | `src/sattlint/cli/entry.py` | Add `--simulate` |
| 8 | Tests | `tests/test_sfc_simulation.py` | Unit + integration |

**Input:**
```json
{
  "source": "Filename:BasePicture.Instance.Path",
  "inputs": {"param": value},
  "mode": "steady_state",
  "max_scans": 100,
  "detect_cycles": true,
  "trace_level": "minimal"
}
```

**7-Phase Execution Order:**

| Phase | Name | Description |
|-------|------|-------------|
| 1 | `read_inputs` | Read external inputs |
| 2 | `evaluate_transitions` | Evaluate transition conditions |
| 3 | `fire_transitions` | Fire true transitions |
| 4 | `activate_deactivate_steps` | Step activation |
| 5 | `execute_actions` | Execute actions |
| 6 | `solve_equations` | Evaluate equations |
| 7 | `commit_outputs` | Commit values |
```

**CLI Options:**

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--mode` | `steady_state`, `fixed_scans`, `debug` | `steady_state` | Mode |
| `--max-scans` | int | 100 | Max scans |
| `--detect-cycles` | flag | true | Enable cycle detection |
| `--trace-level` | `minimal`, `full` | `minimal` | Verbosity |
| `--format` | `json`, `table`, `both` | `json` | Output format |
| `--output` | path | stdout | Output file |

**Output:**
```json
{
  "source": "string",
  "mode": "string",
  "steady_state_reached": boolean,
  "steady_state_scan": number,
  "cycle_detected": boolean,
  "cycle_length": number,
  "total_scans": number,
  "variables": [{"scan": number, "values": {"var": {"value": any, "changed": boolean, "source": string}}}],
  "actions": [{"scan": number, "type": string, "name": string, "source": string}],
  "errors": []
}
```

**Steady State Detection:** Compare all variable values between consecutive scans. Identical = steady state.

**Cycle Detection:** Track `state_hash = hash(values + active_steps)`. Hash repeat = cycle.

**Reuses:**
- `core/semantic.py:load_workspace_snapshot()` - workspace loading
- `analyzers/dataflow.py:_evaluate_expression()` - expression evaluation
- `analyzers/dataflow.py:_evaluate_condition()` - transition evaluation
- `resolution/common.py:resolve_moduletype_def_strict()` - resolve instances

**Validation:** `pytest tests/test_sfc_simulation.py`

---

### D-039 Performance Profiling Tool

**Feature ID:** D-039

**Status:** Open

**Priority:** P1

**Owner:** Devtools

**Target Window:** 2026-Q4

**Wave:** D-Wave-2

**Purpose:** Add profiling capabilities to identify performance bottlenecks in SattLine code execution.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Profiler | `src/sattlint/devtools/profiler.py` | Profile code execution |
| 2 | Bottleneck detector | `src/sattlint/devtools/profiler.py` | Identify performance bottlenecks |
| 3 | Reporter | `src/sattlint/devtools/profiler.py` | Report profiling results |

**Input:** SattLine code + execution parameters

**Output:** Performance profiling report with bottlenecks

**Reuses:**
- `core/semantic.py:load_workspace_snapshot()` - workspace loading
- `engine.py:parse_source_file()` - parsing

**Validation:** `pytest tests/test_profiler.py`

---

### D-040 Automated Refactoring Tools

**Feature ID:** D-040

**Status:** Open

**Priority:** P1

**Owner:** Devtools

**Target Window:** 2026-Q4

**Wave:** D-Wave-2

**Purpose:** Provide safe refactoring operations for common code transformations.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Refactoring engine | `src/sattlint/devtools/refactoring.py` | Perform code transformations |
| 2 | Safety checker | `src/sattlint/devtools/refactoring.py` | Verify refactoring safety |
| 3 | Reporter | `src/sattlint/devtools/refactoring.py` | Report refactoring results |

**Input:** SattLine code + refactoring specifications

**Output:** Refactored code + safety report

**Reuses:**
- `core/semantic.py:load_workspace_snapshot()` - workspace loading
- `analyzers/dataflow.py` - expression evaluation
- `resolution/common.py` - reference resolution

**Validation:** `pytest tests/test_refactoring.py`

---

### D-041 Impact Analysis Tool

**Feature ID:** D-041

**Status:** Open

**Priority:** P1

**Owner:** Devtools

**Target Window:** 2026-Q4

**Wave:** D-Wave-2

**Purpose:** Analyze the impact of changes across the codebase to help with risk assessment.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Change analyzer | `src/sattlint/devtools/impact_analyzer.py` | Analyze code changes |
| 2 | Dependency mapper | `src/sattlint/devtools/impact_analyzer.py` | Map code dependencies |
| 3 | Impact evaluator | `src/sattlint/devtools/impact_analyzer.py` | Evaluate change impact |
| 4 | Reporter | `src/sattlint/devtools/impact_analyzer.py` | Report impact analysis |

**Input:** BasePicture + change specifications

**Output:** Impact analysis report with risk assessment

**Reuses:**
- `core/semantic.py:load_workspace_snapshot()` - workspace loading
- `analyzers/dataflow.py` - expression evaluation
- `resolution/common.py` - reference resolution

**Validation:** `pytest tests/test_impact_analysis.py`

---

### D-042 Code Metrics Dashboard

**Feature ID:** D-042

**Status:** Open

**Priority:** P1

**Owner:** Devtools

**Target Window:** 2026-Q4

**Wave:** D-Wave-2

**Purpose:** Generate and display code quality metrics (complexity, coupling, cohesion, etc.).

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Metrics calculator | `src/sattlint/devtools/metrics_dashboard.py` | Calculate code metrics |
| 2 | Dashboard generator | `src/sattlint/devtools/metrics_dashboard.py` | Generate metrics dashboard |
| 3 | Reporter | `src/sattlint/devtools/metrics_dashboard.py` | Report metrics results |

**Input:** BasePicture

**Output:** Code metrics dashboard with quality assessments

**Reuses:**
- `core/semantic.py:load_workspace_snapshot()` - workspace loading
- `analyzers/cyclomatic_complexity.py` - complexity analysis
- `analyzers/modules.py` - module analysis

**Validation:** `pytest tests/test_metrics_dashboard.py`

---

## Program E: GUI Explorer

New GUI explorer that does not exist yet.

### E Wave Summary

| Wave | Owner | Target Window | Features | Validation |
| --- | --- | --- | --- | --- |
| E-GUI-M1 | GUI core | 2026-Q3 | E1, E12 | No crash on empty |
| E-GUI-M2 | GUI + Semantic | 2026-Q4 | E3, E4 | Virtualization works |
| E-GUI-M3 | GUI + Analyzer | 2026-Q4 | E2, E9 | Diff renders |
| E-GUI-M4 | GUI + Platform | 2027-Q1 | E5, E10 | Feature flags work |
| E-GUI-M5 | GUI + Platform | 2027-Q2 | E6-E11 | a11y audit pass |
| E-GUI-M6 | GUI + Platform | 2027-Q3 | E13, E14 | Debugger functional |
| E-GUI-M8 | GUI + Platform | 2028-Q1 | E15, E16 | Export/import works |

---

### E-GUI-M1 Explorer Skeleton

**Milestone:** E-GUI-M1

**Status:** Open

**Priority:** P1

**Owner:** GUI core

**Target Window:** 2026-Q3

**Wave:** E-GUI-M1

**Purpose:** CreateExplorer GUI application skeleton with basic infrastructure.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Electron main | `electron/main.ts` | Application entry |
| 2 | Renderer | `renderer/index.html` | Base HTML |
| 3 | IPC bridge | `electron/ipc.ts` | Main-renderer IPC |
| 4 | Empty state | `renderer/components/` | Empty state UI |

**Validation:** Build and run, no crash on empty workspace.

---

### E-GUI-M2 Real Data Wiring

**Milestone:** E-GUI-M2

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Semantic core

**Target Window:** 2026-Q4

**Wave:** E-GUI-M2

**Purpose:** Wire real SattLine data into explorer.

**Dependencies:** E-GUI-M1

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Workspace loader | Wire `load_workspace_snapshot()` | Load data |
| 2 | File tree | `renderer/components/FileTree.tsx` | Virtualized file list |
| 3 | Issue list | `renderer/components/IssueList.tsx` | Virtualized issues |
| 4 | Editor | `renderer/components/Editor.tsx` | Code display |

**Validation:** Load real workspace, verify virtualization renders.

---

### E-GUI-M3 Draft vs Official Diff

**Milestone:** E-GUI-M3

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Analyzer

**Target Window:** 2026-Q4

**Wave:** E-GUI-M3

**Purpose:** Render diff between draft and official code.

**Dependencies:** E-GUI-M2

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Diff engine | Wire `analyzers/diff.py` | Compute diff |
| 2 | Diff view | `renderer/components/Diff.tsx` | Render diff |
| 3 | Error surface | `renderer/components/Errors.tsx` | Show errors |

**Validation:** Diff renders correctly.

---

### E-GUI-M4 Resilience and UX Polish

**Milestone:** E-GUI-M4

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2027-Q1

**Wave:** E-GUI-M4

**Purpose:** Feature flags, batch operations, command palette.

**Dependencies:** E-GUI-M3

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Feature flags | `renderer/features/` | Toggle features |
| 2 | Batch ops | `renderer/components/BatchOps.tsx` | Multi-select |
| 3 | Command palette | `renderer/components/CommandPalette.tsx` | Commands |

**Validation:** Feature flags work, batch ops verified.

---

### E-GUI-M5 Accessibility

**Milestone:** E-GUI-M5

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2027-Q2

**Wave:** E-GUI-M5

**Purpose:** i18n, accessibility, security hardening.

**Dependencies:** E-GUI-M4

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | i18n | `renderer/i18n/` | Externalize strings |
| 2 | a11y | `renderer/a11y/` | Screen reader |
| 3 | Security | `renderer/security/` | Hardening |
| 4 | Sync | `renderer/sync/` | Cloud sync |

**Validation:** a11y audit pass, i18n externalized.

---

### E-GUI-M6 Interactive Debugger

**Milestone:** E-GUI-M6

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2027-Q3

**Wave:** E-GUI-M6

**Purpose:** Add debugging capabilities to the GUI explorer with breakpoints, step-through execution, and variable inspection.

**Dependencies:** E-GUI-M5

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Debugger controller | `electron/debugger.ts` | Control debugging session |
| 2 | Breakpoint manager | `renderer/components/BreakpointManager.tsx` | Manage breakpoints |
| 3 | Step controls | `renderer/components/StepControls.tsx` | Step-through execution |
| 4 | Variable inspector | `renderer/components/VariableInspector.tsx` | Inspect variables |
| 5 | Call stack view | `renderer/components/CallStackView.tsx` | Display call stack |

**Validation:** Debugger launches and can set breakpoints, step through code, and inspect variables.

---

### E-GUI-M8 Export/Import Capabilities

**Milestone:** E-GUI-M8

**Status:** Open

**Priority:** P1

**Owner:** GUI core + Platform

**Target Window:** 2028-Q1

**Wave:** E-GUI-M8

**Purpose:** Allow exporting analysis results in various formats and importing configurations.

**Dependencies:** E-GUI-M6

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Export manager | `electron/export_manager.py` | Handle export operations |
| 2 | Import manager | `electron/import_manager.py` | Handle import operations |
| 3 | Format handlers | `renderer/components/FormatHandlers.tsx` | Support various formats |
| 4 | Export dialog | `renderer/components/ExportDialog.tsx` | Configure export options |
| 5 | Import dialog | `renderer/components/ImportDialog.tsx` | Configure import options |

**Validation:** Can export analysis results to JSON, CSV, HTML and import configurations successfully.

---

## Feature Implementation Template

Use this template when adding new features.

### Feature ID

**Feature ID:** F-XXX

**Status:** Open

**Priority:** P1 or P2

**Owner:** Owner team

**Target Window:** Quarter or "Backlog"

**Wave:** Program wave

**Purpose:** One-paragraph description.

**Implementation Guide:**

| Order | Component | File | Description |
| ------|----------|------|-------------|
| 1 | Component A | `path/to/file.py` | What it does |

**Input:** Input format/description

**Output:** Output format/description

**Reuses:**
- Existing component (path)

**Validation:** Command to validate

**See also:** Related features

---

## Common Reusable Components

| Component | Path | Purpose |
|-----------|------|---------|
| Workspace snapshot | `core/semantic.py:load_workspace_snapshot()` | Load workspace |
| Parser | `engine.py:parse_source_file()` | Parse file |
| Expression evaluator | `analyzers/dataflow.py:_evaluate_expression()` | Evaluate |
| Module resolver | `resolution/common.py:resolve_*()` | Resolve refs |
| AST models | `sattline_parser/models/ast_model.py` | Data structures |
| Grammar | `sattline_parser/grammar/sattline.lark` | Parser grammar |
