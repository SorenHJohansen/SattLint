# Resolution and Semantics

SattLint analyzers agree on one semantic view of a loaded project. That view is
built once from the parsed project and shared read-only. It provides canonical
symbols, record layouts, scopes, aliases, accesses, and call signatures.

## Semantic snapshot

`SemanticSnapshot` is the query facade built from a loaded project. It contains:

- the workspace root and entry file;
- the root base picture;
- the project graph;
- a canonical symbol table;
- a record type graph;
- a tuple of canonical symbol definitions;
- call signature occurrences;
- reference indexes used by editor-style queries.

It is immutable. Nested indexes are build artifacts that callers treat as
read-only after construction.

### Definitions and references

A `SymbolDefinition` records:

- the canonical path;
- the symbol kind;
- the datatype;
- the declaration module path;
- the display module path;
- an optional field path;
- the source file and library;
- the declaration span;
- the initializer;
- modifiers.

A `SymbolReference` records the canonical path and the source location of one
use. References are indexed by library-qualified source file and by definition
key.

### Queries

The snapshot supports:

- listing symbols by substring;
- finding definitions by canonical path or suffix;
- finding definitions at a source position;
- finding references to a definition or query;
- finding references at a source position;
- finding call signatures by name or source file;
- serializing the symbol state for invariant checks.

Lookups are case-insensitive because SattLine identifiers are case-insensitive.
Canonical paths use a normalized form so two spellings of the same symbol agree.

## Canonical paths

`resolution/paths.py` owns path helpers and `resolution/symbol_table.py` owns the
case-insensitive symbol table. A canonical path is the stable name of a symbol:
module path segments plus the variable or field path, normalized for case.

Two rules follow from this:

- a lookup by any case spelling resolves to the same definition;
- comparisons use `casefold`, never raw string equality.

## Record type graph

`TypeGraph` resolves record datatypes and their leaf fields. It indexes records
by `(library, name)` so two libraries can declare the same record name with
different layouts.

Resolution order for a lookup with a known library:

1. the exact `(library, name)` record;
2. the type graph's root library, meaning the library of the analyzed picture;
3. the sole remaining definition.

If a name is declared by several libraries and no library disambiguates it,
production code reports an undecidable name and treats the type as a leaf
instead of guessing a layout. The type graph also expands nested records into
leaf paths and detects cycles and unknown record names.

Built-in record specifications form a separate, library-agnostic tier that only
answers when no loaded library declares the name.

## Scope contexts

`ScopeContext` models one lexical scope:

- direct variable declarations;
- parameter mappings from a parameter name to its source variable and field
  prefix;
- the module path and display path;
- module-parameter keys;
- the current library;
- the parent scope;
- a small resolution cache.

`resolve_variable` reconstructs the full field path through a parameter
mapping. For example, a reference `signal.value` mapped to `Dv.I.WT001`
resolves to the source variable with the path `I.WT001.value`.

Resolution order:

1. a parameter mapping in the current scope;
2. a direct variable in the current scope;
3. an absolute module-path reference against the nearest matching ancestor;
4. the parent scope;
5. unresolved.

A separate nearest-declaration lookup walks scopes without following aliases.
That distinction matters when an analyzer needs the declaration a reference
actually names rather than the variable an alias eventually points to.

`resolve_global_name` searches declarations only, ignoring parameter mappings,
which is how an explicit global lookup behaves.

## Access graph

`AccessGraph` records canonical read and write events. It lets analyzers reason
about:

- which module read or wrote a symbol;
- whether an access is a read, a write, or both;
- the order of accesses within a scope.

The access graph is one of the collected views produced by the variable
analyzer and reused by derived analyzers.

## Call signatures

`resolution` and `core/call_signatures.py` record call sites with:

- the call name;
- the call kind;
- the module path;
- the source file and library;
- parameter information.

Call signatures let analyzers inspect connection semantics without re-walking
the AST.

## Origin matching

Every root program has an origin: the source file and library it was loaded
from. Origin matching answers whether a reference belongs to the analyzed root
or to a dependency.

This is how root-only analysis stays honest:

- a root-only check does not report a dependency's internal variable as if the
  analyzed program owned it;
- dependency modules are still available where a check needs workspace context,
  such as module-type usage and datatype-field usage.

Origin comparisons are case-insensitive and library-aware.

## Module-type resolution

Module-type definitions are keyed by library, name, and file. Resolution
prefers:

1. the exact definition in the current library and file;
2. the current library;
3. the remaining unambiguous definition.

A name declared by several libraries without a disambiguating context is
reported as ambiguous instead of silently selecting one.

## Datatype leaf indexing

The variable analyzer builds a compact prefix index over datatype leaf fields.
It normalizes a field path and answers membership questions without expanding a
record per query.

Leaf expansion uses an explicit policy:

- some types are intentionally opaque and stop as leaves without reporting;
- cycles, unknown records, and ambiguous records terminate at the current prefix;
- the result is always a set of leaf paths, even when the caller records a
  problem.

## Shared analysis artifacts

Per-target analyzers share an `AnalysisSharedArtifacts` holder. It contains:

- the variable-analysis foundation: type graph, indices, root environment,
  any-variable index;
- collected views: access graph, usage tracker, alias links, effect-flow
  edges, module contexts, typedef index;
- a local-variable environment cache;
- performance counters;
- the completed variable analyzer for the target.

The holder is opportunistic:

- only the variable analyzer builds the foundation;
- later analyzers may reuse it;
- an analyzer that runs alone builds what it needs;
- no analyzer reads another analyzer's report;
- shared state is never mutated after construction;
- it is scoped to one target, one run, and one parse, and is never persisted.

## Related pages

- [Project loading](project-loading.md)
- [Analysis pipeline](analysis-pipeline.md)
- [Analyzers](analyzers.md)
- [Architecture](architecture.md)
