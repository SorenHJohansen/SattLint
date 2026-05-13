# C-Wave-Backlog S88 Scope Lock

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan replaces the backlog roadmap rows for C-019 and C-020 with a single active scope-lock surface. Before this plan, the roadmap said that S88 control-module contracts and S88 phase sequencing were deferred until domain scope was confirmed, but there was no live file that explained what confirmation meant or what evidence would let implementation start safely. After this plan is executed, maintainers will have one active document that records the accepted S88 vocabulary, the minimum fixture corpus, the promotion criteria, and whether C-019 and C-020 stay deferred or move into implementation.

## Progress

- [x] (2026-05-13 09:12Z) Create the ExecPlan and confirm that `src/sattlint/analyzers/s88_contracts.py` and `src/sattlint/analyzers/s88_sequencing.py` do not exist, and that there is no dedicated S88 analyzer surface or focused S88 test suite in the current tree.
- [x] (2026-05-13 10:08Z) Define the accepted S88 vocabulary from committed repository sources, map it to current SattLine and docgen seams, and list the vendor-specific semantics excluded from the first milestone.
- [x] (2026-05-13 10:19Z) Keep C-019 and C-020 on one shared domain model with two future analyzer entry points because both features depend on the same physical and procedural vocabulary, extraction rules, and public fixture corpus.
- [x] (2026-05-13 10:31Z) Define the minimal public fixture corpus and focused validation route required for promotion, using small parser-valid SattLine samples under `tests/fixtures/sample_sattline_files/s88/` and dedicated pytest owners under `tests/analyzers/`.
- [x] (2026-05-13 10:42Z) Record the promotion decision: remain deferred until a committed public fixture corpus and normative contract semantics exist for both S88 control-module contracts and S88 phase sequencing.

## Surprises & Discoveries

- Observation: the repository already has strong sequence and safety analysis seams, but no S88-specific vocabulary or domain fixtures.
  Evidence: `src/sattlint/analyzers/sfc.py`, `src/sattlint/analyzers/safety_paths.py`, and `src/sattlint/core/semantic.py` provide generic sequence and path reasoning, yet there is no `s88_*` analyzer module or S88-specific test surface.
- Observation: deferring C-019 and C-020 in the roadmap was accurate, but the deferral had no live owner once the items leave the roadmap.
  Evidence: the roadmap entries said to wait until S88 scope was confirmed, but no active ExecPlan file defined the confirmation criteria or the next decision checkpoint.
- Observation: the repository already contains public S88 terminology and naming heuristics, but they live in docs and docgen surfaces rather than in analyzer-ready rules.
  Evidence: `docs/SattLineReferenceDocs/sattline_batch_control_reference.md` defines the physical and procedural hierarchy, while `src/sattlint/docgenerator/docgen.py`, `tests/_docgen_part2.py`, and `tests/_docgen_part3.py` already render and test S88 physical and procedural labels such as units, equipment modules, operations, phases, and control modules.
- Observation: the only committed batch-oriented SattLine sample is the large grammar fixture, which is useful as an extraction seed but not as a focused analyzer corpus.
  Evidence: `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s` contains `UnitSupervisorCore`, multiple phase invocations, and `BatchLoggerMaster`, but it is intentionally broad grammar coverage rather than a small behavior-specific fixture set.

## Decision Log

- Decision: keep C-019 and C-020 together in one backlog scope-lock plan until the accepted S88 vocabulary is explicit.
  Rationale: both features depend on the same domain model, the same fixture corpus, and the same promotion gate. Splitting them now would force the repository to duplicate the same open questions in two files.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: do not start implementation before the repository has a public, repeatable fixture corpus for S88 behavior.
  Rationale: these features are domain integration work. Without fixtures that can be committed and rerun locally, any implementation would depend on private assumptions and would be impossible to validate safely.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: treat the public batch-control reference, docgen S88 headings, docgen classification tests, and the batch-oriented grammar fixture as the only accepted sources for scope-locking S88 vocabulary in this repository.
  Rationale: those sources are committed, reviewable, and already describe the nouns the repository can name safely without depending on proprietary project inputs.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: the first milestone is vendor-neutral and excludes proprietary BatchLib pin contracts, scheduler policies, arbitration timing, approval workflows, and historian payload schemas.
  Rationale: the committed sources name units, equipment modules, control modules, operations, and phases, but they do not define one canonical public interface for `RecipeManagerMaster`, `ProcessManagerMaster`, `UnitSupervisorCore`, or site-specific phase result codes.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: if promotion happens later, implement one shared S88 helper layer with two public analyzer entry points rather than two independent implementations.
  Rationale: control-module contract checks and phase-sequencing checks need the same unit, equipment, control-module, operation, and phase extraction rules. The checks differ, but the domain model does not.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: keep C-019 and C-020 deferred after this review.
  Rationale: the repository can now name the vocabulary and the required corpus shape, but it still lacks committed fixtures and normative public semantics for valid control-module contracts and valid phase transitions.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This review completed the scope lock in deferred state. The repository now has an explicit S88 vocabulary, a documented implementation shape, a concrete public fixture-corpus contract, and a promotion gate for C-019 and C-020. The work does not move into implementation yet because the committed materials still stop at naming and documentation heuristics; they do not define one public contract schema for control modules or one accepted valid or invalid transition matrix for phases. The next review should happen when a small committed S88 fixture corpus is ready, or by 2026-08-31 if no public fixtures have landed sooner.

## Context and Orientation

The nearest existing semantic seams are generic rather than S88-specific. `src/sattlint/analyzers/sfc.py` already understands sequence structure. `src/sattlint/analyzers/safety_paths.py` already traces critical signals. `src/sattlint/core/semantic.py` remains the repository-standard workspace loader. Those surfaces can support S88 work later, but they do not establish the domain model by themselves.

There is no S88 owner surface today. No analyzer modules named `s88_contracts.py` or `s88_sequencing.py` exist. There is also no dedicated S88 test file and no roadmap-independent domain note that defines what this repository means by a control module, a phase interface, or a valid phase transition in S88 terms. This plan exists to create that scope lock before anyone writes analyzer code.

## Accepted S88 Vocabulary

The repository can safely recognize the following S88 terms from committed sources. This is the full accepted vocabulary for the first milestone. Anything beyond these nouns or their direct mappings remains out of scope until public fixtures exist.

| Term | Current repository meaning | Current source inputs | First-milestone scope |
| --- | --- | --- | --- |
| Process cell | Top-level physical grouping used for documentation context, not a direct analyzer target for C-019 or C-020. | `docs/SattLineReferenceDocs/sattline_batch_control_reference.md`; `src/sattlint/docgenerator/docgen.py` physical-model headings | Naming context only |
| Unit | A root process module that owns equipment and procedural behavior for one batch context. | Batch-control reference physical hierarchy; docgen unit discovery; `SattLineFullGrammarTest.s` unit-supervisor examples | In scope |
| Equipment module | A bounded activity module under a unit, already surfaced by docgen equipment-module heuristics. | Batch-control reference; docgen physical-model text; docgen tests that classify equipment modules | In scope |
| Control module | A low-level device-oriented module under a unit or equipment path, currently evidenced publicly only through terminology and docgen control-module reporting. | Batch-control reference; `tests/_docgen_part3.py` control-module reporting | In scope for naming and presence only |
| Operation | A major procedural activity that groups one or more phases. | Batch-control reference recipe hierarchy; docgen procedural-model text; docgen `OperationPhase` tests | In scope as parent context |
| Phase | The smallest procedural element. Public evidence today is a named phase invocation and sequence-bearing module context, not a normative public interface schema. | Batch-control reference; `SattLineFullGrammarTest.s` phase invocations; generic sequence seams in `src/sattlint/analyzers/sfc.py` | In scope, but semantics are partial |
| Phase interface | The externally visible parameter, condition, result, and status surface of a phase. | Batch-control reference operation recipe structure and execution flow | Blocked pending committed fixture contract |
| Phase sequencing | The explicit ordering and transition logic between phases inside one unit or operation context. | Batch-control reference execution flow; generic sequence analysis seams | Blocked pending committed transition fixtures |
| Control-module contract | The required parameter mappings, status fields, and result or command links that make a low-level control module analyzable in S88 terms. | No committed normative source today; only terminology and broad batch examples exist | Blocked |

## Explicit First-Milestone Exclusions

The first milestone must stay vendor-neutral. The repository does not currently accept the following as public S88 analyzer requirements:

- The exact interface pin schema of `RecipeManagerMaster`, `ProcessManagerMaster`, `UnitSupervisorCore`, `UnitSupervisorServer`, `BatchJournalSampler`, or `BatchLoggerMaster`.
- Site-specific phase state enumerations, command words, result codes, timeout policies, and operator-override semantics.
- Multi-unit transfer handshakes, shared-equipment arbitration policies, and priority rules beyond the generic terminology already described in the batch-control reference.
- Recipe approval workflows, version-control procedures, historian payload structure, and regulatory-report formatting.
- GUI editor layout or drag-and-drop recipe authoring behavior.

## Shared Implementation Shape

C-019 and C-020 should share one future domain helper layer and then split into two analyzer entry points:

- Shared helper responsibilities: identify units, equipment modules, control modules, operations, and phases from workspace facts; normalize parameter mappings and relevant status links; derive explicit phase-order edges from sequence-bearing contexts.
- Future public analyzers: `src/sattlint/analyzers/s88_contracts.py` for control-module and phase-interface contracts, and `src/sattlint/analyzers/s88_sequencing.py` for valid phase ordering and transition checks.
- Registration and reporting: follow the normal analyzer registry and reporting seams only after the helper layer and fixtures exist. This plan does not authorize speculative registry changes now.

## Minimal Public Fixture Corpus And Validation Route

The first acceptable public corpus should be small, parser-valid, and committed under `tests/fixtures/sample_sattline_files/s88/`. The minimum useful set is:

- `UnitHierarchy.s`: one process cell context with one unit, one equipment module, and one control module so the shared helper layer can prove physical classification without recipe logic noise.
- `PhaseSequenceHappyPath.s`: one unit or operation context with a short legal phase order so sequencing extraction has a positive baseline.
- `PhaseSequenceInvalidTransition.s`: one intentionally invalid transition or skipped phase so sequencing analysis has a negative proof.
- `ControlModuleContractMissingMapping.s`: one small module tree where a required control-module or phase-interface mapping is missing so C-019 has a negative proof.

The current repository does not contain those focused fixtures yet. `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s` may be mined as a seed source, but it is not itself the committed analyzer corpus for this work.

When promotion becomes justified, the first focused validation route remains:

  python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_s88_contracts.py tests/analyzers/test_s88_sequencing.py -x -q --tb=short

Until those files exist, the only validation for this scope-lock slice is markdownlint on this plan.

## Promotion Decision

C-019 and C-020 remain deferred after this review.

Promotion requires all of the following:

1. A committed focused fixture corpus under `tests/fixtures/sample_sattline_files/s88/`.
2. A public note or fixture-backed contract that states which control-module or phase-interface fields are required for analyzer checks.
3. A fixture-backed valid and invalid transition matrix for phase sequencing.
4. Dedicated focused pytest owners for contracts and sequencing.

If those conditions are not met, future work should update this file again rather than starting `s88_*` analyzer modules directly.

## Plan of Work

First, collect and write down the accepted S88 vocabulary inside this plan itself. Define which S88 concepts will be represented directly, which existing SattLine constructs they map onto, and which vendor- or site-specific conventions are explicitly out of scope for the first milestone. If those definitions cannot be made from committed repository materials, record that as a blocker rather than guessing.

Second, decide the implementation shape. If C-019 and C-020 share the same domain model, keep one shared helper layer and expose two analyzer entry points later. If the required facts diverge immediately, split them only after the shared vocabulary is documented. Either way, do not let the roadmap remain the only place where those decisions are recorded.

Third, create a minimal fixture corpus and validation route. That corpus must live in the repository and be small enough to run in focused pytest without special environment setup. If no acceptable fixture corpus can be created yet, keep the features deferred and record the missing input contract and next review checkpoint in this plan.

## Concrete Steps

Run all commands from the repository root.

Survey the nearest generic sequence-analysis seams and confirm the S88 surfaces are still absent:

    rg -n "sfc|sequence|phase|control module" src/sattlint/analyzers src/sattlint/core tests
    rg -n "s88_contracts|s88_sequencing" src tests docs/exec-plans

If promotion to implementation becomes justified, establish the first focused validation route with committed fixtures:

    python scripts/run_repo_python.py -m pytest --no-cov tests/analyzers/test_s88_contracts.py tests/analyzers/test_s88_sequencing.py -x -q --tb=short

Run markdownlint after any scope-lock or milestone updates in this file:

    python scripts/run_repo_python.py scripts/run_markdownlint.py docs/exec-plans/completed/30-c-wave-backlog-s88-scope-lock.md

## Validation and Acceptance

Deferred-state acceptance means this file records the accepted S88 vocabulary, the explicit blockers, and the next review condition. Promoted-state acceptance means the file now contains concrete implementation milestones, a committed fixture corpus, and a focused pytest route that can prove behavior locally. In either state, the backlog work must be owned here rather than implicitly by the roadmap.

## Idempotence and Recovery

This plan is safe to revisit repeatedly. Each review should add evidence without deleting earlier rationale. If a proposed S88 scope depends on private or non-committed production inputs, stop and record that as a blocker instead of starting implementation. If a later review provides fixtures and vocabulary, update this same file rather than creating a second competing backlog owner.

## Artifacts and Notes

Record one short note for each review cycle: the accepted vocabulary, any missing inputs, whether the fixture corpus exists, and the final defer-or-promote decision. If implementation is promoted, capture the exact first-validation command and the fixture paths used to support it.

- 2026-05-13 review: accepted vocabulary locked to the batch-control reference, docgen S88 physical and procedural model seams, docgen classification tests, and the batch-oriented grammar fixture. Missing inputs are a small committed S88 fixture corpus plus normative control-module and phase-transition semantics. Fixture corpus does not exist yet. Final decision: keep C-019 and C-020 deferred and re-review when public fixtures land or by 2026-08-31.

## Interfaces and Dependencies

This plan depends on the generic sequence-analysis seams in `src/sattlint/analyzers/sfc.py`, `src/sattlint/analyzers/safety_paths.py`, and `src/sattlint/core/semantic.py`, but it does not authorize implementation there yet. If the work is promoted, new public analyzer entry points should live in `src/sattlint/analyzers/s88_contracts.py` and `src/sattlint/analyzers/s88_sequencing.py`, with registration handled in the normal analyzer registry files and validation anchored in committed S88 fixtures under `tests/`.
