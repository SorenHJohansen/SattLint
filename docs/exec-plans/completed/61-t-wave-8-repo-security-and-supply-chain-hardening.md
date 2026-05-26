# T-Wave-8 Repo Security And Supply-Chain Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan hardens the repository surfaces that can turn a release or local maintenance workflow into a security incident. After this work lands, SattLint's checked-in helper scripts will stop exposing local infrastructure with default credentials, the publish workflow will enforce a narrower trust boundary before PyPI publication, dependency monitoring will cover both the Python and Node trees, and repo-owned audit checks will start flagging workflow-hardening regressions instead of only checking whether a CI file exists.

The observable proof is straightforward. The checked-in legacy local search-helper scripts should be gone so the repository no longer teaches maintainers to expose a local database service with default credentials. A manual or tag-driven publish run should gate publication behind job-scoped permissions, an explicit protected environment, and the same smoke-validation path already required by the active release plans. The repository should also be able to prove that both `pip` and `npm` dependency trees are monitored and that repo-audit reports workflow-security defects such as excessive permissions, missing release protection, or raw unverified binary downloads.

## Progress

- [x] (2026-05-19 00:00Z) Create this ExecPlan and capture the current security-review baseline across `.github/workflows/`, `.github/dependabot.yml`, `package-lock.json`, legacy local search-helper scripts under `scripts/`, and `src/sattlint/devtools/`.
- [x] (2026-05-19 00:00Z) Confirm that GitHub Actions are already SHA-pinned, but the repo still has concrete hardening gaps: publish-wide `id-token` scope, no protected release environment, repeated unverified `actionlint` downloads, missing `npm` Dependabot coverage, and legacy local search-helper scripts that bind SurrealDB to `0.0.0.0` with `root/root` credentials.
- [x] (2026-05-19 00:00Z) Confirm that repo-audit currently checks only for CI-workflow presence in this area and does not yet enforce workflow hardening, release protection, or supply-chain policy.
- [x] (2026-05-20 00:00Z) Remove the checked-in legacy local search-helper scripts so the repository no longer carries a default-credential local database helper surface.
- [x] (2026-05-21 00:00Z) Harden `.github/workflows/publish.yml` with job-scoped permissions, the protected `pypi-release` environment reference, and a publish-job tag guard that keeps `workflow_dispatch` rehearsals non-publishing.
- [x] (2026-05-21 00:00Z) Add Node ecosystem monitoring and vulnerability scanning for the checked-in VS Code client manifest under `vscode/sattline-vscode/` alongside the existing Python dependency audit.
- [x] (2026-05-21 00:00Z) Extend repo-audit public-readiness checks with deterministic findings for workflow-level `id-token: write`, missing publish environments, missing publish tag guards, raw workflow downloads without visible checksum verification, missing npm monitoring, and unsafe helper-script database defaults.
- [x] (2026-05-21 00:00Z) Align `AGENTS.md`, `docs/quality-gates.md`, and nearby release-security guidance with the tightened trust model and the AI-only operating constraints.
- [x] (2026-05-21 00:00Z) Focused validation passed for the touched workflows, repo-audit rules, tests, and docs; the remaining live GitHub environment approval policy stays an operational follow-up outside this chat environment.

## Surprises & Discoveries

- Observation: third-party GitHub Actions are already pinned to full commit SHAs, so the main workflow supply-chain risk is not floating `uses:` references.
  Evidence: `.github/workflows/ci.yml`, `.github/workflows/lint.yml`, `.github/workflows/typing.yml`, `.github/workflows/repo-audit.yml`, and `.github/workflows/publish.yml` all use SHA-pinned `actions/*`, `astral-sh/setup-uv`, and `pypa/gh-action-pypi-publish` references.
- Observation: the strongest concrete local-infrastructure exposure was outside GitHub Actions.
  Evidence: three checked-in legacy local search-helper scripts started or documented SurrealDB with `--bind 0.0.0.0:3004 --user root --pass root`, which exposed a reachable service with default credentials if a maintainer ran those helpers on a networked machine.
- Observation: the publish workflow already uses PyPI trusted publishing, but the trust boundary is broader than necessary.
  Evidence: `.github/workflows/publish.yml` grants `id-token: write` at workflow scope and publishes on any `v*` tag push without an explicit protected `environment:` gate.
- Observation: dependency-audit coverage is partial rather than absent.
  Evidence: `.github/workflows/typing.yml` runs `pip-audit --skip-editable`, but `.github/dependabot.yml` only covers `pip` and `github-actions`, while `package-lock.json` contains a real Node dependency tree with `better-sqlite3` and an install script.
- Observation: repo-audit is currently too shallow to catch the workflow-security problems identified in the review.
  Evidence: `src/sattlint/devtools/_repo_audit_reporting.py` checks for the existence of `.github/workflows/*.yml` and reports `missing-ci-workflow`, but the reviewed code does not yet add findings for workflow permissions, release protection, direct unverified binary installs, or Node dependency-monitoring gaps.
- Observation: the first helper-script hardening milestone did not need a new shared shell helper.
  Evidence: all insecure SurrealDB defaults were confined to `scripts/codegraph-start-db.sh`, `scripts/codegraph-import.sh`, and `scripts/codegraph-index-export.sh`, and the repo had no existing shared CodeGraph shell utility seam to extend without widening the claim surface.
- Observation: the earlier `actionlint` download concern was already resolved before this implementation pass.
  Evidence: `.github/actions/setup-ci-tooling/action.yml` now installs `actionlint` through `scripts/install_actionlint.py` with per-platform SHA-256 selection and verification instead of a raw workflow download.
- Observation: the current Node surface is the VS Code client manifest rather than a checked-in root lockfile.
  Evidence: the repository currently contains `vscode/sattline-vscode/package.json` and no tracked `package-lock.json`, so the npm monitoring and audit wiring now targets that owner directory directly.

## Decision Log

- Decision: keep this slice separate from the broader CI-consolidation and public-release plans.
  Rationale: `docs/exec-plans/completed/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md` already owns workflow deduplication and rehearsal wiring, and `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` already owns public-release contract work. This plan is narrower: repository security invariants, supply-chain controls, and release trust boundaries.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: treat the legacy local search-helper scripts as in-scope even though they are developer utilities rather than the main product.
  Rationale: the user explicitly asked for security-sensitive review of helper scripts and untrusted-input or local-infrastructure paths. A checked-in script that opens a networked database with default credentials is a repo-security defect regardless of whether it ships to end users.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: enforce workflow-security rules in repo-audit rather than relying only on human review.
  Rationale: this repository is AI-only and already depends on machine-readable quality gates. The workflow trust model should therefore be checked by repo-owned automation, not only by reviewer memory.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: keep release rehearsal and artifact smoke execution in the existing release-plan seams, but make this plan responsible for the security boundary around those steps.
  Rationale: this avoids inventing a second release-smoke design. This plan should require a protected environment, narrower permissions, and deterministic release gating while reusing the artifact-execution work already planned elsewhere.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: cover both automated updates and vulnerability scanning for the Node tree.
  Rationale: `package-lock.json` proves that a real npm dependency graph exists. Dependabot coverage without scanning, or scanning without update visibility, would leave a partial blind spot.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The repository-owned work in this plan is now complete. The checked-in legacy CodeGraph helper scripts are gone, `publish.yml` narrows OIDC access to the publish job and routes publication through `pypi-release`, `typing.yml` now audits both Python and Node dependency surfaces, and repo-audit public-readiness checks now fail deterministically when those controls regress.

The remaining risk is GitHub-hosted policy drift rather than checked-in repository logic. The workflow now requires the named `pypi-release` environment, but the approval rules attached to that environment still live in GitHub configuration rather than in the repository tree. That operational boundary is acceptable for this slice because the checked-in workflow contract now makes the release gate explicit and machine-checkable from the repo side.

## Context and Orientation

The relevant security-sensitive surfaces live in four areas. The first is `.github/workflows/`, which owns CI, lint, typing, repo-audit, and publish behavior. The publish path is `.github/workflows/publish.yml`. Today it builds distributions and publishes on `v*` tags using PyPI trusted publishing, but it grants `id-token: write` at workflow scope instead of only at the publish job and does not show an explicit protected `environment:` gate.

The second area is dependency monitoring. Python packaging and dependencies are declared in `pyproject.toml`, and `.github/workflows/typing.yml` already runs `pip-audit --skip-editable`. The Node side is the checked-in VS Code client under `vscode/sattline-vscode/package.json`. That manifest is smaller than the earlier baseline review suggested, but it is still a real npm owner surface and now merits the same automated update and audit coverage as the Python tree.

The third area is local helper scripts under `scripts/`. `scripts/run_repo_python.sh`, `scripts/run_repo_python.py`, and `scripts/run_actionlint.py` use argv-based subprocess execution and are not the main risk from this review. The stronger issue was a legacy semantic-search helper trio that started or documented SurrealDB, bound it to all interfaces on port `3004`, and used the literal username and password `root` and `root`. In plain terms, those scripts could expose a reachable database service with known credentials on a developer workstation, so this plan now treats their removal as the correct hardening outcome.

The fourth area is repo-audit enforcement under `src/sattlint/devtools/`. `src/sattlint/devtools/repo_audit.py`, `src/sattlint/devtools/repo_audit_cli.py`, `src/sattlint/devtools/pipeline.py`, and `src/sattlint/devtools/_repo_audit_public_readiness.py` define what the repository checks automatically. Before this implementation pass, repo-audit could aggregate Bandit and other pipeline outputs, but the workflow-hardening logic was shallow: it checked whether CI workflows existed, not whether those workflows were secure. The completed slice closes that gap with repo-state-based checks for release permissions, publish environment wiring, npm monitoring, workflow downloads, and unsafe helper defaults.

This repository is AI-only. In this plan, `AI-only` means the repo expects machine-readable quality gates and automation-friendly contracts rather than relying on a human maintainer remembering subtle release or workflow-security rules. A `protected release environment` means a GitHub Actions environment that can hold approval rules and environment-scoped secrets or policy around the final publish step. A `supply-chain risk` means the risk that an external dependency, downloaded binary, or publish path introduces code or permissions that the repository did not verify adequately.

Two nearby plans are adjacent and must be treated as dependencies, not duplicates. `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` already owns the public release contract and release-smoke behavior. `docs/exec-plans/completed/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md` already owns workflow deduplication, shared setup, and release rehearsal wiring. This plan should reuse those seams and tighten their security constraints rather than redefining them.

## Plan of Work

Start by removing the checked-in legacy local search-helper scripts because they are the clearest concrete defect and the least dependent on the rest of the release pipeline. The repository already has Semble configured for semantic code search, so retaining a second checked-in helper stack that teaches maintainers to run SurrealDB with predictable credentials no longer makes sense. The hardening outcome for this surface is absence rather than a narrower default.

Next, harden the publish trust boundary in `.github/workflows/publish.yml`. Move `id-token: write` from workflow scope to the smallest job that actually needs it. Add an explicit `environment:` on the publish job so the final publish step can be protected independently from the build job. Keep the artifact build and smoke-validation path aligned with the active release plans, but make this plan responsible for ensuring that publication cannot happen through a broader or less-reviewed path than the rehearsal path. If GitHub-side policy requires a named environment such as `pypi-release`, document that exact name in the plan and in the workflow comments or adjacent docs.

Then close the dependency-monitoring blind spot. Extend `.github/dependabot.yml` with an `npm` entry for `/vscode/sattline-vscode` so the checked-in VS Code client manifest is monitored like the Python and workflow dependencies. Add a Node vulnerability scan in the appropriate owner workflow. Keep the implementation machine-readable and cheap enough for CI.

After the direct hardening changes exist, teach repo-audit to enforce them. Extend `src/sattlint/devtools/_repo_audit_public_readiness.py` and any needed supporting tests so repo-audit emits findings for checked-in workflow security defects such as workflow-level `id-token: write`, missing publish `environment:` protection, missing publish tag guards, direct unverified binary downloads in workflows, missing npm dependency-monitoring coverage when a tracked Node manifest exists, and any future checked-in helper scripts that bind a database to all interfaces or use hardcoded credentials. Keep these checks deterministic and repository-state-based. Repo-audit should not call GitHub APIs or inspect live environment settings beyond what the checked-in files can prove.

Finish by aligning the nearby docs and workflow guidance. Update `AGENTS.md` and `docs/quality-gates.md` only where they describe the release or security gate incorrectly after the changes. Add or adjust a short note in the workflow or security-facing docs so a novice can see that publish is protected, the legacy local helper scripts are removed, and both Python and Node dependency trees are monitored. Do not widen this into a full release-policy narrative; keep the docs updates narrowly tied to the new security contract.

## Concrete Steps

Run all commands from the repository root.

Capture the baseline workflow and helper-script defects before editing:

    rg -n "id-token|environment:|tags:|workflow_dispatch" .github/workflows/publish.yml
    rg -n "package-ecosystem" .github/dependabot.yml
    git grep -n -I "0.0.0.0:3004\|root --pass root\|SurrealDB" -- scripts
    rg -n "missing-ci-workflow|workflow_dir = root / \".github\" / \"workflows\"" src/sattlint/devtools/_repo_audit_reporting.py

After the helper-script removal lands, run a focused shell and docs sanity pass. If a small shell-test seam is added, run that exact test. At minimum, verify the repository no longer advertises or executes all-interface bind plus literal default credentials from checked-in helper scripts:

    git grep -n -I "0.0.0.0:3004\|root --pass root" -- scripts

After the workflow and Dependabot changes land, validate the YAML and the updated security expectations:

    python scripts/run_actionlint.py
    python -m pre_commit run --files .github/workflows/publish.yml .github/dependabot.yml AGENTS.md docs/quality-gates.md

After the repo-audit rule changes land, run focused tests for the new findings and then the exact repo-audit slice that should catch the tightened rules:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_repo_audit.py tests/test_pipeline.py -x -q --tb=short
    bash scripts/run_repo_python.sh -m sattlint.devtools.repo_audit --profile full --check public-readiness --skip-pipeline --output-dir artifacts/audit-security-plan

If this slice adds new Python helper modules or repo-audit reporting helpers, run touched-file Ruff and Pyright on the exact files changed:

    bash scripts/run_repo_python.sh -m ruff check <touched-python-files>
    bash scripts/run_repo_python.sh -m pyright <touched-python-files> tests/test_repo_audit.py tests/test_pipeline.py

For final acceptance, run one manual publish rehearsal after the workflow hardening lands. Use the rehearseable path owned by the existing release plans and confirm that the build or smoke job runs, the publish job stays behind the protected environment, and a `workflow_dispatch` run does not publish.

## Validation and Acceptance

Acceptance is behavioral. The checked-in legacy local search-helper scripts must be absent from the repository, and no remaining checked-in helper script should show SurrealDB bound to all interfaces with hardcoded `root/root` credentials. A maintainer should not be able to follow the checked-in repository instructions and accidentally expose a reachable database service with known credentials.

The publish path must show a narrower trust boundary. The final publish job in `.github/workflows/publish.yml` must be the only place that receives `id-token: write`, and that job must declare a protected `environment:`. A manual rehearsal path must still stop before publication, while a real tag push must pass through the same hardened gate before publish.

The dependency-monitoring acceptance bar is that the repository treats the checked-in Node owner surface as real and monitored. `.github/dependabot.yml` must cover `npm` when a tracked `package.json` or `package-lock.json` exists, and CI or repo-owned auditing must surface Node vulnerability results in a deterministic way. The repo should no longer rely on Python-only monitoring for the VS Code client surface.

Repo-audit acceptance is that the reviewed security defects become machine-checkable. If a future change reintroduces workflow-level `id-token: write`, removes the publish environment gate or publish tag guard, adds an unverified binary download pattern, drops npm monitoring while a tracked Node manifest exists, or reintroduces all-interface default-credential helper scripts, focused repo-audit tests and the resulting repo-audit check must fail with a clear finding.

## Idempotence and Recovery

The helper-script removal must be safe to rerun. A maintainer should be able to repeat the cleanup without manual recovery beyond removing any local untracked residue. If a future replacement helper surface is introduced, it should fail closed by default and document its required environment variables or local-only defaults explicitly.

The workflow hardening changes must preserve rehearsal safety. Adding a protected `environment:` and narrower permissions must not make `workflow_dispatch` publish accidentally. If a rehearsal run fails after the changes, the recovery path should be to rerun the same rehearsal after fixing the workflow or release-smoke defect, not to bypass the protected environment or widen permissions temporarily.

Repo-audit rule changes must stay deterministic and repository-state-based. If a new rule proves too noisy, tune the detection logic or narrow the exact pattern it matches rather than adding a blanket ignore. This slice should make the security boundary clearer, not create a fragile policy that maintainers immediately suppress.

## Artifacts and Notes

Security-review baseline captured when this plan was created:

    - `.github/workflows/publish.yml` grants `id-token: write` at workflow scope and publishes on `v*` tags
    - `.github/workflows/publish.yml` does not show an explicit protected `environment:` on the publish job
    - `.github/dependabot.yml` covered `pip` and `github-actions`, but not `npm`
    - the earlier review snapshot still referenced a root `package-lock.json`, but the current checked-in Node owner surface is `vscode/sattline-vscode/package.json`
    - `.github/workflows/typing.yml` runs `pip-audit --skip-editable`
    - three checked-in legacy local search-helper scripts used or documented `--bind 0.0.0.0:3004 --user root --pass root`
    - `src/sattlint/devtools/_repo_audit_reporting.py` currently checks for workflow presence but not workflow hardening

Adjacent active plans that this slice depends on but does not replace:

    - `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md`
    - `docs/exec-plans/completed/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md`

The implementation phase should record one concise before-and-after excerpt for the legacy helper-script removal or credential-surface cleanup and one concise repo-audit finding example for each new security rule family.

## Interfaces and Dependencies

The helper-script surface is the removed legacy local search-helper trio that previously exposed SurrealDB defaults from `scripts/`. At the end of this slice, those scripts should be absent from the repository, and any future checked-in helper script must not embed literal production-like credentials or all-interface bind defaults. If environment variables are used, document their exact names in the script comments and in any touched docs.

The workflow surface is `.github/workflows/publish.yml` plus `.github/dependabot.yml`. `publish.yml` must end with job-scoped publish permissions and an explicit protected `environment:` on the final publish job. Dependabot must include `npm` coverage for `/vscode/sattline-vscode` while the checked-in VS Code client manifest remains present.

The audit surface is `src/sattlint/devtools/_repo_audit_public_readiness.py` and any supporting repo-audit helper modules or tests needed to keep the rules maintainable. Add focused regression coverage in `tests/test_repo_audit.py` and any adjacent workflow or pipeline tests that already cover audit-facing behavior.

The neighboring policy surfaces are `AGENTS.md` and `docs/quality-gates.md`. Only update the parts that must reflect the hardened release and security posture. Keep workflow deduplication details in `docs/exec-plans/completed/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md` and keep artifact smoke-validation semantics in `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md`.
