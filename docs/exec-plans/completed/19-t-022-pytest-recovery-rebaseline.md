# T-022 Pytest Recovery Rebaseline

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

T-022 says the repository has 22 failing tests spread across tracker, editor, LSP, parser, and phase-0 guardrail suites. The current repository does not match that description. By implementation time on 2026-05-04, a fresh full-suite run no longer reproduced the earlier 4-failure snapshot from plan creation either: only `tests/test_repo_audit.py::test_collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source` was still failing. This plan exists to turn that stale umbrella debt item into a current executable recovery path. The observable outcome is that `pytest --tb=short -q` returns zero failures on the current branch, and the tracker closes T-022 instead of continuing to describe the stale 22-test list.

## Progress

- [x] (2026-05-04 00:00Z) Create this ExecPlan from a fresh full-suite run and targeted reads of the current failing tests.
- [x] (2026-05-04 00:13Z) Reproduce the current failing baseline with `pytest --tb=short -q` and record the exact failing test in this file before editing anything.
- [x] (2026-05-04 00:13Z) Verify that the checked-in AI work-map artifacts and parser fuzz-helper route were already green on the current branch, so no AI-map regeneration or fuzz-helper code change was required.
- [x] (2026-05-04 00:16Z) Repair the remaining repo-audit aggregation failure by isolating the test from the separately covered `verify-recommendations` drift check.
- [x] (2026-05-04 00:18Z) Rerun the full suite; `pytest --tb=short -q` now reports `1551 passed, 1 warning`.
- [x] (2026-05-04 00:19Z) Update `docs/exec-plans/tech-debt-tracker.md` so T-022 no longer claims 22 stale failures.
- [x] (2026-05-04 00:20Z) Move this closed recovery record to `docs/exec-plans/completed/` now that the tracker and full-suite evidence are both current.

## Surprises & Discoveries

- Observation: by implementation time the earlier 4-failure snapshot no longer reproduced; the live baseline had only one failing test.
  Evidence: `& ".venv/Scripts/python.exe" -m pytest --tb=short -q` reported only `tests/test_repo_audit.py::test_collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source` as failing before any code edit.
- Observation: the AI work-map and parser routes were already green on the current branch.
  Evidence: the same full-suite baseline showed no failures in `tests/test_ai_work_map.py` or `tests/test_parser.py`, so the planned AI-map regeneration and fuzz-helper repair were unnecessary for this branch state.
- Observation: the remaining failure was a stale unit-test assumption, not a repo-audit runtime defect.
  Evidence: `src/sattlint/devtools/repo_audit_entrypoints.py` now includes `verify-recommendations` in the default `collect_custom_findings()` check list, and `tests/test_repo_audit_entrypoints_helpers.py` already has dedicated assertions that this check emits the generated-artifact drift IDs. The failing aggregation test had not patched that later-added runner, so it leaked unrelated drift findings into its expected list.

## Decision Log

- Decision: rebaseline T-022 from current failing evidence before touching production code.
  Rationale: the tracker's current failure list is stale, and implementing against stale failure names would misroute the work.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: sequence the AI-map regeneration before the repo-audit repair.
  Rationale: the repo-audit failing assertion is likely observing stale generated-artifact drift, so the cheapest discriminating step is to make the checked-in AI maps current first.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: keep the parser fix in the existing fuzz-harness seam rather than weakening the test.
  Rationale: the test documents a user-facing helper contract: generated fuzz text should stay near the requested target length while remaining deterministic when seeded.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: fix the stale repo-audit aggregation test instead of changing production repo-audit behavior.
  Rationale: the production `verify-recommendations` behavior is already covered by focused helper tests; the only live failure was that one aggregation test had not been updated to isolate the newer check.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Closed with one test-only repair. The branch state at implementation time was already much healthier than the stale T-022 description and healthier than the plan-creation snapshot. No AI-map regeneration or parser changes were required. The only needed change was to isolate `tests/test_repo_audit.py::test_collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source` from the separately tested `verify-recommendations` drift check, after which the full suite passed.

Archive outcome complete: this file is now historical closeout evidence rather than an active recovery plan because the tracker and full-suite baseline are both green.

## Context and Orientation

This plan touches three distinct but small seams.

The first seam is the checked-in AI planning metadata. `src/sattlint/devtools/ai_work_map.py` scans `docs/exec-plans/active/*.md`, parses owner-suite and validation metadata from those files, and writes two checked-in JSON artifacts:

- `.github/skills/validation-routing/references/ai-work-map.json`
- `.github/skills/validation-routing/references/ai-session-context-map.json`

`tests/test_ai_work_map.py` compares the live build of those artifacts against the checked-in JSON. Any new active ExecPlan or change to owner-suite text changes the generated output. That means adding this plan file and the companion T-009 plan file necessarily requires regenerating those JSON artifacts.

The second seam is the parser fuzz helper in `src/sattline_parser/fuzz_harness.py`. This helper does not validate parser correctness directly; it generates randomized source text near a requested length so fuzz tests can exercise the parser without crashing or hanging. The current implementation uses token-sized jumps and stops when the next token would exceed the requested length. That early stop is what lets a target of `50` produce a string of length `39`.

The third seam is the repo-audit custom-finding aggregation path exercised by `tests/test_repo_audit.py`. That test checks the final filtered finding IDs returned by the repo-audit helpers. Because AI-work-map drift is one of the generated-artifact findings in this repository, stale checked-in JSON can change the observed finding list.

Primary owner suites for this plan:

- `tests/test_ai_work_map.py` -> `src/sattlint/devtools/ai_work_map.py`, `.github/skills/validation-routing/references/ai-work-map.json`, `.github/skills/validation-routing/references/ai-session-context-map.json`, `docs/exec-plans/active/*.md`
- `tests/test_parser.py` -> `src/sattline_parser/fuzz_harness.py`
- `tests/test_repo_audit.py` -> `src/sattlint/devtools/repo_audit.py`, `src/sattlint/devtools/doc_gardener.py`, and generated-artifact expectations that depend on current AI-map files

## Plan of Work

Begin with the AI-map drift because it is both reproducible and structurally required after adding new active ExecPlans. Regenerate the two checked-in JSON artifacts from the live `ai_work_map` builder, then rerun `tests/test_ai_work_map.py` before editing any other code. This step is expected to either fix two failures outright or reveal a real builder bug in `src/sattlint/devtools/ai_work_map.py`.

Once the checked-in AI maps are current, rerun the targeted repo-audit failing assertion. If that test now passes, do not touch repo-audit code. If it still fails, read only the failing assertion and the nearest production helper to decide whether the expected list or the filtering logic is stale.

After the metadata slice is green, repair the parser fuzz helper. The fix must preserve seeded determinism and must not expand into parser-core behavior changes. The simplest acceptable repair is one that keeps generated text within the documented tolerance band for the target length while still using non-cryptographic randomness and existing token vocabulary.

Finish by rerunning the full suite. If the suite is green, update T-022 in `docs/exec-plans/tech-debt-tracker.md` so the tracker no longer claims 22 failures that do not reproduce. If the suite is not green, use the fresh failing set to rewrite T-022 into an accurate current debt item.

## Concrete Steps

Run commands from the repository root.

Per-slice first validations:

    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_ai_work_map.py -x -q --tb=short
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short -k "collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source"
    & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser.py -x -q --tb=short -k "GenerateRandomText"

Regenerate the checked-in AI-map artifacts before rerunning `tests/test_ai_work_map.py`:

    & ".venv/Scripts/python.exe" -c "from sattlint.devtools.ai_work_map import DEFAULT_OUTPUT_PATH, DEFAULT_SESSION_CONTEXT_OUTPUT_PATH, render_ai_work_map, render_session_context_map; DEFAULT_OUTPUT_PATH.write_text(render_ai_work_map() + '\n', encoding='utf-8'); DEFAULT_SESSION_CONTEXT_OUTPUT_PATH.write_text(render_session_context_map() + '\n', encoding='utf-8')"

Once the three focused routes are green, rerun the full suite:

    & ".venv/Scripts/python.exe" -m pytest --tb=short -q

Observed failing baseline before repair:

  FAILED tests/test_repo_audit.py::test_collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source

Expected success condition at plan close:

    <full suite passes>
    no FAILED entries in the short summary

## Validation and Acceptance

This plan is complete when all of the following are true:

- `tests/test_ai_work_map.py` passes and the checked-in AI-map artifacts match the live builder,
- `tests/test_parser.py -k "GenerateRandomText"` passes with seeded determinism preserved,
- the targeted repo-audit failing assertion passes without suppressing real generated-artifact drift incorrectly,
- `pytest --tb=short -q` shows zero failures,
- `docs/exec-plans/tech-debt-tracker.md` no longer describes T-022 as a 22-failure umbrella item unless a fresh full-suite run proves that state again.

## Idempotence and Recovery

AI-map regeneration is safe to repeat; it rewrites checked-in generated JSON from current active ExecPlans. If the regenerated files create merge conflicts, regenerate again after rebasing instead of hand-merging JSON. The parser fix should stay local to `src/sattline_parser/fuzz_harness.py`; if a proposed repair starts touching parser core or grammar files, stop and re-scope. If current workstream claims on `src/sattline_parser/fuzz_harness.py` or `tests/test_repo_audit.py` are still active, coordinate in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state before editing those files and keep the AI-map slice separate until the claim is resolved.

## Artifacts and Notes

Recorded validation evidence:

  & ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_repo_audit.py -x -q --tb=short -k "collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source"
  1 passed, 113 deselected in 0.54s

  & ".venv/Scripts/python.exe" -m pytest --tb=short -q
  1551 passed, 1 warning in 92.83s (0:01:32)

  & ".venv/Scripts/ruff.exe" check tests/test_repo_audit.py
  All checks passed!

  & ".venv/Scripts/pyright.exe" tests/test_repo_audit.py
  0 errors, 0 warnings, 0 informations

## Interfaces and Dependencies

Use the existing generator in `src/sattlint/devtools/ai_work_map.py`; do not hand-edit the checked-in JSON except for the generated output itself. Use the existing fuzz helper in `src/sattline_parser/fuzz_harness.py`; do not alter parser grammar or AST code for this plan. Keep repo-audit work in the nearest existing assertion and helper seam rather than widening into unrelated audit checks.
