
# SattLine Language – Condensed Technical Reference

## 1. Core Concepts

### 1.1 Modules
- Primary unit of structure and execution
- Can be hierarchical (modules contain sub-modules)
- A module type can have multiple module instances
- Contains:
  - Variable & parameter declarations
  - Equation blocks
  - Sequence blocks
  - Sub-modules
- Parameters connect modules together (actual variables, parameters, or literals)

#### Module Variants
- **Single Module**: one instance
- **Frame Module**:
  - No own variables or parameters
  - Uses enclosing module’s scope
  - Cannot be connected externally
  - Used for grouping / presentation

---

## 2. Variables & Parameters

### 2.1 Variables
- Explicit data type
- Always hold a valid value at runtime
- Attributes:
  - `State` (supports OLD/NEW semantics)
  - `Const` (initial value treated as constant)
  - `OpSave`, `Secure`
- Have name, type, initial value, optional description (≤140 chars)

### 2.2 Parameters
- Declared like variables inside module types
- Connected externally to:
  - Variables
  - Other parameters
  - Literals
- Direction rules apply when used in procedures (`in`, `out`, `in out`)

---

## 3. Data Types

### 3.1 Basic Types
- `boolean`, `integer`, `real`, `string`

### 3.2 Structured Types (Records)
- Aggregates of named components
- Components accessed via dot notation
- Can nest other structured types
- Max components: 65534 (simple components)

### 3.3 Literals
- **Boolean**: `True`, `False`, `on`, `off` (case-insensitive)
- **Integer**: decimal, `_` allowed, range ±2,147,483,647
- **Real**: must contain decimal point, optional exponent
- **String**:
  - `"..."`, doubled quotes escape quotes
  - Max length typically 140
- **Time**:
  - Format: `YYYY-MM-DD-hh:mm:ss.ttt`
  - Internally stored as days + milliseconds since `1979-12-31`

---

## 4. Identifiers
- Max length: 20 characters
- Letters, digits, `_`
- Must start with letter
- Case-insensitive
- Quoted identifiers (`'Name with space'`) allowed

---

## 5. Equation Blocks

### 5.1 Types
- Continuous equation blocks
- Start equation blocks
  - Name must start with `Start_`
  - Executed once after:
    - Program download
    - Initialize / cold start
    - Program structure change

### 5.2 Statements
- Assignment: `Variable = Expression;`
- Variable must be simple type or record component
- Integer → real auto-conversion allowed

### 5.3 If-statements
- Multiple branches
- First true condition executes
- Optional `ELSE`
- Only one branch executes

### 5.4 Procedures & Functions
- Procedure: standalone call
- Function: usable in expressions
- Parameter rules:
  - `in`: expression allowed for simple types
  - `out`, `in out`: must be variables
- `AnyType` allows generic procedures

---

## 6. Expressions

### 6.1 Operators (Priority High → Low)
1. `()`
2. Function calls
3. `* /`
4. `+ -`
5. Relational: `> < >= <= == <>`
6. `NOT`
7. `AND`
8. `OR`
9. `IF ... THEN` expressions

### 6.2 If-expressions
- Expression-level conditional
- All branches must return same type
- Integer + real → real

---

## 7. State Variables
- Declared with `State` attribute
- Accessed as:
  - `Var:OLD`
  - `Var:NEW`
- `NEW` updates immediately within cycle
- Used for edge detection and counters

---

## 8. Comments
- `(* ... *)`
- May be nested
- Treated as independent statements
- Any printable characters allowed

---

## 9. Execution Model

### 9.1 Sorting
- Equation blocks sorted by data dependency
- Ensures all variables updated once per cycle
- Active sequence statements participate in sorting
- Start equation blocks sorted separately

### 9.2 Program Loops
- Cross–equation-block loops detected
- Loops inside a block are not detected
- Execution continues with warning

---

## 10. Sequence Blocks (SFC-like)

### 10.1 Basics
- Graphical sequential control
- Steps + transitions
- Each step activates actions
- Steps execute until outgoing transition condition is true

### 10.2 Step Actions
- `enter` – once on activation
- `active` – continuously while active
- `exit` – once on deactivation

### 10.3 Auto-generated Step Variables
- `StepName.X` → boolean (active)
- `StepName.T` → integer ms since activation

---

## 11. Sequence Types
- **Sequence**: closed loop, restarts automatically
- **Open Sequence**: must exit via fork or reset

---

## 12. Structured Sequence Constructs

### 12.1 Parallel Branch
- Concurrent execution
- All branches must complete before continuation
- Starts/ends with steps

### 12.2 Alternative Branch
- Conditional selection
- Leftmost true condition chosen
- Starts/ends with transitions

### 12.3 Subsequence
- Collapsible group of sequence elements
- Logical grouping only

---

## 13. Non-Structured Constructs

### 13.1 Forks
- Jump from:
  - Step → Transition
  - Transition → Step
- Can cross sequences within same module
- Multiple forks allowed
- Higher priority than normal transitions
- Dangerous inside parallel branches
- Required to exit last step of open sequence

### 13.2 Sequence Break
- Disconnects normal flow
- Requires fork to continue
- Not allowed:
  - At end of subsequence
  - At end of parallel branch

---

## 14. Sequence Control Variables
Per sequence:
- `Sequence.Reset`
- `Sequence.Hold`
- `Sequence.Disable`

---

## 15. Transition Semantics

### 15.1 Activation Rules
- Transition fires if:
  - Condition true
  - All preceding steps active

### 15.2 Priority
1. Forks
2. Left-to-right structure order

### 15.3 No Avalanche Rule
- Only one transition per cycle
- Effects propagate before next evaluation

### 15.4 Execution Order (Same Cycle)
1. Exit-statements
2. Enter-statements
3. Active-statements

---

## 16. Strings

### 16.1 Types
- `IdentString`
- `TagString` (≤30 chars)
- `String`
- `LineString`
- `MaxString` (140 chars)

### 16.2 Properties
- Indexed from 1
- Current length tracked
- Current position tracked
- Writes beyond length fill with blanks

### 16.3 Status Parameter
- >0 success
- 0 pending
- <0 error (no side effects)

---

## 17. Library Handling
- Libraries contain module types
- Programs instantiate modules from directly linked libraries
- Sub-libraries cannot be instantiated directly

---

## 18. Linter-Relevant Constraints
- Multiple active steps in same sequence usually invalid
- Forks may introduce implicit parallelism
- Sorting order affects runtime semantics
- State variables can introduce hidden delays
- Const variables do not auto-update when initial value changes
- Dependency loops inside equation blocks are not detected
