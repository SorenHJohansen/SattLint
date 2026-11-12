# SattLint parser upgrade plan

Status: in progress, Phases 0 to 2 committed on the migration branch; the
legacy traversal cleanup (Phase 4) blocks a green suite and must land before
Phase 3
Target parser: `sattline-parser==2026.11.4`
Current SattLint release: `2026.11.3`, pinned to `sattline-parser==2026.11.3`
Next SattLint release: next available CalVer, with the target parser pin

## Why this upgrade needs its own branch

`sattline-parser` 2026.11.4 changes the AST surface. SattLint 2026.11.3 pins the
previous release exactly, so published installs are safe. The upgrade must not
land on `main` until the analyzer suite is green against 2026.11.4.

Work on a long-lived branch, for example `feature/parser-2026.11.4`. Keep `main`
on `sattline-parser==2026.11.3` until the branch is ready. The branch may change
the pin to `==2026.11.4` immediately so CI exercises the target, but that pin is
released only after Phase 6.

## Goals

- Move every parser import to a supported door: `sattline_parser.ast`,
  `sattline_parser.types`, `sattline_parser.formatting`,
  `sattline_parser.project`, and the top-level parse and validation names.
- Preserve analyzer behavior. In particular, no new false unused-variable or
  unused-field findings caused by references that became invisible.
- Delete the reflective traversal layer and the branches that only understand
  shapes the parser no longer emits.
- Keep the exact parser pin until the parser adopts a compatibility policy.

## Non-goals

- No new analyzers and no new rule policy in this branch.
- No parser changes. The parser release is already published.
- No generic AST abstraction beyond the SattLint parser surface module.

## Phase close convention

Every phase ends the same way, on the migration branch:

1. Run the phase gate and `/verify`, and record the result.
2. Request a read-only review from the `sattlint-reviewer` subagent (`/review`).
   Treat a multi-file change, a new public seam, or an analyzer behavior change
   as requiring a review. The reviewer reports findings and does not edit files.
3. Apply the findings, then rerun the phase gate and `/verify`.
4. Commit the phase with a focused message, for example
   `refactor(parser): add the parser surface module`.

Do not start the next phase until the review is resolved and the phase commit
exists.

## Review and delivery practices

These follow the sattline-parser agent workflow:

- The reviewer lives in `.opencode/agents/sattlint-reviewer.md`. The `verify`,
  `review`, and `release` commands live in `.opencode/commands/`.
- One reviewer pass per phase, not a review loop. Apply the findings, rerun the
  gate, and commit. Request a second review only when the user asks for one.
- The reviewer is read-only. It reports findings with file and line references
  and never edits or runs the suite.
- Each phase is one focused commit on the migration branch. Do not mix phases
  in one commit.
- Land through a PR. Never commit or push directly to `main`.
- Keep the change inside the phase. Do not broaden into unrelated analyzers.
- Update the matching instruction page and `CHANGELOG.md` in the same change
  when behavior or the public surface changes.
- Keep the exact parser pin. Do not widen it during the migration.
- If a check cannot run, say which command the parent agent should run. Do not
  claim a pass.

## Phase 0: branch, target pin, contract test

1. Branch from `main`:
   `git switch -c feature/parser-2026.11.4`.
2. Change `pyproject.toml` to `sattline-parser==2026.11.4`.
3. Install the target parser in the development environment.
4. Confirm the compatibility test reads the pin rather than hardcoding a
   version: [tests/core/test_parser_compatibility.py](tests/core/test_parser_compatibility.py).
5. Add a fixture-based contract test. Use real parser output, not hand-built
   legacy shapes. Cover:
   - a text-object `VarName`,
   - a pick-button `VarName`,
   - `Enable_ = True : InVar_ "Flag"`,
   - an `OutVar_` tail in an interactor,
   - a `ComButProc_` with an expression argument,
   - a header with `Param1 = 5` and `Module_In_View`,
   - `ClippingBounds` with coordinate tails,
   - an interactor body with an assignment, a flag, and a colour.
6. Let the contract test fail. It is the destination, not a regression.

Acceptance: the branch installs 2026.11.4 and the contract test demonstrates the
expected shapes.

Phase close: run the contract gate and `/verify`, request the
`sattlint-reviewer` pass (`/review`), apply the findings, then commit the branch
setup and contract test.

## Phase 1: one parser surface

1. Create `src/sattlint/parser_api.py`, or repurpose the unused
   [models/ast_model.py](src/sattlint/models/ast_model.py), as the single
   re-export module:
   - nodes, clauses, tails, and walker from `sattline_parser.ast`,
   - type facts from `sattline_parser.types`,
   - `format_expr` and related helpers from `sattline_parser.formatting`,
   - `GraphicsModel`, `GraphicsBinding`, and graphics entry points from
     `sattline_parser.project`,
   - `parse_source_text`, `parse_and_validate`, `Diagnostic`, and
     `DiagnosticCode` from the top-level package.
2. Replace direct imports. Start with the files that already import
   `sattline_parser.models.ast_model`, `sattline_parser.models.expressions`,
   `sattline_parser.grammar.constants`, and `sattline_parser.validation.typing`.
3. Add an import guard that fails when source imports a parser submodule outside
   the surface module. Allowlist anything still pending, and shrink the
   allowlist every phase.
4. Delete `models/ast_model.py` if it is not used as the surface.

Acceptance: no behavior change, and the suite is green except the Phase 0
contract test.

Phase close: run the import guard and the suite, run `/verify`, request the
`sattlint-reviewer` pass (`/review`), apply the findings, then commit the
surface module and import changes.

## Phase 2: loud breaks

These fail at import or at first use, so fix them before the silent losses.

1. Remove `DiagnosticSeverity`:
   - [project/parser_adapter.py](src/sattlint/project/parser_adapter.py)
   - [validation/policy.py](src/sattlint/validation/policy.py)

   Every parser validation diagnostic is an error. Keep the root-versus-
   dependency policy. Use `Diagnostic.tentative` where the parser marks a finding
   as dependent on an unloaded closure.
2. Move graphics imports off `sattline_parser.api`:
   - [graphics/validation.py](src/sattlint/graphics/validation.py)
3. Rename `ModuleCode.equations` to `equationblocks` in every production path,
   including:
   - [analyzers/dataflow/_dataflow_traversal.py](src/sattlint/analyzers/dataflow/_dataflow_traversal.py)
   - [analyzers/shared/_dependency_usage_facts.py](src/sattlint/analyzers/shared/_dependency_usage_facts.py)
   - [analyzers/variables/_variable_traversal_walk.py](src/sattlint/analyzers/variables/_variable_traversal_walk.py)
   - [analyzers/reset_contamination](src/sattlint/analyzers/reset_contamination)
   - [analyzers/_modules_fingerprints.py](src/sattlint/analyzers/_modules_fingerprints.py)
   - [analyzers/_alarm_path_traversal.py](src/sattlint/analyzers/_alarm_path_traversal.py)
4. Move graphics attachments off `BasePicture`:
   - Add a SattLint-owned attachments value to
     [models/project_graph.py](src/sattlint/models/project_graph.py), keyed by
     program name or program identity.
   - Have [graphics/graphics_helpers.py](src/sattlint/graphics/graphics_helpers.py)
     return that value instead of setting attributes on the AST.
   - Pass the current program attachments into
     [core/_semantic_index.py](src/sattlint/core/_semantic_index.py) and
     [analyzers/variables/_variables_picture_display_support.py](src/sattlint/analyzers/variables/_variables_picture_display_support.py).
5. Read library dependencies from `ProjectGraph`, not from the AST:
   - [resolution/_moduletype_resolution.py](src/sattlint/resolution/_moduletype_resolution.py)
6. Bump cache identity:
   - `CACHE_VERSION` in [cache/__init__.py](src/sattlint/cache/__init__.py)
   - `PROJECT_CACHE_SCHEMA_VERSION`
   - `FOUNDATION_CACHE_SCHEMA_VERSION`

   A cached project graph pickles ASTs, so reusing 2026.11.3 entries under the
   new model is unsafe.
7. Delete the parser compatibility tests that rely on the retained parse tree:
   [tests/core/test_parser_compatibility.py](tests/core/test_parser_compatibility.py).

Acceptance: the suite imports and runs against 2026.11.4. Remaining failures are
the Phase 3 behavior gaps.

Observed ordering hazard: the parser removes the legacy tuple and Lark tree
constants that the reflective traversal layer still reads, so those branches
raise at first use. The suite therefore cannot go green, and Phase 3 cannot
compare a finding baseline, until the Phase 4 cleanup lands. Do Phase 4 before
Phase 3.

Phase close: run the suite and `/verify`, request the `sattlint-reviewer` pass
(`/review`), apply the findings, then commit the loud-break fixes.

## Phase 3: silent losses

These are the dangerous changes. They do not raise, but they make references
invisible and produce false findings.

1. `GraphProperties["text_vars"]` is `list[VarRef]`.
   - Update [analyzers/variables/_variable_traversal_objects.py](src/sattlint/analyzers/variables/_variable_traversal_objects.py).
   - Test with a text object that names a local variable.
2. `ModuleDef.properties` is gone. Clipping tails live on
   `ModuleDef.clipping.tails`.
   - Update the module-definition traversal in the same file.
   - Test with `ClippingBounds` coordinate tails that name variables.
3. `ModuleHeader.invoke_coord_tails` holds only the five coordinate tails.
   - `Enable_`, `Module_In_View`, and `Name = value` arguments live on
     `ModuleHeader.arguments`.
   - Update the header traversal.
   - Test an `Enable_` tail, a `Module_In_View` tail, and `Param1 = 5`.
4. `ParameterMapping.source_type` is a `MappingSource` value.
   - [analyzers/alarm_integrity.py](src/sattlint/analyzers/alarm_integrity.py)
     compares it with a string today. Compare with `MappingSource.VALUE`.
   - [resolution/context_builder.py](src/sattlint/resolution/context_builder.py)
     calls string methods on it. Use `str(...)` or the enum value.
   - Test a literal mapping and a variable mapping.
5. `InteractProperties["procedure"]` is a `ProcedureCall`.
   - Update [analyzers/variables/_variable_traversal_objects.py](src/sattlint/analyzers/variables/_variable_traversal_objects.py).
   - Record the call and walk its arguments, including expression arguments.
   - Test a `ComButProc_` that calls `ToggleWindow` with a variable argument.
6. Interact-body entries are typed clauses, not Lark trees.
   - Replace the tree-sniffing scan with `walk` over the interact object.
   - Handle `AssignClause`, `EnableClause`, `FlagClause`, `TailedClause`,
     `ColourSpec`, `PickButton`, `ScaleSelector`, `Alignment`, and `CodeComment`.
   - Test an interactor body with an assignment, an enable tail, and a colour.
7. `PickButton.reference` is a `VarRef`.
   - Record it as a read when it is present.

For each item, add a test that parses a real fixture through the parser and
asserts the analyzer result. A test that builds the AST by hand can hide the
exact regression this phase exists to catch.

Acceptance: the Phase 0 contract test passes, and the analyzer findings on the
fixture corpus match the 2026.11.3 baseline.

Phase close: run the contract test and the finding baseline, run `/verify`,
request the `sattlint-reviewer` pass (`/review`), apply the findings, then commit
the silent-loss fixes.

## Phase 4: delete the reflective layer

1. Rewrite [core/ast_tools.py](src/sattlint/core/ast_tools.py):
   - `iter_variable_refs` becomes a `walk` filter over `VarRef` plus the bound
     `VarTail` cases.
   - `iter_call_sites` handles `FuncCall`, `FuncCallStmt`, and `ProcedureCall`.
   - Delete the mapping, sequence, `children`, dataclass, and `__dict__`
     guessing helper.
   - Delete `VariableRef = dict` from [types.py](src/sattlint/types.py) when no
     caller remains.
2. Delete legacy shape branches in:
   - [analyzers/variables/_variable_traversal_walk.py](src/sattlint/analyzers/variables/_variable_traversal_walk.py)
   - [analyzers/variables/_variable_traversal_support.py](src/sattlint/analyzers/variables/_variable_traversal_support.py)
   - [analyzers/_wave2_node_traversal.py](src/sattlint/analyzers/_wave2_node_traversal.py)
   - [analyzers/dataflow/_dataflow_traversal.py](src/sattlint/analyzers/dataflow/_dataflow_traversal.py)
   - [analyzers/shared/_dependency_usage_facts.py](src/sattlint/analyzers/shared/_dependency_usage_facts.py)
   - [analyzers/shared/ast_node_helpers.py](src/sattlint/analyzers/shared/ast_node_helpers.py)
3. Remove tuple tags, `KEY_VAR_NAME` dictionaries, Lark `Tree` checks, and
   `SimpleNamespace(children=...)` paths.
4. Delete the tests that feed those shapes. They keep dead branches green.
5. Add a guard that rejects `__dict__`, attribute-style `children` access,
   `.data ==`, and tuple tag constants in analyzer code. Keep a shrinking
   allowlist only while a phase is open.

Acceptance: no reflective traversal remains in the analyzer path, and the suite
is green.

Phase close: run the suite and the traversal guard, run `/verify`, request the
`sattlint-reviewer` pass (`/review`), apply the findings, then commit the legacy
deletion.

## Phase 5: change review and normalization

1. [change_review/_ast_normalize.py](src/sattlint/change_review/_ast_normalize.py):
   - Remove `enable_tail` and `invoke_coord_tails` from the ignored fields. They
     are semantic, not layout.
   - Drive layout ignoring from the parser field metadata, not a global name
     list.
   - Keep a small SattLint policy override for comments if the product wants
     comment-only changes ignored.
2. [change_review/_code_model.py](src/sattlint/change_review/_code_model.py):
   - Replace the dataclass recursion for assignment targets with `walk`.
3. [analyzers/shared/_walk_utils.py](src/sattlint/analyzers/shared/_walk_utils.py):
   - Keep the stateful module walk, since analyzer scope is domain state.
   - Add a test that every parser container type that can nest modules is
     covered.

Acceptance: a change to a bound tail produces a semantic diff, and a change to a
span does not.

Phase close: run the normalization tests and `/verify`, request the
`sattlint-reviewer` pass (`/review`), apply the findings, then commit the
normalization changes.

## Phase 6: finalize and release

1. Keep `sattline-parser==2026.11.4`.
2. Remove the temporary import-guard allowlist.
3. Run the full gate:
   - `ruff check` and `ruff format --check`
   - `pyright src/sattlint`
   - full pytest suite
   - build wheel and sdist, `twine check`
   - clean-venv install smoke
   - CLI run against a real project
4. Compare analyzer output on the fixture corpus with the 2026.11.3 baseline.
   Review every new or removed finding.
5. Bump the SattLint version to the next CalVer, update `CHANGELOG.md`, merge
   through a PR, tag, and publish.
6. Do not widen the parser pin after release. Keep the exact pin until the
   parser publishes a compatibility policy.

Phase close: run the full gate and `/verify`, request the `sattlint-reviewer`
pass (`/review`) on the release diff, apply the findings, then commit the release
preparation. The release commit and tag follow the normal PR and tag flow.

## Verification matrix

| Gate | Command | When |
| --- | --- | --- |
| Contract test | focused pytest | every phase |
| Variables analyzers | focused pytest | Phases 3 and 4 |
| Dataflow and SFC | focused pytest | Phases 2 and 4 |
| Full suite | `pytest -q` | every phase end |
| Lint and format | `ruff check`, `ruff format --check` | every phase end |
| Types | `pyright src/sattlint` | every phase end |
| Build and metadata | `python -m build`, `twine check` | Phase 6 |
| Installed smoke | clean venv install, `sattlint --version` | Phase 6 |
| Finding baseline | analyze fixture corpus, diff against 2026.11.3 | Phases 3 and 6 |

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Text-object and pick-button references become invisible | Phase 3 tests on real fixtures; baseline findings diff |
| Clipping tails stop counting as uses | Walk `ModuleDef.clipping`; test with coordinate tails |
| Header argument tails are missed | Walk `ModuleHeader.arguments`; test `Enable_`, `Module_In_View`, and assignments |
| Literal parameter mappings are treated as references | Replace string comparison with `MappingSource`; test both mapping kinds |
| Procedure calls disappear from the semantic index | Handle `ProcedureCall`; test a `ComButProc_` call with an argument |
| Stale cached ASTs are decoded into the new model | Bump all cache versions |
| Test fixtures keep dead branches green | Delete legacy-shape tests; require real parser output in new tests |
| The pin is widened too early | Keep the exact pin until the parser publishes a compatibility policy |

## Rollback

If the branch cannot be completed in one release cycle:

1. Keep `main` on `sattline-parser==2026.11.3`.
2. Leave the migration branch open or parked.
3. Do not publish a SattLint release with a parser pin that has not passed the
   contract test and the finding baseline.

Rolling back a published SattLint release is a new release with the previous
exact pin. PyPI metadata for the broken release cannot be edited.

## Definition of done

- SattLint pins `sattline-parser==2026.11.4` and installs cleanly from PyPI.
- The contract test covers text references, pick-button references, bound
  tails, header arguments, clipping tails, parameter mapping kinds, procedures,
  and interactor bodies.
- Analyzer findings on the fixture corpus match the reviewed 2026.11.3 baseline.
- No source file imports a parser submodule outside the single surface module.
- No reflective child enumeration or `.data` tree sniffing remains.
- The cache version bump is present and the project cache is invalidated.
- The release notes state the parser pairing and the migration outcome.
