# Glossary

## SattLine terms

**Base picture**
The root program or library unit that SattLint loads for a target. It contains
the unit header, modules, datatype definitions, module-type definitions, and
sequences.

**Draft mode**
Load mode that resolves draft source files. The opposite is official mode.

**Equation block**
A block of cyclic logic that runs every scan. Reads inside a cyclic block are
not reported as read-before-write because the block repeats.

**Graphics companion**
A sidecar file that describes graphics for a program or library, including
bindings and PictureDisplay records.

**ICF file**
A connection configuration file that links external values to paths inside
programs. ICF files are validated by the ICF configuration analyzer.

**Library**
A reusable unit that programs import. SattLint distinguishes the primary program
root, the ABB library root, and additional library roots.

**Mode**
The file variant the loader resolves: `official` or `draft`.

**Module type**
A reusable module definition that can be instantiated inside programs and other
modules.

**Official mode**
Load mode that resolves official source files. The opposite is draft mode.

**PictureDisplay path**
A path used by a graphics button to open a screen or module. SattLint validates
that the path resolves inside the project and that literal assets exist where
expected.

**Program**
A top-level SattLine unit that can be analyzed as a target.

**Record datatype**
A composite datatype with fields. Record layouts resolve per library so two
libraries can define the same record name with different fields.

**SFC**
Sequential function chart. A sequence of steps and transitions. SattLint checks
initial steps, reachability, and transition guards.

**String capacity**
The configured maximum size of a SattLine string datatype. Capacities are part
of the project file and drive inference, validation, path resolution, and cache
invalidation.

**Target**
A configured program or library name that an analysis loads. Names are bare unit
names with no file extension.

**Transition**
A condition that moves an SFC from one step to another.

## SattLint terms

**Analysis context**
The typed input passed to one analyzer for one target. It carries the loaded
project, configuration, debug state, string capacities, loaders, and shared
artifacts.

**Analysis report cache**
A cache of one analyzer report per target and analyzer. Its key covers the
project, the analyzer, the analyzer behavior version, and analyzer settings.

**Analyzer**
A self-contained check that receives an analysis context and returns a report.

**Analyzer catalog**
The registry of selectable analyzers. The CLI, UI, reporting, and run history
read from it.

**AST cache**
A cache of a parsed project graph for one target, validated against a manifest
of the files that contributed to the load.

**Change Review**
A semantic comparison of an official and a draft project version that produces
JSON and Markdown artifacts with changes, context blocks, and variable
definitions.

**Finding**
One normalized issue from an analyzer. It has a kind, message, module path,
optional rule identifier, optional explanation and suggestion, and structured
data.

**Finding ID**
A stable hash that identifies one finding across runs.

**Per-run analyzer**
An analyzer that runs once for the whole analysis run instead of once per
target. ICF configuration is per run.

**Per-target analyzer**
An analyzer that runs once for every loaded target.

**Project file**
A `.slproj` TOML file that describes one analysis project.

**Project graph**
The analysis index built from a loaded project. It holds parsed pictures, type
definitions, source files, failures, warnings, graphics attachments, and cache
metadata.

**Report cache**
See analysis report cache.

**Run history**
Stored records of completed analyses, used by `findings`, `show`, and the
Results view.

**Semantic snapshot**
The immutable query facade over a loaded project: symbols, references, type
graph, and call signatures.

**Shared artifacts**
Per-target semantic state built once and reused read-only by analyzers in the
same batch. It is an optimization, not a dependency contract.

**String inference**
The exact-string engine that sizes literals, copies, concatenations, and
built-in string operations against the configured capacities.

**Target view**
The root base picture with the loaded module-type and datatype definitions
merged in, as analyzers receive it.

**Type graph**
The case-insensitive graph of record datatypes and their leaf fields, keyed by
library and name.
