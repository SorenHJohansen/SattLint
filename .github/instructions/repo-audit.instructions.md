---
description: "Use when changing repo audit checks, pipeline artifacts, public-readiness scans, portability checks, or devtools JSON outputs in SattLint. Covers preferred seams and focused validation."
name: "Repo Audit Instructions"
applyTo: ["src/sattlint/devtools/**", "tests/test_repo_audit*.py", "tests/test_pipeline*.py", "tests/test_artifact_contracts.py"]
---
# Repo Audit

- Extend existing devtools seams instead of adding parallel registries or artifact formats.
- Keep outputs machine-readable and actionable.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) before full-profile verification.
- Open `artifacts/audit/status.json` first when inspecting audit results.
- For `--check-my-changes` triage, separate current-slice findings from inherited repo findings before choosing the owner seam or widening scope.
- Prefer scoping and path-attribution fixes before suppressing findings or broadening checks.
- Treat finish-gate JSON and other `artifacts/audit/` outputs as point-in-time snapshots. After narrow validation changes, regenerate stale artifacts before treating them as blockers.
- If a structural-report failure comes from counting or inventory behavior, prefer the inventory or helper seam before editing debt-controlled report owners.
- Any new full-profile repo-audit or shared-pipeline check must have a registry-backed individual command and appear in the `--list-checks` catalog exposed by `sattlint-repo-audit` or `sattlint-analysis-pipeline`.

## Scope Of Permitted Changes

- Add or improve checks for: hardcoded paths and environment leaks, secrets and PII, dead code, feature wiring, architecture issues, configuration hygiene, CLI/TUI UX consistency, logging and observability, test coverage gaps, public-readiness.
- Prefer lightweight standard tools over redundant new dependencies.
- If custom audit logic is needed, place it in `tools/audit/` or integrate into `src/sattlint/devtools/repo_audit.py` or the shared devtools pipeline.
- Add tests for custom audit logic where practical.
