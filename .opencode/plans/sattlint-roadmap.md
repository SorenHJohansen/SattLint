# SattLint Development Roadmap

## 🔥 High Priority - Core Analysis Enhancements

### Variable Analysis Improvements
- [ ] **Min/Max mismatch detection** - Detect "min" variables written to "max" parameters (and vice-versa)
- [ ] **Parameter default analysis** - Flag parameters always set to same value as candidates for defaults
- [ ] **Variable shadowing detection** - Local variables hiding outer/global ones
- [ ] **Scope optimization** - Flag global/module-level variables only used in few submodules
- [ ] **Read-before-init detection** - Variables read before any initialization
- [ ] **Race condition detection** - Variables written in multiple parallel tasks
- [ ] **Datatype sizing** - Flag oversized datatypes (e.g., STRING[256] for "OK")
- [ ] **High fan-in/out analysis** - Identify fragile variables (many readers) and race-prone variables (many writers)
- [ ] **Text_vars validation** - Variables only in UI fields but not in code

### Control Flow Analysis
- [ ] **Unreachable code detection** - Dead ELSE branches, constant FALSE transitions
- [ ] **Constant condition analysis** - Always true/false conditions
- [ ] **Cyclomatic complexity** - Per-module/SFC step complexity metrics
- [ ] **Missing error handling** - Functions returning status codes but ignored by callers

## 🟡 Medium Priority - Advanced Features

### SFC-Specific Analysis
- [ ] **Transition logic validation** - Always FALSE/TRUE transitions, duplicate conditions
- [ ] **Step execution issues** - Actions without reset, orphaned timers, concurrent writes
- [ ] **Dead step detection** - Steps unreachable due to logic flow
- [ ] **SFC performance** - Repeated expensive operations in high-frequency actions
- [ ] **Initialization validation** - Missing step-local variable initialization

### Parameter & Structural Analysis
- [ ] **Parameter mapping validation** - Datatype mismatches, unused parameters
- [ ] **Global variable abuse detection** - Too many modules accessing same globals
- [ ] **Naming consistency** - Inconsistent naming patterns across modules
- [ ] **Non-reentrant module detection** - Variables that should be local but are global

### Architectural Analysis
- [ ] **Dependency cycle detection** - A depends on B and B depends on A
- [ ] **Module coupling analysis** - Cross-module data dependency visualization
- [ ] **Duplicate code detection** - Duplicated code across submodules

## 🔵 Low Priority - Documentation & Tooling

### Documentation Generation
- [ ] **Auto-generated design documentation** - Module-by-module specs with parameters, variables, SFC steps
- [ ] **Parameter interface catalog** - All module parameters with datatypes, defaults, usage examples
- [ ] **Call-graph generation** - Variable and module dependency graphs (DOT/PNG export)
- [ ] **Change-impact analysis** - Transitive impact analysis for variable/parameter changes

### OPC/MES Integration
- [ ] **OPC consistency validation** - Compare .icf XML file with SattLine variable index
- [ ] **Missing variable detection** - OPC references not found in SattLine code
- [ ] **Datatype validation** - OPC vs SattLine type mismatches
- [ ] **Dead OPC tag detection** - OPC items mapped to never-written variables

### Advanced Visualization
- [ ] **Variable usage heatmaps** - Density visualization for refactor targets
- [ ] **Pattern-based bug detection** - Typical PLC/SFC antipatterns (latch-without-reset, etc.)
- [ ] **Concurrency analysis** - Parallel SFC branch race conditions
- [ ] **Resource usage analysis** - Memory-heavy operations in scan loops

## 🛠️ Implementation Notes

### Reset/Batch Contamination Detection
- [ ] **Event timeline tracking** - Track variable writes/reads across operation windows
- [ ] **Reset boundary validation** - Detect contamination between batch operations
- [ ] **Configurable reset detection** - Support .Reset suffix, canonical reset values

### AST-Driven Features
- [ ] **Upgrade note generation** - Diff ASTs between versions for release notes
- [ ] **Design pattern recognition** - Identify common SattLine implementation patterns
- [ ] **Performance profiling** - Identify expensive operations in scan loops

## 📋 Current Status Assessment

### ✅ Already Implemented
- [x] Basic variable usage analysis (unused, read-only non-const, written-but-never-read)
- [x] Variable read/write location tracking
- [x] Module duplication detection
- [x] Basic AST generation and traversal
- [x] DOCX documentation generation

### 🔄 In Progress
- [ ] Enhanced variable analysis (based on variables.py refactor potential)
- [ ] Integration with existing analyzer framework

### 📝 Implementation Priority Rationale
1. **High**: Core static analysis features that provide immediate value for code quality
2. **Medium**: Advanced features requiring significant AST enhancement but high impact
3. **Low**: Documentation and tooling features useful for project management but not core analysis

---

## 🎯 Quick Wins (Implementation Candidates)
- Min/max mismatch detection (simple string pattern matching)
- Parameter default analysis (track assignment patterns)
- Variable shadowing detection (scope context already exists)
- Unreachable code detection (simple condition analysis)