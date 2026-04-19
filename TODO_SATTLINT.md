# TODO – SattLint Analyzer Features

Domain-specific analyzer roadmap for SattLine code. Focused on correctness, safety, and maintainability.

---

## 1. Safety & Control-Critical Analysis (Highest Priority)

### Alarm Integrity Checks

* Detect never-cleared alarms
* Identify duplicated alarm conditions
* Flag conflicting alarm priorities across modules
* Alarm names must be unique across the entire application. Detect if two alarms have the same tag name.

---

### Safety-Critical Path Analysis

* Trace signals affecting shutdown/emergency logic
* Verify proper reset behavior and redundancy handling
* Detect unsafe propagation of critical signals

---

### Scan-Cycle Semantics Violations

* Detect logic assuming immediate updates within the same scan cycle
* Flag misuse of `:OLD` or equivalent temporal constructs

---

### Missing Reset Symmetry / Implicit Latching

* Detect signals set in some paths but not reset in all
* Generalized latch detection across branches and SFC steps

---

### Unsafe Default Values

* Identify defaults that may trigger equipment or bypass safety checks

---

## 2. SFC & State Machine Correctness

### Dead SFC Paths & Unreachable Transitions

* Graph-based reachability analysis
* Identify transitions that can never trigger

---

### Illegal State Combinations

* Detect mutually exclusive states active at the same time
* Validate state invariants

---

### Parallel Branch Write Conflicts

* Detect concurrent writes to the same variable in parallel SFC branches

---

### SFC Transition Logic Validation

* Flag always-true / always-false conditions
* Detect duplicated or redundant transitions

---

### SFC Step Entry/Exit Contracts

* Ensure entry actions initialize required state
* Ensure exit actions clean up state
* Detect state leakage between steps

---

### Procedure Status Handling

* Ensure procedure/function status outputs are handled by callers

---

## 4. Dataflow & Semantic Correctness

### Read-Before-Write & Dead Overwrites

* Detect uninitialized reads
* Identify values overwritten before being used

---

### Lightweight Dataflow / Behavioral Inference

* Infer variable ranges and state propagation
* Detect impossible or contradictory conditions

---

### Dataflow Taint Tracking

* Track external inputs (MES, operator, sensors)
* Flag unsafe usage without validation in control logic

---

### AnyType Field Compatibility

* Ensure required fields exist when accessing generic structures

---

### Write-Without-Effect Detection

* Identify writes that never influence outputs

---

## 5. Cross-Module & System-Level Consistency

### Cross-Module Contract Mismatches

* Detect type and semantic mismatches between connected modules

---

### Hidden Global Coupling

* Detect globals acting as implicit interfaces
* Encourage explicit parameter mapping

---

### Global Scope Minimization

* Identify globals used in limited scope
* Suggest localization

---

### High Fan-In / Fan-Out Variables

* Flag heavily shared variables with unclear ownership

---

### Parameter Drift Across Instances

* Detect inconsistent parameter values across module instances

---

### Version Drift Detection

* Identify near-identical modules diverging over time

---

## 6. Structural Quality & Maintainability

### Cyclomatic Complexity Analysis

* Measure complexity per module / SFC step
* Flag overly complex logic

---

### Duplicate Logic Detection

* Detect structurally identical logic blocks
* Suggest refactoring into shared components

---

### Resource Usage in Scan Loop

* Flag heavy operations in high-frequency scan logic
* Identify potential performance risks

---

### Loop Output Refactoring Tool

* Analyze loop outputs provided by SattLine
* Suggest structural transformations to eliminate loops

---

## 7. Naming & Semantic Conventions

### Naming Consistency

* Enforce consistent naming conventions across modules

---

### Naming-to-Behavior Validation

* `Cmd` variables not used as state
* `Status` variables not directly written

---

### Engineering Unit Consistency

* Detect inconsistent unit usage across modules

---

## 8. Configuration & Interface Validation

### Required Parameter Connections

* Flag critical parameters that must be explicitly mapped

---

### Initial Value Validation

* Detect missing defaults for recipe and engineering parameters

---

### OPC / MES Validation

* Datatype validation
* Duplicate tag detection
* Dead tag cleanup
* Naming drift detection

---

## 9. Architecture & Impact Analysis

### Dependency Graph & Impact Analysis

* Generate coupling diagrams
* Provide change-impact reports

---

### AST Diff & Upgrade Insights

* Semantic diff between versions
* Auto-generate upgrade notes for changed elements

---

## 10. Observability & Developer Experience

### Explanation & Fix Suggestions

* Convert findings into actionable explanations
* Provide suggested fixes per issue type

---

### Confidence Scoring

* Classify findings:

  * Definite bug
  * Likely issue
  * Style suggestion

---

### Documentation Output

* Generate Markdown / HTML reports
* Produce parameter catalogs and interface inventories

---

### UI/Display-Only Variable Detection

* Identify variables only used in UI/graphs
* Flag unnecessary resource usage

---

