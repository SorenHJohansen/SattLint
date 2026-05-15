# T-Wave-6 GUI Test and Coverage Ratchet

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan addresses the GUI-side test and coverage debt from the 2026-05-15 architecture review. The biggest current problem is not a missing feature; it is that `tests/test_gui.py` has become a 1743-line bottleneck, while several GUI frames and widgets sit at the lowest coverage floors in the repository. After this work lands, the GUI test surface will be split into smaller behavior-focused files, and the lowest-coverage frame and widget owners will have focused regression coverage that makes future edits cheaper.

The observable proof is that GUI tests still pass after the split, widget and frame behavior remain stable, and the touched GUI owners gain stronger focused coverage instead of staying ratchet traps.

## Progress

- [x] (2026-05-15) Create the ExecPlan and confirm `tests/test_gui.py` is 1743 lines, while the repo-health snapshot identifies `src/sattlint_gui/widgets/analyzer_list.py`, `src/sattlint_gui/frames/results_frame.py`, `src/sattlint_gui/frames/sidebar.py`, `src/sattlint_gui/frames/docs_frame.py`, `src/sattlint_gui/frames/analyze_frame.py`, `src/sattlint_gui/frames/tools_frame.py`, and `src/sattlint_gui/widgets/target_list.py` as the lowest GUI coverage-ratchet owners.
- [x] (2026-05-15) Split the monolithic GUI tests into `tests/test_gui.py` for config behavior, `tests/test_gui_boot.py` for boot, binding, theme, and window flows, `tests/test_gui_widgets.py` for widget behavior, and `tests/test_gui_frames.py` for analyze, docs, results, sidebar, and tools flows, with shared doubles in `tests/_gui_test_support.py`.
- [x] (2026-05-15) Add focused constructor and headless-behavior tests for the lowest-coverage GUI owners, including `AnalyzerList`, `TargetList`, `AnalyzeFrame`, `DocsFrame`, `ResultsFrame`, `SidebarFrame`, and `ToolsFrame`.
- [x] (2026-05-15) Keep GUI startup and frame wiring stable while moving tests; no production GUI source changes were required for this slice.
- [x] (2026-05-15) Rerun the focused GUI pytest slice in a `tkinter`-enabled repo environment: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_gui.py tests/test_gui_boot.py tests/test_gui_widgets.py tests/test_gui_frames.py -x -q --tb=short` now passes with `51 passed in 0.31s`.

## Surprises & Discoveries

Observation: the worst GUI debt is validation cost, not source-file size.
Evidence: most of the low-coverage GUI owners are small files, but `tests/test_gui.py` is large enough that every GUI change pays a very high rerun and maintenance cost.

Observation: the lowest-coverage GUI owners are narrow widgets and frames.
Evidence: the coverage list from the repo-health snapshot points to `analyzer_list.py`, `target_list.py`, and the small frame modules rather than the top-level GUI bootstrap files.

Observation: the GUI coverage debt is a good candidate for focused tests instead of broad integration growth.
Evidence: the target owners are small and responsibility-specific, so targeted widget or frame tests should raise coverage faster than adding more assertions to the already oversized integration file.

Observation: the split GUI test surface now has direct executable proof instead of only static checks.
Evidence: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_gui.py tests/test_gui_boot.py tests/test_gui_widgets.py tests/test_gui_frames.py -x -q --tb=short` completes with `51 passed in 0.31s` once `tkinter` is available in the repo environment.

## Decision Log

Decision: split the monolithic GUI test before adding more broad integration assertions.
Rationale: continuing to extend `tests/test_gui.py` would make future GUI refactors even more expensive to validate.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: prioritize the lowest-coverage frame and widget owners first.
Rationale: those files are already the strongest coverage-on-touch traps, and they are small enough to raise with focused tests quickly.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: keep GUI wiring stable while moving tests.
Rationale: the debt is in test concentration and missing focused coverage, not in the current top-level GUI startup flow.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The GUI test bottleneck is no longer a single file. The old `tests/test_gui.py` now holds only the config-heavy slice, while boot, widget, and frame behavior live in dedicated test modules with a small shared support module. The lowest-coverage GUI owners also gained targeted constructor and behavior tests instead of relying only on the oversized integration surface.

Finish-gate evidence is complete for the slice: the focused GUI pytest command passes with 51 tests, and the touched-file Ruff and Pyright checks already passed on the split test files. The remaining work for this plan is documentation state only, not missing executable proof.

## Context and Orientation

The GUI package lives under `src/sattlint_gui/`. The specific low-coverage owners from the review are `widgets/analyzer_list.py`, `widgets/target_list.py`, and the frame modules under `frames/` for analyze, docs, results, sidebar, and tools behavior.

The current GUI integration test surface is `tests/test_gui.py`. That file exercises enough of the GUI to be useful, but it is too large to be the only place where widget and frame behavior is validated.

The top-level GUI entry flow is in `src/sattlint_gui/main.py` and `src/sattlint_gui/window.py`. Keep that wiring stable while splitting tests and adding coverage to the narrower frame and widget owners.

## Plan of Work

Start by splitting `tests/test_gui.py` into smaller files that match actual GUI behavior areas. Create `tests/test_gui_boot.py` for application startup, `tests/test_gui_widgets.py` for analyzer and target list behavior, and `tests/test_gui_frames.py` for docs, results, sidebar, analyze, and tools frames. Keep shared builders or support helpers in a dedicated helper module if needed, but do not create a second giant test file under a new name.

Then add focused tests for the lowest-coverage owners. Each new test should prove one real widget or frame behavior, such as populating analyzer or target lists, rendering docs or results state, or preserving sidebar and tools frame interactions.

Only touch the GUI source files when the split exposes missing seams or testability problems. If a frame or widget needs a tiny helper extraction for testing, keep it narrow and avoid turning this plan into a UI redesign.

## Concrete Steps

Run all commands from the repository root.

Inspect the current GUI debt surfaces before editing code:

    wc -l tests/test_gui.py src/sattlint_gui/widgets/analyzer_list.py src/sattlint_gui/widgets/target_list.py src/sattlint_gui/frames/analyze_frame.py src/sattlint_gui/frames/docs_frame.py src/sattlint_gui/frames/results_frame.py src/sattlint_gui/frames/sidebar.py src/sattlint_gui/frames/tools_frame.py
    rg -n "AnalyzerList|TargetList|AnalyzeFrame|DocsFrame|ResultsFrame|Sidebar|ToolsFrame" src/sattlint_gui tests/test_gui.py

Before splitting the tests, capture the current focused proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_gui.py -x -q --tb=short

After the test split and coverage additions land, rerun the focused GUI slice using the new split files plus any remaining slim integration file:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_gui.py tests/test_gui_boot.py tests/test_gui_widgets.py tests/test_gui_frames.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint_gui tests/test_gui.py tests/test_gui_boot.py tests/test_gui_widgets.py tests/test_gui_frames.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint_gui

## Validation and Acceptance

Acceptance requires two visible improvements. First, the GUI test surface must stop being a single 1743-line bottleneck. Second, the lowest-coverage widget and frame owners must gain focused regression proof so future edits do not immediately hit the same coverage-on-touch debt. The GUI application and frame wiring must keep the same observed behavior under focused tests.

## Idempotence and Recovery

This plan is safe to execute one test cluster at a time. Split one behavior area out of `tests/test_gui.py`, rerun the focused tests, and only then move to the next cluster. If a new focused test requires a small source seam, add that seam narrowly and keep the GUI startup flow unchanged.

## Artifacts and Notes

Current GUI debt facts at plan creation time:

    1743 tests/test_gui.py
    77 src/sattlint_gui/widgets/analyzer_list.py
    36 src/sattlint_gui/widgets/target_list.py
    102 src/sattlint_gui/frames/analyze_frame.py
    117 src/sattlint_gui/frames/docs_frame.py
    90 src/sattlint_gui/frames/results_frame.py
    31 src/sattlint_gui/frames/sidebar.py
    61 src/sattlint_gui/frames/tools_frame.py

The review identified those widget and frame owners as the lowest GUI coverage-ratchet surfaces, which is why this plan focuses there first.

Post-split GUI test file sizes after this slice:

    262 tests/test_gui.py
    482 tests/test_gui_boot.py
    296 tests/test_gui_widgets.py
    870 tests/test_gui_frames.py
     81 tests/_gui_test_support.py

## Interfaces and Dependencies

The implementation surface is `src/sattlint_gui/` plus the GUI test suite under `tests/`. Preserve the current GUI startup flow in `src/sattlint_gui/main.py` and `src/sattlint_gui/window.py`, and prefer focused widget or frame tests over adding more broad integration assertions to one monolithic test file.
