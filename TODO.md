# TODO

Ranking notes:

- Ease is 1 (easiest) to 5 (hardest).
- Usefulness is 1 (low) to 5 (high).

## Ranked backlog (easiest to hardest)

### 2. Required parameter connections (no defaults)

- Ease: 2/5. Usefulness: 3/5.
- Why: flags parameters that are vital for module function and must be mapped (no default).
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/analyzers/modules.py](src/sattlint/analyzers/modules.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [tests/test_module_localvar_strict.py](tests/test_module_localvar_strict.py)

### 3. Magic numbers in equations

- Ease: 2/5. Usefulness: 4/5.
- Why: encourages named constants for maintainability.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/transformer/sl_transformer.py](src/sattlint/transformer/sl_transformer.py), [tests/test_analyzers.py](tests/test_analyzers.py)

### 4. Variable shadowing (local hides outer/global)

- Ease: 3/5. Usefulness: 3/5.
- Why: prevents silent overrides in nested modules.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/resolution/symbol_table.py](src/sattlint/resolution/symbol_table.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [tests/test_analyzers.py](tests/test_analyzers.py)

### 5. Global variables used only in a few submodules

- Ease: 3/5. Usefulness: 4/5.
- Why: suggests reducing scope and improving encapsulation.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/resolution/access_graph.py](src/sattlint/resolution/access_graph.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [tests/test_analyzers.py](tests/test_analyzers.py)

### 6. Naming consistency across modules

- Ease: 3/5. Usefulness: 3/5.
- Why: standardizes naming (PumpSpeed vs PUMP_SPD).
- Files: [src/sattlint/analyzers/modules.py](src/sattlint/analyzers/modules.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/app.py](src/sattlint/app.py), [tests/test_analyzers.py](tests/test_analyzers.py)

### 7. High fan-in / fan-out variables

- Ease: 3/5. Usefulness: 4/5.
- Why: exposes fragile shared signals and unclear ownership.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/resolution/access_graph.py](src/sattlint/resolution/access_graph.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [tests/test_analyzers.py](tests/test_analyzers.py)

### 8. Variables referenced only by UI/graph objects

- Ease: 3/5. Usefulness: 3/5.
- Why: catches display-only signals not used in logic.
- Files: [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/transformer/sl_transformer.py](src/sattlint/transformer/sl_transformer.py), [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [SattLineReferenceDocs/sattline_graphics_reference.md](SattLineReferenceDocs/sattline_graphics_reference.md)

### 9. SFC transition logic sanity checks

- Ease: 4/5. Usefulness: 4/5.
- Why: flags always-true/false transitions and duplicate conditions.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/analyzers/sfc.py](src/sattlint/analyzers/sfc.py), [SattLineReferenceDocs/sattline_language_reference.md](SattLineReferenceDocs/sattline_language_reference.md)

### 10. Cyclomatic complexity per module or step

- Ease: 4/5. Usefulness: 3/5.
- Why: surfaces overly complex logic.
- Files: [src/sattlint/analyzers/sfc.py](src/sattlint/analyzers/sfc.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/analyzers/modules.py](src/sattlint/analyzers/modules.py), [tests/test_analyzers.py](tests/test_analyzers.py)

### 11. Missing status handling for procedures

- Ease: 4/5. Usefulness: 4/5.
- Why: checks status outputs from builtins are ignored.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py),
[src/sattlint/analyzers/sattline_builtins.py](src/sattlint/analyzers/sattline_builtins.py),
[src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py),
[tests/test_analyzers.py](tests/test_analyzers.py)

### 12. Read-before-init and dead overwrite detection

- Ease: 4/5. Usefulness: 4/5.
- Why: catches uninitialized reads and overwritten values.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/resolution/access_graph.py](src/sattlint/resolution/access_graph.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [SattLineReferenceDocs/sattline_execution_reference.md](SattLineReferenceDocs/sattline_execution_reference.md)

### 13. Parallel branch write races in SFC

- Ease: 5/5. Usefulness: 5/5.
- Why: detects concurrent writes across parallel branches.
- Files: [src/sattlint/analyzers/sfc.py](src/sattlint/analyzers/sfc.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/resolution/access_graph.py](src/sattlint/resolution/access_graph.py), [SattLineReferenceDocs/sattline_language_reference.md](SattLineReferenceDocs/sattline_language_reference.md)
- Status: implemented (parallel-branch write race detection).

### 14. Reset-detection and batch contamination checks

- Ease: 5/5. Usefulness: 5/5.
- Why: prevents cross-batch data leakage and stale state usage.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/resolution/access_graph.py](src/sattlint/resolution/access_graph.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [SattLineReferenceDocs/sattline_batch_control_reference.md](SattLineReferenceDocs/sattline_batch_control_reference.md)

### 15. OPC/MES validation enhancements (beyond current ICF path checks)

- Ease: 4/5. Usefulness: 4/5.
- Why: adds datatype checks, duplicates, dead tags, and naming drift.
- Files: [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/resolution/type_graph.py](src/sattlint/resolution/type_graph.py), [src/sattlint/engine.py](src/sattlint/engine.py), [SattLineReferenceDocs/sattline_io_communication_reference.md](SattLineReferenceDocs/sattline_io_communication_reference.md)

### 16. Markdown/HTML doc output and parameter catalog

- Ease: 4/5. Usefulness: 4/5.
- Why: adds lightweight docs and a single-page interface inventory.
- Files: [src/sattlint/docgenerator/docgen.py](src/sattlint/docgenerator/docgen.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/app.py](src/sattlint/app.py), [tests/test_app.py](tests/test_app.py)

### 17. Dependency diagrams and change-impact analysis

- Ease: 5/5. Usefulness: 4/5.
- Why: visualizes module/variable coupling and supports impact reports.
- Files: [src/sattlint/resolution/access_graph.py](src/sattlint/resolution/access_graph.py), [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/models/project_graph.py](src/sattlint/models/project_graph.py), [src/sattlint/docgenerator/docgen.py](src/sattlint/docgenerator/docgen.py)

### 18. AST diff and upgrade notes

- Ease: 5/5. Usefulness: 3/5.
- Why: auto-generates release notes for renamed or changed elements.
- Files: [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [src/sattlint/engine.py](src/sattlint/engine.py), [src/sattlint/app.py](src/sattlint/app.py), [tests/test_engine.py](tests/test_engine.py)

### 19. PLC/SFC pattern-based bug rules

- Ease: 5/5. Usefulness: 4/5.
- Why: codifies common PLC anti-patterns (latch without reset, etc.).
- Include: `State` variable `:OLD` misuse within same scan (e.g., exit writes then next-step entry reads `:OLD` and overwrites reset).
- Files: [src/sattlint/analyzers/sfc.py](src/sattlint/analyzers/sfc.py), [src/sattlint/analyzers/variables.py](src/sattlint/analyzers/variables.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [SattLineReferenceDocs/sattline_execution_reference.md](SattLineReferenceDocs/sattline_execution_reference.md)

### 20. Resource and buffer analysis in scan loop

- Ease: 5/5. Usefulness: 3/5.
- Why: flags heavy operations inside high-frequency actions.
- Files: [src/sattlint/analyzers/sfc.py](src/sattlint/analyzers/sfc.py), [src/sattlint/analyzers/sattline_builtins.py](src/sattlint/analyzers/sattline_builtins.py), [src/sattlint/models/ast_model.py](src/sattlint/models/ast_model.py), [SattLineReferenceDocs/sattline_execution_reference.md](SattLineReferenceDocs/sattline_execution_reference.md)
