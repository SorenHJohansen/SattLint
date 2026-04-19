# TODO – SattLint Tooling Roadmap

Focused roadmap for analyzers, developer tooling, and pipeline maturity.

---

## 1. Core Analyzer Capabilities (High Priority)

### SattLine Semantic Analysis Layer

Introduce `sattline-semantics` category with domain-aware checks:

* Unused variables (SattLine-aware, not generic)
* Read-before-write detection
* Cross-module interface mismatches
* Invalid module definitions
* IEC 61131-3 structural violations
* Dead branches / unreachable logic

**Outcome:** Domain-correctness, not just syntax quality.

---

### Lightweight Dataflow / Symbolic Execution

Track variable state across branches:

* Detect always-true/false conditions
* Identify unreachable paths
* Surface implicit logic bugs

Optional:

* Generate pytest cases from detected edge conditions

---

### Structural Graph Generation

Generate machine-readable artifacts:

* `call_graph.json`
* `dependency_graph.json`
* `analyzer_registry.json` (rule → analyzer → output mapping)

**Use cases:** debugging, visualization, AI-assisted reasoning

---

### Rule Engine Standardization

Unify all checks under a rule model:

```
{id, source, category, severity, applies_to}
```

**Outcome:** consistent execution, filtering, and reporting

---

## 2. Signal Quality & Observability

### Execution Tracing

Track per run:

* Rules executed
* Files analyzed
* Execution time (rule + file)
* Findings triggered

Output:

* `analysis_trace.json`

---

### Performance Profiling

* Identify slow rules
* Configurable thresholds for warnings

---

### Semantic Coverage & Rule Effectiveness

Track:

* Seen vs supported SattLine constructs
* Rule execution count vs trigger rate

Outputs:

* `semantic_coverage.json`
* `rule_metrics.json`

---

### Standardized Output Schema

Unify all outputs:

```
{
  tool,
  summary,
  findings: [
    {type, file, line, symbol, message, confidence, category, impact}
  ]
}
```

---

## 3. Accuracy Improvements

### Improved Dead Code Detection

Replace naive detection with:

```
unused = defined - referenced - entrypoints
```

Entrypoints collected from:

* CLI
* LSP
* Analyzer registry

---

### Feature Exposure Validation

Ensure all rules are reachable via:

* CLI
* TUI
* LSP

Output:

* `missing_exposure` findings

---

### Architecture & Boundary Checks

Detect:

* Circular dependencies
* Layer violations (e.g. core used incorrectly by CLI)
* High fan-in / fan-out
* Overloaded modules/functions

---

## 4. Security & Hygiene Checks

### Secrets & Environment Leak Detection

* Hardcoded paths (`C:\`, `/home/...`)
* API keys, tokens, credentials
* Machine-specific config

---

### Public Readiness Checks

* Internal URLs
* Debug artifacts
* Dev-only configs

---

### Configuration Validation

* Missing required fields
* Deprecated options
* Inconsistent config structure

---

## 5. Developer Experience

### CLI / TUI Consistency

* Naming conventions
* Command structure alignment
* Predictable UX patterns

---

### Logging & Observability

* Ensure critical paths are logged
* Detect missing error handling

---

### Analyzer Coverage Checks

Verify:

* All rules are registered
* All analyzers are exposed
* No orphaned logic

---

## 6. CI / Pipeline Integration

### Pre-commit Hooks

* Run fast checks locally before commit

---

### CI Validation Pipeline

* Full analysis run
* Artifact publishing
* Fail on critical findings

---

### Incremental Analysis (Diff-Based)

* Run only affected analyzers based on changes

---

### Baseline & Diff System

Support:

```
--baseline baseline.json
```

Outputs:

* `analysis_diff.json` (new / resolved / unchanged issues)

---

## 7. Testing Strategy

### Property-Based Parser Testing

* Validate grammar robustness across edge cases

---

### Fuzzing Targets

* Grammar fuzzing (AFL / libFuzzer)
* Detect crashes and hangs

---

### Regression Suite

* Lock down critical analyzer behavior

---

### Coverage Analysis

* Detect untested modules and weak tests

---

## 8. Documentation & AI Integration

### Analyzer Reference Examples

* Input/output examples per rule
* Expected findings

---

### AI Task Templates

* Reusable prompts for:

  * Fixing findings
  * Refactoring code
  * Explaining analysis results

---

## Suggested Execution Order

1. Semantic analysis layer
2. Dataflow tracking
3. Dead code accuracy fix
4. Execution tracing + output schema
5. Feature exposure validation
6. CI + baseline system
7. Structural graphs
8. Coverage + rule metrics
