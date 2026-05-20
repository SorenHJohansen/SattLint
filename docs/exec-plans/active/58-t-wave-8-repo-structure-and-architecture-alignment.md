# T-Wave-8 Repo Structure and Architecture Alignment

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the 2026-05-19 repo-map and architecture review into a concrete cleanup slice. After this work lands, the repository root will match the canonical top-level layout enforced by repo audit, the short and long architecture docs will name the actual shipped surfaces, and a new contributor will be able to trace the CLI, GUI, LSP, editor-facing facade, and repo-audit surfaces from documentation straight to the owning files without guessing. The same docs should also distinguish documented architecture from actual runtime architecture so a maintainer can tell which entrypoints are central, which surfaces are preview-only, and which paths are stale or merely ceremonial.

The observable proof is that the repository no longer tracks undocumented scratch or generated entries at the root, `sattlint-repo-audit --profile quick` no longer reports `unexpected-tracked-root-entry` or `tracked-generated-artifacts` for the current tree, and the docs in `AGENTS.md`, `docs/repo-map.md`, `docs/architecture.md`, and `ARCHITECTURE.md` all point at the current module names and package layout.

## Progress

- [x] (2026-05-19) Create the ExecPlan from the repo-map and architecture review. Confirm the main mismatches: undocumented `src/sattlint_gui/`, stale `arch_linter.py` references, incomplete documentation of `src/sattlint/editor_api.py`, and tracked root clutter outside the canonical allowlist.
- [ ] Classify the tracked root clutter into reusable tooling versus disposable probe or generated residue, then remove or relocate every non-canonical entry.
- [ ] Add ignore coverage so local Node dependencies and Pyright probe outputs stop reappearing at the repository root.
- [ ] Update the architecture documentation stack so `AGENTS.md`, `docs/repo-map.md`, `docs/architecture.md`, and `ARCHITECTURE.md` describe the same shipped surfaces, module names, and actual runtime ownership.
- [ ] Produce one concise actual-runtime-architecture map across the architecture docs so maintainers can see the real entrypoints, central modules, high-level call flow, and any preview-only or disconnected surfaces.
- [ ] Re-run focused repo-audit, context-health, and architecture-lint proof and record the observed results in this file.

## Surprises & Discoveries

- Observation: the repository already carries a machine-readable definition of the canonical root layout.
  Evidence: `src/sattlint/devtools/repo_audit_shared.py` defines `TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST`, and that allowlist does not include `node_modules`, `package.json`, `package-lock.json`, root-level Pyright probe JSON files, or one-off helper scripts such as `compare.py`.

- Observation: the short architecture docs omit a shipped package.
  Evidence: `pyproject.toml` publishes `sattlint-gui = "sattlint_gui.main:gui"`, but `docs/repo-map.md`, `docs/architecture.md`, and the quick reference text in `AGENTS.md` do not currently describe `src/sattlint_gui/` as a first-class surface.

- Observation: the long architecture document still names a tool that no longer exists under that module name.
  Evidence: `ARCHITECTURE.md` references `arch_linter.py`, while the actual implementation and tests live under `src/sattlint/devtools/layer_linter.py` and `tests/devtools/test_layer_linter.py`.

- Observation: the root ignore rules do not currently protect the repo from the exact residue found in the review.
  Evidence: `.gitignore` ignores `build/`, `dist/`, `coverage.xml`, and `htmlcov/`, but it does not ignore `node_modules/` or the root-level `tmp-pyright-*` and `temp_pyright*` families that are already present in the tree.

- Observation: the current architecture docs describe shipped surfaces better than they describe runtime centrality.
  Evidence: the reviewed docs name the CLI, GUI, LSP, editor facade, and repo-audit packages, but they do not yet give one concise map from checked-in entrypoints to the first owning modules or distinguish validated central paths from preview-only or disconnected surfaces.

- Observation: several tracked directories and files behave like generated or machine-local residue rather than stable source.
  Evidence: the tracked tree currently includes `node_modules/`, `artifacts/audit-full-current.tmp-g_ap8njm/`, root-level probe outputs such as `pyright_output.json` and `tmp-pyright-devtools-strict.json`, and generated reports such as `artifacts/generated/precommit-fast-audit/status.json` and `artifacts/generated/repo-health.json`.

- Observation: some checked-in artifact families are clearly policy inputs, while neighboring files in the same broad area look like stale snapshots.
  Evidence: repo docs and checks explicitly reference `artifacts/analysis/coverage_ratchet.json`, `artifacts/analysis/file_debt_ratchet.json`, `artifacts/analysis/structural_budget_ratchet.json`, and `metrics/ratchet.json`, but the same evidence trail does not justify keeping point-in-time outputs such as `artifacts/analysis/bandit.json`, `artifacts/analysis/pyright.json`, `artifacts/analysis/pytest.junit.xml`, or `metrics/history/2026-05-03-ai-first-baseline.json` as canonical checked-in sources.

## Decision Log

- Decision: treat the root `package.json`, `package-lock.json`, and `node_modules/` tree as accidental root clutter unless this plan finds a checked-in consumer that cannot be relocated.
  Rationale: the root Node surface is undocumented, outside the repo-audit allowlist, and separate from the actual shipped VS Code client under `vscode/sattline-vscode/`. The default fix is removal, not canonization.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: make the repository match `docs/quality-gates.md` rather than weakening the quality-gate text.
  Rationale: the current quality-gates doc already states the desired canonical-root policy. The drift is in the tree, not in that policy document.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: document `src/sattlint/editor_api.py` as a compatibility facade distinct from `src/sattlint/core/`.
  Rationale: the review found that the editor-facing boundary is currently split across those paths. Hiding `editor_api.py` keeps the docs shorter but makes the actual entry surface harder to find.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: add one explicit actual-runtime-architecture map instead of letting several partial docs imply it indirectly.
  Rationale: AI-generated repositories can accumulate documented, intended, and actual architectures at the same time. One concise runtime map is cheaper to keep honest than several aspirational descriptions.
  Date/Author: 2026-05-20 / Copilot (GPT-5.4)

- Decision: rename stale doc references to `layer_linter.py` instead of restoring an `arch_linter.py` alias.
  Rationale: the current code, tests, and published entrypoint already use `layer_linter`. Reintroducing the old name would expand the compatibility surface for no user benefit.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Fill this in after the cleanup lands. The final entry must state which root entries were removed, which reusable helpers were moved, which docs changed, and whether repo audit became clean for the targeted structural findings.

## Hygiene Review Inventory

The 2026-05-19 tracked-file hygiene review produced four implementation buckets that this plan owns.

### 1. Suspicious tracked paths

- Root Node surface that is outside the repo-audit allowlist and currently looks accidental: `package.json`, `package-lock.json`, and `node_modules/`.
- Tracked temp audit output: `artifacts/audit-full-current.tmp-g_ap8njm/`.
- Tracked root Pyright probe or scratch outputs: `probe_results.json`, `pyright_batch_probe_out.json`, `pyright_output.json`, `pyright_output_devtools.json`, `pyright_probe_cfg.json`, `pyright_probe_out.json`, `pyright_strict_devtools_results.json`, `tmp-pyright-*.json`, and `temp_pyright*`.
- Tracked root probe configuration spillover that does not yet have a stable owner surface: `pyrightconfig_probe.json`, `pyrightconfig_task.json`, `pyrightconfig_temp_probe.json`, `pyrightconfig_temp_strict.json`, and similar root-level one-off config files.
- Generated output trees that should justify themselves explicitly or leave the index: `artifacts/generated/precommit-fast-audit/`, `artifacts/generated/repo-health.json`, `artifacts/generated/ruff-current.json`, and `artifacts/generated/semantic-coverage.json`.
- Likely stale analysis snapshots mixed into a directory that also contains real ratchet inputs: `artifacts/analysis/bandit.json`, `artifacts/analysis/pyright.json`, `artifacts/analysis/pytest.json`, `artifacts/analysis/pytest.junit.xml`, `artifacts/analysis/ruff.json`, `artifacts/analysis/vulture.json`, `artifacts/analysis/environment.json`, and `artifacts/analysis/impact_analysis.json`.
- Dated metrics history snapshot with no confirmed live consumer: `metrics/history/2026-05-03-ai-first-baseline.json`.

### 2. Ignore coverage gaps

- Add root ignore coverage for `node_modules/`.
- Add root ignore coverage for `tmp-pyright-*.json`.
- Add root ignore coverage for the `temp_pyright*` family.
- Add root ignore coverage for root Pyright output spill such as `pyright_output*.json`, `pyright_probe*.json`, `probe_results.json`, and sibling temporary config outputs unless they are moved under a stable tool-owned path.
- Add ignore coverage for full-audit temp directories such as `artifacts/audit-full-current.tmp-*/`.
- Add ignore coverage for local CodeGraph output such as `codegraph-index.surql`.

### 3. Regenerate rather than commit

- Treat `artifacts/generated/precommit-fast-audit/` as disposable quick-audit output.
- Treat `artifacts/generated/repo-health.json` as stale unless the health pipeline is intentionally rewritten to use `artifacts/generated/` instead of the current `artifacts/health/` path.
- Treat `artifacts/audit-full-current.tmp-*/` as ephemeral run output.
- Treat root Pyright probe results and temporary configs as rerunnable local outputs, not source.
- Separate `artifacts/analysis/` into policy inputs that must remain checked in versus scanner snapshots that should be regenerated on demand.

### 4. Contributor workflow risks

- Local `npm install`, CodeGraph runs, or Pyright experiments can currently dirty the root because the ignore rules are incomplete.
- The tracked vendor and artifact trees add substantial review noise and repository weight, especially under `node_modules/` and `artifacts/analysis/`.
- The tracked tree does not currently match the canonical root policy encoded in `TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST`, which makes repo-audit guidance less trustworthy to contributors.
- The repository currently presents at least two repo-health locations, `artifacts/health/` and `artifacts/generated/repo-health.json`, which risks stale reads by humans or automation.

## Context and Orientation

This slice is about structure and discoverability, not feature behavior. In this repository, a "canonical top-level layout" means the set of root entries that `src/sattlint/devtools/repo_audit_shared.py` allows to be tracked in git without triggering the public-readiness finding `unexpected-tracked-root-entry`. That allowlist already treats the root as a small routing surface containing documentation, Python packaging metadata, `scripts/`, `src/`, `tests/`, `artifacts/`, `metrics/`, and the `vscode/` client folder.

The main runtime packages live under `src/`. `src/sattline_parser/` is the parser core. `src/sattlint/` is the main application, analyzers, reporting, config, and devtools surface. `src/sattlint_lsp/` is the language server. `src/sattlint_gui/` is the desktop GUI package and already has a published console script in `pyproject.toml`. `src/sattlint/editor_api.py` is a public compatibility facade for editor-facing consumers, while `src/sattlint/core/` contains the shared semantic helpers behind that facade.

The docs that must align are `AGENTS.md`, `docs/repo-map.md`, `docs/architecture.md`, `docs/quality-gates.md`, and `ARCHITECTURE.md`. The first four are the fast-routing surfaces that AI and humans read first. `ARCHITECTURE.md` is the deeper design document they are sent to next. The review found that `docs/quality-gates.md` is already describing the correct root-layout policy, so the implementation should keep that document stable unless a command name or validation step truly changes.

The root clutter called out by the review falls into three groups. The first group is clearly generated or disposable residue, such as the committed `node_modules/` tree and root-level Pyright probe outputs like `tmp-pyright-*.json`, `temp_pyright*.json`, and `pyright_probe_out.json`. The second group is ad hoc helper scripts such as `compare.py`, `process_pyright.py`, and `pyright_audit.py`; these must either move under `scripts/` with names that explain their purpose or be deleted. The third group is undocumented root packaging state, namely `package.json` and `package-lock.json`; this plan treats that as removable unless a checked-in workflow proves otherwise.

The hygiene review narrowed the first-pass deletion targets further. `node_modules/` and `artifacts/audit-full-current.tmp-*/` already look purely disposable. The root Pyright result and temp-config files should be treated the same way unless the executor finds a documented consumer and relocates the file under an existing tool-owned surface. Within `artifacts/analysis/`, the ratchet and policy inputs have a stronger claim to stay checked in than scanner snapshots; the cleanup must keep the former while challenging the latter one by one.

## Plan of Work

Start by cleaning the root layout. Use `git ls-tree --name-only HEAD` and the allowlist in `src/sattlint/devtools/repo_audit_shared.py` to enumerate every tracked root entry that does not belong. For each such entry, decide once whether it is reusable tooling or disposable residue. Reusable tooling must move under `scripts/` or another existing owner directory in the same change, and any path references in docs or commands must be updated. Disposable residue must be deleted from version control rather than renamed into another root-level stash.

Treat the root Node surface as disposable unless the executor finds a checked-in command or test that actually imports or shells into it. If no such consumer exists, remove `package.json`, `package-lock.json`, and `node_modules/` from the repository root and add ignore coverage so a local `npm install` cannot recreate the same drift in a later change. Do not move this surface into `vscode/sattline-vscode/`; that folder is already a separate shipped extension with its own `package.json`, and merging the two would blur unrelated ownership.

After the root cleanup, harden the ignore rules. Update `.gitignore` so the exact classes of residue found in the review are ignored at the root. At minimum, cover `node_modules/`, `tmp-pyright-*.json`, and the `temp_pyright*` family. If any reusable Pyright probe configuration truly needs to remain checked in, move it under an existing analysis or script surface and give it a stable name instead of keeping probe artifacts at the root.

As part of the same pass, decide whether `codegraph-index.surql` is local-only output in this repository. If it is, ignore it explicitly so CodeGraph use does not keep reintroducing root noise. Also add ignore coverage for `artifacts/audit-full-current.tmp-*/` so future full-audit runs do not recreate tracked temp directories.

Then align the docs. Update `AGENTS.md` so the quick-reference purpose sentence and any repo-map guidance acknowledge the GUI surface where appropriate. Update `docs/repo-map.md` to add `src/sattlint_gui/` and to name `src/sattlint/editor_api.py` explicitly as the editor-facing compatibility facade, separate from `src/sattlint/core/`. Update `docs/architecture.md` to include the same surfaces in the short layering summary. Update `ARCHITECTURE.md` to replace `arch_linter.py` with `layer_linter.py`, keep the GUI section accurate, and make the editor-facing boundary description consistent with the short docs. As part of that same pass, add one concise actual-runtime-architecture map that starts from the checked-in entrypoints, names the first owning modules they reach, and makes preview-only or disconnected surfaces explicit instead of implied.

Do not weaken `docs/quality-gates.md`. The structural review already found that its root-hygiene rule is correct. The implementation goal is to make the repository and the other architecture docs agree with that policy, not to broaden the allowlist to fit accidental residue.

## Concrete Steps

Run all commands from the repository root.

First, capture the tracked root layout and the structural-policy anchor:

    git ls-tree --name-only HEAD | sort
    sed -n '25,80p' src/sattlint/devtools/repo_audit_shared.py

Before deleting or moving any root helper file, prove whether it is actually used:

    rg -n "compare\.py|process_pyright\.py|pyright_audit\.py|package\.json|package-lock\.json|node_modules|better-sqlite3" .

Remove or relocate every non-canonical tracked root entry. For reusable scripts, move them under `scripts/` and rename them if the current name does not communicate ownership. For disposable residue, delete the tracked file or directory outright.

Classify the artifact trees before deleting broadly. Keep checked-in policy inputs with demonstrated consumers, such as the ratchet JSON files under `artifacts/analysis/` and `metrics/ratchet.json`. Challenge neighboring run snapshots individually: if the executor cannot point to a current code or workflow consumer, remove the file from git and rely on regeneration instead.

Update the docs named in this plan so they all describe the same shipped surfaces and module names.

After the edits land, run the narrow proof for the touched structural and documentation seams:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/_repo_audit_part3.py tests/test_recommendation_routing.py tests/test_repo_audit_entrypoints_finish_gate.py tests/devtools/test_context_health.py tests/devtools/test_layer_linter.py -x -q --tb=short
    python scripts/context_health.py --check

Then run one observable repo-level check that exercises the public-readiness rule on the current working tree:

    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile quick --output-dir artifacts/audit-plan-58

Inspect the resulting findings and confirm that the structural findings `unexpected-tracked-root-entry` and `tracked-generated-artifacts` no longer appear for the repository root.

## Validation and Acceptance

Acceptance is behavioral, not editorial. A human reviewer should be able to open `AGENTS.md`, `docs/repo-map.md`, `docs/architecture.md`, and `ARCHITECTURE.md` and find the CLI, GUI, LSP, editor-facing facade, repo-audit, and layer-lint surfaces without guessing or cross-correcting stale names. Those docs must also make the actual runtime architecture legible enough that a maintainer can tell which entrypoints are live, which modules are central, what calls what at a high level, and which surfaces are preview-only or disconnected. `git ls-tree --name-only HEAD` should no longer show `node_modules` or the reviewed root probe clutter. The quick repo-audit run for this slice must stop emitting the structural findings `unexpected-tracked-root-entry` and `tracked-generated-artifacts` for the current tracked tree. The focused pytest and context-health commands above must pass.

For the artifact half of the slice, acceptance also means contributors can tell which files are canonical inputs and which are regenerate-on-demand outputs. In practice that means the remaining checked-in `artifacts/analysis/` and `metrics/` files must each have an obvious policy or workflow consumer, while disposable snapshots such as temp audit directories, root probe files, and stale generated health outputs have been removed or moved behind stable generation commands.

If the executor discovers a real, supported root Node workflow, acceptance changes slightly: the workflow must move under a documented owner surface, be named in the architecture docs, and stop living as an undocumented top-level package. Simply documenting the existing accidental root layout is not sufficient.

## Idempotence and Recovery

This cleanup is safe to apply in small passes. Re-running the root inspection commands is harmless. Removing generated residue is idempotent because the files should stay gone after the ignore rules land. If a supposedly disposable helper turns out to be used, recover by moving it under `scripts/` in the same change and updating every path reference found by `rg`; do not restore it to the root. If repo audit still reports root-layout findings after the first cleanup pass, compare the remaining tracked entries against `TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST` and remove the next out-of-policy entry rather than broadening the allowlist.

## Artifacts and Notes

Current facts gathered during plan creation:

    pyproject.toml publishes:
      sattlint = sattlint.app:cli
      sattlint-gui = sattlint_gui.main:gui
      sattlint-lsp = sattlint_lsp.server:cli

    ARCHITECTURE.md still says:
      arch_linter.py enforces layered architecture

    The root allowlist in src/sattlint/devtools/repo_audit_shared.py does not include:
      node_modules
      package.json
      package-lock.json
      compare.py
      process_pyright.py
      pyright_audit.py

    The current root .gitignore does not ignore:
      node_modules/
      tmp-pyright-*.json
      temp_pyright*

    Additional hygiene review targets:
      artifacts/audit-full-current.tmp-*/
      codegraph-index.surql
      artifacts/generated/precommit-fast-audit/
      artifacts/generated/repo-health.json

## Interfaces and Dependencies

The implementation touches repository policy, not runtime semantics. The controlling structural interface is `src/sattlint/devtools/repo_audit_shared.py`, especially `TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST` and `GENERATED_PATH_PREFIXES`. The controlling packaging interface is `pyproject.toml`, which already defines the shipped Python entrypoints. The controlling documentation interfaces are `AGENTS.md`, `docs/repo-map.md`, `docs/architecture.md`, `docs/quality-gates.md`, and `ARCHITECTURE.md`.

Do not add new external dependencies to solve this slice. Reuse the existing Python tooling, the existing quick repo-audit command, and the existing layer-linter surface. If a helper must survive, keep it in Python under `scripts/` unless there is a strong, demonstrated reason to place it somewhere else. If a Node-based tool is truly required in the future, give it a dedicated documented owner directory and validation path rather than reviving an undocumented root package.
