# AGENTS.md - AI Assistant Context for SattLint

> This file provides context for AI assistants working with the SattLint codebase.
> SattLint is a Python-based static analyzer and documentation generator for SattLine,
> a proprietary PLC programming language developed by ABB for industrial automation.

---

## What is SattLine?

**SattLine** is a proprietary PLC (Programmable Logic Controller) programming language and runtime environment originally developed by Alfa Laval Automation, later acquired by ABB. It is used for industrial automation control systems in manufacturing, process industries, and batch control applications.

**Key Characteristics:**
- **Scan-based execution**: Programs run in continuous scan cycles, reading inputs, executing logic, and writing outputs
- **Hierarchical module structure**: Programs are organized as a tree of modules with BasePicture at the root
- **Graphical + Textual**: Supports both visual SFC (Sequential Function Chart) programming and textual equation blocks
- **Real-time control**: Designed for deterministic real-time control of industrial equipment

**File Mode Convention:**
- **Draft mode** (`.s`, `.l`): Work-in-progress files, can be edited freely
- **Official mode** (`.x`, `.z`): Frozen/approved files, changes require explicit version increment

**Example Programs:** See `tests/fixtures/sample_sattline_files/` for real examples:
- `LinterTestProgram.s` - Basic program with various variable usage patterns
- `BatchDemo.s` - Complex batch processing with multiple scangroups
- `SattLineFullGrammarTest.s` - Comprehensive grammar coverage examples

---

## Table of Contents

1. [What is SattLine?](#what-is-sattline)
2. [Project Overview](#project-overview)
3. [SattLine Language Fundamentals](#sattline-language-fundamentals)
4. [AST Architecture](#ast-architecture)
5. [Variable Analysis System](#variable-analysis-system)
6. [Code Patterns & Conventions](#code-patterns--conventions)
7. [Working with the Codebase](#working-with-the-codebase)
8. [Testing & Debugging](#testing--debugging)
9. [Key Files Reference](#key-files-reference)

---

## Project Overview

**SattLint** parses SattLine source files, builds an Abstract Syntax Tree (AST), resolves dependencies across library directories, and performs static analysis on variable usage.

### File Extensions

- `.s` / `.x` - Source files (draft / official mode)
  - **Draft mode** (`.s`): Work-in-progress, freely editable
  - **Official mode** (`.x`): Frozen/approved, changes require explicit version increment
- `.l` / `.z` - Library dependencies (draft / official mode)
- `.g` - Graphical representation files
- `.p` - Program files

### Core Workflow

1. **Parse**: Lark grammar (`grammar/sattline.lark`) → Parse tree
2. **Transform**: `SLTransformer` → AST objects (`models/ast_model.py`)
3. **Resolve**: Build unified `BasePicture` with all dependencies
4. **Analyze**: `VariablesAnalyzer` detects issues (unused vars, type mismatches, etc.)
5. **Report**: Generate findings or DOCX documentation

---

## SattLine Language Fundamentals

### Scan-Based Execution Model

SattLine programs run in a **continuous scan cycle**, which is fundamental to PLC programming:

1. **Read Inputs**: All input signals are read at the start of the scan
2. **Execute Logic**: Equation blocks and active sequence steps are evaluated
3. **Write Outputs**: All outputs are updated at the end of the scan
4. **Repeat**: The cycle repeats continuously (typically 10-1000ms per scan)

This deterministic execution means:
- Variables retain their values between scans
- State variables (`:OLD` / `:NEW`) can detect edge transitions
- Equations are continuously evaluated, not called once

### Minimal Example ("Hello World")

Here's a complete, minimal SattLine program:

```sattline
BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
LOCALVARIABLES
    Counter: integer := 0;
    Running: boolean := False;
ModuleCode
    EQUATIONBLOCK Main :
        Counter = Counter + 1;
        IF Counter > 100 THEN
            Counter = 0;
            Running = True;
        ENDIF;
    ENDDEF (*Main*);
ENDDEF (*BasePicture*);
```

### Module Hierarchy

SattLine programs are organized hierarchically:

```sattline
BasePicture              # Root container
├── ModuleTypeDefs       # Type definitions (reusable templates)
│   ├── DataType (Records)
│   └── ModuleTypeDefinitions
├── LocalVariables       # Global variables
└── Submodules           # Module instances
    ├── SingleModule     # Defined inline with MODULEDEFINITION
    ├── FrameModule      # Grouping container (no own vars)
    └── ModuleTypeInstance  # Instance of a ModuleTypeDef
```

### Variables

Variables have attributes and are declared in groups:

```sattline
LOCALVARIABLES
    Var1, Var2 "description": integer := 10;           # Basic declaration
    GlobalVar: GLOBAL boolean;                         # Global scope
    ConstVar: CONST integer := 5;                      # Constant (read-only)
    StateVar: STATE real;                              # Supports OLD/NEW
    SecureVar: SECURE string;                          # Protected value
    OpSaveVar: OPSAVE boolean := True;                 # Operator-saveable
```

**Key Variable Attributes:**
- `State` - Access via `Var:OLD` or `Var:NEW` for edge detection
- `Const` - Value set at initialization, never changes
- `Global` - Accessible across module boundaries
- `OpSave` - Value preserved across operator stations
- `Secure` - Protected from unauthorized modification

### Data Types (Records)

Structured types defined with RECORD:

```sattline
TYPEDEFINITIONS
    MyRecord = RECORD DateCode_ 12345
        Field1: integer := 0;
        Field2: string := "default";
        Nested: AnotherRecord;                        # Nested records allowed
    ENDDEF (*MyRecord*);
```

Access via dot notation: `MyVar.Field1`, `MyVar.Nested.Field2`

### Equation Blocks

Continuous logic executed every scan cycle:

```sattline
EQUATIONBLOCK Main COORD -0.9, 0.06 OBJSIZE 0.82, 0.72 :
    Output = Input * Gain + Offset;                    # Assignment
    
    IF Condition THEN                                  # If-statement
        Value = 1;
    ELSIF OtherCondition THEN
        Value = 2;
    ELSE
        Value = 0;
    ENDIF;
    
    Result = IF Cond THEN 1 ELSE 0 ENDIF;              # Ternary expression
    
    CopyVariable(Source, Destination, Status);         # Procedure call
    IsEqual = Equal(A, B);                             # Function call
ENDDEF (*Main*);
```

### Sequence Blocks (SFC - Sequential Function Chart)

Graphical sequential control with steps and transitions:

```sattline
SEQUENCE MySeq (SeqControl, SeqTimer)
    InitStep Start                                     # Initial step (executes first)
        Enter:
            Counter = 0;
        Active:
            Running = True;
        Exit:
            Log("Starting");
    
    Transition                                          # Condition to proceed
        WAIT_FOR StartCondition;
    
    Step Processing                                     # Normal step
        Active:
            DoWork();
    
    ALTERNATIVESEQ                                      # Conditional branch
        Transition WAIT_FOR ConditionA;
        Step PathA
        ALTERNATIVEBRANCH
        Transition WAIT_FOR ConditionB;
        Step PathB
    ENDALTERNATIVE;
    
    PARALLELSEQ                                         # Parallel execution
        Step Branch1
        PARALLELBRANCH
        Step Branch2
    ENDPARALLEL;
    
    Fork JumpToOtherTransition;                         # Jump (dangerous)
    Break;                                              # Stop normal flow
ENDSEQUENCE;
```

**SFC Auto-generated Variables:**
- `StepName.X` - Boolean, true when step is active
- `StepName.T` - Integer, milliseconds since activation

### Comments

```sattline
(* This is a comment
   (* Comments can be nested *)
   And span multiple lines *)
```

### Parameter Mappings

When instantiating modules, parameters are connected via `=>`:

```sattline
SUBMODULES
    MyInstance Invocation (0.0, 0.0, 0.0, 1.0, 1.0) : ModuleType (
        Param1 => SourceVar,                           # Map to variable
        Param2 => GLOBAL GlobalVar,                    # Map to global
        Param3 => 42                                   # Map to literal
    );
```

### Graphics and Interaction Objects

SattLine includes a rich graphics system for operator interfaces (HMI). See `sattline_graphics_reference.md` for complete details.

**Key Concepts:**
- **ModuleDef** - Graphical definition with clipping bounds, zoom limits, grid settings
- **GraphObjects** - Visual primitives (Rectangle, Line, Oval, Polygon, Text)
- **InteractObjects** - Operator controls (buttons, checkboxes, text editors)
- **Animation** - Variables can drive position, rotation, scaling, color

**Graphical Elements in Source Files:**
```sattline
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ZoomLimits = 0.0 0.01
    Zoomable
    GraphObjects :
        RectangleObject ( -1.0 , 1.0 ) ( 1.0 , -1.0 ) 
            OutlineColour : Colour0 = 5
        TextObject ( 0.12 , -0.04 ) ( 0.12 , -0.2 ) 
            "Label" VarName Width_ = 5
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 0.1 , 0.05 )
            Enable_ = True : InVar_ "ButtonVar"
ENDDEF (*ModuleName*);
```

**Important:** The parser extracts graphical information but static analysis focuses on variable usage within code blocks.

---

## AST Architecture

### Core AST Classes

All defined in `src/sattlint/models/ast_model.py`:

#### BasePicture
The root container aggregating all parsed content:

```python
@dataclass
class BasePicture:
    header: ModuleHeader
    name: str = "BasePicture"
    datatype_defs: list[DataType]           # Record definitions
    moduletype_defs: list[ModuleTypeDef]    # Module type definitions
    localvariables: list[Variable]          # Global variables
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance]
    moduledef: ModuleDef | None             # Graphical definition
    modulecode: ModuleCode | None           # Sequences and equations
    library_dependencies: dict[str, list[str]]  # Lib dependency graph
```

#### Variable
Central to analysis, tracks usage:

```python
@dataclass
class Variable:
    name: str
    datatype: Simple_DataType | str         # Built-in or record name
    global_var: bool = False
    const: bool = False
    state: bool = False
    opsave: bool = False
    secure: bool = False
    init_value: Any = None
    description: str = None
    # Usage tracking (populated during analysis)
    read: bool = False
    written: bool = False
    usage_locations: list[tuple[list[str], str]]  # [(path, kind), ...]
    field_reads: dict[str, list[list[str]]]       # Field-level reads
    field_writes: dict[str, list[list[str]]]      # Field-level writes
```

#### Module Types

```python
# Inline module definition
@dataclass
class SingleModule:
    header: ModuleHeader
    moduleparameters: list[Variable]
    localvariables: list[Variable]
    submodules: list[...]                   # Can be nested
    modulecode: ModuleCode | None
    parametermappings: list[ParameterMapping]

# Reference to a ModuleTypeDef
@dataclass
class ModuleTypeInstance:
    header: ModuleHeader
    moduletype_name: str
    parametermappings: list[ParameterMapping]

# Type template (reusable definition)
@dataclass
class ModuleTypeDef:
    name: str
    moduleparameters: list[Variable]
    localvariables: list[Variable]
    submodules: list[...]
    modulecode: ModuleCode | None
```

#### ModuleCode

```python
@dataclass
class ModuleCode:
    sequences: list[Sequence]               # SFC blocks
    equations: list[Equation]               # Equation blocks

@dataclass
class Sequence:
    name: str
    type: str                               # "sequence" or "opensequence"
    code: list[SFCStep | SFCTransition | SFCAlternative | ...]

@dataclass  
class Equation:
    name: str
    code: list[Any]                         # Statements/expressions
```

#### SFC Nodes

```python
@dataclass
class SFCStep:
    kind: str                               # "init" or "step"
    name: str
    code: SFCCodeBlocks                     # enter, active, exit

@dataclass
class SFCTransition:
    name: str | None
    condition: Any                          # Expression

@dataclass
class SFCAlternative:
    branches: list[list[Any]]               # Each branch is list of nodes

@dataclass
class SFCParallel:
    branches: list[list[Any]]

@dataclass
class SFCFork:
    target: str                             # Jump target

@dataclass
class SFCBreak:
    pass                                    # Stops sequence flow
```

### Expression Representation

Expressions are stored as nested tuples for easy traversal:

```python
# Assignment: Target = Value
('assign', {'var_name': 'Output'}, ('mul', Left, [(op, Right), ...]))

# If statement: IF Cond THEN ... ELSIF ... ELSE ... ENDIF
('IF', [(cond1, [stmts1...]), (cond2, [stmts2...])], else_stmts)

# Comparison: A > B
('compare', left_expr, [('>', right_expr)])

# Boolean operators
('OR', [expr1, expr2, ...])
('AND', [expr1, expr2, ...])
('NOT', expr)

# Arithmetic
('add', left, [('+', right1), ('-', right2), ...])
('mul', left, [('*', right1), ('/', right2), ...])

# Function/procedure calls
('FunctionCall', 'FunctionName', [arg1, arg2, ...])

# Variable reference with optional field path and OLD/NEW
{'var_name': 'VarName.Field:OLD'}
```

### Grammar to AST Pipeline

1. **Grammar** (`grammar/sattline.lark`):
   - Lark grammar defining SattLine syntax
   - Uses placeholders like `{GRAMMAR_VALUE_IF}` resolved at runtime
   - Handles nested expressions with proper operator precedence

2. **Transformer** (`transformer/sl_transformer.py`):
   - `SLTransformer` extends Lark's `Transformer`
   - Methods named after grammar rules convert trees to AST objects
   - Uses `_flatten_items()` to unwrap nested structures
   - Builds `ParameterMapping` objects for `=>` connections

3. **Engine** (`engine.py`):
   - `create_parser()` - Loads grammar, creates Lark parser
   - `parse_file()` - Parses single file to `BasePicture`
   - `load_project()` - Recursively resolves dependencies
   - `merge_basepictures()` - Combines multiple files into unified AST

---

## Variable Analysis System

### Scope Context

The `VariablesAnalyzer` maintains scope as it traverses the module hierarchy:

```python
@dataclass
class ScopeContext:
    env: dict[str, Variable]               # Variables declared in this scope
    param_mappings: dict[str, tuple[       # Parameter => Source mappings
        Variable,                           # Source variable
        str,                                # Field prefix
        list[str],                          # Source declaration module path
        list[str]                           # Source display path
    ]]
    module_path: list[str]                 # Current location in hierarchy
    display_module_path: list[str]
    parent_context: ScopeContext | None    # Parent scope for lookups
```

### Analysis Process

1. **Build Symbol Tables**: Register all variables and their locations
2. **Track Accesses**: Mark variables as read/written when encountered
3. **Resolve Mappings**: Follow parameter mappings to track field-level usage
4. **Build Alias Links**: Connect source variables to parameter usages
5. **Generate Issues**: Report problems found

### Issue Types

```python
class IssueKind(Enum):
    UNUSED = "unused"                           # Never read or written
    READ_ONLY_NON_CONST = "read_only_non_const" # Read but not written, should be CONST
    NEVER_READ = "never_read"                   # Written but never read
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"  # String param mapped to non-string
    DATATYPE_DUPLICATION = "datatype_duplication"        # Same complex type defined multiple times
```

### Field-Level Tracking

When a record variable is mapped to a parameter:

```sattline
# Source module has:
MessageSetup: MessageType;  # Record with fields AckText, Priority, etc.

# Submodule mapping:
OpMessage => MessageSetup   # Maps entire record

# In submodule, accessing:
OpMessage.AckText           # Accesses MessageSetup.AckText
```

The analyzer:
1. Creates an alias link: `MessageSetup -> OpMessage` with prefix ""
2. When `OpMessage.AckText` is accessed, marks `MessageSetup.AckText` as read
3. Accumulates prefixes through nested mappings

### Key Analyzer Methods

- `analyze_variables(bp)` - Main entry, returns `VariablesReport`
- `analyze_mms_interface_variables(bp)` - Find MMS communication mappings
- `analyze_module_localvar_fields(bp, path, var_name)` - Deep field analysis
- `debug_variable_usage(bp, var_name)` - Show all usages of a variable

---

## Code Patterns & Conventions

### Good Patterns

**Use CONST for read-only values:**
```sattline
# Good
MaxRetries: CONST integer := 5;

# Bad (linter will flag)
MaxRetries: integer := 5;  # Never written, should be CONST
```

**Initialize state variables:**
```sattline
Counter: STATE integer := 0;  # Clear initial value
```

**Use descriptive variable names (max 20 chars):**
```sattline
TankLevelHigh: boolean;  # Good
TLH: boolean;            # Too abbreviated
```

**Clean up unused variables:**
```sattline
# Remove variables that are never accessed
TempUnused: integer;  # Linter will flag this
```

### Common Anti-Patterns (Linter Catches These)

**Unused variables:**
```sattline
LOCALVARIABLES
    UsedVar, UnusedVar: boolean;  # UnusedVar will be flagged
```

**Read-only non-CONST:**
```sattline
ConfigValue: integer := 10;  # Never written after init, should be CONST
```

**Write-only variables:**
```sattline
DebugOutput: string;  # Written but never read (dead code)
```

**String type mismatches in mappings:**
```sattline
# Source module:
NumericCode: integer;

# Submodule mapping (bad):
StringParam => NumericCode  # String parameter mapped to integer variable
```

**Duplicated complex datatypes:**
```sattline
# Multiple modules defining the same record structure
# Instead, define once in a library and reuse
```

### State Variable Usage

```sattline
Trigger: STATE boolean;

# In equation block:
IF Trigger:OLD = False AND Trigger:NEW = True THEN
    RisingEdgeDetected = True;  # Detect rising edge
ENDIF;
```

### Built-in Functions

Common SattLine functions (defined in `analyzers/sattline_builtins.py`):

```python
# Comparison
Equal(A, B) -> boolean

# Variable operations  
CopyVariable(Source, Destination, Status)

# String operations
StringLength(Str) -> integer
StringConcat(A, B, Result, Status)

# Type conversions
RealToInteger(R, I, Status)
IntegerToReal(I, R)

# See sattline_builtins.py for complete list
```

---

## Working with the Codebase

### Adding a New Analyzer

1. **Create analyzer file** (e.g., `analyzers/my_analyzer.py`):

```python
from ..models.ast_model import BasePicture, Variable, SingleModule
from dataclasses import dataclass
from enum import Enum

class MyIssueKind(Enum):
    MY_ISSUE = "my_issue"

@dataclass
class MyIssue:
    kind: MyIssueKind
    module_path: list[str]
    message: str

@dataclass
class MyReport:
    issues: list[MyIssue]
    
    def summary(self) -> str:
        return f"Found {len(self.issues)} issues"

def analyze_something(base_picture: BasePicture) -> MyReport:
    issues = []
    # Walk the AST and collect issues
    return MyReport(issues=issues)
```

2. **Integrate in app.py** - Add menu option to run the analyzer
3. **Add tests** in `tests/test_analyzers.py`

### Extending the Grammar

1. **Add rule to `grammar/sattline.lark`**:

```lark
new_construct: NEW_KEYWORD some_argument
NEW_KEYWORD.10: "{GRAMMAR_VALUE_NEW_KEYWORD}"
```

2. **Add constant to `grammar/constants.py`**:

```python
GRAMMAR_VALUE_NEW_KEYWORD = "NewKeyword"
TREE_TAG_NEW_CONSTRUCT = "new_construct"
```

3. **Add transformer method** in `transformer/sl_transformer.py`:

```python
def new_construct(self, items):
    # Transform parse tree items to AST
    return NewConstructNode(args)
```

4. **Update AST model** if needed in `models/ast_model.py`

### Adding Tests

```python
# tests/test_my_feature.py
import pytest
from sattlint.engine import parse_text
from sattlint.analyzers.my_analyzer import analyze_something

def test_my_analyzer():
    code = '''
    BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123
    LOCALVARIABLES
        TestVar: boolean;
    ModuleCode
        EQUATIONBLOCK Main :
            TestVar = True;
        ENDDEF (*Main*);
    ENDDEF (*BasePicture*);
    '''
    bp = parse_text(code)
    report = analyze_something(bp)
    assert len(report.issues) == 0
```

---

## Testing & Debugging

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_analyzers.py

# With debug output
pytest -v --tb=short

# Specific test
pytest tests/test_analyzers.py::test_variable_usage -v
```

### Debug Mode

Enable debug logging to see detailed trace:

```python
# In code
analyzer = VariablesAnalyzer(bp, debug=True)

# Or set environment variable
DEBUG=1 sattlint
```

Debug output includes:
- File discovery and loading
- Parse tree structure
- Variable access tracking
- Parameter mapping resolution
- Alias link creation

### Common Debugging Scenarios

**Parse Error:**
- Check `grammar/sattline.lark` for correct syntax rules
- Verify transformer handles all grammar branches
- Look at test fixtures for valid syntax examples

**Variable Not Found:**
- Check scope resolution in `variables.py`
- Verify parameter mappings are correctly parsed
- Use `debug_variable_usage(bp, "VarName")` to trace

**False Positive in Analysis:**
- Check if variable is accessed through parameter mapping
- Verify alias links are created correctly
- Review field path reconstruction logic

### Useful Debug Functions

```python
from sattlint.analyzers.variables import (
    debug_variable_usage,
    analyze_datatype_usage,
    analyze_module_localvar_fields
)

# Show all usages of a specific variable
print(debug_variable_usage(bp, "MyVariable"))

# Analyze field-level usage for a record variable
print(analyze_datatype_usage(bp, "MyRecordVar"))

# Deep analysis of a local variable within a module
print(analyze_module_localvar_fields(bp, "BasePicture.Module1", "LocalVar"))
```

---

## Key Files Reference

### Core Source Files

| File | Purpose |
|------|---------|
| `src/sattlint/app.py` | CLI entry point, interactive menu |
| `src/sattlint/engine.py` | Parser creation, project loading, BasePicture merging |
| `src/sattlint/cache.py` | AST caching for faster reloads |
| `src/sattlint/grammar/sattline.lark` | Lark grammar definition |
| `src/sattlint/grammar/constants.py` | Grammar constants and tree tag keys |
| `src/sattlint/transformer/sl_transformer.py` | Lark Transformer → AST objects |
| `src/sattlint/models/ast_model.py` | AST node dataclasses |
| `src/sattlint/models/project_graph.py` | Project dependency graph |

### Analysis

| File | Purpose |
|------|---------|
| `src/sattlint/analyzers/variables.py` | Variable usage analyzer (main analysis) |
| `src/sattlint/analyzers/modules.py` | Module structure analyzer |
| `src/sattlint/analyzers/sattline_builtins.py` | Built-in function signatures |
| `src/sattlint/resolution/symbol_table.py` | Symbol table management |
| `src/sattlint/resolution/type_graph.py` | Type dependency tracking |
| `src/sattlint/resolution/access_graph.py` | Variable access tracking |

### Documentation Generation

| File | Purpose |
|------|---------|
| `src/sattlint/docgenerator/docgen.py` | Word document (.docx) generator |
| `src/sattlint/docgenerator/configgen.py` | Excel configuration generator |

### Tests & Examples

| Path | Contents |
|------|----------|
| `tests/fixtures/sample_sattline_files/` | Real SattLine code examples |
| `tests/fixtures/sample_sattline_files/LinterTestProgram.s` | Comprehensive test program |
| `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s` | Grammar coverage test |
| `tests/fixtures/sample_sattline_files/BatchDemo.s` | Complex batch processing example |

### Reference Documentation

| File | Contents |
|------|----------|
| `sattline_language_reference.md` | Complete language syntax and semantics reference |
| `sattline_graphics_reference.md` | Graphics, interaction objects, and window management |
| `sattline_execution_reference.md` | Scan groups, execution order, and runtime behavior |
| `sattline_hardware_reference.md` | Control systems, I/O systems, and hardware configuration |
| `sattline_system_procedures_reference.md` | System procedures, string handling, timers, and utility functions |
| `sattline_data_acquisition_reference.md` | Journals, history logging, and data storage |
| `sattline_batch_control_reference.md` | S88.01 batch control, BatchLib modules, and recipe management |
| `sattline_controllers_analog_reference.md` | PID controllers, analog signals, and control loop components |
| `sattline_alarms_events_reference.md` | Event detection, alarm handling, and EventLib modules |
| `sattline_io_communication_reference.md` | I/O connection, MMS, COMLI, and network communication |

**Important Notes:**

- **Graphics reference** covers module visualization, graphical objects, interaction objects, composite objects, and animation

- **Execution reference** covers scan groups (Fast/Normal/Slow/Manual), cycle time, priority, phase, and execution order sorting

- **System procedures** include: String handling (ClearString, StringLength, Concatenate), Timers (StartTimer, StopTimer, TimerExpired), ACOF valve supervision (Acof1-Acof9), and variable operations (CopyVariable, Equal)

- **Data acquisition** covers journal operations (JouCreate, JouWriteEntry, JouReadEntry), history logging, and data storage

- **Batch control** follows S88.01 standard with Process Cell → Unit → Equipment Module → Control Module hierarchy, RecipeManagerMaster, ProcessManagerMaster, and Unit Supervisor modules

- **Controllers** include RealSignal data type, AnalogInRealS, FilterRealS, PID controllers, and mathematical operations

- **Alarms/Events** use EventDetector modules, severity levels (1-8), classes (1-16), and EventLib for presentation and logging

- **I/O & Communication** covers I/O addressing (bus.node.module.channel), MMS protocol, COMLI protocol, and network routing

---

## Quick Reference: Common Tasks

### Parse a SattLine file

```python
from sattlint.engine import create_parser, parse_file

parser = create_parser()
bp = parse_file(parser, "path/to/Program.s")
```

### Run variable analysis

```python
from sattlint.analyzers.variables import analyze_variables

report = analyze_variables(bp, debug=False)
print(report.summary())
```

### Find all MMS interface mappings

```python
from sattlint.analyzers.variables import analyze_mms_interface_variables

mms_report = analyze_mms_interface_variables(bp)
print(mms_report.summary())
```

### Generate documentation

```python
from sattlint.docgenerator.docgen import generate_docx

generate_docx(bp, "output.docx")
```

### Walk the module hierarchy

```python
def walk_modules(modules, path=None):
    if path is None:
        path = []
    for mod in modules or []:
        current_path = path + [mod.header.name]
        print(f"{' -> '.join(current_path)}: {type(mod).__name__}")
        if hasattr(mod, 'submodules'):
            walk_modules(mod.submodules, current_path)

walk_modules(bp.submodules, [bp.header.name])
```

---

## Tips for AI Assistants

1. **Always refer to test fixtures** when unsure about syntax - they contain real working examples
2. **Use the AST model classes** defined in `ast_model.py` - they have helpful `__str__` methods for debugging
3. **Check for field-level access** - SattLine heavily uses record types with dot notation
4. **Respect parameter mappings** - Variables are often accessed indirectly through `=>` connections
5. **Consider case-insensitivity** - SattLine identifiers are case-insensitive (compare with `.casefold()`)
6. **Understand the scope hierarchy** - Variables can be accessed from parent scopes unless shadowed
7. **Look at existing analyzers** - Follow the pattern in `variables.py` for new analysis features
8. **Test with the fixtures** - The test files in `tests/fixtures/` cover most language features

---

*Last updated: 2026-02-11*
*For questions about SattLine syntax, see `sattline_language_reference.md`*
