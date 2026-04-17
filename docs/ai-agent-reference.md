# AI Agent Reference For SattLint

This file supplements `AGENTS.md` with deeper background, examples, and file references. It is reference material, not the primary control file.

- Follow direct user instructions first.
- Follow code and tests over stale documentation.
- Use `AGENTS.md` for stable workflow rules, safety guidance, and critical invariants.

---

## Repo Architecture Summary

- `src/sattline_parser/` is the parser-core package.
- `src/sattlint/` is the application package that consumes the parser core.
- `src/sattlint/core/semantic.py` contains shared workspace discovery, symbol lookup, references, completions, and snapshot construction.
- `src/sattlint/core/document.py` contains shared line-index and UTF-16 offset helpers.
- `src/sattlint/editor_api.py` is a compatibility facade over the shared semantic core.
- `src/sattlint_lsp/` contains the external language-server layer.
- `vscode/sattline-vscode/` contains the no-build VS Code client.
- `src/sattlint/devtools/pipeline.py` runs the repo-local lint, type, test, dead-code, security, and architecture checks into JSON artifacts.
- `src/sattlint/tracing.py` traces parser-to-analyzer execution for a concrete SattLine file.

---

## SattLine Quick Reference

### Execution Model

SattLine is scan-based PLC code. Programs continuously read inputs, execute logic, write outputs, and repeat. Variables retain values between scans, and `:OLD` or `:NEW` state access is used for transition detection.

### Minimal File Skeleton

```sattline
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
LOCALVARIABLES
    Counter: integer := 0;
ModuleCode
    EQUATIONBLOCK Main :
        Counter = Counter + 1;
    ENDDEF (*Main*);
ENDDEF (*BasePicture*);
```

### Module Hierarchy

```text
BasePicture
|- datatype_defs
|- moduletype_defs
|- localvariables
|- submodules
|  |- SingleModule
|  |- FrameModule
|  \- ModuleTypeInstance
|- moduledef
\- modulecode
```

### Variables

- `CONST` variables are read-only after initialization.
- `STATE` variables allow `:OLD` and `:NEW` access.
- `GLOBAL` variables can cross module boundaries.
- `OPSAVE` variables preserve operator-station values.
- Record fields are accessed with dot notation such as `MyVar.Field1`.

### Equation And Sequence Notes

- Equation blocks run continuously each scan.
- Sequences use steps, transitions, alternatives, parallel branches, forks, and breaks.
- Sequence auto-vars include `StepName.X` and `StepName.T` when the surrounding sequence supports them.

### Parameter Mappings

Parameter mappings use `=>` and matter for both type resolution and variable-usage analysis.

```sattline
SUBMODULES
    MyInstance Invocation (0,0,0,1,1) : ModuleType (
        Param1 => SourceVar,
        Param2 => GLOBAL GlobalVar,
        Param3 => 42
    );
```

### Graphics And Interact Notes

The parser retains graphics and interact structures, but most static analysis is code-focused. An important exception is `InVar_` tracking in supported graphics and interact tails, which can represent real variable reads.

---

## AST And Analysis Reference

### Core AST Types

- `BasePicture` is the root aggregate for datatype definitions, moduletype definitions, variables, submodules, module graphics, and module code.
- `Variable` stores declaration metadata and optional source spans.
- `ModuleTypeDef`, `SingleModule`, `FrameModule`, and `ModuleTypeInstance` represent module structure.
- `ModuleCode` contains `sequences` and `equations`.
- Expressions are stored as nested tuples plus variable-reference dictionaries and literal wrapper objects.

### Expression Shapes

```python
('assign', {'var_name': 'Output'}, value_expr)
('IF', [(cond1, [stmts1]), (cond2, [stmts2])], else_stmts)
('compare', left_expr, [('>', right_expr)])
('FunctionCall', 'FunctionName', [arg1, arg2])
{'var_name': 'VarName.Field', 'state': 'old', 'span': SourceSpan(...)}
```

### Grammar Pipeline

1. `src/sattline_parser/grammar/sattline.lark` defines syntax.
2. `src/sattline_parser/transformer/sl_transformer.py` maps parse trees to AST objects.
3. `src/sattlint/engine.py` handles parsing, project loading, merging, and syntax-check behavior.

### Variable-Usage Model

- Usage tracking is detached from the AST in `src/sattlint/models/usage.py`.
- `VariableUsage` tracks whole-variable reads and writes plus field-level reads and writes.
- Record usage can propagate through parameter mappings and nested alias chains.
- Whole-record access suppresses partial unused-field findings.
- Partial record-leaf findings are emitted as `UNUSED_DATATYPE_FIELD`, aggregated by datatype across the analyzed target.

### Common Analyzer Issue Kinds

- `UNUSED`
- `READ_ONLY_NON_CONST`
- `NEVER_READ`
- `STRING_MAPPING_MISMATCH`
- `DATATYPE_DUPLICATION`
- `MAGIC_NUMBER`
- `SHADOWING`
- `RESET_CONTAMINATION`

---

## Workspace, Editor, And LSP Details

- Workspace snapshots use shared semantic-core logic and a proximity-based dependency heuristic for bare `.l` or `.z` dependency stems.
- The heuristic is editor or LSP only: same library directory first, then sibling library roots in the nearest cluster, then the rest of the discovered workspace.
- CLI resolution remains config-driven.
- Workspace loading may keep going with unavailable proprietary dependencies such as `ControlLib`.
- Interactive editor requests may use cached bundles or local source snapshots instead of blocking on a full workspace reload.
- Dirty unsaved buffers can get syntax-only diagnostics without rebuilding the full semantic snapshot.
- Definition, completion, hover, references, and rename may upgrade local analysis to a source snapshot on demand.

---

## Common Tasks

### Parse A SattLine File

```python
from pathlib import Path
from sattlint.engine import parse_source_file

bp = parse_source_file(Path("path/to/Program.s"))
```

### Run Strict Single-File Validation

```bash
sattlint syntax-check path/to/Program.s
```

### Run Variable Analysis

```python
from sattlint.analyzers.variables import analyze_variables

report = analyze_variables(bp, debug=False)
print(report.summary())
```

### Generate Documentation

```python
from sattlint.config import get_documentation_config
from sattlint.docgenerator.docgen import generate_docx

generate_docx(bp, "output.docx", documentation_config=get_documentation_config())
```

### Run Tests From The Repo Venv

```powershell
& ".venv/Scripts/python.exe" -m pytest
```

### Trace A Concrete File

```bash
sattlint-trace path/to/Program.s
```

### Run The Dev-Analysis Pipeline

```bash
sattlint-analysis-pipeline
```

---

## Key File Map

### Core Application

- `src/sattlint/app.py`: CLI entry point and interactive menu.
- `src/sattlint/config.py`: persistent config, self-checks, analyzed-target validation.
- `src/sattlint/engine.py`: syntax validation, project loading, parser-core integration.
- `src/sattlint/cache.py`: AST caching.

### Shared Editor Semantics

- `src/sattlint/core/semantic.py`: workspace discovery, symbol lookup, snapshots.
- `src/sattlint/core/document.py`: shared document and offset helpers.
- `src/sattlint/editor_api.py`: compatibility facade.

### Parser Core

- `src/sattline_parser/api.py`: parser-core entry points.
- `src/sattline_parser/grammar/sattline.lark`: grammar definition.
- `src/sattline_parser/grammar/constants.py`: grammar constants.
- `src/sattline_parser/transformer/sl_transformer.py`: transformer implementation.
- `src/sattline_parser/models/ast_model.py`: AST node dataclasses.
- `src/sattline_parser/utils/text_processing.py`: comment stripping.
- `src/sattline_parser/utils/formatter.py`: AST formatting helpers.

### Analyzers And Reporting

- `src/sattlint/analyzers/variables.py`: variable-usage analyzer.
- `src/sattlint/analyzers/spec_compliance.py`: engineering-spec compliance checks.
- `src/sattlint/analyzers/shadowing.py`: shadowing analyzer.
- `src/sattlint/analyzers/mms.py`: MMS analysis.
- `src/sattlint/analyzers/comment_code.py`: commented-out code detection.
- `src/sattlint/reporting/variables_report.py`: variable report formatting.
- `src/sattlint/devtools/pipeline.py`: repeatable repo-audit pipeline.
- `src/sattlint/tracing.py`: parser and analyzer tracing.

### LSP

- `src/sattlint_lsp/document_state.py`: per-document text state and cached local analysis metadata.
- `src/sattlint_lsp/local_parser.py`: incremental parser backend.
- `src/sattlint_lsp/workspace_store.py`: cached workspace snapshots and invalidation.
- `src/sattlint_lsp/server.py`: Pygls language server.
- `vscode/sattline-vscode/extension.js`: VS Code client.
- `vscode/sattline-vscode/package.json`: extension metadata.

### Tests And Fixtures

- `tests/fixtures/sample_sattline_files/`: real SattLine examples.
- `tests/test_app.py`: interactive CLI coverage.
- `tests/test_editor_api.py`: editor-facing snapshot and lookup coverage.
- `tests/test_lsp_server.py`: LSP behavior and invalidation coverage.

### Reference Docs

- `sattline_language_reference.md`: language syntax and semantics.
- `sattline_graphics_reference.md`: graphics and interaction objects.
- `sattline_execution_reference.md`: execution model and scan groups.
- `sattline_system_procedures_reference.md`: system procedures and utility functions.
- `SattLineReferenceDocs/`: broader vendor and domain references.

---

## Practical Reminders

- Use the sample fixtures when unsure about real syntax.
- Use token constants rather than literal token strings when extending grammar or validation code.
- Keep analyzer changes aligned with existing framework and registry patterns.
- Preserve the distinction between strict single-file validation and dependency-aware workspace behavior.
- Restart the VS Code language server after LSP or client changes so on-disk code matches the live editor state.