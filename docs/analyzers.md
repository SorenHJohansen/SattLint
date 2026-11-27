# Analyzers

An analyzer is a self-contained check that receives one analysis context and
returns one report. The analyzer registry is the single catalog used by the
CLI, the interactive Analyze view, output formatting, and run history.

## Selection model

- There is no default analyzer set.
- A run selects analyzers with `--analyzer` or with the project's `analyzers`
  list.
- Selection is exact: the analyzers that run are exactly the ones selected.
- Nothing is added, dropped, reordered, or folded into another analyzer.
- Each analyzer is self-contained. It never requires another analyzer to have
  run first.

Use `sattlint analyzers list` to see the current keys, names, categories, and
scopes.

## Execution scope

| Scope | Meaning |
| --- | --- |
| Per target | Runs once for every loaded target, with that target's base picture and project graph. |
| Per run | Runs once for the whole run, independent of an individual target. |

Most analyzers are per target. ICF configuration is per run because it validates
every configured `.icf` file across the project.

## Categories

| Category | Meaning |
| --- | --- |
| `correctness` | A likely defect or an unreachable or inconsistent behavior. |
| `heuristic` | A design signal that needs judgment. |
| `style` | A complexity or readability threshold. |

The category is metadata, not a severity. A finding is a finding.

## Severity

Severity answers one question for CI: is this finding certain enough to fail a
build? It is assigned per finding kind, not from the analyzer category, because
one analyzer can report both defects and advice.

| Severity | Meaning | Fails |
| --- | --- | --- |
| `error` | A defect the tool can prove from the parsed structure, such as a read of an overwritten value or a broken SFC contract. | `--fail-on error` and `--fail-on warning` |
| `warning` | A risky pattern or a heuristic whose classification needs judgment. | `--fail-on warning` and `--fail-on any` |
| `info` | Naming, comment, complexity, or design advice. | `--fail-on any` only |

A finding whose kind has no specific severity uses its analyzer's default. An
analyzer outside the catalog falls back to `warning`.

| Analyzer | Default severity |
| --- | --- |
| `variables` | `warning` |
| `datatype-fields` | `warning` |
| `moduletype-usage` | `warning` |
| `module-layout` | `warning` |
| `picture-display-paths` | `warning` |
| `string-capacity` | `warning` |
| `string-style` | `info` |
| `icf` | `warning` |
| `sfc` | `warning` |
| `comment-code` | `info` |
| `alarm-integrity` | `warning` |
| `cyclomatic-complexity` | `info` |
| `same-cycle` | `warning` |
| `dataflow` | `warning` |

A proven defect, such as a read of an overwritten value or a broken SFC
contract, is `error`. An unused declaration or an uncertain heuristic is
`warning`. A magic number, commented-out code, or a complexity finding is
`info`. The exact severity is visible in the finding output.

The default threshold is `--fail-on any`, so existing pipelines keep their
behavior. A pipeline that wants correctness defects to fail while style advice
stays visible should use `--fail-on warning`, which fails on `warning` and
`error` findings and reports `info` findings without failing.

## Analyzer catalog

| Key | Name | Category | Scope |
| --- | --- | --- | --- |
| `variables` | Variable issues | correctness | per target |
| `datatype-fields` | Datatype field usage | correctness | per target |
| `moduletype-usage` | Module-type usage | correctness | per target |
| `module-layout` | Module layout | heuristic | per target |
| `picture-display-paths` | PictureDisplay paths | correctness | per target |
| `icf` | ICF configuration | correctness | per run |
| `sfc` | SFC checks | correctness | per target |
| `comment-code` | Commented-out code | correctness | per target |
| `alarm-integrity` | Alarm integrity | correctness | per target |
| `cyclomatic-complexity` | Cyclomatic complexity | style | per target |
| `same-cycle` | Same-cycle hazards | correctness | per target |
| `dataflow` | Dataflow | correctness | per target |
| `string-capacity` | String capacity | correctness | per target |
| `string-style` | String style | heuristic | per target |

## Variable issues

Key: `variables`

Checks every variable, datatype field, and input/output mapping in the project.
It reports, among other things:

- unused variables;
- read-only variables that are not declared constant;
- variables written but never read;
- writes whose value never reaches an output;
- implicit latches;
- reset contamination, including an OpSave value that a reset path clears;
- secure candidates: local numeric or boolean values written in a step and
  read by a transition guard, which a restart before that transition could lose;
- reads before a write or initialization in the same scope;
- ignored procedure-status outputs;
- shadowing between scopes;
- unsafe boolean defaults;
- globals that could be localized;
- hidden global coupling;
- high fan-in or fan-out;
- duplicated datatypes;
- Min/Max mapping mismatches;
- contract mismatches;
- string mapping mismatches;
- magic numbers;
- record component order dependence.

Reads in cyclic equation blocks are not reported as read-before-write because
the block runs every scan.

This analyzer builds the shared semantic foundation that other analyzers may
reuse within the same target run.

## String capacity

Key: `string-capacity`

Checks string values against the capacity of the datatype that stores them.

- A literal initializer or assignment is reported when it is longer than the
  declared capacity.
- An assignment from a variable is reported when that variable's value is a
  literal written earlier in the same module.
- A string procedure is reported when it writes more characters than the target
  can hold. The modelled procedures are `PutBlanks`, `InsertString`,
  `Concatenate`, `ExtractString`, `CopyString`, `CopyVariable`, `CopyVarNoSort`,
  and `IntegerToString`; each needs its length-determining arguments to be
  literals or known locals.

The analysis is deliberately literal-only. A value is known when it is a literal,
or when a local's writes in the same module are literals; nothing is carried
across a module boundary, a parameter mapping, or a branch, and there is no
fixed point. That keeps one module's cost proportional to its own statements.

Both checks stay inside the analyzed unit. The merged project view carries the
module types of every dependency library, and the analyzed tree instantiates
many of them, but a finding there would describe code this project does not
own. A module type outside the analyzed origin is therefore never walked.

The trade is worth knowing: a length that only a whole-program analysis could
know is not reported. For example, a value written in one module and read in
another, or a length that depends on a procedure's cursor arithmetic, is left
alone rather than guessed.

## String style

Key: `string-style`

Suggests a more precise string datatype or procedure. The analyzer is a
suggestion set and is selected separately from the capacity checks.

- A local string variable is reported when every literal it receives in its own
  module fits a smaller string datatype. A variable that receives a value the
  analysis cannot read is not suggested, because that value might not fit.
  Module parameters, root-level globals, constants, and record fields are not
  reported, because the caller or another unit may rely on the wider contract.
- Only the analyzed unit is checked: module types from dependency libraries are
  instantiated by the tree but their code is not reported.
- `CopyVariable` and `CopyVarNoSort` are reported when both operands are
  strings, with the matching string-specific procedure in the message.
  `CopyVariable` sorts like `CopyString`, but its third argument is a status
  output. `CopyString` takes a Boolean that selects case sensitivity instead, so
  the call's last argument has to be replaced as well. `CopyVarNoSort` matches
  `CopyStringNoSort` and only names the operands more precisely.

## Datatype field usage

Key: `datatype-fields`

Finds datatypes and record fields that no loaded unit consumes.

- An unused datatype has no declaration or field access anywhere in the scanned
  workspace.
- An unused field has no read or write. A field used by any instance, including
  a whole-record copy, is not reported.
- A field is never reported only because one module that holds the datatype
  leaves it untouched.

The finding says "no consumer in the scanned workspace". It does not claim the
field is dead outside the analyzed set.

This analyzer always loads the files that use the datatype, so it is slower
than a plain variable run. Select it deliberately.

## Module-type usage

Key: `moduletype-usage`

Finds module types with no consumer.

For a library target, the analyzer builds the reverse consumer closure: every
unit that imports the declaring unit, plus its consumers, transitively, across
the program, library, and ABB roots. One consumer suppresses the finding.

A type is reported only when no loaded unit invokes it outside its declaring
unit and the declaring unit has no consumer. Definitions marked private are
never reported. The message names the declaring unit.

This is a workspace-wide check and is selected deliberately.

## Module layout

Key: `module-layout`

Checks each module's clipping rectangle, its placement, and the objects drawn
inside it.

- An empty clipping rectangle has no area and is reported.
- A module's local origin must sit at the center of its clipping rectangle
  (bounds symmetric around zero) or at its bottom-left corner (bounds starting
  at zero). Any other origin position is reported.
- Clipping widths and heights must be multiples of the module's own grid,
  written as the `Grid` clause or taken from the configured default.
- A module's position and placed size must be aligned to the grid of the module
  that contains it.
- A graphics or interactor object that lies entirely outside its module's
  clipping rectangle is reported. An object that touches or crosses an edge is
  not reported, because only a fully hidden object is a defect.

Module types declared beside the analyzed unit are checked the same way. A
module type referenced from another library is not descended into; its own unit
owns those findings.

Geometry whose value comes from a variable input or a computed expression is
skipped rather than judged from its literal fallback value. That covers
clipping corners, invocation coordinates, and object coordinates. An output
binding or a literal-only tail leaves the written coordinate in place, so it is
still checked.

## PictureDisplay paths

Key: `picture-display-paths`

Checks that paths used by PictureDisplay buttons point to a real screen or
module.

The analyzer reports an unresolved display path when a path names a screen or
module that cannot be found in the project. External `.wmf` and `.emf` assets
are skipped silently because their content cannot be inspected.

Path literals are sized with the project's string capacities, so the same
capacities used by string validation also drive path resolution.

## ICF configuration

Key: `icf`

Validates every `.icf` connection file under the configured `icf_dir`. Each
entry links an external value to a path inside a program.

The analyzer reports:

- a program mismatch, where an entry points to the wrong program;
- an unresolved path, where the path does not exist in the program;
- an invalid field path, where a field in the path does not exist;
- a reference case mismatch;
- a unit tag mismatch;
- a group tag mismatch;
- a missing required journal identity field;
- unit structure drift;
- a value prefix inconsistency across lines;
- a referenced program that could not be loaded.

A file name is configuration, not program identity. A channel configuration can
reference several programs and share its name with none of them. Each referenced
program is loaded once per analysis session and reused when possible.

This analyzer runs once per run, not once per target.

## SFC checks

Key: `sfc`

Checks SFC sequences (step diagrams). It reports:

- a missing initial step at sequence start;
- an unreachable sequence node;
- an unreachable transition;
- a duplicate transition guard;
- a step or transition that forks back to itself or to the step it belongs to;
- a fork that targets an element in a different sequence.

The analyzer works from the parsed SFC structure, not from formatted text.

## Commented-out code

Key: `comment-code`

Reads source files and reports SattLine code hidden inside comments. It is a
correctness check for code that looks intentional but never executes.

## Alarm integrity

Key: `alarm-integrity`

Checks alarm blocks and alarm flag writes. It reports:

- duplicate alarm tags;
- duplicate alarm conditions;
- an alarm flag that is set but never cleared.

## Cyclomatic complexity

Key: `cyclomatic-complexity`

Counts how many different paths the logic can take. It reports:

- high module complexity, measured as the worst equation block or step rather
  than the sum of all nested scopes;
- high step complexity;
- high equation block complexity.

Thresholds come from the effective `[analysis]` settings.

## Same-cycle hazards

Key: `same-cycle`

Checks conflicting accesses to the same variable in explicit parallel sequence
branches. Shared access by ordinary modules alone is not reported.

It reports:

- a parallel read/write hazard, where one branch reads a variable another
  branch writes;
- a parallel write race, where two branches write the same variable.

## Dataflow

Key: `dataflow`

Follows variable values through the code step by step. It reports:

- a dead overwrite, where a write is replaced before the value is read;
- conflicting constant values on one path;
- a condition that is always true;
- a condition that is always false;
- an unreachable branch;
- a self-compare condition;
- a stale previous-scan read after a write in the current scan;
- an implicit current-value read that is missing its explicit current-value
  marker;
- a non-State variable written from several sites that can run in the same
  scan.

## Shared semantic artifacts

The `variables` analyzer builds a per-target foundation and collected views:
the type graph, symbol and datatype indices, root environment, access graph,
usage tracker, alias links, and effect-flow edges.

Other per-target analyzers such as `sfc` may reuse these memoized artifacts when
they run in the same batch. This is an optimization, not a contract:

- there is no declared `requires` relationship;
- no analyzer reads another analyzer's report;
- an analyzer that runs alone builds what it needs itself;
- shared state is read-only after construction.

## Reporting contract

Every analyzer returns a report with a summary and a list of issues. Reports are
normalized into one finding model with:

- a kind and human-readable label;
- a message;
- a module path;
- an optional rule identifier;
- an optional explanation and suggestion;
- structured data used by the results tree and JSON output.

Text and Markdown output use the human label. JSON and NDJSON keep the machine
fields needed by consumers.

## Adding a built-in analyzer

A built-in analyzer has three parts:

1. An analyzer module exposing a thin `analyze_*` entry point.
2. A declarative spec in the analyzer catalog with key, name, description,
   category, scope, and context inputs.
3. Delivery metadata that names its acceptance tests and shared artifacts.

Follow the surrounding package conventions:

- keep the public entry point thin;
- put implementation on a class or focused helper modules;
- use underscore-prefixed helper modules when a class spans files;
- read shared helpers before adding a new traversal or casefold comparison;
- keep analyzer-to-analyzer coupling out of the design;
- add a focused owner test and a regression fixture;
- update this page and the project analyzer list examples when the public
  surface changes.

## Adding a plugin analyzer

Third-party code can register an analyzer through the public developer API:

```python
from sattlint.analyzers.plugin import register_analyzer


@register_analyzer(
    key="my-check",
    name="My check",
    description="Reports a project-specific condition.",
)
def my_check(context):
    ...
    return report
```

Rules:

- the runnable receives the full analysis context;
- the key must not collide with a built-in analyzer or an existing plugin;
- registration should happen at import or startup time;
- the catalog is updated when the plugin registry changes;
- plugin analyzers are sorted by canonical key so order never depends on import
  order;
- a plugin report uses the same issue and finding model as a built-in analyzer.

## Related pages

- [Analysis pipeline](analysis-pipeline.md) for selection, execution, and
  finding normalization.
- [Resolution and semantics](resolution-and-semantics.md) for the shared
  semantic layer.
- [Development](development.md) for validation commands.
- [Testing](testing.md) for analyzer test placement.
