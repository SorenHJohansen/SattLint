# Review-Friendly .s/.x Diff Reports

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan adds a direct devtools workflow that compares draft `.s` source files with their official `.x` counterparts and emits a report that is easy to review in code review. After this work lands, a maintainer should be able to point SattLint at one explicit pair or a workspace containing paired files and receive a human-readable Markdown report plus a machine-readable JSON artifact that summarize which pairs changed, whether the change looks layout-only or structural, and the exact unified diff for each pair.

The observable proof is straightforward. From the repository root, a maintainer will run one command such as `bash scripts/run_repo_python.sh -m sattlint.devtools.source_diff_report --draft-file <path>.s --official-file <path>.x --output-dir artifacts/tmp/source-diff-report --format markdown`. That command must write `source_diff_report.md` and `source_diff_report.json`, and the Markdown file must read like a review artifact instead of a raw terminal dump: a top summary, one section per pair, classification of the drift, and a readable unified diff block.

## Progress

- [x] (2026-05-28 10:15Z) Created this ExecPlan and captured the local baseline: `src/sattlint/devtools/refactoring.py` already builds unified diff lines and stable summaries for preview output, `src/sattlint/devtools/differential.py` already defines a machine-readable diff-report pattern, and `src/sattlint/engine.py` already models `.s` as draft and `.x` as official source lookup.
- [x] (2026-05-28 10:15Z) Confirmed that the current committed fixture corpus does not provide an obvious same-basename `.s` and `.x` pair, so this plan must add dedicated paired fixtures instead of assuming the corpus already covers the feature.
- [ ] Extract the reusable diff-rendering and change-summary helpers from `src/sattlint/devtools/refactoring.py` into a small shared helper module so the new report surface does not duplicate diff formatting logic.
- [ ] Implement `src/sattlint/devtools/source_diff_report.py` as a direct command that supports explicit pair comparison first and workspace pair discovery second.
- [ ] Add dedicated `.s` and `.x` paired fixtures plus focused regression tests in `tests/devtools/test_source_diff_report.py`.
- [ ] Validate the new command with focused pytest, direct-command smoke output, touched-file Ruff, and touched-file Pyright.

## Surprises & Discoveries

- Observation: the closest existing implementation seam is the preview-first refactoring tool, not the existing analysis-diff artifact path.
  Evidence: `src/sattlint/devtools/refactoring.py` already produces unified diff lines, changed-line counts, output-directory artifacts, and a direct `python -m sattlint.devtools.*` command contract, while `src/sattlint/devtools/differential.py` only compares finding collections and does not render source-file diffs.
- Observation: draft-versus-official pairing rules already exist in the engine, but there is no current review-focused report built on top of them.
  Evidence: `src/sattlint/engine.py` resolves code files with draft-mode fallback from `.s` to `.x`, and `src/sattlint/app_analysis.py` already labels analyzed sources as `draft` or `official` from the suffix, but no current `src/sattlint/devtools/` module emits a code-review artifact for paired source files.
- Observation: the checked-in test corpus currently lacks an obvious same-stem `.s`/`.x` fixture pair.
  Evidence: a repository scan of committed `tests/**` source fixtures found many `.s` fixtures and a few `.x` fixtures, but no immediately usable same-basename pair for review-report coverage.

## Decision Log

- Decision: implement this as a new direct devtools command instead of overloading `src/sattlint/devtools/refactoring.py`.
  Rationale: refactoring compares one file before and after a transformation, while this feature compares two different source artifacts that already exist on disk. The workflows are adjacent, but the user-facing contract is different enough that a dedicated module keeps the scope legible.
  Date/Author: 2026-05-28 / Copilot (GPT-5.4)
- Decision: support explicit pair inputs before broad workspace auto-discovery.
  Rationale: the current repository does not already contain many checked-in `.s`/`.x` pairs, so a reliable one-pair workflow is the smallest observable contract. Auto-discovery can then reuse the same comparison core for workspaces that do keep draft and official files side by side.
  Date/Author: 2026-05-28 / Copilot (GPT-5.4)
- Decision: emit both Markdown and JSON artifacts, with Markdown as the human-first review surface.
  Rationale: the user request is specifically about easier code review, so the primary artifact should be readable in a PR or attached report. JSON is still needed for scripting, tests, and later pipeline integration.
  Date/Author: 2026-05-28 / Copilot (GPT-5.4)
- Decision: classify layout-only drift instead of hiding it.
  Rationale: code review becomes easier when formatting-only changes are called out clearly, but reviewers still need access to the raw diff. The report should therefore distinguish layout-only drift from structural drift while keeping the underlying diff visible.
  Date/Author: 2026-05-28 / Copilot (GPT-5.4)
- Decision: keep the first slice out of the interactive CLI menus.
  Rationale: `src/sattlint/devtools/` already supports direct `python -m` entry points for specialized workflows, and adding menu routing would widen the change into `src/sattlint/app.py` and menu tests before the core report contract is proven useful.
  Date/Author: 2026-05-28 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This section is intentionally incomplete until implementation finishes. The intended outcome is a small, review-oriented devtools feature that reuses existing diff-building and parsing seams instead of adding another disconnected comparison script. The main risk to watch is over-design: the feature only needs to make `.s` versus `.x` review practical, not introduce a general source-to-source transformation engine.

## Context and Orientation

In this repository, `.s` files are draft SattLine program sources and `.x` files are official program sources. That distinction is already part of the runtime model. `src/sattlint/engine.py` keeps explicit draft-versus-official lookup rules, including draft-mode fallback behavior that tries `.s` before `.x`. `src/sattlint/app_analysis.py` also derives a human-facing `draft` or `official` label from the file suffix when it annotates variable-analysis reports.

The closest existing implementation seam is `src/sattlint/devtools/refactoring.py`. That module is a preview-first tool for deterministic rewrites. It already knows how to build unified diff lines, summarize added and removed lines, write JSON artifacts, and expose a stable direct-command contract with `--workspace-root`, `--format`, and `--output-dir`. Those behaviors are useful here even though no rewriting happens, because the requested feature also needs a readable diff artifact and a scriptable report.

`src/sattlint/devtools/differential.py` is related, but only in shape. It compares two collections of analyzer findings and emits a machine-readable summary of added, removed, and surviving findings. It does not compare source files or render review output, so it should be treated as a schema-style reference rather than the main owner surface.

There is no current checked-in module that turns a draft `.s` file and an official `.x` file into a code-review artifact. There is also no obvious same-basename `.s`/`.x` pair in the current test fixtures, so this plan must create its own tiny paired fixtures under `tests/fixtures/` rather than borrowing an accidental sample.

In this plan, a `pair` means one draft source file and one official source file that represent the same logical program under review. In the simplest case they share the same basename and differ only by suffix, for example `WidgetReview.s` and `WidgetReview.x`. A `layout-only drift` means the raw text changes, but after applying the same layout normalization used by the refactoring tool, the files become textually identical. A `structural drift` means the normalized files still differ, so the reviewer should treat the diff as potentially semantic rather than mere formatting.

## Plan of Work

Start by extracting the generic diff helpers from `src/sattlint/devtools/refactoring.py` into a small shared helper such as `src/sattlint/devtools/_diff_rendering.py`. Move the unified-diff builder and the changed-line summary logic there without changing the refactoring tool's output contract. Keep the helper narrowly scoped to pure rendering and summary work so it can be reused by both tools without dragging refactoring-specific parsing or safety logic into the new report.

Once the shared helper exists, add a new module `src/sattlint/devtools/source_diff_report.py`. That module should expose a direct command named by its module path, following the same repository pattern as `src/sattlint/devtools/refactoring.py` and `src/sattlint/devtools/compare_audit_findings.py`. Its first responsibility is explicit pair comparison. Accept `--workspace-root`, `--draft-file`, and `--official-file` for one pair, and support repeated explicit pairs only if doing so does not complicate the first implementation. After the explicit path works, add optional discovery mode for workspaces that keep same-basename `.s` and `.x` files side by side. Discovery should only pair files when both suffixes exist for the same stem in the same directory tree; do not invent broad fuzzy matching in the first version.

For each pair, the new module should load both texts, compute a raw unified diff through the shared helper, and then compute a normalized comparison using the existing layout-normalization behavior from `src/sattlint/devtools/refactoring.py`. If the raw text differs but the normalized text does not, mark the pair as `layout-only`. If the normalized text still differs, mark the pair as `structural`. If either file fails to load or parse, keep the report entry and classify it as an error instead of silently skipping it.

The report contract should stay small and review-focused. The JSON artifact should include the workspace root, the compared pair paths, the per-pair classification, the raw changed-line counts, and the raw unified diff lines. The Markdown artifact should render a short run summary first, then one section per pair with the draft path, official path, classification, changed-line counts, and the unified diff inside a fenced `diff` block. Use collapsible `<details>` sections only if the generated Markdown stays readable in plain text; if that makes the output harder to scan locally, keep the format simple.

Do not widen the first milestone into top-level CLI or interactive menu wiring. The direct-module command is sufficient for the initial user-facing behavior and keeps the owner surface confined to `src/sattlint/devtools/` plus focused tests.

Then add the dedicated fixtures and tests. Create a new tiny fixture directory under `tests/fixtures/` that contains at least one same-basename pair with a real structural change and one same-basename pair whose differences are only layout noise. Keep the files minimal and valid SattLine so the tests prove the report behavior rather than parser breadth. Add `tests/devtools/test_source_diff_report.py` to cover explicit pair mode, discovery mode, layout-only classification, Markdown rendering, JSON rendering, and the clear error path when the requested pair does not exist.

Finish by validating the direct command end to end and checking the touched files with Ruff and Pyright. Because the diff-rendering helper is shared with `refactoring.py`, rerun the existing refactoring tests alongside the new source-diff tests before widening further.

## Concrete Steps

Run all commands from the repository root.

Inspect the closest owner surfaces before editing code:

    rg -n "_build_diff_lines|_diff_summary|_normalize_layout|--output-dir|--format" src/sattlint/devtools/refactoring.py
    rg -n "draft|official|\.s|\.x" src/sattlint/engine.py src/sattlint/app_analysis.py

After extracting the shared diff helper and implementing the new command, run the narrow test proof first:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/devtools/test_source_diff_report.py tests/devtools/test_refactoring.py -x -q --tb=short

Then exercise the user-facing command against the dedicated fixture pair:

    bash scripts/run_repo_python.sh -m sattlint.devtools.source_diff_report --workspace-root . --draft-file tests/fixtures/source_diff/WidgetReview.s --official-file tests/fixtures/source_diff/WidgetReview.x --output-dir artifacts/tmp/source-diff-report --format markdown

Expected observable behavior from that command:

    - stdout prints the Markdown report or the selected format output
    - `artifacts/tmp/source-diff-report/source_diff_report.md` is created
    - `artifacts/tmp/source-diff-report/source_diff_report.json` is created
    - the Markdown report contains a run summary and one pair section named `WidgetReview`
    - the pair section says whether the drift is `layout-only` or `structural`
    - the pair section includes a unified diff block that a reviewer can read without opening both files manually

If discovery mode is implemented in the same slice, run one explicit discovery smoke as well:

    bash scripts/run_repo_python.sh -m sattlint.devtools.source_diff_report --workspace-root tests/fixtures/source_diff --discover-pairs --output-dir artifacts/tmp/source-diff-discovery --format json

After the focused tests and direct-command smoke pass, run touched-file quality gates:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/devtools/_diff_rendering.py src/sattlint/devtools/refactoring.py src/sattlint/devtools/source_diff_report.py tests/devtools/test_source_diff_report.py tests/devtools/test_refactoring.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/devtools/_diff_rendering.py src/sattlint/devtools/refactoring.py src/sattlint/devtools/source_diff_report.py tests/devtools/test_source_diff_report.py

## Validation and Acceptance

Acceptance is based on a maintainer being able to review `.s` versus `.x` drift without assembling the comparison manually. A direct command must accept one explicit draft file and one explicit official file, generate a readable Markdown report, and write a matching JSON artifact. The report must keep the compared file paths visible, summarize how many lines changed, and show the actual unified diff.

The feature is not complete if it only prints raw diff lines to stdout without any review structure. The report must explicitly classify whether the pair differs only by layout normalization or still differs after normalization. Missing or invalid pair inputs must produce a stable error entry or error message instead of a silent empty report.

Focused tests must prove at least these behaviors: explicit pair success, layout-only classification, structural classification, missing-pair failure, and report artifact creation. Because the implementation reuses diff helpers from the refactoring tool, the nearest refactoring regression tests must continue to pass.

## Idempotence and Recovery

This plan is safe to execute incrementally. The direct command should be read-only by default and should only write report artifacts to a caller-chosen output directory. Re-running the command over the same pair should overwrite the same report files deterministically rather than appending or accumulating stale state.

If pair discovery returns no matches, the tool should exit with a clear message that no same-basename `.s`/`.x` pairs were found and should point the user at explicit `--draft-file` and `--official-file` usage. If Markdown rendering becomes too noisy or too large, simplify the presentation before adding more options; do not introduce HTML, external templating engines, or browser-only dependencies in the first slice.

If the helper extraction accidentally changes `src/sattlint/devtools/refactoring.py` output, stop and restore output compatibility before continuing. The shared helper exists to reduce duplication, not to change an already shipped contract.

## Artifacts and Notes

Baseline facts captured when this plan was created:

    - `src/sattlint/devtools/refactoring.py` already contains `_build_diff_lines(...)`, `_diff_summary(...)`, JSON output, and `--output-dir`
    - `src/sattlint/devtools/differential.py` already defines a stable shape for added or removed change summaries, but it compares findings rather than source text
    - `src/sattlint/engine.py` treats `.s` as draft source and `.x` as official source
    - `src/sattlint/app_analysis.py` already maps `.s` and `.x` suffixes to the human-readable labels `draft` and `official`
    - the current committed fixture corpus did not provide an obvious same-basename `.s`/`.x` pair for this feature

Target artifact examples after implementation:

    artifacts/tmp/source-diff-report/source_diff_report.md
    artifacts/tmp/source-diff-report/source_diff_report.json

Target Markdown shape after implementation:

    # SattLint .s/.x Diff Report

    Compared pairs: 1
    Structural pairs: 1
    Layout-only pairs: 0
    Errors: 0

    ## WidgetReview

    Draft file: tests/fixtures/source_diff/WidgetReview.s
    Official file: tests/fixtures/source_diff/WidgetReview.x
    Classification: structural
    Changed lines: 6

    ```diff
    --- tests/fixtures/source_diff/WidgetReview.s
    +++ tests/fixtures/source_diff/WidgetReview.x
    @@ ...
    ```

The exact wording may change during implementation, but the report must stay recognizably review-focused and concise.

## Interfaces and Dependencies

The main owner surface for this work should be `src/sattlint/devtools/source_diff_report.py`. The shared helper should live in a small sibling module such as `src/sattlint/devtools/_diff_rendering.py`. `src/sattlint/devtools/refactoring.py` should import the shared diff-rendering helper once it exists, but it should keep owning layout normalization and refactoring safety checks.

The existing suffix and pairing knowledge lives in `src/sattlint/engine.py` and `src/sattlint/app_analysis.py`. Reuse those semantics rather than redefining what `.s` and `.x` mean in a new place. For Markdown and JSON emission, stay with the Python standard library plus existing repository helpers. Do not add a new templating or diff-rendering dependency for the first milestone.

Focused regression proof belongs in `tests/devtools/test_source_diff_report.py`, with tiny source fixtures under `tests/fixtures/source_diff/`. If the helper extraction changes refactoring behavior, keep `tests/devtools/test_refactoring.py` in the narrow validation slice as the compatibility guard.
