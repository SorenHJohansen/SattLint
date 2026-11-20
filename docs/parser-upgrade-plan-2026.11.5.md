> Historical migration plan. SattLint 2026.11.5 completed the parser 2026.11.5
> upgrade; follow-up work is tracked separately.

# SattLint parser upgrade plan: 2026.11.5

Status: implemented on `feature/parser-2026.11.5`.
Target parser: `sattline-parser==2026.11.5`
SattLint release: 2026.11.5, pinned to `sattline-parser==2026.11.5`

## Why this needed its own branch

`2026.11.5` is a breaking release. It renames a core datatype enum, changes the
module layout fields from lists to singular fields, removes the interim graphics
payload classes, and removes lenient project loading. The upgrade could not land
on `main` until the analyzer and project suites were green against the new pin.

## What changed in the parser

- `Simple_DataType` is now `ScalarDatatype` in `sattline_parser.ast` and
  `sattline_parser.types`.
- `BasePicture`, `FrameModule`, `SingleModule`, and `ModuleTypeDef` store
  `moduledef` and `modulecode` instead of `moduledefs` and `modulecodes`.
- `ModuleTypeDef.parametermappings`, `BasePicture.graphics_file`, and
  `FlagClause.extra` are removed.
- The interim graphics payload classes (`ClipValue`, `CommonProperties`,
  `CoordinateClipping`, `Grid`, `ModuleOptions`, `SeqLayers`, `TwoLayers`,
  `Zoomable`) are no longer exported from `sattline_parser.ast`.
- A parser diagnostic is never tentative, and the load-skipped and
  dependency-cycle load diagnostic kinds are removed.
- `SattLineProject.load` no longer takes `strict`, and a load returns a complete
  closure or raises a `ProjectLoadError` subclass. A missing body, unreadable
  sidecar, malformed companion, parse failure, dependency cycle, or module type
  that instantiates itself is fatal.
- `ProjectLookup.find` and its helpers no longer take `requester_dir`, and
  companions never resolve through the ordered roots.
- `SattLineProject.cycles()` is empty for a loaded project; cycles arrive as
  `DependencyCycleError` and `ModuleTypeCycleError`.
- Dependency names are validated as identifiers of at most 20 characters.

## What SattLint changed

- `src/sattlint/parser_api.py` re-exports `ScalarDatatype`, the load error
  types, and no longer re-exports the removed payload classes.
- The rename covers 109 occurrences in 19 source files and 839 in 70 test files.
- Fixtures build `moduledef=` and `modulecode=` instead of the list fields, and
  a `ModuleTypeDef` fixture no longer passes a mapping list.
- The variables analyzer no longer checks parameter mappings on a module type
  definition. The grammar has no mapping list there, so those two loops could
  never have run on a parsed program.
- `load_parser_project` drops `strict`, and its single-target memo key partitions
  on the validation scope only.
- `_load_project` translates parser cycle errors into `CircularDependencyError`.
  A directly built project keeps the `cycles()` guard in
  `convert_project_into_graph`.
- `iter_loaded_projects`, the AST cache rebuild, and the AST refresh loop catch
  `ProjectLoadError`, so a failed target is reported and the run continues.
- A reverse-library consumer batch falls back to one load per consumer when the
  batch cannot load, so one broken consumer no longer discards the selected
  library's analysis. The consumer is recorded as a graph failure instead.
- The ICF analyzer catches `ProjectLoadError` and reports a load-failure issue
  instead of raising.
- Every cache version is bumped, because the pickled model changes shape with
  the datatype rename and the singular layout fields. An entry written under
  2026.11.4 is rejected instead of being decoded into the new model.
- Strict validation raises on the first diagnostic. There is no tentative path,
  so the warning sink and the per-result validation warnings are gone.
- `cache_manifest_files` and the reverse-consumer scan resolve a sidecar by name
  only, which matches the parser's ordered lookup.
- The parser rule for an unknown parameter mapping target is suppressed at load
  because the variables analyzer reports the same fact and still needs the root
  indexed.
- Four fixtures whose names exceeded the 20 character unit limit were renamed:
  `CyclomaticHigh`, `TestStringsDisplay`, `ModuleStructIssues`, and
  `SequenceLifetime`.

## Evidence

- `python -m ruff check .`, `ruff format --check .`, and
  `pyright src/sattlint tests` are clean.
- `python -m pytest -q` passes: 1156 tests.
- The two configured library targets load through SattLint with the same closure
  size as under 2026.11.4: 36 and 38 units, with no missing entries. Every
  remaining warning is a pre-existing graphics validation notice about `.emf`
  and `.wmf` resolution.
- The analyzer corpus manifests pass under 2026.11.5. Only that family runs
  today: the workspace, semantic, valid, and edge manifests are checked for
  schema, an existing target, and resolvable analyzer keys, but no runner
  asserts their findings yet.
- The analyzer harness now counts every emitted finding and every declared rule
  count. Two manifests had recorded only part of their fixture's output: the
  signal-lifecycle fixture also reports an unconsumed variable, and the
  high-complexity fixture reports the equation-level finding alongside the
  module-level one. Both manifests record the full output.
- The only analyzer change is the newly active parser rule for an unknown
  parameter mapping target, which SattLint already reports as its own finding.

## Post-review fix batch

A follow-up review of the whole repository found defects outside the parser
upgrade. The batch fixed the ones that affect correctness or CI trust:

- An analyzer that raises now fails the command instead of exiting zero.
- An unusable cache directory degrades to no cache instead of aborting.
- An empty target list is a configuration error, not an internal error.
- Repeated modules with parameter mappings no longer report false drift.
- A module type instance resolves against its own library.
- Run history records the project file, and the UI filters on it.
- The output log trims in batches rather than rebuilding per line.
- Companion pairing follows the parser family and case rules.
- The corpus harness fails on a missing target, and every manifest family is
  schema checked.

Smaller defects were fixed in the same pass: the run-year import cycle,
configuration key warnings, startup error handling, report labels, asset path
containment, run deletion confirmation, and the stale release documentation.

## Parser 2026.11.6 delta

The branch moved from 2026.11.5 to 2026.11.6 before merge. The public surface
SattLint imports is additive: constructors gained keyword fields, the project
layer gained identity and index helpers, and `parse_and_validate` gained
external-definition arguments. The full suite, the corpus manifests, and both
configured library targets were re-run after the pin change with the same
results.
