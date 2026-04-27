---
description: "Use when changing repo audit checks, pipeline artifacts, public-readiness scans, portability checks, or devtools JSON outputs in SattLint. Covers preferred seams and focused validation."
name: "Repo Audit Instructions"
applyTo: ["src/sattlint/devtools/**", "tests/test_repo_audit.py", "tests/test_pipeline.py", "tests/test_artifact_contracts.py", "TODO_TOOLS.md"]
---
# Repo Audit

- Extend existing devtools seams instead of adding parallel registries or artifact formats.
- Keep outputs machine-readable and actionable.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) before full-profile verification.
- Open `artifacts/audit/status.json` first when inspecting audit results.

## Scope Of Permitted Changes

- Add or improve checks for: hardcoded paths and environment leaks, secrets and PII, dead code, feature wiring, architecture issues, configuration hygiene, CLI/TUI UX consistency, logging and observability, test coverage gaps, public-readiness.
- Prefer lightweight standard tools over redundant new dependencies.
- If custom audit logic is needed, place it in `tools/audit/` or integrate into `src/sattlint/devtools/repo_audit.py` or the shared devtools pipeline.
- Add tests for custom audit logic where practical.
