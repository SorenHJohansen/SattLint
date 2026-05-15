# T-Wave-7 Public Calendar-Version Release Readiness

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes SattLint ready for its first stable public release instead of a repo that is merely usable by its current maintainers. After this work lands, an external user should be able to read the top-level docs, install the published package without cloning the repo, run the main CLI and language-server entry points with a version string that matches the release, and understand where to get help or report problems. The maintainers should also be able to rehearse the release before tagging a calendar-versioned release such as `v2026.5`, then publish with the same validated path.

The observable proof is concrete. From a clean checkout and a built distribution, the release gate must be able to build the package, pass `twine check`, install the wheel into a clean environment, run `sattlint --version`, run `sattlint syntax-check` against a checked-in sample file, boot the repo-audit CLI, and produce a passing public-readiness report. The public repository surface must also explain the support contract in plain language: what is stable, what is preview-only, which platforms are supported, and how outside users should get support or report security issues.

## Progress

- [x] (2026-05-15) Created this ExecPlan and captured the current baseline: `pyproject.toml` still uses the beta classifier, package version is `0.1.1`, `src/sattlint_lsp/server.py` reports `0.1.0`, `vscode/sattline-vscode/package.json` and `extension.js` also report `0.1.0`, and the extension publisher is still `local`.
- [x] (2026-05-15) Confirmed that core public-repo hygiene already exists in part: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, issue templates, CI workflows, and a tag-driven PyPI publish workflow are checked in.
- [x] (2026-05-15) Captured the main public-facing gaps: the README still speaks to coworkers and local-folder installs, `CODE_OF_CONDUCT.md` and `SUPPORT.md` do not exist, and the publish workflow builds and runs `twine check` but does not smoke-install the built artifact before publishing.
- [x] (2026-05-15) Verified that the current worktree is not a clean release baseline: attempting `sattlint.devtools.repo_audit --check public-readiness` crashed because locally modified MMS analyzer files are out of sync. Release sign-off must therefore use a clean checkout or CI artifact, not the current dirty worktree.
- [x] (2026-05-15) Chose calendar versioning for stable public releases: use PEP 440-compatible `YYYY.M` for the first stable release in a month, and `YYYY.M.N` only when multiple stable releases ship in that same month.
- [ ] Define the stable-release support contract and classify every shipped surface as stable, preview, or internal-only.
- [ ] Rewrite the public-facing top-level docs so an external user can install, evaluate, and support SattLint without internal context.
- [ ] Add the missing community-health files and wire them into the GitHub-facing issue and support flow.
- [ ] Align all version surfaces across package metadata, CLI, LSP, changelog, and the local VS Code client docs.
- [ ] Add a repo-owned release rehearsal path that builds, validates, smoke-installs, and exercises the shipped artifact before any publish step runs.
- [ ] Extend repo-audit or adjacent validation so the new calendar-version public-readiness requirements stay enforceable after the release.
- [ ] Run one clean release-candidate rehearsal, record the proof, then cut the first stable calendar-version tag from the validated path.

## Surprises & Discoveries

Observation: the repository already has most of the infrastructure expected from a public project.
Evidence: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `CONTRIBUTING.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/`, and the existing repo-audit public-readiness check are all present.

Observation: the remaining release gap is mostly contract and verification depth, not missing package-upload automation.
Evidence: `.github/workflows/publish.yml` already builds distributions, runs `twine check`, uploads artifacts, and publishes to PyPI on `v*` tags.

Observation: version drift is already visible across public entry points.
Evidence: `src/sattlint/__version__.py` is `0.1.1`, while `src/sattlint_lsp/server.py`, `vscode/sattline-vscode/package.json`, `vscode/sattline-vscode/README.md`, and `vscode/sattline-vscode/extension.js` still use `0.1.0`.

Observation: the README is still written for an internal audience rather than first-time outside users.
Evidence: `README.md` says it is written for coworkers, assumes a copied local folder, and documents `pipx install .` rather than a published install path.

Observation: the current dirty worktree can hide or invent release failures.
Evidence: running `bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile full --check public-readiness --skip-pipeline --output-dir artifacts/audit-public-readiness-plan` failed at import time, and `git status --short -- src/sattlint/analyzers/_mms_interface_analysis.py src/sattlint/analyzers/mms.py` showed a modified `mms.py` plus an untracked `_mms_interface_analysis.py`.

Observation: the repo health snapshot is encouraging but not sufficient for a stable-launch decision.
Evidence: `docs/generated/repo-health.md` reports zero audit findings and passing ratchets at `88.26%` coverage, yet it still reports `22` over-budget functions and `3` over-budget classes and does not prove published-artifact installability.

## Decision Log

Decision: do not make the first stable public release depend on closing every active structural or AI-process exec plan.
Rationale: stable public release is primarily about documented support boundaries, green validation, consistent packaging, and reproducible release proof. Open refactor work can continue after the first stable calendar-versioned release if it does not break the supported public contract.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: use PEP 440-compatible calendar versioning for public releases.
Rationale: the requested user-facing identity is time-based rather than milestone-number-based. `YYYY.M` communicates release recency clearly, sorts correctly for Python packaging, and allows `YYYY.M.N` for multiple stable releases in one month without inventing a separate scheme.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: treat clean-checkout and CI-generated proof as the only authoritative release baseline.
Rationale: the current worktree is already dirty in analyzer files, so local state is not trustworthy enough for final release sign-off.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: keep the existing tag-driven publish workflow, but require a dry-run or rehearsal path that executes the same build and smoke checks without publishing.
Rationale: the repo already has a sound publish trigger. The missing capability is safe rehearsal before the irreversible tag-and-publish step.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: scope the first stable release to the Python package and the repository-facing experience, while treating the VS Code client as preview unless a non-local publisher and a public distribution story land in the same slice.
Rationale: the current extension manifest still uses publisher `local`, which is not a public marketplace story. The repo can still ship a stable CLI, repo-audit surface, and Python LSP without blocking on marketplace release.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: define and publish a support contract instead of implying that every existing command and UI surface is equally mature.
Rationale: a stable calendar-versioned release still needs stable expectations. Clear `stable`, `preview`, and `internal` labels are better than optimistic silence.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At creation time, no release-readiness code or docs have changed yet. The current outcome is a concrete cross-cutting plan that narrows the first stable calendar-versioned release to a realistic public contract: stable packaging, version consistency, public-facing docs, enforceable community and support policy, and a rehearsable release gate.

The main risk is over-scoping. This plan explicitly avoids waiting for every non-blocking structural cleanup, because that would delay the first stable calendar-versioned release without materially improving the first external-user experience. The follow-through work should stay focused on what an outside user and maintainer can actually observe.

## Context and Orientation

Several repository surfaces already carry pieces of a public release story, but they are not synchronized yet. `pyproject.toml` defines the package metadata, scripts, dependencies, Python floor, and classifiers. `src/sattlint/__version__.py` is the canonical Python package version used by the CLI parser in `src/sattlint/cli/entry.py`. `src/sattlint_lsp/server.py` exposes the language server process and currently hard-codes its own version string. `vscode/sattline-vscode/package.json`, `vscode/sattline-vscode/extension.js`, and `vscode/sattline-vscode/README.md` describe the local VS Code client that talks to that language server.

The release automation surface already exists. `.github/workflows/ci.yml` runs the main trust gates. `.github/workflows/publish.yml` builds and publishes distributions on version tags. `src/sattlint/devtools/repo_audit.py`, `src/sattlint/devtools/repo_audit_entrypoints.py`, and `src/sattlint/devtools/_repo_audit_reporting.py` already define a public-readiness audit category, but that category currently checks only the basics: required files, project URLs, CI presence, generated publish-leak paths, and root-layout hygiene.

The public-facing docs are spread across `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, and `docs/references/cli-commands.md`. Today those files are good enough for maintainers, but not yet ideal for first-time public users. The README is the most visible problem because it still assumes local folder copies and coworker context.

In this plan, a `support contract` means the exact set of platforms, commands, and user-facing surfaces the maintainers promise to keep working across later stable releases. A `release rehearsal` means running the build and published-artifact smoke checks without actually publishing to PyPI. A `smoke test` means a small end-to-end check that proves the shipped artifact can start and do useful work, such as printing its version or syntax-checking one known-valid checked-in sample file.

In this plan, `calendar versioning` means the release number carries the release date instead of a milestone number. The chosen format is `YYYY.M` for the first stable release in a month, for example `2026.5`, and `YYYY.M.N` if more than one stable release ships in that same month, for example `2026.5.1`.

The checked-in sample file for release smoke should be `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s`. That file is already part of the repository and is suitable for a syntax-check proof that does not depend on private user code.

## Plan of Work

Start by writing down what the first stable calendar-versioned release actually promises. Add one small public support matrix, either in a new file such as `docs/references/public-support-matrix.md` or as a clearly linked top-level doc section, that classifies each shipped surface as `stable`, `preview`, or `internal-only`. The stable set should include only the commands and platforms the team is willing to validate in release rehearsal. A pragmatic first stable contract is the Python package on Linux and Windows, the `sattlint` CLI, the non-interactive `syntax-check` path, the repo-audit surface, and the Python LSP server. The GUI and the VS Code client should either gain a real public distribution story in this slice or be marked preview explicitly.

Then rewrite the public docs around that contract. Update `README.md` so the first screen answers four questions for an outside user: what SattLint is, how to install it from a published artifact, which platforms are supported, and where stable versus preview features begin and end. Keep contributor and source-install details in `CONTRIBUTING.md`; do not leave the public README centered on copying a local folder from a coworker. Update `CHANGELOG.md` with a planned release section for the first stable calendar-versioned release that explains what becomes stable and any incompatible changes from `0.1.x`. Add `CODE_OF_CONDUCT.md` and `SUPPORT.md`, then point issue templates or repo links at those files so the community-health surface is complete.

After that, align version and release metadata everywhere it is user-visible. Update `pyproject.toml` from beta to stable when the release criteria are actually satisfied, not before. Keep `src/sattlint/__version__.py` as the single Python source of truth, and make the LSP server and local VS Code client derive or mirror the same release value intentionally. The first stable release should use the agreed calendar version for its release month, for example `2026.5` if it ships in May 2026. If the VS Code client remains preview-only, its README must say so plainly even if its version is still synchronized.

Next, deepen the publish gate. Extend `.github/workflows/publish.yml` so the build job does more than `python -m build` plus `twine check`. Add a repo-owned smoke validator such as `src/sattlint/devtools/release_smoke.py` that creates a temporary virtual environment, installs the built wheel, runs `sattlint --version`, runs `sattlint syntax-check tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s`, runs `sattlint repo-audit --profile full --list-checks` or an equivalent boot check, and writes compact JSON results to a chosen output directory. The publish workflow should run this validator before the final publish step. Add a `workflow_dispatch` rehearsal mode to the same workflow, or add a separate release-candidate workflow, so maintainers can run the exact build-and-smoke path without publishing.

Once the smoke path exists, extend enforcement where it belongs. The existing public-readiness audit in `src/sattlint/devtools/_repo_audit_reporting.py` should be reviewed and widened only for requirements that can be checked reliably in-repo, such as the presence of `CODE_OF_CONDUCT.md`, `SUPPORT.md`, stable metadata, and explicit docs links. Do not teach repo-audit to rebuild wheels itself; keep artifact execution in the dedicated release-smoke path. Add focused tests in `tests/test_repo_audit.py` for any new public-readiness findings and add dedicated tests such as `tests/devtools/test_release_smoke.py` for the rehearsal tool.

Finish with one clean release-candidate proof run. Use a clean checkout or CI rehearsal artifact, run the release smoke, run the full repo audit, confirm version surfaces all report the chosen calendar version such as `2026.5`, and only then create the final tag. The final human-readable release note should come from the `CHANGELOG.md` entry and should be used again when creating the GitHub release page.

## Concrete Steps

Run all commands from the repository root. Use a clean checkout or a release-candidate branch for final proof.

First, verify the current repository health in a clean environment:

    python scripts/context_health.py --check
    python scripts/repo_health.py --check --audit-dir artifacts/audit
    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile full --output-dir artifacts/release-audit --fail-on high

Then validate the public-facing docs and community files once they are updated:

    python -m pre_commit run --files README.md CONTRIBUTING.md SECURITY.md CHANGELOG.md CODE_OF_CONDUCT.md SUPPORT.md docs/references/public-support-matrix.md
    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile full --check public-readiness --skip-pipeline --output-dir artifacts/release-public-readiness

Build and check the distribution that will become the release artifact:

    bash scripts/run_repo_python.sh -m build
    bash scripts/run_repo_python.sh -m twine check dist/*

Run the new release rehearsal tool against the built wheel:

    bash scripts/run_repo_python.sh -m sattlint.devtools.release_smoke --wheel dist/sattlint-2026.5-py3-none-any.whl --repo-root . --sample-file tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s --output-dir artifacts/release-smoke

Expected behavior from the release rehearsal:

    - it creates an isolated temporary environment
    - it installs the built wheel into that environment
    - `sattlint --version` prints the chosen calendar version, for example `sattlint 2026.5`
    - `sattlint syntax-check tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s` reports success
    - the repo-audit CLI boots successfully from the installed artifact and can at least list checks or run the public-readiness check
    - the tool writes a compact `status.json` and `summary.json` to `artifacts/release-smoke/`

Rehearse the GitHub automation without publishing:

    - trigger the release-candidate workflow manually, or run the publish workflow in dry-run mode if that is the chosen design
    - confirm the same build, `twine check`, and release-smoke steps pass in GitHub Actions
    - confirm the workflow uploads the built distributions and smoke-report artifacts

When the rehearsal passes, update `CHANGELOG.md` with the final release notes, create the matching calendar-version tag such as `v2026.5`, let `.github/workflows/publish.yml` publish, and create the matching GitHub release entry from the same changelog text.

## Validation and Acceptance

Acceptance for this plan is behavior, not only file edits. A first-time outside user must be able to land on the repository, understand what SattLint is, follow a published installation path, and run at least one stable command successfully without internal knowledge. The repository must expose a complete public support surface: install docs, contributing docs, security reporting, a code of conduct, and a support channel or support policy.

The release pipeline must be rehearsable. Before any real publish step runs, maintainers must be able to run the same build and smoke checks in a safe dry run. The final publish path must use that same verified artifact path rather than a separate, less-tested shortcut.

The release artifact must prove it is internally consistent. All user-visible version surfaces that are in scope for the stable release must report the same chosen calendar version. The wheel must install into a clean environment, the main CLI must boot, the syntax checker must accept the known-valid sample file, and the repo-audit CLI must start successfully. If the VS Code client remains preview-only, the docs must say so explicitly and the stable acceptance bar must not claim marketplace availability.

The public-readiness audit must pass in a clean checkout after the new docs and metadata land. Any new audit rule added by this plan must have focused regression coverage.

## Idempotence and Recovery

Documentation and metadata updates are safe to rerun. Rebuilding distributions and rerunning `twine check` are also safe as long as old `dist/` outputs are replaced or cleaned before final proof.

The release rehearsal tool must use temporary virtual environments and a caller-chosen output directory so repeated runs do not mutate the maintainer's primary environment. It should clean up temporary environments automatically on success and leave a readable failure summary on error.

Do not use the final calendar-version tag, for example `v2026.5`, as the first rehearsal. If a workflow or artifact check fails after a real publish tag is pushed, cleanup is harder and PyPI version reuse may be impossible. Always use the dry-run path first, then cut the real tag only after the same commands pass.

If a late-breaking issue appears after the version strings were updated but before the tag is published, keep the version bump in the release-candidate branch or revert it before merging. Do not leave `main` advertising a future calendar version if the release is not actually ready.

## Artifacts and Notes

Baseline facts captured when this plan was created:

    - `pyproject.toml` classifier: `Development Status :: 4 - Beta`
    - package version: `src/sattlint/__version__.py` -> `0.1.1`
    - LSP server version: `src/sattlint_lsp/server.py` -> `0.1.0`
    - VS Code client version: `vscode/sattline-vscode/package.json` -> `0.1.0`
    - VS Code client publisher: `vscode/sattline-vscode/package.json` -> `local`
    - missing public community files: `CODE_OF_CONDUCT.md`, `SUPPORT.md`
    - publish workflow already present: `.github/workflows/publish.yml`
    - current README wording still begins from an internal coworker context

Clean-baseline warning captured when this plan was created:

    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile full --check public-readiness --skip-pipeline --output-dir artifacts/audit-public-readiness-plan

    Traceback ...
    AttributeError: module 'sattlint.analyzers._mms_interface_analysis' has no attribute '_find_parameter_mapping'

    git status --short -- src/sattlint/analyzers/_mms_interface_analysis.py src/sattlint/analyzers/mms.py

     M src/sattlint/analyzers/mms.py
    ?? src/sattlint/analyzers/_mms_interface_analysis.py

This failure should be treated as a local worktree warning, not as final proof that the checked-in baseline is broken. The release sign-off path must rerun from a clean checkout.

## Interfaces and Dependencies

The public metadata owner remains `pyproject.toml`, with `src/sattlint/__version__.py` as the Python version source of truth. `src/sattlint/cli/entry.py` continues to expose `--version`. `src/sattlint_lsp/server.py` must stop drifting from the package version, either by importing the shared version or by receiving it from one compatibility source. If the VS Code client stays in scope, `vscode/sattline-vscode/package.json`, `vscode/sattline-vscode/extension.js`, and `vscode/sattline-vscode/README.md` must align with the chosen support label.

The recommended new internal validation seam is `src/sattlint/devtools/release_smoke.py`. That module should accept at least `--wheel`, `--repo-root`, `--sample-file`, and `--output-dir`, and should emit machine-readable status so CI and humans can consume the same proof. Focused tests should live in `tests/devtools/test_release_smoke.py`.

The existing repo-audit enforcement seam remains `src/sattlint/devtools/_repo_audit_reporting.py` plus the catalog wiring in `src/sattlint/devtools/repo_audit_entrypoints.py`. Any new public-readiness findings added there must be deterministic, cheap, and fully testable from repository state alone. Keep build-and-install execution out of repo-audit so the release-smoke path stays the only owner for artifact execution.

The workflow dependencies are `.github/workflows/ci.yml` and `.github/workflows/publish.yml`. If a new release-candidate workflow is added, keep it thin and reuse the same build plus release-smoke steps so the rehearsal and final publish paths do not diverge.
